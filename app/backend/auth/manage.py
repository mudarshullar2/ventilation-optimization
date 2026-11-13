"""Create or update an application user.

    python -m auth.manage <username> [--role admin|user]

Prompts for the password (hidden) and stores it hashed. Run once per user.
"""
import argparse
import getpass
import sys

from werkzeug.security import generate_password_hash

from database.db import Database


def main():
    parser = argparse.ArgumentParser(description="Create or update an app user")
    parser.add_argument("username")
    parser.add_argument("--role", default="user", choices=["user", "admin"])
    args = parser.parse_args()

    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("passwords do not match", file=sys.stderr)
        sys.exit(1)
    if len(password) < 8:
        print("password must be at least 8 characters", file=sys.stderr)
        sys.exit(1)

    db = Database()
    db.upsert_user(args.username, generate_password_hash(password), args.role)
    print(f"user '{args.username}' ({args.role}) saved")


if __name__ == "__main__":
    main()
