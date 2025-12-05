"""add modelrun_oid to grparameters

Revision ID: 3c9be082f685
Revises: cd951716a1c8
Create Date: 2025-12-05 12:08:57.099056

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3c9be082f685'
down_revision: Union[str, None] = 'cd951716a1c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Add modelrun_oid column as nullable
    op.add_column('grparameters',
                  sa.Column('modelrun_oid', postgresql.UUID(), nullable=True))

    # Step 2: Populate modelrun_oid from modelresult.modelrun_oid
    op.execute("""
        UPDATE grparameters
        SET modelrun_oid = modelresult.modelrun_oid
        FROM modelresult
        WHERE grparameters.modelresult_oid = modelresult.oid
    """)

    # Step 3: Make modelrun_oid non-nullable (should be safe after population)
    op.alter_column('grparameters', 'modelrun_oid',
                    existing_type=postgresql.UUID(),
                    nullable=False)

    # Step 4: Create foreign key constraint
    op.create_foreign_key(
        'fk_grparameters_modelrun_oid_modelrun',
        'grparameters', 'modelrun',
        ['modelrun_oid'], ['oid'],
        ondelete='CASCADE'
    )

    # Step 5: Create index on modelrun_oid
    op.create_index(op.f('ix_grparameters_modelrun_oid'),
                    'grparameters', ['modelrun_oid'], unique=False)


def downgrade() -> None:
    # Remove index
    op.drop_index(op.f('ix_grparameters_modelrun_oid'),
                  table_name='grparameters')

    # Remove foreign key constraint
    op.drop_constraint('fk_grparameters_modelrun_oid_modelrun',
                       'grparameters', type_='foreignkey')

    # Remove column
    op.drop_column('grparameters', 'modelrun_oid')
