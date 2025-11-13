import json
from uuid import UUID

from hydws.parser import BoreholeHydraulics
from seismostats import Catalog
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from hermes.datamodel.data_tables import (EventObservationTable,
                                          InjectionObservationTable,
                                          InjectionPlanTable,
                                          SeismicityObservationTable)
from hermes.datamodel.project_tables import ForecastTable
from hermes.datamodel.result_tables import ModelRunTable
from hermes.io.serialize import serialize_seismostats_catalog
from hermes.repositories.base import repository_factory
from hermes.schemas.data_schemas import (EventObservation,
                                         InjectionObservation, InjectionPlan,
                                         SeismicityObservation)


class EventObservationRepository(repository_factory(
        EventObservation, EventObservationTable)):
    @classmethod
    def create_from_catalog(cls,
                            session: Session,
                            data: Catalog,
                            seismicityobservation_oid: UUID) -> UUID:

        events = serialize_seismostats_catalog(data, EventObservation)

        session.execute(
            insert(EventObservationTable)
            .values(seismicityobservation_oid=seismicityobservation_oid),
            events)
        session.commit()

    @classmethod
    def create_from_quakeml(cls,
                            session: Session,
                            data: str,
                            seismicityobservation_oid: UUID) -> UUID:

        catalog = Catalog.from_quakeml(data,
                                       include_uncertainties=True,
                                       include_quality=True)

        cls.create_from_catalog(session, catalog, seismicityobservation_oid)


class SeismicityObservationRepository(repository_factory(
        SeismicityObservation, SeismicityObservationTable)):

    @classmethod
    def create_from_catalog(cls,
                            session: Session,
                            data: Catalog,
                            forecast_oid: UUID) -> SeismicityObservation:
        qml = data.to_quakeml()
        object_db = SeismicityObservation(
            data=qml,
            forecast_oid=forecast_oid
        )
        object_db = cls.create(session, object_db)

        EventObservationRepository.create_from_catalog(
            session, data, object_db.oid)

        return object_db

    @classmethod
    def create_from_quakeml(cls,
                            session: Session,
                            data: str,
                            forecast_oid: UUID) -> SeismicityObservation:

        object_db = SeismicityObservation(
            data=data,
            forecast_oid=forecast_oid
        )
        object_db = cls.create(session, object_db)

        EventObservationRepository.create_from_quakeml(
            session, data, object_db.oid)

        return object_db


class InjectionObservationRepository(repository_factory(
        InjectionObservation, InjectionObservationTable)):
    @classmethod
    def create_from_hydjson(
            cls,
            session: Session,
            data: str,
            forecast_oid: UUID) -> InjectionObservation:
        object_db = InjectionObservation(
            data=data,
            forecast_oid=forecast_oid
        )

        object_db = cls.create(session, object_db)

        return object_db

    @classmethod
    def create_from_borehole_hydraulics(
            cls,
            session: Session,
            data: BoreholeHydraulics,
            forecast_oid: UUID) -> InjectionObservation:
        hydjson = json.dumps(data.to_json())

        return cls.create_from_hydjson(session, hydjson, forecast_oid)


class InjectionPlanRepository(repository_factory(
        InjectionPlan, InjectionPlanTable)):
    @classmethod
    def create_from_hydjson(
            cls,
            session: Session,
            data: str,
            name: str,
            forecastseries_oid: UUID | None = None) -> InjectionPlan:

        object_db = InjectionPlan(
            data=data,
            forecastseries_oid=forecastseries_oid,
            name=name
        )

        return cls.create(session, object_db)

    @classmethod
    def create_from_borehole_hydraulics(
            cls,
            session: Session,
            data: BoreholeHydraulics,
            name: str,
            forecastseries_oid: UUID) -> InjectionPlan:
        hydjson = json.dumps(data.to_json())

        return cls.create_from_hydjson(
            session, hydjson, name, forecastseries_oid)

    @classmethod
    def get_by_forecastseries(
            cls,
            session: Session,
            forecastseries_oid: UUID) -> list[InjectionPlan]:

        q = select(InjectionPlanTable).where(
            InjectionPlanTable.forecastseries_oid == forecastseries_oid)
        result = session.execute(q).scalars().all()
        return [cls.model.model_validate(f) for f in result]

    @classmethod
    def get_ids_by_forecast(
            cls,
            session: Session,
            forecast_oid: UUID) -> list[UUID]:

        q = select(InjectionPlanTable.oid) \
            .join(ModelRunTable,
                  ModelRunTable.injectionplan_oid == InjectionPlanTable.oid) \
            .join(ForecastTable,
                  ForecastTable.oid == ModelRunTable.forecast_oid) \
            .where(ForecastTable.oid == forecast_oid)

        result = session.execute(q).scalars().all()
        return [f for f in result]
