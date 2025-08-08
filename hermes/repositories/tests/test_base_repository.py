from uuid import uuid4

import pytest
from sqlalchemy import text

from hermes.repositories.project import ProjectRepository, TagRepository
from hermes.schemas import Tag
from hermes.tests.data_factories import TestDataFactory


class TestRepositoryFactory:
    """Test the repository factory functionality using
       ProjectRepository as example.
    """

    def test_create(self, session, connection):
        project = TestDataFactory.create_project(name='factory_test')
        created_project = ProjectRepository.create(session, project)

        assert created_project.oid is not None
        assert created_project.name == 'factory_test'

        # Verify in database
        count = connection.execute(
            text('SELECT COUNT(*) FROM project WHERE oid = :oid'),
            {'oid': created_project.oid}
        ).scalar()
        assert count == 1

    def test_get_by_id(self, session):
        project = TestDataFactory.create_project()
        created = ProjectRepository.create(session, project)

        retrieved = ProjectRepository.get_by_id(session, created.oid)
        assert retrieved.oid == created.oid
        assert retrieved.name == created.name

    def test_get_by_id_not_found(self, session):
        result = ProjectRepository.get_by_id(session, uuid4())
        assert result is None

    def test_update(self, session):
        project = TestDataFactory.create_project(name='original')
        created = ProjectRepository.create(session, project)

        created.name = 'updated'
        updated = ProjectRepository.update(session, created)

        assert updated.name == 'updated'

        # Verify change persisted
        retrieved = ProjectRepository.get_by_id(session, created.oid)
        assert retrieved.name == 'updated'

    def test_update_nonexistent(self, session):
        project = TestDataFactory.create_project()
        project.oid = uuid4()  # Non-existent ID

        with pytest.raises(ValueError, match='No object with id .* found'):
            ProjectRepository.update(session, project)

    def test_get_all(self, session):
        project1 = TestDataFactory.create_project(name='project1')
        project2 = TestDataFactory.create_project(name='project2')

        ProjectRepository.create(session, project1)
        ProjectRepository.create(session, project2)

        all_projects = ProjectRepository.get_all(session)
        assert len(all_projects) == 2

        names = [p.name for p in all_projects]
        assert 'project1' in names
        assert 'project2' in names

    def test_delete(self, session, connection):
        project = TestDataFactory.create_project()
        created = ProjectRepository.create(session, project)

        ProjectRepository.delete(session, created.oid)

        # Verify deleted from database
        count = connection.execute(
            text('SELECT COUNT(*) FROM project WHERE oid = :oid'),
            {'oid': created.oid}
        ).scalar()
        assert count == 0

        # Verify get_by_id returns None
        result = ProjectRepository.get_by_id(session, created.oid)
        assert result is None

    def test_delete_nonexistent(self, session):
        with pytest.raises(ValueError, match='No object with id .* found'):
            ProjectRepository.delete(session, uuid4())

    @pytest.mark.parametrize("repository_class,factory_method", [
        (ProjectRepository, 'create_project'),
        (TagRepository, lambda: Tag(name='test_tag')),
    ])
    def test_crud_operations_all_repositories(self,
                                              session,
                                              repository_class,
                                              factory_method):
        """Test that basic CRUD operations work for all repository types."""
        # Create test data
        if callable(factory_method):
            test_data = factory_method()
        else:
            test_data = getattr(TestDataFactory, factory_method)()

        # Test Create
        created = repository_class.create(session, test_data)
        assert created.oid is not None

        # Test Get by ID
        retrieved = repository_class.get_by_id(session, created.oid)
        assert retrieved.oid == created.oid

        # Test Get All
        all_items = repository_class.get_all(session)
        assert len(all_items) >= 1
        assert any(item.oid == created.oid for item in all_items)

        # Test Delete
        repository_class.delete(session, created.oid)
        deleted_item = repository_class.get_by_id(session, created.oid)
        assert deleted_item is None
