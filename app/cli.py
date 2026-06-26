"""
CLI — Command-line tools for admin operations.

Usage:
    uv run python -m app.cli create-admin --email admin@example.com --password yourpassword

This creates the FIRST admin account. After that, admins create other admins via the API.
"""

import argparse
import asyncio

from sqlalchemy import select

from app.auth import hash_password
from app.database import AsyncSessionLocal
from app.models import RoleEnum, User, UserRole


async def create_admin(email: str, password: str):
    """Create an admin user directly in the database."""
    async with AsyncSessionLocal() as db:
        # Check if exists
        result = await db.execute(select(User).where(User.email == email))
        if result.scalar_one_or_none():
            print(f"❌ User with email {email} already exists")
            return

        # Create user
        user = User(email=email, hashed_password=hash_password(password))
        db.add(user)
        await db.flush()

        # Add admin role
        role = UserRole(user_id=user.id, role=RoleEnum.admin)
        db.add(role)
        await db.commit()

        print(f"✅ Admin created: {email}")


def main():
    parser = argparse.ArgumentParser(description="Athletic Mindset CLI")
    subparsers = parser.add_subparsers(dest="command")

    # create-admin command
    admin_parser = subparsers.add_parser("create-admin")
    admin_parser.add_argument("--email", required=True)
    admin_parser.add_argument("--password", required=True)

    args = parser.parse_args()

    if args.command == "create-admin":
        asyncio.run(create_admin(args.email, args.password))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
