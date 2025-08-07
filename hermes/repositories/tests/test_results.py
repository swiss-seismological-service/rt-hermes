import os
import pickle
import uuid
from datetime import datetime

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
from hermes.schemas.base import EResultType
from hermes.schemas.project_schemas import Forecast, ForecastSeries
from hermes.schemas.result_schemas import (EventForecast, GridCell,
                                           GRParameters, ModelResult, ModelRun,
                                           TimeStep)

MODULE_LOCATION = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'data')


class TestGridCells:
    def test_create(self, session, full_scenario):
        cell1 = GridCell(geom=Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
                         depth_max=10,
                         depth_min=5,
                         forecastseries_oid=full_scenario.forecastseries.oid)
        cell1 = GridCellRepository.create(session, cell1)
        assert cell1.oid is not None

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

    def test_get_by_id(self, session, full_scenario):
        cell1 = GridCell(geom=Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
                         depth_max=10,
                         depth_min=5,
                         forecastseries_oid=full_scenario.forecastseries.oid)
        cell1 = GridCellRepository.create(session, cell1)

        cell2 = GridCellRepository.get_by_id(session, cell1.oid)
        assert cell1 == cell2

    def test_unique_constraint(self, session, full_scenario):
        fs = ForecastSeries(oid=uuid.uuid4(),
                            name='test',
                            schedule_starttime=datetime(2021, 1, 1))

        poly1 = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
        poly2 = Polygon([(0, 0), (2, 0), (1, 1), (0, 1)])

        cell1 = GridCell(geom=poly1,
                         depth_max=10,
                         depth_min=5,
                         forecastseries_oid=full_scenario.forecastseries.oid)

        cell2 = cell1.model_copy(update={'geom': poly2})
        cell3 = cell1.model_copy(update={'depth_max': 20})
        cell4 = cell1.model_copy(update={'depth_min': 2})
        cell5 = cell1.model_copy(update={'forecastseries_oid': fs.oid})

        ForecastSeriesRepository.create(session, fs)
        GridCellRepository.create(session, cell1)
        GridCellRepository.create(session, cell2)
        GridCellRepository.create(session, cell3)
        GridCellRepository.create(session, cell4)
        GridCellRepository.create(session, cell5)

        with pytest.raises(IntegrityError):
            GridCellRepository.create(session, cell1)


class TestTimeStep:
    def test_create(self, session, full_scenario):
        timestep = TimeStep(
            starttime=datetime(2021, 1, 1),
            endtime=datetime(2021, 1, 2),
            forecastseries_oid=full_scenario.forecastseries.oid)
        timestep = TimeStepRepository.create(session, timestep)
        assert timestep.oid is not None

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

    def test_get_by_id(self, session, full_scenario):
        timestep = TimeStep(
            starttime=datetime(2021, 1, 1),
            endtime=datetime(2021, 1, 2),
            forecastseries_oid=full_scenario.forecastseries.oid)
        timestep = TimeStepRepository.create(session, timestep)

        timestep2 = TimeStepRepository.get_by_id(session, timestep.oid)
        assert timestep == timestep2

    def test_unique_constraint(self, session, full_scenario):
        fs = ForecastSeries(oid=uuid.uuid4(),
                            name='test',
                            schedule_starttime=datetime(2021, 1, 1))

        ts1 = TimeStep(starttime=datetime(2021, 1, 1),
                       endtime=datetime(2021, 1, 2),
                       forecastseries_oid=full_scenario.forecastseries.oid)

        ts2 = ts1.model_copy(update={'starttime': datetime(2021, 1, 3)})
        ts3 = ts1.model_copy(update={'endtime': datetime(2021, 1, 3)})
        ts4 = ts1.model_copy(update={'forecastseries_oid': fs.oid})

        ForecastSeriesRepository.create(session, fs)
        TimeStepRepository.create(session, ts1)
        TimeStepRepository.create(session, ts2)
        TimeStepRepository.create(session, ts3)
        TimeStepRepository.create(session, ts4)

        with pytest.raises(IntegrityError):
            TimeStepRepository.create(session, ts1)


class TestModelResult:

    @pytest.fixture(autouse=True)
    def _create_step_cell(self, session):

        forecastseries = ForecastSeries(
            oid=uuid.uuid4(),
            name='test',
            schedule_starttime=datetime(2021, 1, 1))
        self.forecastseries_oid = ForecastSeriesRepository.create(
            session, forecastseries).oid

        forecast = Forecast(oid=uuid.uuid4(),
                            starttime=datetime(2021, 1, 1),
                            endtime=datetime(2021, 1, 2),
                            forecastseries_oid=self.forecastseries_oid)
        self.forecast_oid = ForecastRepository.create(session, forecast).oid

        modelrun = ModelRun(oid=uuid.uuid4(),
                            forecast_oid=self.forecast_oid)
        self.modelrun_oid = ModelRunRepository.create(session, modelrun).oid

        cell = GridCell(geom=Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
                        depth_max=10,
                        depth_min=5,
                        forecastseries_oid=self.forecastseries_oid)
        self.cell = GridCellRepository.create(session, cell)

        timestep = TimeStep(starttime=datetime(2021, 1, 1),
                            endtime=datetime(2021, 1, 2),
                            forecastseries_oid=self.forecastseries_oid)
        self.timestep = TimeStepRepository.create(session, timestep)

        modelresult = ModelResult(result_type=EResultType.CATALOG,
                                  timestep_oid=self.timestep.oid,
                                  gridcell_oid=self.cell.oid,
                                  modelrun_oid=self.modelrun_oid)
        self.modelresult_oid = ModelResultRepository.create(
            session, modelresult).oid

    def test_delete_cascade(self, session):

        ModelResultRepository.delete(session, self.modelresult_oid)
        assert ModelResultRepository.get_by_id(
            session, self.modelresult_oid) is None
        assert GridCellRepository.get_by_id(session, self.cell.oid) is not None
        assert TimeStepRepository.get_by_id(
            session, self.timestep.oid) is not None

        ForecastSeriesRepository.delete(session, self.forecastseries_oid)
        assert GridCellRepository.get_by_id(session, self.cell.oid) is None
        assert TimeStepRepository.get_by_id(session, self.timestep.oid) is None

    def test_batch_create(self, session):
        ids = ModelResultRepository.batch_create(session,
                                                 10,
                                                 EResultType.CATALOG,
                                                 None,
                                                 None,
                                                 None)

        count = session.execute(
            text('SELECT COUNT(modelresult.oid) FROM modelresult;')
        ).one_or_none()

        assert count is not None
        assert count[0] == 11
        assert len(ids) == 10


class TestEventForecast:
    def test_create(self, session):
        event = EventForecast(longitude_value=1,
                              latitude_value=2,
                              depth_value=3,
                              magnitude_value=4,
                              time_value=datetime(2021, 1, 1))

        event = EventForecastRepository.create(session, event)
        assert event.oid is not None

    def test_create_from_forecast_catalog(self, session):
        catalog_path = os.path.join(MODULE_LOCATION, 'catalog.parquet.gzip')

        catalog = ForecastCatalog(pd.read_parquet(catalog_path))
        catalog.n_catalogs = 5
        catalog['catalog_id'] = np.random.randint(0, catalog.n_catalogs,
                                                  catalog.shape[0])

        len_cat0 = len(catalog[catalog['catalog_id'] == 0])
        len_fc = len(catalog)

        modelresult_oids = ModelResultRepository.batch_create(
            session, catalog.n_catalogs, EResultType.CATALOG, None, None, None)

        EventForecastRepository \
            .create_from_forecast_catalog(session, catalog, modelresult_oids)

        count = session.execute(
            text('SELECT COUNT(eventforecast.oid) FROM eventforecast;'))\
            .one_or_none()
        assert count is not None
        assert count[0] == len_fc

        count = session.execute(
            text('SELECT COUNT(eventforecast.oid) FROM eventforecast '
                 'WHERE modelresult_oid = :modelresult_oid;'),
            {'modelresult_oid': modelresult_oids[0]}
        ).one_or_none()
        assert count is not None
        assert count[0] == len_cat0


class TestGRParameters:
    def test_create(self, session):
        gr_params = GRParameters(a_value=1, b_value=2,
                                 mc_value=3, number_events_value=4)
        gr_params = GRParametersRepository.create(session, gr_params)
        assert gr_params.oid is not None

    def test_create_from_forecast_grrategrid(self, session):
        rategrid_path = os.path.join(MODULE_LOCATION, 'forecastgrrategrid.pkl')

        with open(rategrid_path, 'rb') as f:
            data = pickle.load(f)

        rategrid = data[-1]

        # len_cat0 = len(catalog[catalog['catalog_id'] == 0])
        len_fc = len(rategrid)

        modelresult_oids = ModelResultRepository.batch_create(
            session, len(rategrid), EResultType.GRID, None, None, None)

        GRParametersRepository.create_from_forecast_grrategrid(
            session, rategrid, modelresult_oids)

        count = session.execute(
            text('SELECT COUNT(grparameters.oid) FROM grparameters;'))\
            .one_or_none()
        assert count is not None
        assert count[0] == len_fc

        count = session.execute(
            text('SELECT COUNT(grparameters.oid) FROM grparameters '
                 'WHERE modelresult_oid = :modelresult_oid;'),
            {'modelresult_oid': modelresult_oids[0]}
        ).one_or_none()
        assert count is not None
        assert count[0] == 1

    def test_get_forecast_grrategrid(self, session):
        pass
