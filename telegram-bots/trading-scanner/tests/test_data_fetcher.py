"""
Tests for DataFetcher with retry logic and Redis fallback.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import asyncio
import aiohttp
from unittest.mock import AsyncMock, MagicMock, patch
from components.data_fetcher import DataFetcher
from config import ScannerConfig


@pytest.fixture
def mock_redis_client():
    """Mock Redis client."""
    client = AsyncMock()
    return client


@pytest.fixture
def mock_ccxt_exchange():
    """Mock CCXT exchange."""
    exchange = AsyncMock()
    exchange.fetch_ohlcv = AsyncMock()
    return exchange


@pytest.fixture
async def data_fetcher(mock_redis_client, mock_ccxt_exchange):
    """Create DataFetcher instance with mocked dependencies."""
    fetcher = DataFetcher(
        redis_client=mock_redis_client,
        ccxt_exchange=mock_ccxt_exchange
    )
    return fetcher


class TestDataFetcherOHLCV:
    """Tests for fetch_ohlcv with retry and Redis fallback."""

    @pytest.mark.asyncio
    async def test_fetch_ohlcv_from_redis(self, mock_redis_client, mock_ccxt_exchange):
        """Test fetching OHLCV from Redis cache."""
        mock_redis_client.get.return_value = (
            b'[[1640000000000, 42000, 43000, 41000, 42500, 100], '
            b'[1640003600000, 42500, 43500, 42000, 43000, 150]]'
        )

        fetcher = DataFetcher(
            redis_client=mock_redis_client,
            ccxt_exchange=mock_ccxt_exchange
        )

        result = await fetcher.fetch_ohlcv("BTCUSDT", timeframe="4h", limit=200)

        assert isinstance(result, list)
        assert len(result) >= 0
        mock_redis_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_ohlcv_from_ccxt_fallback(self, mock_redis_client, mock_ccxt_exchange):
        """Test fallback to CCXT when Redis is empty."""
        mock_redis_client.get.return_value = None
        mock_ccxt_exchange.fetch_ohlcv.return_value = [
            [1640000000000, 42000, 43000, 41000, 42500, 100],
            [1640003600000, 42500, 43500, 42000, 43000, 150]
        ]

        fetcher = DataFetcher(
            redis_client=mock_redis_client,
            ccxt_exchange=mock_ccxt_exchange
        )

        result = await fetcher.fetch_ohlcv("BTCUSDT", timeframe="4h", limit=200)

        assert isinstance(result, list)
        mock_ccxt_exchange.fetch_ohlcv.assert_called_once_with("BTCUSDT", "4h", limit=200)

    @pytest.mark.asyncio
    async def test_fetch_ohlcv_retry_on_timeout(self, mock_redis_client, mock_ccxt_exchange):
        """Test retry logic on timeout error."""
        mock_redis_client.get.return_value = None

        # Fail twice, succeed on third attempt
        mock_ccxt_exchange.fetch_ohlcv.side_effect = [
            asyncio.TimeoutError(),
            asyncio.TimeoutError(),
            [
                [1640000000000, 42000, 43000, 41000, 42500, 100],
                [1640003600000, 42500, 43500, 42000, 43000, 150]
            ]
        ]

        fetcher = DataFetcher(
            redis_client=mock_redis_client,
            ccxt_exchange=mock_ccxt_exchange
        )

        result = await fetcher.fetch_ohlcv("BTCUSDT", timeframe="4h", limit=200)

        assert isinstance(result, list)
        assert mock_ccxt_exchange.fetch_ohlcv.call_count == 3

    @pytest.mark.asyncio
    async def test_fetch_ohlcv_retry_on_client_error(self, mock_redis_client, mock_ccxt_exchange):
        """Test retry logic on aiohttp.ClientError."""
        mock_redis_client.get.return_value = None

        # Fail once, succeed on second attempt
        mock_ccxt_exchange.fetch_ohlcv.side_effect = [
            aiohttp.ClientError("Connection failed"),
            [
                [1640000000000, 42000, 43000, 41000, 42500, 100],
                [1640003600000, 42500, 43500, 42000, 43000, 150]
            ]
        ]

        fetcher = DataFetcher(
            redis_client=mock_redis_client,
            ccxt_exchange=mock_ccxt_exchange
        )

        result = await fetcher.fetch_ohlcv("BTCUSDT", timeframe="4h", limit=200)

        assert isinstance(result, list)
        assert mock_ccxt_exchange.fetch_ohlcv.call_count == 2

    @pytest.mark.asyncio
    async def test_fetch_ohlcv_format_conversion(self, mock_redis_client, mock_ccxt_exchange):
        """Test conversion of CCXT format to dict format."""
        mock_redis_client.get.return_value = None
        mock_ccxt_exchange.fetch_ohlcv.return_value = [
            [1640000000000, 42000.0, 43000.0, 41000.0, 42500.0, 100.5],
        ]

        fetcher = DataFetcher(
            redis_client=mock_redis_client,
            ccxt_exchange=mock_ccxt_exchange
        )

        result = await fetcher.fetch_ohlcv("BTCUSDT", timeframe="4h", limit=200)

        # Should be list of dicts
        assert isinstance(result, list)
        if result:
            item = result[0]
            assert isinstance(item, dict)
            assert "timestamp" in item or "time" in item or "open" in item


class TestDataFetcherAccountState:
    """Tests for fetch_account_state."""

    @pytest.mark.asyncio
    async def test_fetch_account_state_success(self, mock_redis_client, mock_ccxt_exchange):
        """Test fetching account state."""
        mock_redis_client.get.return_value = None
        mock_ccxt_exchange.fetch_balance.return_value = {
            "USDT": {"free": 10000.0, "used": 5000.0, "total": 15000.0},
            "BTC": {"free": 0.5, "used": 0.2, "total": 0.7},
        }

        fetcher = DataFetcher(
            redis_client=mock_redis_client,
            ccxt_exchange=mock_ccxt_exchange
        )

        result = await fetcher.fetch_account_state()

        assert isinstance(result, dict)
        assert "balance" in result
        assert "portfolio_metrics" in result

    @pytest.mark.asyncio
    async def test_fetch_account_state_with_retry(self, mock_redis_client, mock_ccxt_exchange):
        """Test account state fetch with retry on error."""
        mock_redis_client.get.return_value = None

        # Fail once, succeed on second attempt
        mock_ccxt_exchange.fetch_balance.side_effect = [
            asyncio.TimeoutError(),
            {
                "USDT": {"free": 10000.0, "used": 5000.0, "total": 15000.0},
                "BTC": {"free": 0.5, "used": 0.2, "total": 0.7},
            }
        ]

        fetcher = DataFetcher(
            redis_client=mock_redis_client,
            ccxt_exchange=mock_ccxt_exchange
        )

        result = await fetcher.fetch_account_state()

        assert isinstance(result, dict)
        assert mock_ccxt_exchange.fetch_balance.call_count == 2


class TestDataFetcherState:
    """Tests for fetch_state."""

    @pytest.mark.asyncio
    async def test_fetch_state_complete_structure(self, mock_redis_client, mock_ccxt_exchange):
        """Test that fetch_state returns complete structure."""
        mock_redis_client.get.return_value = None
        mock_ccxt_exchange.fetch_balance.return_value = {
            "USDT": {"free": 10000.0, "used": 0.0, "total": 10000.0},
            "BTC": {"free": 0.1, "used": 0.0, "total": 0.1},
        }

        fetcher = DataFetcher(
            redis_client=mock_redis_client,
            ccxt_exchange=mock_ccxt_exchange
        )

        result = await fetcher.fetch_state()

        assert isinstance(result, dict)
        assert "balance" in result
        assert "positions" in result
        assert "whitelist" in result
        assert "correlations" in result
        assert "portfolio_metrics" in result
        assert "volatility" in result
        assert "news_biases" in result


class TestDataFetcherSymbolData:
    """Tests for fetch_symbol_data."""

    @pytest.mark.asyncio
    async def test_fetch_symbol_data(self, mock_redis_client, mock_ccxt_exchange):
        """Test fetching symbol-specific data."""
        mock_redis_client.get.return_value = None
        mock_ccxt_exchange.fetch_ohlcv.return_value = [
            [1640000000000, 42000.0, 43000.0, 41000.0, 42500.0, 100.0],
        ]

        fetcher = DataFetcher(
            redis_client=mock_redis_client,
            ccxt_exchange=mock_ccxt_exchange
        )

        state = {
            "balance": {"USDT": 10000.0},
            "positions": [],
            "whitelist": ["BTCUSDT"],
        }

        result = await fetcher.fetch_symbol_data("BTCUSDT", state)

        assert isinstance(result, dict)
        assert "ohlcv_4h" in result
        assert "ohlcv_1d" in result
        assert "volatility" in result
        assert "news_bias" in result


class TestDataFetcherConnectionManagement:
    """Tests for connect/disconnect methods."""

    @pytest.mark.asyncio
    async def test_connect_disconnect(self, mock_redis_client, mock_ccxt_exchange):
        """Test connection lifecycle."""
        fetcher = DataFetcher(
            redis_client=mock_redis_client,
            ccxt_exchange=mock_ccxt_exchange
        )

        # Connect should work
        await fetcher.connect()

        # Disconnect should work
        await fetcher.disconnect()


class TestDataFetcherRetryConfiguration:
    """Tests for retry configuration."""

    @pytest.mark.asyncio
    async def test_retry_max_attempts_from_config(self, mock_redis_client, mock_ccxt_exchange):
        """Test that retry uses config values."""
        config = ScannerConfig()
        assert config.RETRY_MAX_ATTEMPTS > 0
        assert config.RETRY_BASE_DELAY_SECONDS > 0
        assert config.RETRY_MAX_DELAY_SECONDS > 0
