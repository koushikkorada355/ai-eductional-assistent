"""Seed the default admin account on backend startup.

Hardcoded prototype credentials (env-overridable via ADMIN_EMAIL /
ADMIN_PASSWORD / ADMIN_NAME in app/config.py):
    email:    admin@gmail.com
    password: 12345
    name:     admin

Idempotent: creates the user if missing, promotes to admin + refreshes the
name if it already exists. Safe to run on every boot.
"""
from loguru import logger
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import get_password_hash
from app.db.models.user import User


def ensure_admin_seed(db: Session) -> User | None:
    email = (settings.ADMIN_EMAIL or "").strip().lower()
    password = settings.ADMIN_PASSWORD or ""
    name = (settings.ADMIN_NAME or "admin").strip() or "admin"
    if not email or not password:
        logger.warning("[admin.seed] ADMIN_EMAIL/ADMIN_PASSWORD not set, skipping admin seed.")
        return None

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(
            email=email,
            hashed_password=get_password_hash(password),
            name=name,
            role="admin",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.success(f"[admin.seed] admin account created: {email}")
        return user

    updated = False
    if (user.role or "user") != "admin":
        user.role = "admin"
        updated = True
    if not user.name:
        user.name = name
        updated = True
    if not user.is_active:
        user.is_active = True
        updated = True
    if updated:
        db.commit()
        db.refresh(user)
        logger.success(f"[admin.seed] existing account promoted to admin: {email}")
    else:
        logger.info(f"[admin.seed] admin account already present: {email}")
    return user
