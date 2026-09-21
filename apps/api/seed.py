"""Seed script: training catalogue + an optional demo account with a demo player.

    python -m seed                    # training catalogue (idempotent)
    python -m seed --with-demo-user  # plus a labelled DEMO account
"""

from __future__ import annotations

import argparse

from app.core.db import SessionLocal, init_db
from app.seed_data import ensure_demo_account, seed_catalogue


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed FOOTBALL OS reference data")
    parser.add_argument("--with-demo-user", action="store_true", help="create a labelled DEMO account + player")
    parser.add_argument("--email", default="demo@footballos.local")
    parser.add_argument("--password", default="demo-password-123")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        created = seed_catalogue(db)
        print(f"training catalogue: {created} rows synchronised")
        if args.with_demo_user:
            player = ensure_demo_account(db, email=args.email, password=args.password)
            print(f"DEMO account ready: {args.email} / {args.password} (player {player.name}, OVR {player.overall})")
        else:
            print("register a real account at POST /api/v1/auth/register")
    finally:
        db.close()


if __name__ == "__main__":
    main()
