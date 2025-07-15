import os
import pickle
from unittest.mock import MagicMock, patch

import pandas as pd
from seismostats import ForecastCatalog
from shapely import from_wkt

from hermes.services.result_service import (
    save_forecast_catalog,
    save_forecast_grrategrid)

MODULE_LOCATION = os.path.dirname(os.path.abspath(__file__))


@patch('hermes.services.result_service.TimeStepRepository.get_or_create',
       autospec=True)
@patch('hermes.services.result_service.GridCellRepository.get_or_create',
       autospec=True)
@patch('hermes.services.result_service.ModelResultRepository.batch_create',
       autospec=True)
@patch('hermes.services.result_service.EventForecastRepository.'
       'create_from_forecast_catalog',
       autospec=True)
def test_save_forecast_catalog(mock_seismic_event_repo,
                                               mock_model_result_repo,
                                               mock_grid_cell_repo,
                                               mock_time):
    catalog_path = os.path.join(
        MODULE_LOCATION, '../../repositories/tests/data/catalog.parquet.gzip')

    catalog = ForecastCatalog(pd.read_parquet(catalog_path))
    catalog.starttime = pd.Timestamp('2022-01-01')
    catalog.endtime = pd.Timestamp('2022-01-31')
    catalog.bounding_polygon = from_wkt(
        'POLYGON ((45.7 5.85, 47.9 5.85, 47.9 10.6, 45.7 10.6, 45.7 5.85))')
    catalog.depth_min = 0
    catalog.depth_max = 100

    save_forecast_catalog(MagicMock(), None, None, catalog)

    # TODO: Add assertions


@patch('hermes.services.result_service.TimeStepRepository.get_or_create',
       autospec=True)
@patch('hermes.services.result_service.GridCellRepository.get_or_create',
       autospec=True)
@patch('hermes.services.result_service.ModelResultRepository.batch_create',
       autospec=True)
@patch('hermes.services.result_service.GRParametersRepository.'
       'create_from_forecast_grrategrid',
       autospec=True)
def test_save_grrategrid_to_repositories(mock_grparameters_repo,
                                         mock_model_result_repo,
                                         mock_grid_cell_repo,
                                         mock_time):
    catalog_path = os.path.join(
        MODULE_LOCATION,
        '../../repositories/tests/data/forecastgrrategrid.pkl')

    with open(catalog_path, 'rb') as f:
        rategrid = pickle.load(f)

    rategrid = rategrid[-1]

    rategrid2 = rategrid.copy()
    rategrid2[['longitude_min', 'longitude_max',
               'latitude_min', 'latitude_max']] = \
        rategrid2[['longitude_min', 'longitude_max',
                   'latitude_min', 'latitude_max']] + 1

    rategrid = pd.concat([rategrid, rategrid2])

    save_forecast_grrategrid(MagicMock(), None, None, rategrid)

    # TODO: Add assertions
