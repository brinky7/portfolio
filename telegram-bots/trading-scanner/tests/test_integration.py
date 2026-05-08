"""
Integration tests for ScannerAgent scan_cycle()
Tests the full flow: fetch state → analyze pairs → filter → size positions → publish signals
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.scanner_agent import ScannerAgent
from components.signal_generator import Signal
from config import ScannerConfig
from core.redis_client import RedisClient


class MockRedisClient:
    """Mock Redis client that tracks published signals without actual Redis"""

    def __init__(self):
        self.published_signals = []
        self.published_channels = []
        self.client = MagicMock()
        self._data = {
            "account:balance": b"10000.00",
            "whitelist_pairs": {b"BTCUSDT", b"ETHUSDT", b"BNBUSDT"},
        }

    async def initialize(self):
        pass

    async def shutdown(self):
        pass

    async def get(self, key: str):
        """Return mock account balance or state"""
        return self._data.get(key)

    async def set(self, key: str, value, ex=None):
        self._data[key] = value

    async def rpush(self, queue: str, data: str):
        """Track published signals to queue"""
        if queue == "scanner:signals":
            self.published_signals.append(json.loads(data))

    async def publish(self, channel: str, message: str):
        """Track pub/sub notifications"""
        if channel == "new_signals":
            self.published_channels.append(message)

    async def smembers(self, key: str):
        """Return mock whitelist"""
        if key == "whitelist_pairs":
            return {b"BTCUSDT", b"ETHUSDT", b"BNBUSDT"}
        return set()

    async def lrange(self, key: str, start: int, end: int):
        """Return empty position list"""
        return []

    async def hgetall(self, key: str):
        """Return mock ATR data"""
        return {b"BTCUSDT": b"500.0", b"ETHUSDT": b"20.0", b"BNBUSDT": b"10.0"}

    async def llen(self, key: str):
        """Return queue length"""
        return 0

    async def hget(self, key: str, field: str):
        """Return single hash value"""
        hdata = await self.hgetall(key)
        return hdata.get(field.encode() if isinstance(field, str) else field)


class MockDataFetcher:
    """Mock DataFetcher that returns predictable OHLCV data"""

    def __init__(self, redis_client=None, logger=None, config=None):
        self.redis_client = redis_client
        self.logger = logger
        self.config = config

    async def fetch_ohlcv(self, symbol: str, timeframe: str = "4h", limit: int = 100):
        """Return mock OHLCV data"""
        if symbol == "BTCUSDT":
            return [
                [1700000000000, 43000, 43500, 42500, 43200, 100],
                [1700003600000, 43200, 44000, 43000, 43800, 120],
                [1700007200000, 43800, 44500, 43500, 44200, 110],
                [1700010800000, 44200, 45000, 44000, 44800, 130],
                [1700014400000, 44800, 45500, 44500, 45200, 140],
            ]
        elif symbol == "ETHUSDT":
            return [
                [1700000000000, 2200, 2250, 2150, 2230, 1000],
                [1700003600000, 2230, 2300, 2200, 2270, 1100],
                [1700007200000, 2270, 2350, 2250, 2320, 1050],
                [1700010800000, 2320, 2400, 2300, 2380, 1200],
                [1700014400000, 2380, 2450, 2350, 2420, 1300],
            ]
        elif symbol == "BNBUSDT":
            return [
                [1700000000000, 600, 610, 590, 605, 5000],
                [1700003600000, 605, 620, 600, 615, 5500],
                [1700007200000, 615, 630, 610, 625, 5200],
                [1700010800000, 625, 640, 620, 635, 5800],
                [1700014400000, 635, 650, 630, 645, 6000],
            ]
        return []

    async def fetch_account_state(self):
        """Return mock account state"""
        return {
            "balance": 10000.0,
            "equity": 10000.0,
            "free_balance": 10000.0,
        }

    async def fetch_state(self):
        """Return mock account state (alternative method)"""
        return await self.fetch_account_state()

    async def fetch_symbol_data(self, symbol: str):
        """Return mock symbol data"""
        return {"symbol": symbol, "quote_asset": "USDT"}


class MockMarketAnalyzer:
    """Mock MarketAnalyzer that returns predictable indicators"""

    def __init__(self, redis_client=None, logger=None, config=None):
        self.redis_client = redis_client
        self.logger = logger
        self.config = config

    async def analyze_pair(self, symbol: str, ohlcv_data, dataframe=None):
        """Return mock analysis result"""
        # Return consistent bullish signal with confidence based on symbol
        confidence_map = {"BTCUSDT": 0.78, "ETHUSDT": 0.72, "BNBUSDT": 0.68}
        confidence = confidence_map.get(symbol, 0.70)

        return {
            "symbol": symbol,
            "timeframe": "4h",
            "rsi": 45.0,
            "macd": 0.015,
            "ichimoku_signal": 1,
            "direction": "long",
            "confidence": confidence,
            "confluence_score": 3,
            "indicators_state": {"rsi": 45.0, "macd": 0.015},
        }

    def compute_rsi(self, close_prices, period=14):
        return 45.0

    def compute_macd(self, close_prices):
        return {"macd": 0.015, "signal": 0.010, "histogram": 0.005}


@pytest.fixture
async def mock_scanner():
    """Create a ScannerAgent with mocked components"""
    config = ScannerConfig()
    redis_client = MockRedisClient()
    await redis_client.initialize()

    # Patch PrometheusMetrics and logger to avoid initialization issues in testing
    with patch('core.scanner_agent.PrometheusMetrics'), patch('core.scanner_agent.StructuredLogger'):
        scanner = ScannerAgent(config=config, redis_client=redis_client)
        # Mock logger methods
        scanner.logger = MagicMock()
        scanner.logger.info = MagicMock()
        scanner.logger.warning = MagicMock()
        scanner.logger.error = MagicMock()
        scanner.logger.debug = MagicMock()

        # Replace components with mocks
        scanner.data_fetcher = MockDataFetcher(
            redis_client=redis_client, config=config
        )
        scanner.market_analyzer = MockMarketAnalyzer(
            redis_client=redis_client, config=config
        )

        yield scanner

    await redis_client.shutdown()


@pytest.mark.asyncio
class TestScannerAgentIntegration:
    """Integration tests for ScannerAgent.scan_cycle()"""

    async def test_scan_cycle_completes_without_errors(self, mock_scanner):
        """Test that scan_cycle() runs without exceptions"""
        # Should not raise any exceptions
        await mock_scanner.scan_cycle()

    async def test_scan_cycle_publishes_signals(self, mock_scanner):
        """Test that scan_cycle() publishes signals to Redis queue"""
        await mock_scanner.scan_cycle()

        # Check that signals were published
        assert len(mock_scanner.redis.published_signals) > 0
        assert len(mock_scanner.redis.published_channels) > 0

    async def test_scan_cycle_signal_format(self, mock_scanner):
        """Test that published signals match expected JSON schema"""
        await mock_scanner.scan_cycle()

        # Get first published signal
        assert len(mock_scanner.redis.published_signals) > 0
        signal_data = mock_scanner.redis.published_signals[0]

        # Verify required fields
        required_fields = [
            "id",
            "timestamp",
            "symbol",
            "direction",
            "confidence",
            "entry_price",
            "stop_loss",
            "take_profit",
            "position_size_usdt",
            "kelly_fraction",
        ]

        for field in required_fields:
            assert field in signal_data, f"Missing field: {field}"

    async def test_scan_cycle_confidence_filtering(self, mock_scanner):
        """Test that only high-confidence signals are published"""
        await mock_scanner.scan_cycle()

        # All signals should exceed MIN_CONFIDENCE threshold
        for signal in mock_scanner.redis.published_signals:
            assert (
                signal["confidence"] >= mock_scanner.config.MIN_CONFIDENCE
            ), f"Signal confidence {signal['confidence']} below threshold {mock_scanner.config.MIN_CONFIDENCE}"

    async def test_scan_cycle_position_sizing(self, mock_scanner):
        """Test that position sizes are calculated correctly"""
        await mock_scanner.scan_cycle()

        # Check that position sizes are reasonable
        for signal in mock_scanner.redis.published_signals:
            position_size = signal["position_size_usdt"]
            account_balance = 10000.0

            # Position should not exceed max portfolio percentage (15% for high confidence)
            max_pct = mock_scanner.config.POSITION_SIZE_PCT_HIGH_CONF / 100.0
            assert (
                position_size / account_balance <= max_pct
            ), f"Position size {position_size} exceeds max portfolio allocation"

            # Position should not be negative
            assert position_size > 0, f"Position size {position_size} is not positive"

    async def test_scan_cycle_stop_loss_validation(self, mock_scanner):
        """Test that stop losses are calculated correctly"""
        await mock_scanner.scan_cycle()

        for signal in mock_scanner.redis.published_signals:
            if signal["direction"] == "long":
                # Long: SL should be below entry
                assert (
                    signal["stop_loss"] < signal["entry_price"]
                ), f"Long SL {signal['stop_loss']} not below entry {signal['entry_price']}"

                # TP should be above entry
                assert (
                    signal["take_profit"] > signal["entry_price"]
                ), f"Long TP {signal['take_profit']} not above entry {signal['entry_price']}"

            elif signal["direction"] == "short":
                # Short: SL should be above entry
                assert (
                    signal["stop_loss"] > signal["entry_price"]
                ), f"Short SL {signal['stop_loss']} not above entry {signal['entry_price']}"

                # TP should be below entry
                assert (
                    signal["take_profit"] < signal["entry_price"]
                ), f"Short TP {signal['take_profit']} not below entry {signal['entry_price']}"

    async def test_scan_cycle_pub_sub_notifications(self, mock_scanner):
        """Test that pub/sub notifications are sent for new signals"""
        await mock_scanner.scan_cycle()

        # Check that notifications were published
        published_symbols = mock_scanner.redis.published_channels
        assert len(published_symbols) > 0, "No pub/sub notifications published"

        # Notifications should be symbol names
        for symbol in published_symbols:
            assert symbol in ["BTCUSDT", "ETHUSDT", "BNBUSDT"]

    async def test_scan_cycle_handles_no_signals(self, mock_scanner):
        """Test scan_cycle behavior when no signals meet criteria"""
        # Lower confidence threshold to trigger filtering
        original_threshold = mock_scanner.config.MIN_CONFIDENCE
        mock_scanner.config.MIN_CONFIDENCE = 0.99  # Impossible to meet

        # Should complete without error even with 0 signals
        await mock_scanner.scan_cycle()

        mock_scanner.config.MIN_CONFIDENCE = original_threshold

    async def test_scan_cycle_handles_low_balance(self, mock_scanner):
        """Test scan_cycle when account balance is insufficient"""
        # Mock insufficient balance
        async def mock_get(key):
            if key == "account:balance":
                return b"100.00"  # Very low balance
            return None

        mock_scanner.redis.get = mock_get

        # Should still complete without error
        await mock_scanner.scan_cycle()

    async def test_multiple_pairs_analyzed_in_parallel(self, mock_scanner):
        """Test that multiple pairs are analyzed (simulating parallel analysis)"""
        await mock_scanner.scan_cycle()

        # Should have analyzed multiple pairs
        published_symbols = set(
            sig["symbol"] for sig in mock_scanner.redis.published_signals
        )

        # Expect at least some of the whitelisted pairs
        assert len(published_symbols) > 0


@pytest.mark.asyncio
class TestScannerComponentIntegration:
    """Integration tests for component interactions"""

    async def test_data_fetcher_integration(self):
        """Test DataFetcher mock with realistic data"""
        fetcher = MockDataFetcher()

        ohlcv = await fetcher.fetch_ohlcv("BTCUSDT")
        assert len(ohlcv) == 5
        assert ohlcv[0][1] == 43000  # First high

        account = await fetcher.fetch_account_state()
        assert account["balance"] == 10000.0

    async def test_market_analyzer_integration(self):
        """Test MarketAnalyzer mock with OHLCV data"""
        analyzer = MockMarketAnalyzer()
        fetcher = MockDataFetcher()

        ohlcv = await fetcher.fetch_ohlcv("BTCUSDT")
        analysis = await analyzer.analyze_pair("BTCUSDT", ohlcv)

        assert analysis["direction"] in ["long", "short"]
        assert 0.0 <= analysis["confidence"] <= 1.0
        assert analysis["symbol"] == "BTCUSDT"

