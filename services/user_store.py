"""
User Store and Authentication Service for Namma Payana.
Persists registered users and credentials in SQLite with secure password hashing.
"""
import os
import sqlite3
import uuid
import secrets
import datetime
import re
from typing import Dict, Any, Optional
from werkzeug.security import generate_password_hash, check_password_hash

import config
from services.validation import validate_password_strength
from services.db import db_connection

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_\-\.]{3,30}$")

_GENERIC_REGISTRATION_ERROR = "Registration failed. Please check your details and try again."


class UserStore:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or config.DATABASE_PATH
        self.init_db()

    def init_db(self, app=None) -> None:
        """Create tables and optionally seed demo user.

        Demo user is only seeded when FLASK_ENV=development AND ENABLE_DEMO_USER=1.
        """
        with db_connection(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    full_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    persona TEXT DEFAULT 'heritage',
                    home_city TEXT DEFAULT 'Bengaluru',
                    created_at TEXT NOT NULL,
                    last_login_at TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
            """)
            existing = conn.execute("SELECT version FROM schema_version WHERE version = 1").fetchone()
            if not existing:
                import datetime as _dt
                conn.execute("INSERT INTO schema_version (version, applied_at) VALUES (1, ?)",
                             (_dt.datetime.now(_dt.timezone.utc).isoformat(),))
            conn.commit()

        flask_env = os.environ.get("FLASK_ENV", "development").lower()
        enable_demo = os.environ.get("ENABLE_DEMO_USER", "0")

        if flask_env == "production":
            return  # Never seed in production, regardless of ENABLE_DEMO_USER

        if flask_env == "development" and enable_demo == "1":
            demo_email = "demo@nammapayana.in"
            try:
                existing = self.get_user_by_email(demo_email)
                if not existing:
                    demo_password = os.environ.get("DEMO_USER_PASSWORD", "demo123")
                    self._create_user_raw(
                        username="demo",
                        email=demo_email,
                        full_name="Praveen Kumar",
                        password=demo_password,
                        persona="Heritage Explorer",
                        home_city="Bengaluru",
                    )
                    print(f"[DEV] Demo user password: {demo_password}", flush=True)
            except Exception:
                pass

    def _create_user_raw(
        self,
        username: str,
        email: str,
        full_name: str,
        password: str,
        persona: str = "Heritage Explorer",
        home_city: str = "Bengaluru",
    ) -> Dict[str, Any]:
        """Low-level user creation that bypasses strength validation (used for seeding)."""
        user_id = str(uuid.uuid4())
        created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        pwd_hash = generate_password_hash(password)

        with db_connection(self.db_path) as conn:
            conn.execute("""
                INSERT INTO users (id, username, email, full_name, password_hash, persona, home_city, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, username, email, full_name, pwd_hash, persona, home_city, created_at))
            conn.commit()
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

        return self._row_to_user(row)

    def _row_to_user(self, row) -> Dict[str, Any]:
        """Convert a DB row to a user dict, never including password_hash."""
        return {
            "id": row["id"],
            "username": row["username"],
            "email": row["email"],
            "full_name": row["full_name"],
            "persona": row["persona"],
            "home_city": row["home_city"],
            "created_at": row["created_at"],
            "last_login_at": row["last_login_at"],
        }

    def create_user(
        self,
        username: str,
        email: str,
        full_name: str,
        password: str,
        persona: str = "Heritage Explorer",
        home_city: str = "Bengaluru"
    ) -> Dict[str, Any]:
        """Registers a new user and returns user info without password hash."""
        username_clean = (username or "").strip().lower()
        email_clean = (email or "").strip().lower()
        full_name_clean = (full_name or "").strip()

        if not username_clean or not USERNAME_REGEX.match(username_clean):
            raise ValueError("Username must be between 3 and 30 alphanumeric characters.")

        if not email_clean or not EMAIL_REGEX.match(email_clean):
            raise ValueError("Please provide a valid email address.")

        if not full_name_clean or len(full_name_clean) < 2:
            raise ValueError("Please provide your full name.")

        # Password strength validation (raises ValueError on failure)
        validate_password_strength(password)

        user_id = str(uuid.uuid4())
        created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        pwd_hash = generate_password_hash(password)

        with db_connection(self.db_path) as conn:
            # Check unique constraints — raise generic error to prevent enumeration
            row = conn.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username_clean, email_clean)).fetchone()
            if row:
                raise ValueError(_GENERIC_REGISTRATION_ERROR)

            conn.execute("""
                INSERT INTO users (id, username, email, full_name, password_hash, persona, home_city, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, username_clean, email_clean, full_name_clean, pwd_hash, persona or "Heritage Explorer", home_city or "Bengaluru", created_at))
            conn.commit()
            new_row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

        return self._row_to_user(new_row)

    def authenticate(self, identifier: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticates user using email or username and password."""
        ident_clean = (identifier or "").strip().lower()
        if not ident_clean or not password:
            return None

        with db_connection(self.db_path) as conn:
            row = conn.execute("""
                SELECT * FROM users WHERE email = ? OR username = ?
            """, (ident_clean, ident_clean)).fetchone()

            if not row:
                return None

            if not check_password_hash(row["password_hash"], password):
                return None

            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (now, row["id"]))
            conn.commit()

            # Re-fetch to get the updated last_login_at
            updated_row = conn.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()
            return self._row_to_user(updated_row)

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        with db_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if not row:
                return None
            return self._row_to_user(row)

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        with db_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", ((email or "").strip().lower(),)).fetchone()
            if not row:
                return None
            return self._row_to_user(row)

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        with db_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", ((username or "").strip().lower(),)).fetchone()
            if not row:
                return None
            return self._row_to_user(row)

    def get_user_by_identifier(self, identifier: str) -> Optional[Dict[str, Any]]:
        clean = (identifier or "").strip().lower()
        if not clean:
            return None
        with db_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ? OR username = ?", (clean, clean)).fetchone()
            if not row:
                return None
            return self._row_to_user(row)

    def update_user(self, user_id: str, updates: dict) -> Optional[Dict[str, Any]]:
        allowed = {"full_name", "home_city", "persona"}
        safe = {k: v for k, v in updates.items() if k in allowed}
        if not safe:
            return None
        set_clause = ", ".join(f"{k} = ?" for k in safe)
        values = list(safe.values()) + [user_id]
        with db_connection(self.db_path) as conn:
            conn.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
            conn.commit()
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._row_to_user(row) if row else None

    def delete_user(self, user_id: str) -> bool:
        with db_connection(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
        return cursor.rowcount > 0


user_store = UserStore()
