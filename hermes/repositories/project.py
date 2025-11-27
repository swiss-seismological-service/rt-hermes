from geoalchemy2.shape import from_shape
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from hermes.datamodel.project_tables import (ForecastSeriesTable,
                                             ForecastTable, ModelConfigTable,
                                             ProjectTable, TagTable)
from hermes.repositories.base import repository_factory
from hermes.schemas import (EStatus, Forecast, ForecastSeries, ModelConfig,
                            Project, Tag)


class ProjectRepository(repository_factory(Project, ProjectTable)):

    @classmethod
    def get_by_name(cls, session: Session, name: str) -> Project:
        q = select(ProjectTable).where(ProjectTable.name == name)
        result = session.execute(q).unique().scalar_one_or_none()
        return cls.model.model_validate(result) if result else None


class TagRepository(repository_factory(
        Tag, TagTable)):

    @classmethod
    def _get_by_name(cls, session: Session, name: str) -> TagTable:
        q = select(TagTable).where(TagTable.name == name)
        result = session.execute(q).unique().scalar_one_or_none()
        return result

    @classmethod
    def get_by_name(cls, session: Session, name: str) -> Tag:
        result = cls._get_by_name(session, name)
        return cls.model.model_validate(result) if result else None

    @classmethod
    def _get_or_create(cls, session: Session, name: str) -> TagTable:
        result = cls._get_by_name(session, name)
        if not result:
            try:
                result = TagTable(name=name)
                session.add(result)
                session.commit()
                session.refresh(result)
            except IntegrityError as e:
                session.rollback()
                result = cls._get_by_name(session, name)
                if not result:
                    raise e
        return result

    @classmethod
    def get_or_create(cls, session: Session, name: str) -> Tag:
        result = cls._get_or_create(session, name)
        return cls.model.model_validate(result) if result else None


class ForecastSeriesRepository(repository_factory(
        ForecastSeries, ForecastSeriesTable)):

    @classmethod
    def update_schedule_id(cls, session: Session, oid, schedule_id) -> None:
        """Update only the schedule_id field for a ForecastSeries."""
        q = select(ForecastSeriesTable).where(ForecastSeriesTable.oid == oid)
        result = session.execute(q).unique().scalar_one_or_none()
        if result and result.schedule_id != schedule_id:
            result.schedule_id = schedule_id
            session.commit()

    @classmethod
    def get_by_name(cls, session: Session, name: str) -> ForecastSeries:
        q = select(ForecastSeriesTable).where(ForecastSeriesTable.name == name)
        result = session.execute(q).unique().scalar_one_or_none()
        return cls.model.model_validate(result) if result else None

    @classmethod
    def get_by_project(cls, session: Session, project_oid: str) \
            -> list[ForecastSeries]:
        q = select(ForecastSeriesTable).where(
            ForecastSeriesTable.project_oid == project_oid)
        result = session.execute(q).unique().scalars().all()
        return [cls.model.model_validate(f) for f in result]

    @classmethod
    def create(cls, session: Session, data: ForecastSeries) -> ForecastSeries:

        # Check if tags exist in the database, if not create them.
        tags = []
        for tag in data.tags:
            tags.append(TagRepository._get_or_create(session, tag))

        # Convert the bounding polygon to a geoalchemy2 shape.
        bounding_polygon = None
        if data.bounding_polygon:
            bounding_polygon = from_shape(data.bounding_polygon)

        # Create the database model and commit it to the database.
        db_model = ForecastSeriesTable(
            _tags=tags,
            bounding_polygon=bounding_polygon,
            **data.model_dump(exclude_unset=True,
                              exclude=['tags', 'bounding_polygon']))

        session.add(db_model)
        session.commit()
        session.refresh(db_model)

        return cls.model.model_validate(db_model)

    @classmethod
    def update(cls, session: Session, data: ForecastSeries) -> ForecastSeries:
        q = select(ForecastSeriesTable).where(
            ForecastSeriesTable.oid == data.oid)

        result = session.execute(q).unique().scalar_one_or_none()

        if result:
            if data.tags:
                result._tags = [TagRepository._get_or_create(session, tag)
                                for tag in data.tags]
            if data.bounding_polygon:
                result.bounding_polygon = from_shape(data.bounding_polygon)

            for key, value in data.model_dump(
                    exclude_unset=True,
                    exclude=['tags', 'bounding_polygon']).items():
                setattr(result, key, value)

            session.commit()
            session.refresh(result)
            return cls.model.model_validate(result)
        return

    @classmethod
    def get_tags(cls, session: Session, forecastseries_oid: str) -> list[Tag]:
        q = select(TagTable).join(ForecastSeriesTable._tags).where(
            ForecastSeriesTable.oid == forecastseries_oid)
        result = session.execute(q).scalars().all()
        return [TagRepository.model.model_validate(tag) for tag in result]

    @classmethod
    def get_model_configs(cls,
                          session: Session,
                          forecastseries_oid: str) -> list[ModelConfig]:

        # Subquery to get tags of the given forecast series
        subquery = select(TagTable.oid).join(ForecastSeriesTable._tags).where(
            ForecastSeriesTable.oid == forecastseries_oid)

        # Query to get model configs with the same tags
        q = select(ModelConfigTable).join(
            ModelConfigTable._tags).where(TagTable.oid.in_(subquery))
        result = session.execute(q).unique().scalars().all()

        return [ModelConfig.model_validate(m) for m in result]


class ForecastRepository(repository_factory(Forecast, ForecastTable)):

    @classmethod
    def update_status(cls,
                      session: Session,
                      forecast_oid: str,
                      status: EStatus) -> Forecast:
        q = select(ForecastTable).where(ForecastTable.oid == forecast_oid)
        result = session.execute(q).unique().scalar_one_or_none()
        if result:
            result.status = status
            session.commit()
            session.refresh(result)
            return cls.model.model_validate(result)
        return None

    @classmethod
    def get_by_forecastseries(cls, session: Session,
                              forecastseries_oid: str) -> list[Forecast]:
        q = select(ForecastTable).where(
            ForecastTable.forecastseries_oid == forecastseries_oid)
        result = session.execute(q).scalars().all()
        return [cls.model.model_validate(f) for f in result]


class ModelConfigRepository(repository_factory(
        ModelConfig, ModelConfigTable)):

    @classmethod
    def create(cls, session: Session, data: ModelConfig) -> ModelConfig:

        # Check if tags exist in the database, if not create them.
        tags = []
        for tag in data.tags:
            tags.append(TagRepository._get_or_create(session, tag))

        # Create the database model and commit it to the database.
        db_model = ModelConfigTable(
            _tags=tags, **data.model_dump(exclude_unset=True,
                                          exclude=['tags']))
        session.add(db_model)
        session.commit()
        session.refresh(db_model)
        return cls.model.model_validate(db_model)

    @classmethod
    def get_by_name(cls, session: Session, name: str) -> ModelConfig:
        q = select(ModelConfigTable).where(ModelConfigTable.name == name)
        result = session.execute(q).unique().scalar_one_or_none()
        return cls.model.model_validate(result) if result else None

    @classmethod
    def update(cls, session: Session, data: ModelConfig) -> ModelConfig:
        q = select(ModelConfigTable).where(
            ModelConfigTable.oid == data.oid)
        result = session.execute(q).unique().scalar_one_or_none()
        if result:
            if data.tags:
                result._tags = [TagRepository._get_or_create(session, tag)
                                for tag in data.tags]
            for key, value in data.model_dump(
                    exclude_unset=True,
                    exclude=['tags']).items():
                setattr(result, key, value)
            session.commit()
            session.refresh(result)
        return cls.model.model_validate(result)
