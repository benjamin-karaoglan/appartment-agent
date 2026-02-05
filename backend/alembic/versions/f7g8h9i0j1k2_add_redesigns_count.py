"""Add redesigns_generated_count to users table

Revision ID: f7g8h9i0j1k2
Revises: e6f7g8h9i0j1
Create Date: 2026-02-05 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7g8h9i0j1k2'
down_revision: Union[str, None] = 'e6f7g8h9i0j1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add redesigns_generated_count column to users table
    op.add_column('users', sa.Column('redesigns_generated_count', sa.Integer(), nullable=True, server_default='0'))

    # Initialize redesigns_generated_count for existing users based on their redesigns
    connection = op.get_bind()
    connection.execute(
        sa.text("""
            UPDATE users
            SET redesigns_generated_count = (
                SELECT COUNT(*)
                FROM photo_redesigns pr
                JOIN photos p ON pr.photo_id = p.id
                WHERE p.user_id = users.id
            )
        """)
    )


def downgrade() -> None:
    op.drop_column('users', 'redesigns_generated_count')
