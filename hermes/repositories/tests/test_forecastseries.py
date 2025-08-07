from shapely.geometry import Polygon
from sqlalchemy import text

from hermes.repositories.project import (ForecastSeriesRepository,
                                         ProjectRepository)
from hermes.tests.data_factories import TestDataFactory


class TestForecastseries:

    def test_create(self, connection, session, full_scenario):
        forecastseries = TestDataFactory.create_forecastseries(
            name='forecastseries',
            project_oid=full_scenario.project.oid,
            tags=['INDUCED', 'FORGE']
        )

        forecastseries = ForecastSeriesRepository.create(
            session, forecastseries)

        assert forecastseries.oid is not None
        assert 'FORGE' in forecastseries.tags

        tags = connection.execute(
            text('SELECT * FROM tag'))
        tags = [t.name for t in tags.all()]
        assert len(tags) >= 2
        assert "INDUCED" in tags
        assert "FORGE" in tags

        assert isinstance(forecastseries.bounding_polygon, Polygon)

    def test_delete(self, session, full_scenario):
        ProjectRepository.delete(session,
                                 full_scenario.forecastseries.project_oid)

        assert ForecastSeriesRepository.get_by_id(
            session, full_scenario.forecastseries.oid) is None

    def test_get_by_name(self, session, full_scenario):
        result = ForecastSeriesRepository.get_by_name(
            session, full_scenario.forecastseries.name)

        assert result.name == full_scenario.forecastseries.name

    def test_get_tags(self, session, full_scenario):
        tags = ForecastSeriesRepository.get_tags(
            session, full_scenario.forecastseries.oid)

        assert len(tags) == 2
        assert 'tag1' in [t.name for t in tags]
        assert 'tag3' not in [t.name for t in tags]

    def test_get_model_configs(self, session, full_scenario):
        model_configs = ForecastSeriesRepository.get_model_configs(
            session, full_scenario.forecastseries.oid)

        assert len(model_configs) == 1
        assert model_configs[0].name == full_scenario.model_config.name
