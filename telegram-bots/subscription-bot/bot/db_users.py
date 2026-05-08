import sqlite3
import time
from pathlib import Path

_DB = Path(__file__).parent.parent / "users.db"


def _conn():
    return sqlite3.connect(_DB)


def init_db():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id       INTEGER PRIMARY KEY,
                username      TEXT,
                first_name    TEXT,
                tier          TEXT    DEFAULT 'trial',
                joined_at     INTEGER,
                tier_updated  INTEGER
            )
        """)


def register_user(user_id: int, username: str | None, first_name: str | None) -> None:
    now = int(time.time())
    with _conn() as c:
        c.execute("""
            INSERT INTO users (user_id, username, first_name, tier, joined_at, tier_updated)
            VALUES (?, ?, ?, 'trial', ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username   = excluded.username,
                first_name = excluded.first_name
        """, (user_id, username, first_name, now, now))


def update_user_tier(user_id: int, tier: str) -> None:
    now = int(time.time())
    with _conn() as c:
        c.execute("""
            INSERT INTO users (user_id, username, first_name, tier, joined_at, tier_updated)
            VALUES (?, NULL, NULL, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                tier         = excluded.tier,
                tier_updated = excluded.tier_updated
        """, (user_id, tier, now, now))


def get_all_users() -> list[dict]:
    with _conn() as c:
        c.row_factory = sqlite3.Row
        rows = c.execute("""
            SELECT user_id, username, first_name, tier, joined_at, tier_updated
            FROM users ORDER BY joined_at DESC
        """).fetchall()
    return [dict(r) for r in rows]


def get_user_count() -> dict:
    with _conn() as c:
        total = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        by_tier = c.execute(
            "SELECT tier, COUNT(*) FROM users GROUP BY tier"
        ).fetchall()
    return {"total": total, "by_tier": dict(by_tier)}


init_db()
