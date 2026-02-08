"""rename minio_key/minio_bucket to storage_key/storage_bucket

Revision ID: i0j1k2l3m4n5
Revises: h9i0j1k2l3m4
Create Date: 2026-02-08 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "i0j1k2l3m4n5"
down_revision: Union[str, None] = "h9i0j1k2l3m4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename columns in documents table
    op.alter_column("documents", "minio_key", new_column_name="storage_key")
    op.alter_column("documents", "minio_bucket", new_column_name="storage_bucket")
    op.execute("ALTER INDEX ix_documents_minio_key RENAME TO ix_documents_storage_key")

    # Rename columns in photos table
    op.alter_column("photos", "minio_key", new_column_name="storage_key")
    op.alter_column("photos", "minio_bucket", new_column_name="storage_bucket")

    # Rename columns in photo_redesigns table
    op.alter_column("photo_redesigns", "minio_key", new_column_name="storage_key")
    op.alter_column("photo_redesigns", "minio_bucket", new_column_name="storage_bucket")


def downgrade() -> None:
    # Revert documents table
    op.alter_column("documents", "storage_key", new_column_name="minio_key")
    op.alter_column("documents", "storage_bucket", new_column_name="minio_bucket")
    op.execute("ALTER INDEX ix_documents_storage_key RENAME TO ix_documents_minio_key")

    # Revert photos table
    op.alter_column("photos", "storage_key", new_column_name="minio_key")
    op.alter_column("photos", "storage_bucket", new_column_name="minio_bucket")

    # Revert photo_redesigns table
    op.alter_column("photo_redesigns", "storage_key", new_column_name="minio_key")
    op.alter_column("photo_redesigns", "storage_bucket", new_column_name="minio_bucket")
