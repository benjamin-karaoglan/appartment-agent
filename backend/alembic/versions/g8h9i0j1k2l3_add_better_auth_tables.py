"""add_better_auth_tables

Revision ID: g8h9i0j1k2l3
Revises: f7g8h9i0j1k2
Create Date: 2025-02-06 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g8h9i0j1k2l3"
down_revision: Union[str, None] = "f7g8h9i0j1k2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create ba_user table (Better Auth users)
    op.create_table(
        "ba_user",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("email_verified", sa.Boolean(), default=False, nullable=False),
        sa.Column("image", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("is_superuser", sa.Boolean(), default=False, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_ba_user_email", "ba_user", ["email"], unique=True)

    # Create ba_session table (Better Auth sessions)
    op.create_table(
        "ba_session",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("ba_user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token", sa.String(255), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_ba_session_token", "ba_session", ["token"], unique=True)
    op.create_index("ix_ba_session_user_id", "ba_session", ["user_id"], unique=False)

    # Create ba_account table (OAuth/credential accounts)
    op.create_table(
        "ba_account",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("ba_user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("account_id", sa.String(255), nullable=False),
        sa.Column("provider_id", sa.String(255), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("access_token_expires_at", sa.DateTime(), nullable=True),
        sa.Column("refresh_token_expires_at", sa.DateTime(), nullable=True),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("password", sa.String(255), nullable=True),  # For credential provider
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_ba_account_user_id", "ba_account", ["user_id"], unique=False)
    op.create_index(
        "ix_ba_account_provider_account",
        "ba_account",
        ["provider_id", "account_id"],
        unique=True,
    )

    # Create ba_verification table (email verification tokens)
    op.create_table(
        "ba_verification",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("identifier", sa.String(255), nullable=False),
        sa.Column("value", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_ba_verification_identifier", "ba_verification", ["identifier"], unique=False
    )

    # Add ba_user_id column to existing users table for linking
    op.add_column(
        "users",
        sa.Column(
            "ba_user_id",
            sa.String(36),
            sa.ForeignKey("ba_user.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_users_ba_user_id", "users", ["ba_user_id"], unique=True)


def downgrade() -> None:
    # Remove ba_user_id from users table
    op.drop_index("ix_users_ba_user_id", table_name="users")
    op.drop_column("users", "ba_user_id")

    # Drop Better Auth tables
    op.drop_index("ix_ba_verification_identifier", table_name="ba_verification")
    op.drop_table("ba_verification")

    op.drop_index("ix_ba_account_provider_account", table_name="ba_account")
    op.drop_index("ix_ba_account_user_id", table_name="ba_account")
    op.drop_table("ba_account")

    op.drop_index("ix_ba_session_user_id", table_name="ba_session")
    op.drop_index("ix_ba_session_token", table_name="ba_session")
    op.drop_table("ba_session")

    op.drop_index("ix_ba_user_email", table_name="ba_user")
    op.drop_table("ba_user")
