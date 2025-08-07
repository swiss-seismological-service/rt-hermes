from datetime import datetime

from sqlalchemy import text

from hermes.repositories.project import ProjectRepository
from hermes.tests.data_factories import TestDataFactory


class TestFixtures:

    def test_fixture_forecastseries(self, connection, full_scenario):
        project_db = connection.execute(text('SELECT * FROM project'))
        assert len(project_db.all()) == 1
        forecastseries_db = connection.execute(
            text('SELECT * FROM forecastseries'))
        assert len(forecastseries_db.all()) == 1

    def test_fixture_rollback(self, session, connection):
        project = TestDataFactory.create_project(
            name='test_project2',
            starttime=datetime.now()
        )
        ProjectRepository.create(session, project)
        project_db = connection.execute(text('SELECT * FROM project'))
        assert len(project_db.all()) == 1
