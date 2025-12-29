"""add_minio_temporal_columns

Revision ID: a1b2c3d4e5f6
Revises: 30257fbe1e49
Create Date: 2025-12-28 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '30257fbe1e49'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add MinIO and Temporal columns to documents table."""
    # Add MinIO storage columns
    op.add_column('documents', sa.Column('minio_key', sa.String(), nullable=True))
    op.add_column('documents', sa.Column('minio_bucket', sa.String(), nullable=True))
    op.add_column('documents', sa.Column('file_hash', sa.String(length=64), nullable=True))

    # Add Temporal workflow columns
    op.add_column('documents', sa.Column('workflow_id', sa.String(), nullable=True))
    op.add_column('documents', sa.Column('workflow_run_id', sa.String(), nullable=True))
    op.add_column('documents', sa.Column('processing_status', sa.String(), nullable=True))
    op.add_column('documents', sa.Column('processing_started_at', sa.DateTime(), nullable=True))
    op.add_column('documents', sa.Column('processing_completed_at', sa.DateTime(), nullable=True))
    op.add_column('documents', sa.Column('processing_error', sa.Text(), nullable=True))

    # Add LangChain tracking columns
    op.add_column('documents', sa.Column('langchain_model', sa.String(), nullable=True))
    op.add_column('documents', sa.Column('langchain_tokens_used', sa.Integer(), nullable=True))
    op.add_column('documents', sa.Column('langchain_cost', sa.Float(), nullable=True))

    # Create indexes for new columns
    op.create_index('ix_documents_minio_key', 'documents', ['minio_key'], unique=False)
    op.create_index('ix_documents_workflow_id', 'documents', ['workflow_id'], unique=False)
    op.create_index('ix_documents_processing_status', 'documents', ['processing_status'], unique=False)
    op.create_index('ix_documents_file_hash', 'documents', ['file_hash'], unique=False)


def downgrade() -> None:
    """Remove MinIO and Temporal columns from documents table."""
    # Drop indexes
    op.drop_index('ix_documents_file_hash', table_name='documents')
    op.drop_index('ix_documents_processing_status', table_name='documents')
    op.drop_index('ix_documents_workflow_id', table_name='documents')
    op.drop_index('ix_documents_minio_key', table_name='documents')

    # Drop columns
    op.drop_column('documents', 'langchain_cost')
    op.drop_column('documents', 'langchain_tokens_used')
    op.drop_column('documents', 'langchain_model')
    op.drop_column('documents', 'processing_error')
    op.drop_column('documents', 'processing_completed_at')
    op.drop_column('documents', 'processing_started_at')
    op.drop_column('documents', 'processing_status')
    op.drop_column('documents', 'workflow_run_id')
    op.drop_column('documents', 'workflow_id')
    op.drop_column('documents', 'file_hash')
    op.drop_column('documents', 'minio_bucket')
    op.drop_column('documents', 'minio_key')
