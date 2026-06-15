from __future__ import annotations

import argparse
import getpass
import secrets
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from web_admin.utils.auth import create_or_update_admin, ensure_admin_schema


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or update a Web Admin account.")
    parser.add_argument("--username", default="admin", help="Admin username. Default: admin")
    parser.add_argument("--password", help="Admin password. Omit to enter interactively.")
    parser.add_argument("--generate", action="store_true", help="Generate a random password.")
    args = parser.parse_args()

    password = args.password
    if args.generate:
        password = secrets.token_urlsafe(18)
    elif not password:
        password = getpass.getpass("Admin password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match.", file=sys.stderr)
            return 1

    if not password or len(password) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        return 1

    ensure_admin_schema()
    create_or_update_admin(args.username, password, update_existing=True)
    print(f"Admin user '{args.username}' is ready.")
    if args.generate:
        print(f"Generated password: {password}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
