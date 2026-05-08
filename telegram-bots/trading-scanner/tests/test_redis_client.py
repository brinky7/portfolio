"""
Tests for RedisClient using mock objects.
Tests all Redis operations with AsyncMock to avoid requiring a live Redis instance.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from core.redis_client import RedisClient


@pytest.fixture
def mock_redis():
    """Fixture providing a mock Redis connection."""
    return AsyncMock()


@pytest.fixture
def client(mock_redis):
    """Fixture providing RedisClient instance with mocked Redis."""
    redis_client = RedisClient(host="localhost", port=6379)
    redis_client.redis = mock_redis
    return redis_client


class TestRedisClientConnection:
    """Test connection management."""

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful Redis connection."""
        with patch('core.redis_client.aioredis.from_url', new_callable=AsyncMock) as mock_connect:
            mock_redis = AsyncMock()
            mock_connect.return_value = mock_redis

            client = RedisClient(host="localhost", port=6379)
            await client.connect()

            assert client.redis is not None
            mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_success(self, client):
        """Test successful Redis disconnection."""
        client.redis = AsyncMock()
        client.redis.close = AsyncMock()
        client.redis.wait_closed = AsyncMock()

        await client.disconnect()

        client.redis.close.assert_called_once()
        client.redis.wait_closed.assert_called_once()


class TestGetBalance:
    """Test get_balance method."""

    @pytest.mark.asyncio
    async def test_get_balance_success(self, client):
        """Test successful balance retrieval."""
        client.redis.get = AsyncMock(return_value=b"1234.56")

        balance = await client.get_balance()

        assert balance == 1234.56
        client.redis.get.assert_called_once_with("account:balance")

    @pytest.mark.asyncio
    async def test_get_balance_empty(self, client):
        """Test balance retrieval when key doesn't exist."""
        client.redis.get = AsyncMock(return_value=None)

        balance = await client.get_balance()

        assert balance == 0.0
        client.redis.get.assert_called_once_with("account:balance")

    @pytest.mark.asyncio
    async def test_get_balance_invalid_value(self, client):
        """Test balance retrieval with invalid value."""
        client.redis.get = AsyncMock(return_value=b"invalid")

        with pytest.raises(ValueError):
            await client.get_balance()


class TestGetOpenPositions:
    """Test get_open_positions method."""

    @pytest.mark.asyncio
    async def test_get_open_positions_success(self, client):
        """Test successful open positions retrieval."""
        positions = [
            {"symbol": "BTCUSDT", "side": "LONG", "qty": 1.0},
            {"symbol": "ETHUSDT", "side": "SHORT", "qty": 10.0}
        ]
        client.redis.get = AsyncMock(return_value=json.dumps(positions).encode())

        result = await client.get_open_positions()

        assert result == positions
        client.redis.get.assert_called_once_with("open_positions")

    @pytest.mark.asyncio
    async def test_get_open_positions_empty(self, client):
        """Test open positions retrieval when none exist."""
        client.redis.get = AsyncMock(return_value=None)

        result = await client.get_open_positions()

        assert result == []
        client.redis.get.assert_called_once_with("open_positions")

    @pytest.mark.asyncio
    async def test_get_open_positions_invalid_json(self, client):
        """Test open positions retrieval with invalid JSON."""
        client.redis.get = AsyncMock(return_value=b"invalid_json{")

        with pytest.raises(json.JSONDecodeError):
            await client.get_open_positions()


class TestGetWhitelistPairs:
    """Test get_whitelist_pairs method."""

    @pytest.mark.asyncio
    async def test_get_whitelist_pairs_success(self, client):
        """Test successful whitelist retrieval."""
        whitelist = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
        client.redis.smembers = AsyncMock(return_value=whitelist)

        result = await client.get_whitelist_pairs()

        assert result == set(whitelist)
        client.redis.smembers.assert_called_once_with("whitelist_pairs")

    @pytest.mark.asyncio
    async def test_get_whitelist_pairs_empty(self, client):
        """Test whitelist retrieval when empty."""
        client.redis.smembers = AsyncMock(return_value=[])

        result = await client.get_whitelist_pairs()

        assert result == set()


class TestGetVolatility:
    """Test get_volatility method."""

    @pytest.mark.asyncio
    async def test_get_volatility_success(self, client):
        """Test successful volatility retrieval."""
        client.redis.get = AsyncMock(return_value=b"0.025")

        result = await client.get_volatility("BTCUSDT")

        assert result == 0.025
        client.redis.get.assert_called_once_with("volatility:BTCUSDT")

    @pytest.mark.asyncio
    async def test_get_volatility_not_found(self, client):
        """Test volatility retrieval when not found."""
        client.redis.get = AsyncMock(return_value=None)

        result = await client.get_volatility("BTCUSDT")

        assert result == 0.0


class TestGetOHLCV:
    """Test get_ohlcv method."""

    @pytest.mark.asyncio
    async def test_get_ohlcv_success(self, client):
        """Test successful OHLCV data retrieval."""
        ohlcv_data = [
            [1618000000000, 100.0, 102.0, 99.0, 101.0, 1000.0],
            [1618003600000, 101.0, 103.0, 100.0, 102.0, 1100.0]
        ]
        client.redis.get = AsyncMock(return_value=json.dumps(ohlcv_data).encode())

        result = await client.get_ohlcv("BTCUSDT", "4h")

        assert result == ohlcv_data
        client.redis.get.assert_called_once_with("ohlcv:BTCUSDT:4h")

    @pytest.mark.asyncio
    async def test_get_ohlcv_default_timeframe(self, client):
        """Test OHLCV data retrieval with default timeframe."""
        ohlcv_data = []
        client.redis.get = AsyncMock(return_value=json.dumps(ohlcv_data).encode())

        result = await client.get_ohlcv("BTCUSDT")

        client.redis.get.assert_called_once_with("ohlcv:BTCUSDT:4h")

    @pytest.mark.asyncio
    async def test_get_ohlcv_not_found(self, client):
        """Test OHLCV retrieval when not found."""
        client.redis.get = AsyncMock(return_value=None)

        result = await client.get_ohlcv("BTCUSDT", "4h")

        assert result == []


class TestGetCorrelations:
    """Test get_correlations method."""

    @pytest.mark.asyncio
    async def test_get_correlations_success(self, client):
        """Test successful correlations retrieval."""
        correlations = {
            "BTCUSDT:ETHUSDT": 0.85,
            "BTCUSDT:BNBUSDT": 0.72
        }
        client.redis.get = AsyncMock(return_value=json.dumps(correlations).encode())

        result = await client.get_correlations()

        assert result == correlations
        client.redis.get.assert_called_once_with("correlations")

    @pytest.mark.asyncio
    async def test_get_correlations_empty(self, client):
        """Test correlations retrieval when empty."""
        client.redis.get = AsyncMock(return_value=None)

        result = await client.get_correlations()

        assert result == {}


class TestGetPortfolioMetrics:
    """Test get_portfolio_metrics method."""

    @pytest.mark.asyncio
    async def test_get_portfolio_metrics_success(self, client):
        """Test successful portfolio metrics retrieval."""
        metrics = {
            "variance": 0.15,
            "max_drawdown": -0.25,
            "margin_level": 3.5
        }
        client.redis.get = AsyncMock(return_value=json.dumps(metrics).encode())

        result = await client.get_portfolio_metrics()

        assert result == metrics
        client.redis.get.assert_called_once_with("portfolio_metrics")

    @pytest.mark.asyncio
    async def test_get_portfolio_metrics_empty(self, client):
        """Test portfolio metrics retrieval when not found."""
        client.redis.get = AsyncMock(return_value=None)

        result = await client.get_portfolio_metrics()

        assert result == {}


class TestGetNewsBias:
    """Test get_news_bias method."""

    @pytest.mark.asyncio
    async def test_get_news_bias_success(self, client):
        """Test successful news bias retrieval."""
        client.redis.get = AsyncMock(return_value=b"0.75")

        result = await client.get_news_bias("BTCUSDT")

        assert result == 0.75
        client.redis.get.assert_called_once_with("news_bias:BTCUSDT")

    @pytest.mark.asyncio
    async def test_get_news_bias_not_found(self, client):
        """Test news bias retrieval when not found."""
        client.redis.get = AsyncMock(return_value=None)

        result = await client.get_news_bias("BTCUSDT")

        assert result == 0.0

    @pytest.mark.asyncio
    async def test_get_news_bias_invalid_value(self, client):
        """Test news bias retrieval with invalid value."""
        client.redis.get = AsyncMock(return_value=b"invalid")

        with pytest.raises(ValueError):
            await client.get_news_bias("BTCUSDT")


class TestPublishSignal:
    """Test publish_signal method."""

    @pytest.mark.asyncio
    async def test_publish_signal_success(self, client):
        """Test successful signal publishing."""
        signal = {
            "symbol": "BTCUSDT",
            "side": "LONG",
            "confidence": 0.85,
            "timestamp": datetime.now().isoformat()
        }

        client.redis.lpush = AsyncMock(return_value=1)
        client.redis.publish = AsyncMock(return_value=1)

        result = await client.publish_signal(signal)

        assert result is True
        client.redis.lpush.assert_called_once()
        client.redis.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_signal_redis_error(self, client):
        """Test signal publishing with Redis error."""
        signal = {"symbol": "BTCUSDT", "side": "LONG"}

        client.redis.lpush = AsyncMock(side_effect=Exception("Redis error"))

        with pytest.raises(Exception):
            await client.publish_signal(signal)


class TestMoveToDLQ:
    """Test move_to_dlq method."""

    @pytest.mark.asyncio
    async def test_move_to_dlq_success(self, client):
        """Test successful DLQ move."""
        signal = {"symbol": "BTCUSDT", "side": "LONG"}
        error = "Invalid signal"

        client.redis.lpush = AsyncMock(return_value=1)

        result = await client.move_to_dlq(signal, error)

        assert result is True
        client.redis.lpush.assert_called_once()

    @pytest.mark.asyncio
    async def test_move_to_dlq_redis_error(self, client):
        """Test DLQ move with Redis error."""
        signal = {"symbol": "BTCUSDT"}
        error = "Error"

        client.redis.lpush = AsyncMock(side_effect=Exception("Redis error"))

        with pytest.raises(Exception):
            await client.move_to_dlq(signal, error)


class TestGetDLQLength:
    """Test get_dlq_length method."""

    @pytest.mark.asyncio
    async def test_get_dlq_length_success(self, client):
        """Test successful DLQ length retrieval."""
        client.redis.llen = AsyncMock(return_value=5)

        result = await client.get_dlq_length()

        assert result == 5
        client.redis.llen.assert_called_once_with("scanner:dlq")

    @pytest.mark.asyncio
    async def test_get_dlq_length_empty(self, client):
        """Test DLQ length when queue is empty."""
        client.redis.llen = AsyncMock(return_value=0)

        result = await client.get_dlq_length()

        assert result == 0


class TestSubscribePortfolioUpdates:
    """Test subscribe_portfolio_updates method."""

    @pytest.mark.asyncio
    async def test_subscribe_portfolio_updates_success(self, client):
        """Test successful subscription to portfolio updates."""
        callback = AsyncMock()
        mock_channel = AsyncMock()
        mock_channel.iter = AsyncMock()

        client.redis.subscribe = AsyncMock(return_value=[mock_channel])

        # Mock iterator to return a few messages then stop
        async def mock_iter():
            yield {"data": b'{"balance": 1000}'}
            yield {"data": b'{"balance": 1100}'}

        mock_channel.iter.return_value = mock_iter()

        # Run subscription with timeout
        try:
            await client.subscribe_portfolio_updates(callback, timeout=0.1)
        except:
            pass  # Timeout is expected in test

        client.redis.subscribe.assert_called_once_with("scanner:positions")

    @pytest.mark.asyncio
    async def test_subscribe_portfolio_updates_invalid_json(self, client):
        """Test subscription with invalid JSON message."""
        callback = AsyncMock()
        mock_channel = AsyncMock()

        client.redis.subscribe = AsyncMock(return_value=[mock_channel])

        async def mock_iter():
            yield {"data": b'invalid_json{'}

        mock_channel.iter.return_value = mock_iter()

        try:
            await client.subscribe_portfolio_updates(callback, timeout=0.1)
        except:
            pass

        callback.assert_not_called()
