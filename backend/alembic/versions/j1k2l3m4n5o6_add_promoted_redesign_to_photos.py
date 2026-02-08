"""add promoted_redesign_id to photos

Revision ID: j1k2l3m4n5o6
Revises: i0j1k2l3m4n5
Create Date: 2026-02-08 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "j1k2l3m4n5o6"
down_revision: Union[str, None] = "i0j1k2l3m4n5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "photos",
        sa.Column("promoted_redesign_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_photos_promoted_redesign_id",
        "photos",
        "photo_redesigns",
        ["promoted_redesign_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_photos_promoted_redesign_id", "photos", type_="foreignkey")
    op.drop_column("photos", "promoted_redesign_id")
