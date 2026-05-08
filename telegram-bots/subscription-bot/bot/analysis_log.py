import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "analysis.db"

# Hours to wait for price to reach entry_price
ENTRY_TIMEOUT = {"short": 24, "mid": 72}
# Hours to wait for TP/SL after entry was hit
TRADE_TIMEOUT = {"short": 48, "mid": 336}  # 14 days for mid


def _conn():
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS analysis_log (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL,
                symbol        TEXT NOT NULL,
                timeframe     TEXT NOT NULL,
                kind          TEXT NOT NULL,
                direction     TEXT NOT NULL,
                confidence    REAL NOT NULL,
                entry_price   REAL NOT NULL,
                sl            REAL NOT NULL,
                tp            REAL NOT NULL,
                created_at    TEXT NOT NULL,
                entry_hit     INTEGER DEFAULT 0,
                entry_hit_at  TEXT,
                outcome       TEXT,
                outcome_at    TEXT,
                outcome_price REAL
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_al_outcome ON analysis_log(outcome)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_al_kind   ON analysis_log(kind)")


def _log_tf(con, user_id: int, symbol: str, label: str, kind: str, tf_data: dict) -> None:
    direction = tf_data.get("effective_direction") or tf_data.get("direction")
    entry = tf_data.get("entry")
    sl = tf_data.get("sl")
    tp = tf_data.get("tp")
    if not direction or direction == "neutral" or not entry or not sl or not tp:
        return
    con.execute("""
        INSERT INTO analysis_log
            (user_id, symbol, timeframe, kind, direction, confidence,
             entry_price, sl, tp, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id, symbol, label, kind, direction,
        tf_data.get("confidence", 0.0),
        entry, sl, tp,
        datetime.now(timezone.utc).isoformat(),
    ))


def log_analysis(user_id: int, symbol: str, result: dict) -> None:
    init_db()
    short = result.get("short_term", {}).get("primary", {})
    mid = result.get("mid_term", {}).get("primary", {})
    mid_label = result.get("mid_term", {}).get("primary_label", "1D")
    with _conn() as con:
        _log_tf(con, user_id, symbol, "1H", "short", short)
        _log_tf(con, user_id, symbol, mid_label, "mid", mid)


def get_pending() -> list:
    init_db()
    with _conn() as con:
        return con.execute(
            "SELECT * FROM analysis_log WHERE outcome IS NULL"
        ).fetchall()


def mark_entry_hit(row_id: int, price: float) -> None:
    with _conn() as con:
        con.execute("""
            UPDATE analysis_log SET entry_hit=1, entry_hit_at=? WHERE id=?
        """, (datetime.now(timezone.utc).isoformat(), row_id))


def mark_outcome(row_id: int, outcome: str, price: float) -> None:
    with _conn() as con:
        con.execute("""
            UPDATE analysis_log
            SET outcome=?, outcome_at=?, outcome_price=?
            WHERE id=?
        """, (outcome, datetime.now(timezone.utc).isoformat(), price, row_id))


def check_outcomes(fetch_price_fn) -> None:
    """Call once daily. Updates entry_hit and outcomes for all pending rows."""
    init_db()
    rows = get_pending()
    now = datetime.now(timezone.utc)

    for row in rows:
        try:
            price = fetch_price_fn(row["symbol"])
        except Exception:
            continue

        kind = row["kind"]
        created = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)

        if not row["entry_hit"]:
            # Check if price reached entry level
            entry_reached = (
                price <= row["entry_price"] if row["direction"] == "long"
                else price >= row["entry_price"]
            )
            if entry_reached:
                mark_entry_hit(row["id"], price)
            elif (now - created).total_seconds() > ENTRY_TIMEOUT[kind] * 3600:
                mark_outcome(row["id"], "no_entry", price)
        else:
            entry_hit_at = datetime.fromisoformat(row["entry_hit_at"].replace("Z", "+00:00"))
            if entry_hit_at.tzinfo is None:
                entry_hit_at = entry_hit_at.replace(tzinfo=timezone.utc)

            if row["direction"] == "long":
                win = price >= row["tp"]
                loss = price <= row["sl"]
            else:
                win = price <= row["tp"]
                loss = price >= row["sl"]

            if win:
                mark_outcome(row["id"], "win", price)
            elif loss:
                mark_outcome(row["id"], "loss", price)
            elif (now - entry_hit_at).total_seconds() > TRADE_TIMEOUT[kind] * 3600:
                mark_outcome(row["id"], "expired", price)


def get_stats(kind: str, days: int = 7, user_id: int | None = None) -> dict | None:
    """Returns winrate stats for 'short' or 'mid' kind over last N days.
    Pass days=0 for all-time. Pass user_id to filter by a specific user."""
    init_db()
    params: list = [kind]
    query = "SELECT symbol, outcome FROM analysis_log WHERE kind=?"
    if days > 0:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        query += " AND created_at >= ?"
        params.append(since)
    if user_id is not None:
        query += " AND user_id=?"
        params.append(user_id)
    query += " AND outcome IN ('win', 'loss', 'no_entry', 'expired')"
    with _conn() as con:
        rows = con.execute(query, params).fetchall()

    if not rows:
        return None

    traded = [r for r in rows if r["outcome"] in ("win", "loss")]
    wins = sum(1 for r in traded if r["outcome"] == "win")
    no_entry = sum(1 for r in rows if r["outcome"] == "no_entry")
    expired = sum(1 for r in rows if r["outcome"] == "expired")

    by_symbol: dict[str, dict] = {}
    for r in traded:
        s = by_symbol.setdefault(r["symbol"], {"total": 0, "wins": 0})
        s["total"] += 1
        if r["outcome"] == "win":
            s["wins"] += 1

    top = sorted(by_symbol.items(), key=lambda x: x[1]["total"], reverse=True)[:5]

    return {
        "total_signals": len(rows),
        "traded": len(traded),
        "wins": wins,
        "losses": len(traded) - wins,
        "winrate": wins / len(traded) * 100 if traded else 0.0,
        "no_entry": no_entry,
        "expired": expired,
        "top_symbols": top,
    }
