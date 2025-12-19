"""add modelrun_oid to eventforecast

Revision ID: a1b2c3d4e5f6
Revises: 3c9be082f685
Create Date: 2025-12-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '3c9be082f685'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BATCH_SIZE = 10000


def upgrade() -> None:
    # Step 1: Add modelrun_oid column as nullable
    op.add_column('eventforecast',
                  sa.Column('modelrun_oid', postgresql.UUID(), nullable=True))

    # Step 2: Populate modelrun_oid in batches to avoid long locks
    conn = op.get_bind()

    while True:
        result = conn.execute(sa.text(f"""
            UPDATE eventforecast
            SET modelrun_oid = modelresult.modelrun_oid
            FROM modelresult
            WHERE eventforecast.modelresult_oid = modelresult.oid
              AND eventforecast.oid IN (
                  SELECT oid FROM eventforecast
                  WHERE modelrun_oid IS NULL
                  LIMIT {BATCH_SIZE}
              )
        """))

        if result.rowcount == 0:
            break

    # Step 3: Make modelrun_oid non-nullable
    op.alter_column('eventforecast', 'modelrun_oid',
                    existing_type=postgresql.UUID(),
                    nullable=False)

    # Step 4: Create foreign key constraint
    op.create_foreign_key(
        'fk_eventforecast_modelrun_oid_modelrun',
        'eventforecast', 'modelrun',
        ['modelrun_oid'], ['oid'],
        ondelete='CASCADE'
    )

    # Step 5: Create index on modelrun_oid
    op.create_index(op.f('ix_eventforecast_modelrun_oid'),
                    'eventforecast', ['modelrun_oid'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_eventforecast_modelrun_oid'),
                  table_name='eventforecast')

    op.drop_constraint('fk_eventforecast_modelrun_oid_modelrun',
                       'eventforecast', type_='foreignkey')

    op.drop_column('eventforecast', 'modelrun_oid')
