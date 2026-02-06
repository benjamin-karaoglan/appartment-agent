#!/usr/bin/env python3
"""
Migrate existing users to Better Auth tables.

This script:
1. Reads all existing users from the `users` table
2. Creates corresponding `ba_user` records
3. Creates `ba_account` records with provider_id="credential" and existing bcrypt password hash
4. Links `users.ba_user_id` to the new `ba_user.id`

Usage:
    python scripts/migrate_users_to_better_auth.py [--dry-run]

Options:
    --dry-run    Preview changes without applying them
"""

import argparse
import logging
import os
import sys
import uuid
from datetime import datetime

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_database_url():
    """Get database URL from environment or default."""
    return os.getenv(
        "DATABASE_URL",
        "postgresql://appart:appart@localhost:5432/appart_agent",
    )


def migrate_users(dry_run: bool = False):
    """
    Migrate existing users to Better Auth tables.

    Args:
        dry_run: If True, preview changes without applying them
    """
    database_url = get_database_url()
    logger.info("Connecting to database...")

    engine = create_engine(database_url)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    try:
        # Check if ba_user table exists
        check_table = text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'ba_user'
            )
        """)
        result = session.execute(check_table).scalar()

        if not result:
            logger.error("Better Auth tables not found. Run Alembic migrations first:")
            logger.error("  cd backend && alembic upgrade head")
            sys.exit(1)

        # Get all existing users
        get_users = text("""
            SELECT id, uuid, email, hashed_password, full_name, is_active, is_superuser, created_at, updated_at, ba_user_id
            FROM users
            WHERE ba_user_id IS NULL
        """)
        users = session.execute(get_users).fetchall()

        logger.info(f"Found {len(users)} users to migrate")

        if len(users) == 0:
            logger.info("No users to migrate. All users already linked to Better Auth.")
            return

        migrated_count = 0

        for user in users:
            user_id = user.id
            email = user.email
            hashed_password = user.hashed_password
            full_name = user.full_name or ""
            is_active = user.is_active
            is_superuser = user.is_superuser
            created_at = user.created_at or datetime.utcnow()
            updated_at = user.updated_at or datetime.utcnow()

            logger.info(f"Processing user {user_id}: {email}")

            # Check if ba_user already exists for this email
            check_ba_user = text("SELECT id FROM ba_user WHERE email = :email")
            existing_ba_user = session.execute(check_ba_user, {"email": email}).fetchone()

            if existing_ba_user:
                # Link existing ba_user to this user
                ba_user_id = existing_ba_user.id
                logger.info(f"  Found existing ba_user: {ba_user_id}")
            else:
                # Create new ba_user
                ba_user_id = str(uuid.uuid4())

                if not dry_run:
                    insert_ba_user = text("""
                        INSERT INTO ba_user (id, email, name, email_verified, image, is_active, is_superuser, created_at, updated_at)
                        VALUES (:id, :email, :name, :email_verified, :image, :is_active, :is_superuser, :created_at, :updated_at)
                    """)
                    session.execute(
                        insert_ba_user,
                        {
                            "id": ba_user_id,
                            "email": email,
                            "name": full_name,
                            "email_verified": True,  # Existing users are considered verified
                            "image": None,
                            "is_active": is_active,
                            "is_superuser": is_superuser,
                            "created_at": created_at,
                            "updated_at": updated_at,
                        },
                    )
                    logger.info(f"  Created ba_user: {ba_user_id}")
                else:
                    logger.info(f"  [DRY RUN] Would create ba_user: {ba_user_id}")

            # Check if ba_account already exists for credential provider
            check_ba_account = text("""
                SELECT id FROM ba_account
                WHERE user_id = :user_id AND provider_id = 'credential'
            """)
            existing_account = session.execute(check_ba_account, {"user_id": ba_user_id}).fetchone()

            if not existing_account:
                # Create ba_account with credential provider and existing password hash
                ba_account_id = str(uuid.uuid4())

                if not dry_run:
                    insert_ba_account = text("""
                        INSERT INTO ba_account (id, user_id, account_id, provider_id, password, created_at, updated_at)
                        VALUES (:id, :user_id, :account_id, :provider_id, :password, :created_at, :updated_at)
                    """)
                    session.execute(
                        insert_ba_account,
                        {
                            "id": ba_account_id,
                            "user_id": ba_user_id,
                            "account_id": email,  # Use email as account_id for credential provider
                            "provider_id": "credential",
                            "password": hashed_password,  # Reuse existing bcrypt hash
                            "created_at": created_at,
                            "updated_at": updated_at,
                        },
                    )
                    logger.info(f"  Created ba_account: {ba_account_id} (credential provider)")
                else:
                    logger.info(f"  [DRY RUN] Would create ba_account: {ba_account_id}")
            else:
                logger.info("  ba_account already exists for credential provider")

            # Link users.ba_user_id to ba_user.id
            if not dry_run:
                update_user = text("""
                    UPDATE users SET ba_user_id = :ba_user_id WHERE id = :user_id
                """)
                session.execute(
                    update_user,
                    {"ba_user_id": ba_user_id, "user_id": user_id},
                )
                logger.info(f"  Linked user {user_id} to ba_user {ba_user_id}")
            else:
                logger.info(f"  [DRY RUN] Would link user {user_id} to ba_user {ba_user_id}")

            migrated_count += 1

        if not dry_run:
            session.commit()
            logger.info(f"Migration complete. Migrated {migrated_count} users.")
        else:
            logger.info(f"[DRY RUN] Would migrate {migrated_count} users.")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Migrate existing users to Better Auth tables")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Better Auth User Migration")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("Running in DRY RUN mode - no changes will be made")

    migrate_users(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
