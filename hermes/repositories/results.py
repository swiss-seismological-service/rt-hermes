from uuid import UUID

import numpy as np
from geoalchemy2.functions import (ST_Envelope, ST_Equals, ST_GeomFromText,
                                   ST_SetSRID)
from geoalchemy2.shape import from_shape
from seismostats import ForecastCatalog, ForecastGRRateGrid
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from hermes.datamodel.result_tables import (EventForecastTable, GridCellTable,
                                            GRParametersTable,
                                            ModelResultTable, ModelRunTable,
                                            TimeStepTable)
from hermes.io.serialize import (serialize_seismostats_catalog,
                                 serialize_seismostats_grrategrid)
from hermes.repositories.base import repository_factory
from hermes.schemas.result_schemas import (EventForecast, GridCell,
                                           GRParameters, ModelResult, ModelRun,
                                           TimeStep)


class ModelResultRepository(
    repository_factory(ModelResult,
                       ModelResultTable)):
    @classmethod
    def batch_create(cls,
                     session: Session,
                     number: int,
                     result_type: str,
                     timestep_oid: UUID | None = None,
                     gridcell_oid: UUID | None = None,
                     modelrun_oid: UUID | None = None) -> list[UUID]:
        data = [{'timestep_oid': timestep_oid,
                 'gridcell_oid': gridcell_oid,
                 'modelrun_oid': modelrun_oid,
                 'result_type': result_type,
                 'realization_id': i} for i in range(number)]

        q = insert(ModelResultTable).returning(
            ModelResultTable.oid,
            ModelResultTable.realization_id)

        result = session.execute(q, data).fetchall()
        session.commit()

        # make sure that the list id is the same as the realization_id
        # since the database does not guarantee the order of the results
        batch = sorted(result, key=lambda x: x[1])
        return [x[0] for x in batch]

    @classmethod
    def count_by_modelrun(cls, session: Session, modelrun_oid: UUID) -> int:
        """Count ModelResult records for a specific modelrun."""
        q = select(ModelResultTable).where(
            ModelResultTable.modelrun_oid == modelrun_oid)
        result = session.execute(q).unique().scalars().all()
        return len(result)

    @classmethod
    def get_by_modelrun(cls, session: Session,
                        modelrun_oid: UUID) -> list[ModelResult]:
        """Get all ModelResult records for a specific modelrun."""
        q = select(ModelResultTable).where(
            ModelResultTable.modelrun_oid == modelrun_oid)
        result = session.execute(q).unique().scalars().all()
        return [cls.model.model_validate(row) for row in result]


class GridCellRepository(
    repository_factory(GridCell,
                       GridCellTable)):
    @classmethod
    def create(cls,
               session: Session,
               data: GridCell) -> GridCell:

        geom = None
        if data.geom:
            geom = from_shape(data.geom)

        db_model = GridCellTable(
            geom=geom,
            **data.model_dump(exclude_unset=True,
                              exclude=['geom']))

        session.add(db_model)
        session.commit()
        session.refresh(db_model)

        return cls.model.model_validate(db_model)

    @classmethod
    def get_or_create(cls,
                      session: Session,
                      gridcell: GridCell) -> GridCell:
        q = select(GridCellTable).where(
            GridCellTable.forecastseries_oid == gridcell.forecastseries_oid,
            # TODO: Improve SRID handling
            ST_Equals(
                ST_Envelope(GridCellTable.unique_geom),
                ST_Envelope(
                    ST_SetSRID(
                        ST_GeomFromText(gridcell.geom.wkt),
                        4326
                    )
                )
            )
        )
        result = session.execute(q).unique().scalar_one_or_none()

        if not result:
            try:
                result = cls.create(session, gridcell)
            except IntegrityError as e:
                session.rollback()
                result = session.execute(q).unique().scalar_one_or_none()
                if not result:
                    raise e
        return result

    @classmethod
    def find_by_forecastseries(cls, session: Session,
                               forecastseries_oid: UUID) -> list[GridCell]:
        """Find all GridCells for a forecastseries."""
        q = select(GridCellTable).where(
            GridCellTable.forecastseries_oid == forecastseries_oid)
        result = session.execute(q).unique().scalars().all()
        return [cls.model.model_validate(row) for row in result]

    @classmethod
    def find_by_spatial_bounds(cls, session: Session,
                               forecastseries_oid: UUID,
                               depth_min: float, depth_max: float) -> GridCell:
        """Find GridCell by spatial bounds."""
        q = select(GridCellTable).where(
            GridCellTable.forecastseries_oid == forecastseries_oid,
            GridCellTable.depth_min == depth_min,
            GridCellTable.depth_max == depth_max)
        result = session.execute(q).unique().scalar_one_or_none()
        return cls.model.model_validate(result) if result else None


class TimeStepRepository(
    repository_factory(TimeStep,
                       TimeStepTable)):
    @classmethod
    def get_or_create(cls,
                      session: Session,
                      timestep: TimeStep) -> TimeStep:
        q = select(TimeStepTable).where(
            TimeStepTable.starttime == timestep.starttime,
            TimeStepTable.endtime == timestep.endtime,
            TimeStepTable.forecastseries_oid == timestep.forecastseries_oid)
        result = session.execute(q).unique().scalar_one_or_none()
        if not result:
            try:
                result = cls.create(session, timestep)
            except IntegrityError as e:
                session.rollback()
                result = session.execute(q).unique().scalar_one_or_none()
                if not result:
                    raise e
        return result

    @classmethod
    def find_by_bounds(cls, session: Session, forecastseries_oid: UUID,
                       starttime, endtime) -> TimeStep:
        """Find TimeStep by temporal bounds."""
        q = select(TimeStepTable).where(
            TimeStepTable.forecastseries_oid == forecastseries_oid,
            TimeStepTable.starttime == starttime,
            TimeStepTable.endtime == endtime)
        result = session.execute(q).unique().scalar_one_or_none()
        return cls.model.model_validate(result) if result else None


class GRParametersRepository(
    repository_factory(GRParameters,
                       GRParametersTable)):
    @classmethod
    def create_from_forecast_grrategrid(
            cls,
            session: Session,
            rategrid: ForecastGRRateGrid,
            modelresult_oids: list[UUID]) -> None:

        # make sure that the grid_id is 0 indexed
        if max(rategrid.grid_id) >= len(modelresult_oids):
            raise ValueError('The number of modelresult_oids is less than the '
                             'maximum grid_id in the rategrid.')

        # Modelresult_oid is guaranteed to be in the same order as the
        # 0 indexed grid_id. Replace the grid_id with the modelresult_oid.
        rategrid.grid_id = np.array(modelresult_oids)[rategrid.grid_id]
        rategrid = rategrid.rename(columns={'grid_id': 'modelresult_oid'})
        grparameters = serialize_seismostats_grrategrid(rategrid)

        session.execute(insert(GRParametersTable), grparameters)
        session.commit()

    @classmethod
    def count_by_modelrun(cls, session: Session, modelrun_oid: UUID) -> int:
        """Count GRParameters records for a specific modelrun."""
        from sqlalchemy import func
        q = (select(func.count(GRParametersTable.oid))
             .join(ModelResultTable,
                   GRParametersTable.modelresult_oid == ModelResultTable.oid)
             .where(ModelResultTable.modelrun_oid == modelrun_oid))
        result = session.execute(q).scalar()
        return result or 0


class EventForecastRepository(
    repository_factory(EventForecast,
                       EventForecastTable)):

    @classmethod
    def create_from_forecast_catalog(cls,
                                     session: Session,
                                     catalog: ForecastCatalog,
                                     modelresult_oids: list[UUID]) -> None:
        if catalog.empty:
            return
        # make sure that the catalog_id is 0 indexed
        if max(catalog.catalog_id) >= len(modelresult_oids):
            raise ValueError('The number of modelresult_oids is less than the '
                             'maximum catalog_id in the catalog.')

        # Modelresult_oid is guaranteed to be in the same order as the 0
        # indexed grid_id. Replace the catalog_id column with the
        # modelresult_oids.
        catalog.catalog_id = np.array(modelresult_oids)[catalog.catalog_id]
        catalog = catalog.rename(columns={'catalog_id': 'modelresult_oid'})
        events = serialize_seismostats_catalog(catalog)

        session.execute(insert(EventForecastTable), events)
        session.commit()

    @classmethod
    def count_by_modelrun(cls, session: Session, modelrun_oid: UUID) -> int:
        """Count EventForecast records for a specific modelrun."""
        from sqlalchemy import func
        q = (select(func.count(EventForecastTable.oid))
             .join(ModelResultTable,
                   EventForecastTable.modelresult_oid == ModelResultTable.oid)
             .where(ModelResultTable.modelrun_oid == modelrun_oid))
        result = session.execute(q).scalar()
        return result or 0


class ModelRunRepository(repository_factory(
        ModelRun, ModelRunTable)):
    @classmethod
    def update_status(cls,
                      session: Session,
                      modelrun_oid: UUID,
                      status: str) -> ModelRun:
        q = select(ModelRunTable).where(ModelRunTable.oid == modelrun_oid)
        result = session.execute(q).unique().scalar_one_or_none()

        if result:
            result.status = status
            session.commit()
            session.refresh(result)
            return cls.model.model_validate(result)
        return None

    @classmethod
    def get_by_modelconfig(cls,
                           session: Session,
                           modelconfig_oid: UUID) -> ModelRun:
        q = select(ModelRunTable).where(
            ModelRunTable.modelconfig_oid == modelconfig_oid)
        result = session.execute(q).unique().scalars().all()
        return [cls.model.model_validate(r) for r in result]

    @classmethod
    def get_by_injectionplan(cls,
                             session: Session,
                             injectionplan_oid: UUID) -> ModelRun:
        q = select(ModelRunTable).where(
            ModelRunTable.injectionplan_oid == injectionplan_oid)
        result = session.execute(q).unique().scalars().all()
        return [cls.model.model_validate(r) for r in result]
