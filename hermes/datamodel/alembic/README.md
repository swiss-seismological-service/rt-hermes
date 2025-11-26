# Generic single-database configuration.

Two branches are configured:
- `schema`: which contains changes to everything tracked inside SQLAlchemy.
- `utils`: which contains changes to functions, triggers and so on.

## Usage
To instantiate, upgrade and run the database you can use the __hermes__ cli:

```bash
# Initialize the database to the latest version.
hermes db initialize

# Upgrade the database to the latest version if it's not already.
hermes db upgrade

# Upgrade a specific branch or to a specific revision.
hermes db upgrade schema@head
hermes db upgrade utils@+1

# Downgrade a specific branch or to a specific revision.
hermes db downgrade schema@-1
hermes db downgrade utils@base

# Remove all data, tables and other database objects.
hermes db downgrade -y
```

## Migrations
To use the `alembic` CLI directly, you need to specify the config file location:

```bash
# Set the config path (or add to .env)
export ALEMBIC_CONFIG=hermes/datamodel/alembic/alembic.ini

# View current branches and revisions
alembic branches
alembic history

# Create a new migration for the utils branch
alembic revision --autogenerate -m "your message here" --head=utils@head

# Create a new migration for the schema branch
alembic revision --autogenerate -m "your message here" --head=schema@head
```

Alternatively, use the `-c` flag for each command:
```bash
alembic -c hermes/datamodel/alembic/alembic.ini branches
```

Please be extremely careful to always specify the correct head for the branch you are working on, otherwise you might end up with a migration that is not applied, or erroneously applied in case of a fresh database instantiation.

## Details
On database instantiation, the `schema` branch is directly set to the latest version, without executing any migration. This is because the schema branch is supposed to contain only changes to the schema, which are already applied by creating the database using the latest SQLAlchemy models.

The `utils` branch however is applied by running all migrations from the beginning to the latest version. This is because the `utils` branch is supposed to contain changes to functions, triggers and so on, which are not applied by creating the database using the latest SQLAlchemy models.

## Notes
- Names of the database objects created through the `utils` branch should be prefixed with `hermes_` to be picked up correctly and avoid conflicts with other objects.