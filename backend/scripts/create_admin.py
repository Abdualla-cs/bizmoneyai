import argparse
import sys
from pathlib import Path

from sqlalchemy.exc import OperationalError

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.admin import Admin


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create an admin account.")
    parser.add_argument("--name", required=True, help="Admin display name")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--password", required=True, help="Admin password")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db = SessionLocal()
    try:
        existing = db.query(Admin).filter(Admin.email == args.email).first()
        if existing:
            print(f"Admin with email {args.email} already exists.")
            return 1

        admin = Admin(
            name=args.name,
            email=args.email,
            password_hash=get_password_hash(args.password),
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        print(f"Admin created: id={admin.admin_id} email={admin.email}")
        return 0
    except OperationalError as exc:
        print("Database connection failed. Check DATABASE_URL in backend/.env.")
        print(str(exc))
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
