import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from hermes.repositories.project import ModelConfigRepository
from hermes.tests.data_factories import TestDataFactory


class TestModel:

    def test_create(self, connection, session):
        model_config = TestDataFactory.create_model_config(
            name='config',
            tags=['INDUCED', 'FORGE']
        )

        model_config = ModelConfigRepository.create(session, model_config)

        assert model_config.oid is not None
        assert 'FORGE' in model_config.tags

        tags = connection.execute(
            text('SELECT * FROM tag'))
        tags = [t.name for t in tags.all()]
        assert len(tags) == 2
        assert "INDUCED" in tags

    def test_unique(self, session):
        model_config = TestDataFactory.create_model_config(
            name='config',
            tags=['INDUCED', 'FORGE']
        )

        ModelConfigRepository.create(session, model_config)

        with pytest.raises(IntegrityError):
            ModelConfigRepository.create(session, model_config)
