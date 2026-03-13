"""
User management CLI commands (add-user).
"""

import getpass

from src.cli import get_db_session
from src.web.auth import create_user


def register_user_commands(subparsers):
    """Register user management subcommands."""
    p = subparsers.add_parser("add-user", help="Create a new user account.")
    p.add_argument("--username", required=True, help="Login username.")
    p.add_argument("--display-name", type=str, default=None, help="Display name shown in the UI.")
    p.add_argument("--role", type=str, default="teacher", choices=["teacher", "admin"], help="User role (default: teacher).")


def handle_add_user(config, args):
    """Create a new user account with a prompted password."""
    engine, session = get_db_session(config)
    try:
        password = getpass.getpass(f"Password for '{args.username}': ")
        if len(password) < 8:
            print("[FAIL] Password must be at least 8 characters.")
            return

        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("[FAIL] Passwords do not match.")
            return

        user = create_user(
            session,
            username=args.username,
            password=password,
            display_name=args.display_name,
            role=args.role,
        )
        if user:
            print(f"[OK] User '{user.username}' created (role: {user.role}).")
        else:
            print(f"[FAIL] Username '{args.username}' already exists.")
    finally:
        session.close()
