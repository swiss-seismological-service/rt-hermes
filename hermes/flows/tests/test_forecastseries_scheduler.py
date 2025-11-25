import uuid
from datetime import datetime, timedelta
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from dateutil.rrule import SECONDLY, rrule

from hermes.flows.forecastseries_scheduler import ForecastSeriesScheduler
from hermes.schemas import ForecastSeries


@patch('hermes.repositories.project.ForecastSeriesRepository.get_by_id',
       autospec=True)
class TestForecastSeriesScheduler:

    @pytest.mark.parametrize("fs", [
        {
            "schedule_starttime": None,
            "schedule_interval": 1800,
            "forecast_duration": 1800,
        },
        {
            "schedule_starttime": datetime(2021, 1, 2, 0, 0, 0),
            "schedule_interval": None,
            "forecast_duration": 1800,
        },
        {
            "schedule_starttime": datetime(2021, 1, 2, 0, 0, 0),
            "schedule_interval": 1800
        },
        {
            "schedule_starttime": datetime(2021, 1, 2, 0, 0, 0),
            "schedule_interval": 1800,
            "schedule_endtime": datetime(2021, 1, 3, 0, 0, 0),
            "forecast_endtime": datetime(2021, 1, 3, 0, 0, 0)
        }
    ])
    def test_schedule_assertions(self,
                                 # MOCKS
                                 mock_fs_get_by_id: MagicMock,
                                 # FIXTURES
                                 fs: ForecastSeries
                                 ):
        """
        Test that the assertions in the ForecastSeriesScheduler
        constructor work.
        """
        mock_fs_get_by_id.return_value = ForecastSeries()

        with pytest.raises(ValueError):
            scheduler = ForecastSeriesScheduler(None)
            scheduler._check_schedule_validity(fs)

    def test_schema_instance_attr(self,
                                  # MOCKS
                                  mock_fs_get_by_id: MagicMock
                                  ):
        forecastseries = ForecastSeries(
            schedule_starttime=datetime(2021, 1, 2, 0, 0, 0))
        mock_fs_get_by_id.return_value = forecastseries

        scheduler = ForecastSeriesScheduler(None)

        scheduler.schedule_starttime = datetime(2024, 1, 2, 0, 0, 0)

        assert scheduler.forecastseries.schedule_starttime == datetime(
            2024, 1, 2, 0, 0, 0)

    @pytest.mark.parametrize("fs, expected", [
        (ForecastSeries(schedule_starttime=datetime.now() + timedelta(days=1),
                        schedule_interval=1800,
                        forecast_duration=1800),
         rrule(SECONDLY,
               interval=1800,
               dtstart=datetime.now() + timedelta(days=1))),
        (ForecastSeries(schedule_starttime=datetime.now() + timedelta(days=1),
                        schedule_interval=1800,
                        forecast_duration=1800,
                        schedule_endtime=datetime.now() + timedelta(days=2)),
         rrule(SECONDLY,
               interval=1800,
               dtstart=datetime.now() + timedelta(days=1),
               until=datetime.now() + timedelta(days=2))),
        (ForecastSeries(schedule_starttime=datetime.now() - timedelta(days=2),
                        schedule_interval=1800,
                        forecast_duration=1800,
                        schedule_endtime=datetime.now() - timedelta(days=1)),
         rrule(SECONDLY,
               interval=1800,
               dtstart=datetime.now() - timedelta(days=2),
               until=datetime.now() - timedelta(days=1)
               )),
    ])
    def test_build_rrule(self,
                         # MOCKS
                         mock_fs_get_by_id: MagicMock,
                         # PARAMETERS
                         fs: ForecastSeries,
                         expected: rrule
                         ):
        mock_fs_get_by_id.return_value = fs
        scheduler = ForecastSeriesScheduler(None)

        rule = scheduler._build_rrule()
        assert str(rule) == str(expected)

    def test_future_rrule(self,
                          # MOCKS
                          mock_fs_get_by_id: MagicMock
                          ):
        fs = ForecastSeries(
            schedule_starttime=datetime.now() - timedelta(days=1),
            schedule_interval=1800,
            forecast_duration=1800)
        expected = rrule(SECONDLY,
                         interval=1800,
                         dtstart=datetime.now() + timedelta(seconds=1800))

        mock_fs_get_by_id.return_value = fs
        scheduler = ForecastSeriesScheduler(None)

        rule = scheduler._build_rrule('future')
        assert str(rule) == str(expected)

        scheduler.schedule_endtime = datetime.now() - timedelta(hours=1)

        with pytest.raises(ValueError):
            scheduler._build_rrule('future')

    @patch('hermes.flows.forecastseries_scheduler.forecast_runner',
           new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_catchup(self,
                           # MOCKS
                           mock_forecastrunner: AsyncMock,
                           mock_fs_get_by_id: MagicMock
                           ):
        fs = ForecastSeries(
            oid=uuid.uuid4(),
            schedule_starttime=datetime(2024, 1, 1, 0, 0, 0),
            schedule_endtime=datetime(2024, 1, 1, 0, 59, 0),
            schedule_interval=1800,
            forecast_duration=1800)

        mock_fs_get_by_id.return_value = fs
        scheduler = ForecastSeriesScheduler(None)

        assert await scheduler.check_prefect_schedule_exists() is False

        await scheduler.run_past_forecasts()

        assert mock_forecastrunner.call_count == 2
        mock_forecastrunner.assert_any_call(
            fs.oid, starttime=datetime(2024, 1, 1, 0, 0), mode='local'
        )
        mock_forecastrunner.assert_any_call(
            fs.oid, starttime=datetime(2024, 1, 1, 0, 30), mode='local'
        )


@patch('hermes.repositories.project.ForecastSeriesRepository.get_by_id',
       autospec=True)
@patch('hermes.repositories.project.ForecastSeriesRepository.update',
       autospec=True)
@patch('hermes.flows.forecastseries_scheduler.get_deployment_schedule_by_id',
       autospec=True)
class TestSchedulerClientInteractions:
    @patch('hermes.flows.forecastseries_scheduler.deployment_active',
           new_callable=AsyncMock, return_value=True)
    @patch('hermes.flows.forecastseries_scheduler.deployment_exists',
           new_callable=AsyncMock, return_value=True)
    @patch('hermes.flows.forecastseries_scheduler.add_deployment_schedule',
           new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_create(self,
                          # MOCKS
                          mock_add: AsyncMock,
                          mock_deployment_exists: AsyncMock,
                          mock_deployment_active: AsyncMock,
                          mock_get: MagicMock,
                          mock_fs_update: MagicMock,
                          mock_fs_get_by_id: MagicMock
                          ):

        fs = ForecastSeries(schedule_id=uuid.uuid4())
        mock_fs_get_by_id.return_value = fs
        mock_fs_update.return_value = fs
        mock_get.return_value = {}
        mock_add.return_value.id = fs.schedule_id

        scheduler = ForecastSeriesScheduler(None)

        with pytest.raises(ValueError):
            await scheduler.create({})

        mock_get.return_value = None

        start = datetime.now() + timedelta(days=1)

        schedule_data = {
            'schedule_starttime': start,
            'schedule_interval': 1800,
            'forecast_duration': 1800,
            'schedule_endtime': None}

        await scheduler.create(schedule_data)

        assert scheduler.forecastseries.schedule_starttime == start
        assert scheduler.forecastseries.schedule_interval == 1800
        assert scheduler.forecastseries.forecast_duration == 1800
        assert scheduler.forecastseries.schedule_endtime is None

        mock_add.assert_called_once_with(scheduler.deployment_name,
                                         ANY,
                                         True)
        mock_fs_update.assert_called_with(scheduler.session,
                                          scheduler.forecastseries)

        schedule_data2 = schedule_data.copy()
        schedule_data2['schedule_id'] = uuid.uuid4()

        with pytest.raises(ValueError):
            await scheduler.create(schedule_data2)

        mock_deployment_exists.return_value = False
        with pytest.raises(ValueError):
            await scheduler.create(schedule_data)

    @patch('hermes.flows.forecastseries_scheduler.'
           'ForecastSeriesScheduler.check_schedule_exists',
           new_callable=AsyncMock, return_value=True)
    @patch('hermes.flows.forecastseries_scheduler.'
           'ForecastSeriesScheduler.check_prefect_schedule_exists',
           new_callable=AsyncMock, return_value=True)
    @patch('hermes.flows.forecastseries_scheduler.delete_deployment_schedule',
           new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_delete(self,
                          # MOCKS
                          mock_delete: AsyncMock,
                          mock_prefect_schedule_exists: AsyncMock,
                          mock_schedule_exists: AsyncMock,
                          mock_get: MagicMock,
                          mock_fs_update: MagicMock,
                          mock_fs_get_by_id: MagicMock
                          ):
        sid = uuid.uuid4()
        fs = ForecastSeries(schedule_id=sid)
        fs_empty = ForecastSeries(schedule_active=True)
        mock_fs_get_by_id.return_value = fs
        mock_fs_update.return_value = fs_empty
        mock_get.return_value = {}

        scheduler = ForecastSeriesScheduler(None)

        await scheduler.delete_schedule()

        mock_delete.assert_called_once_with(scheduler.deployment_name,
                                            sid)
        mock_fs_update.assert_called_with(scheduler.session, fs_empty)

    @patch('hermes.flows.forecastseries_scheduler'
           '.update_deployment_schedule_status',
           new_callable=AsyncMock)
    @patch('hermes.flows.forecastseries_scheduler.'
           'ForecastSeriesScheduler.check_schedule_exists',
           new_callable=AsyncMock, return_value=True)
    @patch('hermes.flows.forecastseries_scheduler.'
           'ForecastSeriesScheduler.check_prefect_schedule_exists',
           new_callable=AsyncMock, return_value=True)
    @pytest.mark.asyncio
    async def test_update_status(self,
                                 mock_prefect_schedule_exists: AsyncMock,
                                 mock_schedule_exists: AsyncMock,
                                 mock_update_status: AsyncMock,
                                 mock_get: MagicMock,
                                 mock_fs_update: MagicMock,
                                 mock_fs_get_by_id: MagicMock):

        scheduler = ForecastSeriesScheduler(None)
        await scheduler.update_status(True)
        assert mock_update_status.call_count == 1

        mock_schedule_exists.return_value = False
        with pytest.raises(ValueError):
            await scheduler.update_status(True)

        mock_schedule_exists.return_value = True
        mock_prefect_schedule_exists.return_value = False

        assert mock_update_status.call_count == 1
