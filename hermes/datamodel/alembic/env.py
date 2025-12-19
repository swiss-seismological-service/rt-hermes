from logging.config import fileConfig

from alembic import context
from alembic_utils.replaceable_entity import register_entities
from sqlalchemy import engine_from_config, pool, text

from hermes.config import get_settings
from hermes.datamodel.alembic.functions import dummy
from hermes.datamodel.base import ORMBase

EXCLUDE_TABLES = [
    'spatial_ref_sys',
    'geometry_columns',
    'topology',
    'layer'
]

EXCLUDE_NAMES = [
    'topology_id_seq']

EXCLUDE_TYPES = ['grant_table', 'function', 'view',
                 'extension', 'trigger', 'policy',
                 'materialized_view']

INCLUDE_NAMESPACES = ['hermes']

SEARCH_PATH = 'public'

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
target_metadata = ORMBase.metadata

# other values from the config
config.set_main_option(
    'sqlalchemy.url',
    get_settings().SQLALCHEMY_DATABASE_URL.render_as_string(
        hide_password=False))


def include_name(name, type_, parent_names):
    """
    Filter out tables and other objects that we don't want to track in
    our migrations.
    """
    if (type_ == 'table' and name in EXCLUDE_TABLES) or \
        (type_ != 'table' and name in EXCLUDE_NAMES) or \
        (type_ in EXCLUDE_TYPES
            and not any([ns in name for ns in INCLUDE_NAMESPACES])):
        return False
    return True


# At least one entity must be registered for replaceable objects to be
# included in the migration.
register_entities([dummy])


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_name=include_name
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        connection.execute(text(f"SET search_path TO {SEARCH_PATH}"))
        connection.commit()

        context.configure(
            connection=connection, target_metadata=target_metadata,
            include_name=include_name
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
