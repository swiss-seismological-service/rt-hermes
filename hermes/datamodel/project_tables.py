from datetime import datetime, timezone

from geoalchemy2 import Geometry
from sqlalchemy import (JSON, Boolean, Column, Float, ForeignKey, Index,
                        Integer, String)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from hermes.datamodel.base import (CreationInfoMixin, DefaultEpochMixin,
                                   FiniteEpochMixin, ForecastEpochMixin,
                                   NameMixin, ObservationEpochMixin, ORMBase,
                                   ScheduleEpochMixin)
from hermes.datamodel.data_tables import (tag_forecast_series_association,
                                          tag_model_config_association)


class ProjectTable(CreationInfoMixin,
                   NameMixin,
                   DefaultEpochMixin,
                   ORMBase):

    description = Column(String)

    forecastseries = relationship(
        'ForecastSeriesTable',
        back_populates='project',
        cascade='all, delete-orphan',
        passive_deletes=True)


class ForecastTable(CreationInfoMixin,
                    FiniteEpochMixin,
                    ORMBase):

    status = Column(String(25), default='PENDING')

    forecastseries_oid = Column(UUID,
                                ForeignKey('forecastseries.oid',
                                           ondelete="CASCADE"),
                                index=True)
    forecastseries = relationship('ForecastSeriesTable',
                                  back_populates='forecasts')

    modelruns = relationship('ModelRunTable',
                             back_populates='forecast',
                             cascade='all, delete-orphan',
                             passive_deletes=True)

    injectionobservation = relationship('InjectionObservationTable',
                                        back_populates='forecast',
                                        cascade='all, delete-orphan',
                                        passive_deletes=True,
                                        uselist=False)

    seismicityobservation = relationship('SeismicityObservationTable',
                                         back_populates='forecast',
                                         cascade='all, delete-orphan',
                                         passive_deletes=True,
                                         uselist=False)
    __table_args__ = (
        Index('idx_forecast_starttime', 'starttime',
              postgresql_using='brin'),
        Index('idx_forecast_endtime', 'endtime',
              postgresql_using='brin'))


class ForecastSeriesTable(CreationInfoMixin,
                          ObservationEpochMixin,
                          ScheduleEpochMixin,
                          ForecastEpochMixin,
                          NameMixin,
                          ORMBase):

    status = Column(String(25))
    description = Column(String)

    observation_window = Column(Integer)
    forecast_duration = Column(Integer)
    schedule_interval = Column(Integer)
    schedule_id = Column(UUID)
    schedule_active = Column(Boolean)

    # Spatial dimensions of the area considered.
    bounding_polygon = Column(Geometry('POLYGON', srid=4326))
    depth_min = Column(Float)
    depth_max = Column(Float)

    model_settings = Column(JSON, default={})

    project_oid = Column(UUID,
                         ForeignKey('project.oid', ondelete="CASCADE"),
                         index=True)
    project = relationship('ProjectTable',
                           back_populates='forecastseries')

    forecasts = relationship('ForecastTable',
                             back_populates='forecastseries',
                             cascade='all, delete-orphan',
                             passive_deletes=True)
    _tags = relationship('TagTable',
                         back_populates='forecastseries',
                         secondary=tag_forecast_series_association,
                         lazy='joined')

    fdsnws_url = Column(String)
    hydws_url = Column(String)

    seismicityobservation_required = Column(String(15), default='REQUIRED')
    injectionobservation_required = Column(String(15), default='REQUIRED')
    injectionplan_required = Column(String(15), default='REQUIRED')

    @hybrid_property
    def tags(self):
        t = [tag.name for tag in self._tags]
        return t

    injectionplans = relationship('InjectionPlanTable',
                                  back_populates='forecastseries',
                                  cascade='all, delete-orphan',
                                  passive_deletes=True)


class ModelConfigTable(ORMBase, NameMixin):

    description = Column(String)
    enabled = Column(Boolean, default=True)
    result_type = Column(String(15), nullable=False)

    # The model should be called by sfm_module.sfm_function(*args)
    sfm_module = Column(String)
    sfm_function = Column(String)

    last_modified = Column(
        TIMESTAMP(precision=0),
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    model_parameters = Column(JSON, nullable=False)

    modelruns = relationship('ModelRunTable',
                             back_populates='modelconfig')

    _tags = relationship('TagTable',
                         back_populates='modelconfigs',
                         lazy='joined',
                         secondary=tag_model_config_association)

    @hybrid_property
    def tags(self):
        t = [tag.name for tag in self._tags]
        return t


class TagTable(ORMBase, NameMixin):

    modelconfigs = relationship(
        'ModelConfigTable',
        back_populates='_tags',
        secondary=tag_model_config_association)

    forecastseries = relationship(
        'ForecastSeriesTable',
        back_populates='_tags',
        secondary=tag_forecast_series_association)
