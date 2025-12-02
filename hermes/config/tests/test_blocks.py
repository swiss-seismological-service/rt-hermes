from unittest.mock import MagicMock, patch

from pydantic import SecretStr

from hermes.config import HermesDatabaseCredentials, Settings


class TestHermesDatabaseCredentials:
    """Unit tests for HermesDatabaseCredentials block."""

    def test_get_connection_url_sync(self):
        """Test sync connection URL generation."""
        block = HermesDatabaseCredentials(
            host="db.example.com",
            port=5433,
            user="testuser",
            password=SecretStr("testpass"),
            database="testdb"
        )

        url = block.get_connection_url(async_driver=False)

        assert url.drivername == "postgresql+psycopg2"
        assert url.host == "db.example.com"
        assert url.port == 5433
        assert url.username == "testuser"
        assert url.database == "testdb"

    def test_get_connection_url_async(self):
        """Test async connection URL generation."""
        block = HermesDatabaseCredentials(
            host="localhost",
            port=5432,
            user="postgres",
            password=SecretStr("secret"),
            database="hermes"
        )

        url = block.get_connection_url(async_driver=True)

        assert url.drivername == "postgresql+asyncpg"
        assert url.host == "localhost"
        assert url.port == 5432

    def test_password_is_secret(self):
        """Test that password is stored as SecretStr."""
        block = HermesDatabaseCredentials(
            host="localhost",
            password=SecretStr("mysecret"),
        )

        assert isinstance(block.password, SecretStr)
        assert block.password.get_secret_value() == "mysecret"
        assert "mysecret" not in str(block.password)


class TestSettingsCredentialSource:
    """Tests for Settings credential source switching."""

    def test_credential_source_env_uses_env_vars(self, monkeypatch):
        """Test that CREDENTIAL_SOURCE=env uses environment variables."""
        monkeypatch.setenv("CREDENTIAL_SOURCE", "env")
        monkeypatch.setenv("POSTGRES_HOST", "envhost")
        monkeypatch.setenv("POSTGRES_HOST_EXTERNAL", "envhostexternal")
        monkeypatch.setenv("POSTGRES_PORT", "5555")
        monkeypatch.setenv("POSTGRES_USER", "envuser")
        monkeypatch.setenv("POSTGRES_PASSWORD", "envpass")
        monkeypatch.setenv("POSTGRES_DB", "envdb")

        settings = Settings()

        url = settings.SQLALCHEMY_DATABASE_URL
        assert url.host == "envhost"
        assert url.port == 5555
        assert url.username == "envuser"
        assert url.database == "envdb"

    @patch.object(HermesDatabaseCredentials, 'load')
    def test_credential_source_prefect_loads_block(
        self,
        mock_load: MagicMock,
        monkeypatch
    ):
        """Test that CREDENTIAL_SOURCE=prefect loads from Prefect Block."""
        mock_block = HermesDatabaseCredentials(
            host="blockhost",
            port=6666,
            user="blockuser",
            password=SecretStr("blockpass"),
            database="blockdb"
        )
        mock_load.return_value = mock_block

        monkeypatch.setenv("CREDENTIAL_SOURCE", "prefect")

        settings = Settings()
        url = settings.SQLALCHEMY_DATABASE_URL

        mock_load.assert_called_once_with("hermes-db")
        assert url.host == "blockhost"
        assert url.port == 6666
        assert url.username == "blockuser"
        assert url.database == "blockdb"

    @patch.object(HermesDatabaseCredentials, 'load')
    def test_async_url_with_prefect_source(
        self,
        mock_load: MagicMock,
        monkeypatch
    ):
        """Test async URL also loads from block when source is prefect."""
        mock_block = HermesDatabaseCredentials(
            host="asynchost",
            port=5432,
            user="user",
            password=SecretStr("pass"),
            database="db"
        )
        mock_load.return_value = mock_block

        monkeypatch.setenv("CREDENTIAL_SOURCE", "prefect")

        settings = Settings()
        url = settings.ASYNC_SQLALCHEMY_DATABASE_URL

        assert url.drivername == "postgresql+asyncpg"
        assert url.host == "asynchost"

    @patch.object(HermesDatabaseCredentials, 'load')
    def test_credential_source_prefect_handles_coroutine(
        self,
        mock_load: MagicMock,
        monkeypatch
    ):
        """Test that CREDENTIAL_SOURCE=prefect handles coroutine from load().

        In Prefect 3.x, Block.load() returns a coroutine in async contexts.
        This test verifies the code handles that case correctly.
        """
        mock_block = HermesDatabaseCredentials(
            host="corohost",
            port=7777,
            user="corouser",
            password=SecretStr("coropass"),
            database="corodb"
        )

        async def mock_coro():
            return mock_block

        mock_load.return_value = mock_coro()

        monkeypatch.setenv("CREDENTIAL_SOURCE", "prefect")

        settings = Settings()
        url = settings.SQLALCHEMY_DATABASE_URL

        mock_load.assert_called_once_with("hermes-db")
        assert url.host == "corohost"
        assert url.port == 7777
        assert url.username == "corouser"
        assert url.database == "corodb"
