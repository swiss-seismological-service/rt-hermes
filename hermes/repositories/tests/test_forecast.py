from hermes.repositories.project import ForecastRepository, ProjectRepository
from hermes.schemas.base import EStatus
from hermes.tests.data_factories import TestDataFactory


class TestForecast:
    def test_create(self, session, full_scenario):
        forecast = TestDataFactory.create_forecast(
            forecastseries_oid=full_scenario.forecastseries.oid,
            status=EStatus.PENDING
        )

        forecast = ForecastRepository.create(session, forecast)
        assert forecast.oid is not None

        ProjectRepository.delete(session, full_scenario.project.oid)

        assert ForecastRepository.get_by_id(session, forecast.oid) is None
