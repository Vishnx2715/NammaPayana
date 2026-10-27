"""
SQLite Trip Persistence Store for Namma Payana.
Guest-friendly storage using UUID4 trip IDs and SHA-256 hashed client edit tokens.
Data survives server restarts.
"""
import sqlite3
import hashlib
import hmac
import json
import uuid
import datetime
import secrets
from decimal import Decimal
from typing import Dict, Any, Optional, List
import config
from services.db import db_connection

def _json_serial(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return str(obj)

def safe_json_dumps(obj: Any) -> str:
    return json.dumps(obj, default=_json_serial)

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

class TripStore:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or config.DATABASE_PATH
        self.init_db()

    def init_db(self) -> None:
        with db_connection(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trips (
                    id TEXT PRIMARY KEY,
                    edit_token_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    dna_json TEXT NOT NULL,
                    itinerary_json TEXT NOT NULL,
                    cost_json TEXT NOT NULL,
                    dataset_version TEXT NOT NULL,
                    uncertainties_json TEXT NOT NULL,
                    user_id TEXT
                )
            """)
            conn.commit()
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trips_user_id ON trips(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trips_created_at ON trips(created_at DESC)")
            conn.commit()
            # Migration: add user_id column to existing databases
            cols = {row[1] for row in conn.execute("PRAGMA table_info(trips)")}
            if "user_id" not in cols:
                conn.execute("ALTER TABLE trips ADD COLUMN user_id TEXT")
                conn.commit()
            if "share_token" not in cols:
                conn.execute("ALTER TABLE trips ADD COLUMN share_token TEXT")
                conn.commit()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
            """)
            # Record initial schema version if not already set
            existing = conn.execute("SELECT version FROM schema_version WHERE version = 1").fetchone()
            if not existing:
                import datetime as _dt
                conn.execute("INSERT INTO schema_version (version, applied_at) VALUES (1, ?)",
                             (_dt.datetime.now(_dt.timezone.utc).isoformat(),))
            conn.commit()

    def save_trip(
        self,
        dna: Dict[str, Any],
        itinerary: Dict[str, Any],
        cost_summary: Dict[str, Any],
        trip_id: Optional[str] = None,
        edit_token: Optional[str] = None,
        uncertainties: Optional[List[str]] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        uncertainties_list = uncertainties or []

        with db_connection(self.db_path) as conn:
            if trip_id:
                # Update existing
                row = conn.execute("SELECT edit_token_hash FROM trips WHERE id = ?", (trip_id,)).fetchone()
                if not row:
                    raise KeyError(f"Trip with ID {trip_id} does not exist.")

                # Verify token
                if not edit_token or not hmac.compare_digest(hash_token(edit_token), row["edit_token_hash"]):
                    raise PermissionError("Invalid or missing edit token for trip update.")

                conn.execute("""
                    UPDATE trips
                    SET updated_at = ?, dna_json = ?, itinerary_json = ?, cost_json = ?, uncertainties_json = ?,
                        user_id = CASE WHEN ? IS NOT NULL THEN ? ELSE user_id END
                    WHERE id = ?
                """, (
                    now,
                    safe_json_dumps(dna),
                    safe_json_dumps(itinerary),
                    safe_json_dumps(cost_summary),
                    safe_json_dumps(uncertainties_list),
                    user_id,
                    user_id,
                    trip_id
                ))
                conn.commit()
                return {"id": trip_id, "edit_token": edit_token, "updated_at": now}
            else:
                # Create new trip
                new_id = str(uuid.uuid4())
                raw_token = str(uuid.uuid4())
                tok_hash = hash_token(raw_token)
                share_token = secrets.token_urlsafe(12)

                conn.execute("""
                    INSERT INTO trips (
                        id, edit_token_hash, created_at, updated_at,
                        dna_json, itinerary_json, cost_json, dataset_version, uncertainties_json,
                        user_id, share_token
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    new_id,
                    tok_hash,
                    now,
                    now,
                    safe_json_dumps(dna),
                    safe_json_dumps(itinerary),
                    safe_json_dumps(cost_summary),
                    "1.0",
                    safe_json_dumps(uncertainties_list),
                    user_id,
                    share_token
                ))
                conn.commit()
                return {"id": new_id, "edit_token": raw_token, "share_token": share_token, "created_at": now}

    def get_trip(self, trip_id: str) -> Optional[Dict[str, Any]]:
        with db_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM trips WHERE id = ?", (trip_id,)).fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "dna": json.loads(row["dna_json"]),
                "itinerary": json.loads(row["itinerary_json"]),
                "cost_summary": json.loads(row["cost_json"]),
                "dataset_version": row["dataset_version"],
                "uncertainties": json.loads(row["uncertainties_json"]),
                "user_id": row["user_id"],
                "share_token": row["share_token"],
            }

    def list_trips(self, limit: int = 50, user_id: Optional[str] = None, edit_tokens: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        if user_id is None:
            return []

        with db_connection(self.db_path) as conn:
            # Fetch trips owned by the user
            owned_rows = conn.execute(
                "SELECT id, created_at, updated_at, dna_json, cost_json FROM trips "
                "WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit)
            ).fetchall()

            results = [
                {
                    "id": row["id"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "dna": json.loads(row["dna_json"]),
                    "cost_summary": json.loads(row["cost_json"])
                }
                for row in owned_rows
            ]

            # Also include guest trips the caller can prove ownership of via edit_tokens
            if edit_tokens:
                hashed_set = {hash_token(t) for t in edit_tokens}
                placeholders = ",".join("?" * len(hashed_set))
                guest_rows = conn.execute(
                    f"SELECT id, created_at, updated_at, dna_json, cost_json FROM trips "
                    f"WHERE user_id IS NULL AND edit_token_hash IN ({placeholders}) "
                    f"ORDER BY created_at DESC LIMIT ?",
                    (*hashed_set, limit)
                ).fetchall()
                for row in guest_rows:
                    results.append({
                        "id": row["id"],
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                        "dna": json.loads(row["dna_json"]),
                        "cost_summary": json.loads(row["cost_json"])
                    })

            # Sort merged results by created_at DESC and cap at limit
            results.sort(key=lambda r: r["created_at"], reverse=True)
            return results[:limit]

    def duplicate_trip(self, trip_id: str) -> Dict[str, Any]:
        original = self.get_trip(trip_id)
        if not original:
            raise KeyError(f"Trip with ID {trip_id} not found.")

        return self.save_trip(
            dna=original["dna"],
            itinerary=original["itinerary"],
            cost_summary=original["cost_summary"],
            uncertainties=original.get("uncertainties", [])
        )

    def delete_trip(self, trip_id: str, edit_token: str = "", user_id: Optional[str] = None) -> bool:
        with db_connection(self.db_path) as conn:
            row = conn.execute("SELECT edit_token_hash, user_id FROM trips WHERE id = ?", (trip_id,)).fetchone()
            if not row:
                return False

            # Owner can always delete
            if user_id is not None and row["user_id"] == user_id:
                conn.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
                conn.commit()
                return True

            # Edit token bearer can delete
            if edit_token and hmac.compare_digest(hash_token(edit_token), row["edit_token_hash"]):
                conn.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
                conn.commit()
                return True

            raise PermissionError("Forbidden.")

    def claim_trips(self, edit_tokens: List[str], user_id: str) -> int:
        """Claim guest trips (user_id IS NULL) by stamping user_id onto them via edit token verification."""
        total = 0
        with db_connection(self.db_path) as conn:
            for token in edit_tokens:
                tok_hash = hash_token(token)
                cursor = conn.execute(
                    "UPDATE trips SET user_id = ? WHERE edit_token_hash = ? AND user_id IS NULL",
                    (user_id, tok_hash)
                )
                total += cursor.rowcount
            conn.commit()
        return total

    def get_trip_by_share_token(self, share_token: str) -> Optional[Dict[str, Any]]:
        """Returns a trip dict (same shape as get_trip) for the given share_token, or None."""
        if not share_token:
            return None
        with db_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM trips WHERE share_token = ?", (share_token,)).fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "dna": json.loads(row["dna_json"]),
                "itinerary": json.loads(row["itinerary_json"]),
                "cost_summary": json.loads(row["cost_json"]),
                "dataset_version": row["dataset_version"],
                "uncertainties": json.loads(row["uncertainties_json"]),
                "user_id": row["user_id"],
                "share_token": row["share_token"],
            }

# Global store singleton
trip_store = TripStore()
