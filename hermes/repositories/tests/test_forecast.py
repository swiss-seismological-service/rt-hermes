from datetime import datetime

from hermes.repositories.project import ForecastRepository, ProjectRepository
from hermes.schemas.base import EStatus
from hermes.schemas.project_schemas import Forecast


class TestForecast:
    def test_create(self, session, full_scenario):
        forecast = Forecast(
            starttime=datetime(2021, 1, 1, 0, 0, 0),
            endtime=datetime(2021, 1, 2, 0, 0, 0),
            status=EStatus.PENDING,
            forecastseries_oid=full_scenario.forecastseries.oid)

        forecast = ForecastRepository.create(session, forecast)
        assert forecast.oid is not None

        ProjectRepository.delete(session, full_scenario.project.oid)

        assert ForecastRepository.get_by_id(session, forecast.oid) is None
