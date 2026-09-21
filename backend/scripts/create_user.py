"""Create a user account directly in the database, bypassing ALLOW_REGISTRATION.

Usage (from the backend directory):
    python -m scripts.create_user --username X --email Y [--admin]
"""

import argparse
import asyncio
import getpass
import sys

from pydantic import ValidationError

from app.core.database import AsyncSessionLocal, engine
from app.core.security import hash_password
from app.repositories.user_repo import UserRepository
from app.schemas.user import UserCreate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a BIG user account.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--admin", action="store_true", help="grant admin rights")
    return parser.parse_args()


def prompt_password() -> str:
    password = getpass.getpass("Password: ")
    if getpass.getpass("Confirm password: ") != password:
        sys.exit("Passwords do not match.")
    return password


async def create_user(username: str, email: str, password: str, is_admin: bool) -> int:
    async with AsyncSessionLocal() as session:
        repo = UserRepository(session)

        if await repo.get_by_username(username) is not None:
            print(f"Username '{username}' already exists.", file=sys.stderr)
            return 1
        if await repo.get_by_email(email) is not None:
            print(f"Email '{email}' already exists.", file=sys.stderr)
            return 1

        user = await repo.create(
            username=username,
            password_hash=hash_password(password),
            email=email,
        )
        user.is_admin = is_admin
        await session.commit()

        print(f"Created {'admin ' if is_admin else ''}user '{user.username}' ({user.id}).")
        return 0


async def main() -> int:
    args = parse_args()
    password = prompt_password()

    try:
        # Same validation as the registration endpoint.
        payload = UserCreate(username=args.username, password=password, email=args.email)
    except ValidationError as exc:
        # Location and message only — never input_value, which would echo the password.
        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"])
            print(f"{location}: {error['msg']}", file=sys.stderr)
        return 1

    try:
        return await create_user(
            payload.username, str(payload.email), payload.password, args.admin
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
