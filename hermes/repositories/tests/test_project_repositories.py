import pytest
from sqlalchemy.exc import IntegrityError

from hermes.repositories.project import (ForecastRepository,
                                         ForecastSeriesRepository,
                                         ModelConfigRepository,
                                         ProjectRepository, TagRepository)
from hermes.schemas import Tag
from hermes.schemas.base import EStatus
from hermes.tests.data_factories import TestDataFactory


class TestProjectRepository:
    def test_get_by_name(self, session):
        project = TestDataFactory.create_project(name='unique_project')
        ProjectRepository.create(session, project)

        result = ProjectRepository.get_by_name(session, 'unique_project')
        assert result.name == 'unique_project'

    def test_get_by_name_not_found(self, session):
        result = ProjectRepository.get_by_name(session, 'nonexistent')
        assert result is None


class TestTagRepository:
    def test_get_or_create_existing(self, session):
        tag = Tag(name='existing_tag')
        TagRepository.create(session, tag)

        result = TagRepository.get_or_create(session, 'existing_tag')
        assert result.name == 'existing_tag'

    def test_get_or_create_new(self, session):
        result = TagRepository.get_or_create(session, 'new_tag')
        assert result.name == 'new_tag'


class TestForecastSeriesRepository:

    def test_get_by_project(self, session, full_scenario):
        series_list = ForecastSeriesRepository.get_by_project(
            session, full_scenario.project.oid)
        assert len(series_list) == 1
        assert series_list[0].name == full_scenario.forecastseries.name

    def test_delete_cascade(self, session):
        project = TestDataFactory.create_project()
        project = ProjectRepository.create(session, project)

        forecastseries = TestDataFactory.create_forecastseries(
            project_oid=project.oid
        )
        forecastseries = ForecastSeriesRepository.create(
            session, forecastseries)

        ProjectRepository.delete(session, project.oid)

        assert ForecastSeriesRepository.get_by_id(
            session, forecastseries.oid) is None

    def test_get_tags(self, session, full_scenario):
        tags = ForecastSeriesRepository.get_tags(
            session, full_scenario.forecastseries.oid)

        assert len(tags) == 2
        tag_names = [t.name for t in tags]
        assert 'tag1' in tag_names
        assert 'tag3' not in tag_names

    def test_get_model_configs(self, session, full_scenario):
        model_configs = ForecastSeriesRepository.get_model_configs(
            session, full_scenario.forecastseries.oid)

        assert len(model_configs) == 1
        assert model_configs[0].name == full_scenario.model_config.name


class TestForecastRepository:

    def test_update_status(self, session, full_scenario):
        forecast = TestDataFactory.create_forecast(
            forecastseries_oid=full_scenario.forecastseries.oid,
            status=EStatus.PENDING
        )
        forecast = ForecastRepository.create(session, forecast)

        updated = ForecastRepository.update_status(
            session, forecast.oid, EStatus.RUNNING)
        assert updated.status == EStatus.RUNNING

    def test_get_by_forecastseries(self, session, full_scenario):
        # full_scenario already has one forecast, get initial count
        initial_forecasts = ForecastRepository.get_by_forecastseries(
            session, full_scenario.forecastseries.oid)
        initial_count = len(initial_forecasts)

        # Create another forecast for the same forecastseries
        forecast = TestDataFactory.create_forecast(
            forecastseries_oid=full_scenario.forecastseries.oid
        )
        ForecastRepository.create(session, forecast)

        # Should now have initial_count + 1 forecasts
        forecasts = ForecastRepository.get_by_forecastseries(
            session, full_scenario.forecastseries.oid)
        assert len(forecasts) == initial_count + 1

    def test_delete_cascade_from_project(self, session, full_scenario):
        forecast = TestDataFactory.create_forecast(
            forecastseries_oid=full_scenario.forecastseries.oid,
            status=EStatus.PENDING
        )
        forecast = ForecastRepository.create(session, forecast)

        ProjectRepository.delete(session, full_scenario.project.oid)

        assert ForecastRepository.get_by_id(session, forecast.oid) is None


class TestModelConfigRepository:
    def test_get_by_name(self, session):
        model_config = TestDataFactory.create_model_config(
            name='unique_config')
        ModelConfigRepository.create(session, model_config)

        result = ModelConfigRepository.get_by_name(session, 'unique_config')
        assert result.name == 'unique_config'

    def test_unique_constraint(self, session):
        model_config = TestDataFactory.create_model_config(
            name='duplicate_config',
            tags=['INDUCED', 'FORGE']
        )

        ModelConfigRepository.create(session, model_config)

        with pytest.raises(IntegrityError):
            ModelConfigRepository.create(session, model_config)
