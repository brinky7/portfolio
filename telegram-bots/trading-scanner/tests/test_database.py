import pytest
import sys
import asyncio
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import Database

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def db():
    """Create an in-memory SQLite database for testing."""
    database = Database(":memory:")
    await database.connect()
    await database.initialize_schema()
    yield database
    await database.disconnect()


@pytest.mark.asyncio
async def test_log_debug(db):
    """Test debug logging."""
    await db.log_debug(
        message="Test debug message",
        agent="test_agent",
        signal_id="sig_001",
        data={"key": "value"}
    )

    logs = await db.get_logs_by_signal_id("sig_001")
    assert len(logs) == 1
    assert logs[0]["level"] == "DEBUG"
    assert logs[0]["message"] == "Test debug message"
    assert logs[0]["agent"] == "test_agent"
    assert logs[0]["data"] == {"key": "value"}
    assert logs[0]["error"] is None


@pytest.mark.asyncio
async def test_log_info(db):
    """Test info logging."""
    await db.log_info(
        message="Test info message",
        agent="scanner",
        signal_id="sig_002"
    )

    logs = await db.get_logs_by_signal_id("sig_002")
    assert len(logs) == 1
    assert logs[0]["level"] == "INFO"
    assert logs[0]["message"] == "Test info message"


@pytest.mark.asyncio
async def test_log_warning(db):
    """Test warning logging."""
    await db.log_warning(
        message="Test warning message",
        agent="scanner",
        signal_id="sig_003",
        data={"warning_type": "timeout"}
    )

    logs = await db.get_logs_by_signal_id("sig_003")
    assert len(logs) == 1
    assert logs[0]["level"] == "WARNING"
    assert logs[0]["data"]["warning_type"] == "timeout"


@pytest.mark.asyncio
async def test_log_error(db):
    """Test error logging."""
    await db.log_error(
        message="Test error message",
        agent="scanner",
        signal_id="sig_004",
        error="ValueError: invalid signal",
        data={"error_code": 500}
    )

    logs = await db.get_logs_by_signal_id("sig_004")
    assert len(logs) == 1
    assert logs[0]["level"] == "ERROR"
    assert logs[0]["error"] == "ValueError: invalid signal"
    assert logs[0]["data"]["error_code"] == 500


@pytest.mark.asyncio
async def test_save_signal_history(db):
    """Test saving signal history."""
    signal = {
        "signal_id": "sig_test_001",
        "symbol": "BTCUSDT",
        "direction": "long",
        "confidence": 0.85,
        "entry_price": 45000.0,
        "stop_loss": 44000.0,
        "take_profit": 47000.0,
        "position_size_usdt": 1000.0,
        "position_size_pct": 5.0,
        "kelly_fraction": 0.25,
        "news_bias_score": 0.7,
        "published_at": datetime.now().isoformat(),
        "executed": 0,
        "execution_price": None,
        "execution_status": None,
        "closed_at": None,
        "pnl_usdt": None,
        "close_reason": None
    }

    await db.save_signal_history(signal)

    # Retrieve the signal
    cursor = await db.connection.execute(
        "SELECT * FROM signals_history WHERE signal_id = ?",
        ("sig_test_001",)
    )
    row = await cursor.fetchone()

    assert row is not None
    assert row["symbol"] == "BTCUSDT"
    assert row["direction"] == "long"
    assert float(row["confidence"]) == 0.85
    assert float(row["entry_price"]) == 45000.0


@pytest.mark.asyncio
async def test_save_signal_history_partial(db):
    """Test saving signal with minimal fields."""
    signal = {
        "signal_id": "sig_minimal",
        "symbol": "ETHUSDT",
        "direction": "short",
        "confidence": 0.6
    }

    await db.save_signal_history(signal)

    cursor = await db.connection.execute(
        "SELECT * FROM signals_history WHERE signal_id = ?",
        ("sig_minimal",)
    )
    row = await cursor.fetchone()

    assert row is not None
    assert row["symbol"] == "ETHUSDT"
    assert row["direction"] == "short"
    assert float(row["confidence"]) == 0.6
    assert row["entry_price"] is None


@pytest.mark.asyncio
async def test_record_retry_attempt(db):
    """Test recording retry attempts."""
    # First save a signal
    signal = {
        "signal_id": "sig_retry_001",
        "symbol": "BTCUSDT",
        "direction": "long",
        "confidence": 0.8
    }
    await db.save_signal_history(signal)

    # Record retry attempts
    await db.record_retry_attempt(
        signal_id="sig_retry_001",
        attempt=1,
        error="Connection timeout",
        backoff_delay_seconds=5
    )

    await db.record_retry_attempt(
        signal_id="sig_retry_001",
        attempt=2,
        error="Invalid order parameters",
        backoff_delay_seconds=10
    )

    # Verify retries
    cursor = await db.connection.execute(
        "SELECT * FROM retry_attempts WHERE signal_id = ? ORDER BY attempt",
        ("sig_retry_001",)
    )
    rows = await cursor.fetchall()

    assert len(rows) == 2
    assert rows[0]["attempt"] == 1
    assert rows[0]["error"] == "Connection timeout"
    assert rows[0]["backoff_delay_seconds"] == 5
    assert rows[1]["attempt"] == 2
    assert rows[1]["error"] == "Invalid order parameters"
    assert rows[1]["backoff_delay_seconds"] == 10


@pytest.mark.asyncio
async def test_get_logs_by_signal_id_limit(db):
    """Test getting logs with limit."""
    signal_id = "sig_limit_test"

    # Create 150 logs
    for i in range(150):
        await db.log_info(
            message=f"Message {i}",
            signal_id=signal_id
        )

    # Fetch with default limit (100)
    logs = await db.get_logs_by_signal_id(signal_id)
    assert len(logs) == 100

    # Fetch with custom limit
    logs_custom = await db.get_logs_by_signal_id(signal_id, limit=50)
    assert len(logs_custom) == 50


@pytest.mark.asyncio
async def test_get_logs_by_signal_id_ordering(db):
    """Test that logs are returned in descending order."""
    signal_id = "sig_order_test"

    await db.log_info(message="Message 1", signal_id=signal_id)
    await db.log_info(message="Message 2", signal_id=signal_id)
    await db.log_info(message="Message 3", signal_id=signal_id)

    logs = await db.get_logs_by_signal_id(signal_id)

    # Check all three are present
    assert len(logs) == 3
    messages = [log["message"] for log in logs]
    assert "Message 1" in messages
    assert "Message 2" in messages
    assert "Message 3" in messages


@pytest.mark.asyncio
async def test_log_without_signal_id(db):
    """Test logging without signal_id."""
    await db.log_info(
        message="No signal ID",
        agent="test"
    )

    cursor = await db.connection.execute(
        "SELECT * FROM logs WHERE message = ?",
        ("No signal ID",)
    )
    row = await cursor.fetchone()

    assert row is not None
    assert row["signal_id"] is None


@pytest.mark.asyncio
async def test_save_signal_history_update(db):
    """Test updating existing signal in history."""
    signal_id = "sig_update_test"

    # First insert
    signal_v1 = {
        "signal_id": signal_id,
        "symbol": "BTCUSDT",
        "direction": "long",
        "confidence": 0.7,
        "executed": 0
    }
    await db.save_signal_history(signal_v1)

    # Update with execution details
    signal_v2 = {
        "signal_id": signal_id,
        "symbol": "BTCUSDT",
        "direction": "long",
        "confidence": 0.7,
        "executed": 1,
        "execution_price": 45500.0,
        "execution_status": "filled",
        "pnl_usdt": 500.0
    }
    await db.save_signal_history(signal_v2)

    # Verify only one record exists with updated values
    cursor = await db.connection.execute(
        "SELECT COUNT(*) as count FROM signals_history WHERE signal_id = ?",
        (signal_id,)
    )
    count_row = await cursor.fetchone()
    assert count_row["count"] == 1

    cursor = await db.connection.execute(
        "SELECT * FROM signals_history WHERE signal_id = ?",
        (signal_id,)
    )
    row = await cursor.fetchone()

    assert row["executed"] == 1
    assert float(row["execution_price"]) == 45500.0
    assert row["execution_status"] == "filled"
    assert float(row["pnl_usdt"]) == 500.0


@pytest.mark.asyncio
async def test_database_not_connected_error(db):
    """Test error when operations are called before connect."""
    new_db = Database(":memory:")

    with pytest.raises(RuntimeError, match="Database not connected"):
        await new_db.log_info("test")

    with pytest.raises(RuntimeError, match="Database not connected"):
        await new_db.save_signal_history({"signal_id": "test"})

    with pytest.raises(RuntimeError, match="Database not connected"):
        await new_db.get_logs_by_signal_id("test")
