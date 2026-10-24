"""`krama users ...`: seeded accounts (#94; there is no public sign-up in the MVP).

uv run krama users seed --claim      # demo@krama.dev (KRAMA_DEMO_PASSWORD), and give it the older rows
uv run krama users add someone@example.com --name "Someone"   # asks for the password twice
uv run krama users list
"""

import argparse
import asyncio
import getpass

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.accounts import PasswordRuleError, create_user, hash_password, normalize_email
from app.config import get_settings
from app.db import TaskRow, UserRow, WorkflowRow, create_engine, create_sessionmaker

DEMO_EMAIL = "demo@krama.dev"


def add_parser(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    users = commands.add_parser("users", help="seeded sign-in accounts", description=__doc__)
    users.add_argument("action", choices=["seed", "add", "list"])
    users.add_argument("email", nargs="?", help="for add")
    users.add_argument("--name", help="display name (add)")
    users.add_argument(
        "--claim",
        action="store_true",
        help="seed: give tasks and workflows without an owner to the demo account",
    )


def users_command(args: argparse.Namespace) -> int:
    try:
        return asyncio.run(_run(args))
    except PasswordRuleError as e:
        print(f"Not created: {e}.")
        return 1


async def _run(args: argparse.Namespace) -> int:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    sessions = create_sessionmaker(engine)
    try:
        async with sessions.begin() as s:
            if args.action == "list":
                for user in await s.scalars(select(UserRow).order_by(UserRow.created_at)):
                    print(f"{user.email}  {user.display_name or ''}")
                return 0
            if args.action == "add":
                if not args.email:
                    print("Name the email: `krama users add someone@example.com`.")
                    return 2
                password = getpass.getpass("Password (15+ characters): ")
                if getpass.getpass("Again: ") != password:
                    print("The passwords differ; nothing was created.")
                    return 1
                if await _exists(s, args.email):
                    print(f"{normalize_email(args.email)} already exists.")
                    return 1
                await create_user(s, args.email, password, args.name)
                print(f"Created {normalize_email(args.email)}.")
                return 0
            # seed
            password = settings.krama_demo_password.get_secret_value()
            if not password:
                print("Set KRAMA_DEMO_PASSWORD (15+ characters) in the repo-root .env first.")
                return 1
            demo = await s.scalar(select(UserRow).where(UserRow.email == DEMO_EMAIL))
            if demo is None:
                demo = await create_user(s, DEMO_EMAIL, password, "Demo")
                print(f"Created {DEMO_EMAIL}.")
            else:
                demo.password_hash = hash_password(password)
                print(f"{DEMO_EMAIL} exists; its password now matches KRAMA_DEMO_PASSWORD.")
            if args.claim:
                tasks = await s.execute(
                    update(TaskRow).where(TaskRow.user_id.is_(None)).values(user_id=demo.id)
                )
                flows = await s.execute(
                    update(WorkflowRow).where(WorkflowRow.user_id.is_(None)).values(user_id=demo.id)
                )
                claimed = f"{tasks.rowcount} task(s) and {flows.rowcount} workflow(s)"  # type: ignore[attr-defined]
                print(f"Gave {claimed} without an owner to {DEMO_EMAIL}.")
            return 0
    finally:
        await engine.dispose()


async def _exists(s: AsyncSession, email: str) -> bool:
    count = await s.scalar(
        select(func.count()).select_from(UserRow).where(UserRow.email == normalize_email(email))
    )
    return bool(count)
