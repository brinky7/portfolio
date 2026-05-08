import aiosqlite
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Any, Dict, List


class Database:
    """SQLite database module for trading scanner logging and history."""

    def __init__(self, db_path: str = "scanner.db"):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.connection: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        """Open database connection."""
        self.connection = await aiosqlite.connect(self.db_path)
        self.connection.row_factory = aiosqlite.Row

    async def disconnect(self) -> None:
        """Close database connection."""
        if self.connection:
            await self.connection.close()

    async def initialize_schema(self) -> None:
        """Load and execute SQL schema from schema.sql."""
        if not self.connection:
            raise RuntimeError("Database not connected. Call connect() first.")

        schema_path = Path(__file__).parent.parent / "storage" / "schema.sql"

        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")

        with open(schema_path, "r") as f:
            schema_sql = f.read()

        # Split by semicolon and execute each statement
        statements = schema_sql.split(";")
        for statement in statements:
            statement = statement.strip()
            if statement:
                await self.connection.execute(statement)

        await self.connection.commit()

    async def log_debug(
        self,
        message: str,
        agent: str = "scanner",
        signal_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log debug message.

        Args:
            message: Log message
            agent: Agent name
            signal_id: Optional signal ID
            data: Optional additional data dict
        """
        await self._log("DEBUG", message, agent, signal_id, data)

    async def log_info(
        self,
        message: str,
        agent: str = "scanner",
        signal_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log info message.

        Args:
            message: Log message
            agent: Agent name
            signal_id: Optional signal ID
            data: Optional additional data dict
        """
        await self._log("INFO", message, agent, signal_id, data)

    async def log_warning(
        self,
        message: str,
        agent: str = "scanner",
        signal_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log warning message.

        Args:
            message: Log message
            agent: Agent name
            signal_id: Optional signal ID
            data: Optional additional data dict
        """
        await self._log("WARNING", message, agent, signal_id, data)

    async def log_error(
        self,
        message: str,
        agent: str = "scanner",
        signal_id: Optional[str] = None,
        error: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log error message.

        Args:
            message: Log message
            agent: Agent name
            signal_id: Optional signal ID
            error: Optional error traceback/details
            data: Optional additional data dict
        """
        await self._log("ERROR", message, agent, signal_id, data, error)

    async def _log(
        self,
        level: str,
        message: str,
        agent: str,
        signal_id: Optional[str],
        data: Optional[Dict[str, Any]],
        error: Optional[str] = None,
    ) -> None:
        """Internal method to log messages."""
        if not self.connection:
            raise RuntimeError("Database not connected. Call connect() first.")

        data_json = json.dumps(data) if data else None

        await self.connection.execute(
            """
            INSERT INTO logs (agent, level, signal_id, message, data, error)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (agent, level, signal_id, message, data_json, error),
        )
        await self.connection.commit()

    async def save_signal_history(self, signal: Dict[str, Any]) -> None:
        """
        Save signal to signals_history table.

        Args:
            signal: Signal dict with keys matching table columns
        """
        if not self.connection:
            raise RuntimeError("Database not connected. Call connect() first.")

        # Extract signal fields, use None for missing ones
        fields = [
            "signal_id",
            "symbol",
            "direction",
            "confidence",
            "entry_price",
            "stop_loss",
            "take_profit",
            "position_size_usdt",
            "position_size_pct",
            "kelly_fraction",
            "news_bias_score",
            "published_at",
            "executed",
            "execution_price",
            "execution_status",
            "closed_at",
            "pnl_usdt",
            "close_reason",
        ]

        values = tuple(signal.get(field) for field in fields)

        placeholders = ", ".join(["?"] * len(fields))
        field_names = ", ".join(fields)

        await self.connection.execute(
            f"""
            INSERT OR REPLACE INTO signals_history ({field_names})
            VALUES ({placeholders})
            """,
            values,
        )
        await self.connection.commit()

    async def record_retry_attempt(
        self,
        signal_id: str,
        attempt: int,
        error: str,
        backoff_delay_seconds: int,
    ) -> None:
        """
        Record retry attempt for a signal.

        Args:
            signal_id: Signal ID
            attempt: Attempt number
            error: Error message
            backoff_delay_seconds: Backoff delay in seconds
        """
        if not self.connection:
            raise RuntimeError("Database not connected. Call connect() first.")

        await self.connection.execute(
            """
            INSERT INTO retry_attempts (signal_id, attempt, error, backoff_delay_seconds)
            VALUES (?, ?, ?, ?)
            """,
            (signal_id, attempt, error, backoff_delay_seconds),
        )
        await self.connection.commit()

    async def get_logs_by_signal_id(
        self, signal_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get logs for a specific signal.

        Args:
            signal_id: Signal ID to query
            limit: Maximum number of logs to return

        Returns:
            List of log entries as dicts
        """
        if not self.connection:
            raise RuntimeError("Database not connected. Call connect() first.")

        cursor = await self.connection.execute(
            """
            SELECT id, timestamp, agent, level, signal_id, message, data, error
            FROM logs
            WHERE signal_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (signal_id, limit),
        )
        rows = await cursor.fetchall()

        result = []
        for row in rows:
            result.append({
                "id": row["id"],
                "timestamp": row["timestamp"],
                "agent": row["agent"],
                "level": row["level"],
                "signal_id": row["signal_id"],
                "message": row["message"],
                "data": json.loads(row["data"]) if row["data"] else None,
                "error": row["error"],
            })

        return result
