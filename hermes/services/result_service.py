from uuid import UUID

from seismostats import ForecastCatalog, ForecastGRRateGrid
from shapely.geometry import box

from hermes.repositories.results import (EventForecastRepository,
                                         GridCellRepository,
                                         GRParametersRepository,
                                         ModelResultRepository,
                                         TimeStepRepository)
from hermes.schemas import GridCell, TimeStep
from hermes.schemas.base import EResultType


def save_forecast_catalog(
        session,
        forecastseries_oid: UUID,
        modelrun_oid: UUID,
        forecast_catalog: ForecastCatalog) -> None:

    # create the timestep and gridcell objects
    timestep = TimeStep(starttime=forecast_catalog.starttime,
                        endtime=forecast_catalog.endtime,
                        forecastseries_oid=forecastseries_oid)
    griddcell = GridCell(geom=forecast_catalog.bounding_polygon,
                         forecastseries_oid=forecastseries_oid,
                         depth_min=forecast_catalog.depth_min,
                         depth_max=forecast_catalog.depth_max)

    # save the timestep and gridcell objects to the database
    timestep = TimeStepRepository.get_or_create(session, timestep)
    griddcell = GridCellRepository.get_or_create(session, griddcell)

    # create n_catalogs number of ModelResults
    ids = ModelResultRepository.batch_create(
        session,
        forecast_catalog.n_catalogs,
        EResultType.CATALOG,
        timestep.oid,
        griddcell.oid,
        modelrun_oid
    )

    EventForecastRepository.create_from_forecast_catalog(
        session, forecast_catalog, ids)


def save_forecast_grrategrid(
        session,
        forecastseries_oid: UUID,
        modelrun_oid: UUID,
        forecast_grrategrid: ForecastGRRateGrid) -> None:

    timestep = TimeStep(starttime=forecast_grrategrid.starttime,
                        endtime=forecast_grrategrid.endtime,
                        forecastseries_oid=forecastseries_oid)
    timestep = TimeStepRepository.get_or_create(session, timestep)

    forecast_grrategrid['modelrun_oid'] = modelrun_oid

    cells = forecast_grrategrid.groupby(['longitude_min', 'longitude_max',
                                         'latitude_min', 'latitude_max',
                                         'depth_min', 'depth_max'])

    for cell, data in cells:
        gridcell = GridCell(geom=box(cell[0], cell[2], cell[1], cell[3]),
                            forecastseries_oid=forecastseries_oid,
                            depth_min=cell[4],
                            depth_max=cell[5])

        gridcell = GridCellRepository.get_or_create(session, gridcell)

        ids = ModelResultRepository.batch_create(
            session,
            len(data),
            EResultType.GRID,
            timestep.oid,
            gridcell.oid,
            modelrun_oid
        )

        GRParametersRepository.create_from_forecast_grrategrid(
            session, data, ids)
