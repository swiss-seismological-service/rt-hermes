from geoalchemy2 import Geometry
from geoalchemy2.shape import from_shape, to_shape
from sqlalchemy import (Column, Float, ForeignKey, Index, Integer, String,
                        UniqueConstraint, delete, event, select)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import relationship

from hermes.datamodel.base import (CreationInfoMixin, ORMBase,
                                   RealQuantityMixin, TimeQuantityMixin)
from hermes.datamodel.data_tables import InjectionPlanTable


class TimeStepTable(ORMBase):
    starttime = Column(TIMESTAMP(precision=0), nullable=False)
    endtime = Column(TIMESTAMP(precision=0), nullable=False)

    forecastseries_oid = Column(UUID, ForeignKey(
        'forecastseries.oid', ondelete='CASCADE'), index=True)

    modelresults = relationship(
        'ModelResultTable',
        back_populates='timestep')

    __table_args__ = (
        UniqueConstraint('starttime', 'endtime', 'forecastseries_oid'),
        Index('idx_timestep_oid', 'oid'))


class GridCellTable(ORMBase):
    geom = Column(Geometry('POLYGON'), nullable=False)
    unique_geom = Column(Geometry('POLYGON'), nullable=False)
    depth_min = Column(Float)
    depth_max = Column(Float)
    forecastseries_oid = Column(UUID,
                                ForeignKey('forecastseries.oid',
                                           ondelete='CASCADE'),
                                index=True)

    modelresults = relationship(
        'ModelResultTable',
        back_populates='gridcell')

    __table_args__ = (
        UniqueConstraint('unique_geom', 'forecastseries_oid',
                         'depth_min', 'depth_max'),
        Index('ix_grid_cells_unique_geom', 'unique_geom',
              postgresql_using='gist'),
        Index('idx_gridcell_oid', 'oid'))


# TODO: This part should eventually become a database trigger!
def set_unique_geom(mapper, connection, target):
    if target.geom is not None:
        polygon = to_shape(target.geom)
        target.unique_geom = from_shape(polygon.envelope, srid=4326)


# Attach event listeners to ensure unique_geom is populated
event.listen(GridCellTable, 'before_insert', set_unique_geom)
event.listen(GridCellTable, 'before_update', set_unique_geom)


class ModelResultTable(CreationInfoMixin, ORMBase):

    modelrun_oid = Column(UUID,
                          ForeignKey('modelrun.oid', ondelete='CASCADE'),
                          index=True)

    realization_id = Column(Integer)

    modelrun = relationship('ModelRunTable',
                            back_populates='modelresults')

    result_type = Column(String(25), nullable=False)

    timestep_oid = Column(UUID,
                          ForeignKey('timestep.oid', ondelete='SET NULL'))
    timestep = relationship('TimeStepTable',
                            back_populates='modelresults')

    gridcell_oid = Column(UUID,
                          ForeignKey('gridcell.oid', ondelete='SET NULL'))
    gridcell = relationship('GridCellTable',
                            back_populates='modelresults')

    eventforecasts = relationship('EventForecastTable',
                                  back_populates='modelresult',
                                  cascade='all, delete-orphan',
                                  passive_deletes=True)

    grparameters = relationship('GRParametersTable',
                                back_populates='modelresult',
                                cascade='all, delete-orphan',
                                passive_deletes=True)

    __table_args__ = (
        Index('idx_modelresult_oid', 'oid'),
        Index('idx_modelresult_timestep_oid', 'timestep_oid'),
        Index('idx_modelresult_gridcell_oid', 'gridcell_oid'),
        Index('idx_modelresult_modelrun_timestep', 'modelrun_oid',
              'timestep_oid'),
        Index('idx_modelresult_modelrun_gridcell', 'modelrun_oid',
              'gridcell_oid'),
    )


class EventForecastTable(TimeQuantityMixin('time'),
                         RealQuantityMixin('latitude'),
                         RealQuantityMixin('longitude'),
                         RealQuantityMixin('depth'),
                         RealQuantityMixin('magnitude'),
                         ORMBase):
    magnitude_type = Column(String)
    coordinates = Column(Geometry('POINT', srid=4326))

    modelresult_oid = Column(UUID,
                             ForeignKey('modelresult.oid',
                                        ondelete='CASCADE'),
                             index=True)

    modelresult = relationship(
        'ModelResultTable',
        back_populates='eventforecasts')


class ModelRunTable(ORMBase):

    status = Column(String(25), default='PENDING')

    modelconfig_oid = Column(UUID,
                             ForeignKey('modelconfig.oid',
                                        ondelete="RESTRICT"),
                             index=True)
    modelconfig = relationship('ModelConfigTable',
                               back_populates='modelruns')

    forecast_oid = Column(UUID,
                          ForeignKey('forecast.oid',
                                     ondelete="CASCADE"),
                          index=True)
    forecast = relationship('ForecastTable',
                            back_populates='modelruns')

    injectionplan_oid = Column(UUID,
                               ForeignKey('injectionplan.oid',
                                          ondelete='SET NULL'))
    injectionplan = relationship('InjectionPlanTable',
                                 back_populates='modelruns')

    modelresults = relationship('ModelResultTable',
                                back_populates='modelrun',
                                cascade='all, delete-orphan',
                                passive_deletes=True)

    grparameters = relationship('GRParametersTable',
                                back_populates='modelrun',
                                cascade='all, delete-orphan',
                                passive_deletes=True)

# TODO: This part should eventually become a database trigger!
# Event listener for after delete


@event.listens_for(ModelRunTable, "after_delete")
def delete_orphaned_injectionplans(mapper, connection, target):
    # Check if the modelrun had an injectionplan
    if target.injectionplan_oid is None:
        return
    # Check if there are any remaining references
    stmt = select(ModelRunTable) \
        .filter_by(injectionplan_oid=target.injectionplan_oid)
    result = connection.execute(stmt).first()
    if result is None:
        # No remaining references, delete the injectionplan
        del_stmt = delete(InjectionPlanTable) \
            .where(InjectionPlanTable.oid == target.injectionplan_oid)
        connection.execute(del_stmt)


class GRParametersTable(RealQuantityMixin('number_events'),
                        RealQuantityMixin('a'),
                        RealQuantityMixin('b'),
                        RealQuantityMixin('mc'),
                        RealQuantityMixin('alpha'),
                        ORMBase):
    modelresult_oid = Column(UUID, ForeignKey(
        'modelresult.oid', ondelete='CASCADE'), index=True)
    modelresult = relationship(
        'ModelResultTable',
        back_populates='grparameters')

    modelrun_oid = Column(UUID, ForeignKey(
        'modelrun.oid', ondelete='CASCADE'), index=True)
    modelrun = relationship(
        'ModelRunTable',
        back_populates='grparameters')
