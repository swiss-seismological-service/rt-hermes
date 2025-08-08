import os
import pickle
from datetime import datetime
from uuid import uuid4

import numpy as np
import pandas as pd
import pytest
from seismostats import ForecastCatalog
from shapely import Polygon
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from hermes.repositories.project import (ForecastRepository,
                                         ForecastSeriesRepository)
from hermes.repositories.results import (EventForecastRepository,
                                         GridCellRepository,
                                         GRParametersRepository,
                                         ModelResultRepository,
                                         ModelRunRepository,
                                         TimeStepRepository)
from hermes.schemas.base import EResultType, EStatus
from hermes.schemas.result_schemas import GridCell, ModelRun, TimeStep
from hermes.tests.data_factories import TestDataFactory

MODULE_LOCATION = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'data')


class TestGridCellRepository:
    def test_get_or_create(self, session, full_scenario):
        cell1 = GridCell(geom=Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
                         depth_max=10,
                         depth_min=5,
                         forecastseries_oid=full_scenario.forecastseries.oid)
        cell1 = GridCellRepository.get_or_create(session, cell1)
        assert cell1.oid is not None

        cell2 = GridCell(geom=Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
                         depth_max=10,
                         depth_min=5,
                         forecastseries_oid=full_scenario.forecastseries.oid)
        cell2 = GridCellRepository.get_or_create(session, cell2)
        assert cell1.oid == cell2.oid

    def test_unique_constraint(self, session, full_scenario):
        fs = TestDataFactory.create_forecastseries(
            project_oid=full_scenario.project.oid,
            name='test'
        )

        poly1 = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
        cell1 = GridCell(geom=poly1,
                         depth_max=10,
                         depth_min=5,
                         forecastseries_oid=full_scenario.forecastseries.oid)

        ForecastSeriesRepository.create(session, fs)
        GridCellRepository.create(session, cell1)

        with pytest.raises(IntegrityError):
            GridCellRepository.create(session, cell1)

    def test_find_by_forecastseries(self, session, full_scenario):
        cell = GridCell(geom=Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
                        depth_max=10,
                        depth_min=5,
                        forecastseries_oid=full_scenario.forecastseries.oid)
        GridCellRepository.create(session, cell)

        cells = GridCellRepository.find_by_forecastseries(
            session, full_scenario.forecastseries.oid)
        assert len(cells) == 1
        assert cells[0].depth_min == 5

    def test_find_by_spatial_bounds(self, session, full_scenario):
        cell = GridCell(geom=Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
                        depth_max=10,
                        depth_min=5,
                        forecastseries_oid=full_scenario.forecastseries.oid)
        GridCellRepository.create(session, cell)

        found_cell = GridCellRepository.find_by_spatial_bounds(
            session, full_scenario.forecastseries.oid, 5, 10)
        assert found_cell.depth_min == 5
        assert found_cell.depth_max == 10


class TestTimeStepRepository:
    def test_get_or_create(self, session, full_scenario):
        timestep = TimeStep(
            starttime=datetime(2021, 1, 1),
            endtime=datetime(2021, 1, 2),
            forecastseries_oid=full_scenario.forecastseries.oid)
        timestep = TimeStepRepository.get_or_create(session, timestep)
        assert timestep.oid is not None

        timestep2 = TimeStep(
            starttime=datetime(2021, 1, 1),
            endtime=datetime(2021, 1, 2),
            forecastseries_oid=full_scenario.forecastseries.oid)
        timestep2 = TimeStepRepository.get_or_create(session, timestep2)
        assert timestep.oid == timestep2.oid

    def test_unique_constraint(self, session, full_scenario):
        ts1 = TimeStep(starttime=datetime(2021, 1, 1),
                       endtime=datetime(2021, 1, 2),
                       forecastseries_oid=full_scenario.forecastseries.oid)

        TimeStepRepository.create(session, ts1)

        with pytest.raises(IntegrityError):
            TimeStepRepository.create(session, ts1)

    def test_find_by_bounds(self, session, full_scenario):
        starttime = datetime(2021, 1, 1)
        endtime = datetime(2021, 1, 2)
        timestep = TimeStep(
            starttime=starttime,
            endtime=endtime,
            forecastseries_oid=full_scenario.forecastseries.oid)
        TimeStepRepository.create(session, timestep)

        found_timestep = TimeStepRepository.find_by_bounds(
            session, full_scenario.forecastseries.oid, starttime, endtime)
        assert found_timestep.starttime == starttime
        assert found_timestep.endtime == endtime


class TestModelResultRepository:
    def test_batch_create(self, session, connection):
        ids = ModelResultRepository.batch_create(session,
                                                 10,
                                                 EResultType.CATALOG,
                                                 None,
                                                 None,
                                                 None)

        count = connection.execute(
            text('SELECT COUNT(modelresult.oid) FROM modelresult;')
        ).scalar()

        assert count == 10
        assert len(ids) == 10

    def test_count_by_modelrun(self, session, full_scenario):
        forecast = TestDataFactory.create_forecast(
            forecastseries_oid=full_scenario.forecastseries.oid
        )
        forecast = ForecastRepository.create(session, forecast)

        modelrun = ModelRun(forecast_oid=forecast.oid)
        modelrun = ModelRunRepository.create(session, modelrun)

        ModelResultRepository.batch_create(
            session, 5, EResultType.CATALOG, None, None, modelrun.oid)

        count = ModelResultRepository.count_by_modelrun(session, modelrun.oid)
        assert count == 5

    def test_get_by_modelrun(self, session, full_scenario):
        forecast = TestDataFactory.create_forecast(
            forecastseries_oid=full_scenario.forecastseries.oid
        )
        forecast = ForecastRepository.create(session, forecast)

        modelrun = ModelRun(forecast_oid=forecast.oid)
        modelrun = ModelRunRepository.create(session, modelrun)

        ModelResultRepository.batch_create(
            session, 3, EResultType.CATALOG, None, None, modelrun.oid)

        results = ModelResultRepository.get_by_modelrun(session, modelrun.oid)
        assert len(results) == 3
        assert all(r.modelrun_oid == modelrun.oid for r in results)


class TestModelRunRepository:
    def test_update_status(self, session):
        modelrun = ModelRun(status=EStatus.PENDING)
        modelrun = ModelRunRepository.create(session, modelrun)

        updated = ModelRunRepository.update_status(
            session, modelrun.oid, EStatus.RUNNING)
        assert updated.status == EStatus.RUNNING

        # Verify the change was persisted
        retrieved = ModelRunRepository.get_by_id(session, modelrun.oid)
        assert retrieved.status == EStatus.RUNNING

    def test_get_by_modelconfig(self, session, full_scenario):
        # full_scenario already has one modelrun, so we expect 1 initially
        initial_modelruns = ModelRunRepository.get_by_modelconfig(
            session, full_scenario.model_config.oid)
        initial_count = len(initial_modelruns)

        # Create another modelrun with the same modelconfig
        modelrun = ModelRun(
            status=EStatus.PENDING,
            modelconfig_oid=full_scenario.model_config.oid
        )
        ModelRunRepository.create(session, modelrun)

        # Now we should have initial_count + 1
        modelruns = ModelRunRepository.get_by_modelconfig(
            session, full_scenario.model_config.oid)
        assert len(modelruns) == initial_count + 1
        assert all(mr.modelconfig_oid == full_scenario.model_config.oid
                   for mr in modelruns)


class TestEventForecastRepository:
    def test_create_from_forecast_catalog(self, session, connection):
        catalog_path = os.path.join(MODULE_LOCATION, 'catalog.parquet.gzip')

        catalog = ForecastCatalog(pd.read_parquet(catalog_path))
        catalog.n_catalogs = 5
        catalog['catalog_id'] = np.random.randint(0, catalog.n_catalogs,
                                                  catalog.shape[0])

        len_cat0 = len(catalog[catalog['catalog_id'] == 0])
        len_fc = len(catalog)

        modelresult_oids = ModelResultRepository.batch_create(
            session, catalog.n_catalogs, EResultType.CATALOG, None, None, None)

        EventForecastRepository.create_from_forecast_catalog(
            session, catalog, modelresult_oids)

        count = connection.execute(
            text('SELECT COUNT(eventforecast.oid) FROM eventforecast;')
        ).scalar()
        assert count == len_fc

        count = connection.execute(
            text('SELECT COUNT(eventforecast.oid) FROM eventforecast '
                 'WHERE modelresult_oid = :modelresult_oid;'),
            {'modelresult_oid': modelresult_oids[0]}
        ).scalar()
        assert count == len_cat0

    def test_count_by_modelrun(self, session):
        modelrun = ModelRun(oid=uuid4())
        modelrun = ModelRunRepository.create(session, modelrun)

        ModelResultRepository.batch_create(
            session, 3, EResultType.CATALOG, None, None, modelrun.oid)

        count = EventForecastRepository.count_by_modelrun(
            session, modelrun.oid)
        assert count == 0  # No events linked to modelrun


class TestGRParametersRepository:
    def test_create_from_forecast_grrategrid(self, session, connection):
        rategrid_path = os.path.join(MODULE_LOCATION, 'forecastgrrategrid.pkl')

        with open(rategrid_path, 'rb') as f:
            data = pickle.load(f)

        rategrid = data[-1]
        len_fc = len(rategrid)

        modelresult_oids = ModelResultRepository.batch_create(
            session, len(rategrid), EResultType.GRID, None, None, None)

        GRParametersRepository.create_from_forecast_grrategrid(
            session, rategrid, modelresult_oids)

        count = connection.execute(
            text('SELECT COUNT(grparameters.oid) FROM grparameters;')
        ).scalar()
        assert count == len_fc

        count = connection.execute(
            text('SELECT COUNT(grparameters.oid) FROM grparameters '
                 'WHERE modelresult_oid = :modelresult_oid;'),
            {'modelresult_oid': modelresult_oids[0]}
        ).scalar()
        assert count == 1

    def test_count_by_modelrun(self, session):
        modelrun = ModelRun(oid=uuid4())
        modelrun = ModelRunRepository.create(session, modelrun)

        ModelResultRepository.batch_create(
            session, 5, EResultType.GRID, None, None, modelrun.oid)

        count = GRParametersRepository.count_by_modelrun(session, modelrun.oid)
        assert count == 0  # No GR parameters created yet
