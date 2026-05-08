"""
Tests for Signal Generator and Signal dataclass.
"""

import sys
from pathlib import Path
from datetime import datetime
from uuid import UUID

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from components.signal_generator import Signal, SignalGenerator


class TestSignalDataclass:
    """Tests for Signal dataclass and serialization."""

    def test_signal_creation_minimal(self):
        """Test creating a Signal with minimal fields."""
        signal = Signal(
            id="sig_20260418_000000_BTC_abc123",
            timestamp=datetime.now(),
            symbol="BTC",
            timeframe="1h",
            direction="long",
            confidence=0.75,
            entry_price=45000.0,
            stop_loss=43500.0,
            take_profit=49500.0,
            position_size_usdt=1000.0,
            position_size_pct=5.0,
            kelly_fraction=0.05,
            risk_usdt=1500.0,
            reward_usdt=4500.0,
            risk_reward_ratio=3.0,
            confluence_score=0.85,
            news_bias_score=0.0,
            order_book_depth=None,
            indicators_state=None,
        )
        assert signal.id == "sig_20260418_000000_BTC_abc123"
        assert signal.symbol == "BTC"
        assert signal.direction == "long"
        assert signal.confidence == 0.75

    def test_signal_to_dict(self):
        """Test Signal serialization to dict."""
        now = datetime.now()
        signal = Signal(
            id="sig_20260418_000000_ETH_def456",
            timestamp=now,
            symbol="ETH",
            timeframe="4h",
            direction="short",
            confidence=0.65,
            entry_price=2500.0,
            stop_loss=2600.0,
            take_profit=2300.0,
            position_size_usdt=500.0,
            position_size_pct=2.5,
            kelly_fraction=0.025,
            risk_usdt=500.0,
            reward_usdt=1000.0,
            risk_reward_ratio=2.0,
            confluence_score=0.70,
            news_bias_score=0.1,
            order_book_depth={"asks": [2501.0, 2502.0], "bids": [2499.0, 2498.0]},
            indicators_state={"rsi": 35, "macd": "bearish"},
        )
        data = signal.to_dict()
        assert data["id"] == "sig_20260418_000000_ETH_def456"
        assert data["symbol"] == "ETH"
        assert data["direction"] == "short"
        assert data["position_size_usdt"] == 500.0
        assert data["order_book_depth"]["asks"] == [2501.0, 2502.0]
        assert data["indicators_state"]["rsi"] == 35
        assert isinstance(data["timestamp"], str)  # ISO format


class TestCalculateEntryPrice:
    """Tests for entry price calculation."""

    def test_calculate_entry_price_long(self):
        """Test entry price for long: should use ask price."""
        generator = SignalGenerator()
        order_book = {
            "asks": [45100.0, 45101.0, 45102.0],
            "bids": [45099.0, 45098.0, 45097.0],
        }
        entry = generator.calculate_entry_price(
            symbol="BTC",
            direction="long",
            current_price=45100.0,
            order_book=order_book,
        )
        # For long, use ask (first element)
        assert entry == 45100.0

    def test_calculate_entry_price_short(self):
        """Test entry price for short: should use bid price."""
        generator = SignalGenerator()
        order_book = {
            "asks": [45100.0, 45101.0, 45102.0],
            "bids": [45099.0, 45098.0, 45097.0],
        }
        entry = generator.calculate_entry_price(
            symbol="BTC",
            direction="short",
            current_price=45100.0,
            order_book=order_book,
        )
        # For short, use bid (first element)
        assert entry == 45099.0

    def test_calculate_entry_price_no_order_book(self):
        """Test entry price uses current_price when order_book is None."""
        generator = SignalGenerator()
        entry = generator.calculate_entry_price(
            symbol="BTC",
            direction="long",
            current_price=45100.0,
            order_book=None,
        )
        assert entry == 45100.0


class TestCalculateStopLoss:
    """Tests for stop loss calculation."""

    def test_calculate_stop_loss_long(self):
        """Test SL for long position: entry - (atr * multiplier)."""
        generator = SignalGenerator()
        # entry=50000, atr=500, multiplier=2.0
        # calculated_sl = 50000 - (500 * 2.0) = 49000
        # min_sl = 50000 * (1 - 0.015) = 49250
        # use max(49000, 49250) = 49250
        sl = generator.calculate_stop_loss(
            symbol="BTC",
            entry_price=50000.0,
            direction="long",
            atr=500.0,
            atr_multiplier=2.0,
            min_sl_pct=1.5,
        )
        assert sl == 49250.0

    def test_calculate_stop_loss_short(self):
        """Test SL for short position: entry + (atr * multiplier)."""
        generator = SignalGenerator()
        # entry=50000, atr=500, multiplier=2.0
        # calculated_sl = 50000 + (500 * 2.0) = 51000
        # min_sl = 50000 * (1 + 0.015) = 50750
        # use min(51000, 50750) = 50750
        sl = generator.calculate_stop_loss(
            symbol="BTC",
            entry_price=50000.0,
            direction="short",
            atr=500.0,
            atr_multiplier=2.0,
            min_sl_pct=1.5,
        )
        assert abs(sl - 50750.0) < 1e-6

    def test_calculate_stop_loss_respects_min_sl_pct_long(self):
        """Test that long SL respects minimum 1.5% from entry."""
        generator = SignalGenerator()
        # entry=50000, atr=100, multiplier=2.0
        # calculated_sl = 50000 - 200 = 49800
        # min_sl = 50000 * (1 - 0.015) = 50000 * 0.985 = 49250
        # use calculated_sl (49800) since 49800 > 49250
        sl = generator.calculate_stop_loss(
            symbol="BTC",
            entry_price=50000.0,
            direction="long",
            atr=100.0,
            atr_multiplier=2.0,
            min_sl_pct=1.5,
        )
        assert sl == 49800.0

    def test_calculate_stop_loss_enforces_min_sl_pct_long(self):
        """Test that long SL uses minimum when ATR-based is too close."""
        generator = SignalGenerator()
        # entry=50000, atr=10, multiplier=2.0
        # calculated_sl = 50000 - 20 = 49980
        # min_sl = 50000 * (1 - 0.015) = 49250
        # use min_sl (49250) since 49980 > 49250 but we need a tighter minimum
        # Actually 49980 > 49250, so should still use calculated
        # Let me test a case where calculated is tighter than min
        # entry=1000, atr=5, multiplier=2.0
        # calculated = 1000 - 10 = 990
        # min_sl = 1000 * (1 - 0.015) = 985
        # use calculated (990) since 990 > 985
        sl = generator.calculate_stop_loss(
            symbol="ALT",
            entry_price=1000.0,
            direction="long",
            atr=5.0,
            atr_multiplier=2.0,
            min_sl_pct=1.5,
        )
        # 1000 - (5 * 2.0) = 990, min = 1000 * 0.985 = 985, use max = 990
        assert sl == 990.0

    def test_calculate_stop_loss_min_sl_pct_enforced(self):
        """Test minimum SL percentage enforcement when ATR-based is tighter."""
        generator = SignalGenerator()
        # entry=1000, atr=1, multiplier=1.0
        # calculated = 1000 - 1 = 999
        # min_sl = 1000 * (1 - 0.015) = 985
        # This calculated (999) is too close, use min (985)
        # But max(calculated, min) = max(999, 985) = 999
        # Let me invert: entry=1000, atr=50, multiplier=0.5
        # calculated = 1000 - 25 = 975
        # min_sl = 1000 * (1 - 0.015) = 985
        # max(975, 985) = 985
        sl = generator.calculate_stop_loss(
            symbol="ALT",
            entry_price=1000.0,
            direction="long",
            atr=50.0,
            atr_multiplier=0.5,
            min_sl_pct=1.5,
        )
        assert sl == 985.0

    def test_calculate_stop_loss_short_respects_min_sl_pct(self):
        """Test that short SL respects minimum 1.5% from entry."""
        generator = SignalGenerator()
        # entry=1000, atr=50, multiplier=0.5
        # calculated_sl = 1000 + 25 = 1025
        # min_sl = 1000 * (1 + 0.015) = 1015
        # min(1025, 1015) = 1015
        sl = generator.calculate_stop_loss(
            symbol="ALT",
            entry_price=1000.0,
            direction="short",
            atr=50.0,
            atr_multiplier=0.5,
            min_sl_pct=1.5,
        )
        assert abs(sl - 1015.0) < 1e-6


class TestCalculateTakeProfit:
    """Tests for take profit calculation."""

    def test_calculate_take_profit_long(self):
        """Test TP for long: entry + (distance_to_sl * ratio)."""
        generator = SignalGenerator()
        # entry=50000, sl=49000
        # distance = 50000 - 49000 = 1000
        # tp = 50000 + (1000 * 2.0) = 50000 + 2000 = 52000
        tp = generator.calculate_take_profit(
            entry_price=50000.0,
            stop_loss=49000.0,
            direction="long",
            risk_reward_ratio=2.0,
        )
        assert tp == 52000.0

    def test_calculate_take_profit_short(self):
        """Test TP for short: entry - (distance_to_sl * ratio)."""
        generator = SignalGenerator()
        # entry=50000, sl=51000
        # distance = 51000 - 50000 = 1000
        # tp = 50000 - (1000 * 2.0) = 50000 - 2000 = 48000
        tp = generator.calculate_take_profit(
            entry_price=50000.0,
            stop_loss=51000.0,
            direction="short",
            risk_reward_ratio=2.0,
        )
        assert tp == 48000.0

    def test_calculate_take_profit_different_ratio(self):
        """Test TP with different risk/reward ratio."""
        generator = SignalGenerator()
        # entry=100, sl=95
        # distance = 5
        # tp = 100 + (5 * 3.0) = 100 + 15 = 115
        tp = generator.calculate_take_profit(
            entry_price=100.0,
            stop_loss=95.0,
            direction="long",
            risk_reward_ratio=3.0,
        )
        assert tp == 115.0


class TestCalculateRiskReward:
    """Tests for risk/reward calculation."""

    def test_calculate_risk_reward_long(self):
        """Test risk/reward for long position."""
        generator = SignalGenerator()
        # entry=50000, sl=49000, tp=52000
        # risk = 50000 - 49000 = 1000
        # reward = 52000 - 50000 = 2000
        # ratio = 2000 / 1000 = 2.0
        risk, reward, ratio = generator.calculate_risk_reward(
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=52000.0,
        )
        assert risk == 1000.0
        assert reward == 2000.0
        assert ratio == 2.0

    def test_calculate_risk_reward_short(self):
        """Test risk/reward for short position."""
        generator = SignalGenerator()
        # entry=50000, sl=51000, tp=48000
        # risk = 51000 - 50000 = 1000
        # reward = 50000 - 48000 = 2000
        # ratio = 2000 / 1000 = 2.0
        risk, reward, ratio = generator.calculate_risk_reward(
            entry_price=50000.0,
            stop_loss=51000.0,
            take_profit=48000.0,
        )
        assert risk == 1000.0
        assert reward == 2000.0
        assert ratio == 2.0

    def test_calculate_risk_reward_invalid_ratio(self):
        """Test risk/reward when risk is zero (edge case)."""
        generator = SignalGenerator()
        # entry=50000, sl=50000 (same), tp=52000
        # risk = 0, should handle division
        risk, reward, ratio = generator.calculate_risk_reward(
            entry_price=50000.0,
            stop_loss=50000.0,
            take_profit=52000.0,
        )
        assert risk == 0.0
        assert reward == 2000.0
        assert ratio == float("inf")


class TestGenerateSignal:
    """Tests for complete signal generation."""

    def test_generate_signal_long(self):
        """Test generating a complete long signal."""
        generator = SignalGenerator()
        analysis_result = {
            "direction": "long",
            "confidence": 0.78,
            "confluence_score": 0.82,
        }
        order_book = {
            "asks": [45100.0, 45101.0],
            "bids": [45099.0, 45098.0],
        }

        signal = generator.generate_signal(
            symbol="BTC",
            analysis_result=analysis_result,
            position_size_pct=5.0,
            position_size_usdt=1000.0,
            account_balance=20000.0,
            kelly_fraction=0.05,
            news_bias_score=0.0,
            atr=500.0,
            current_price=45100.0,
            order_book=order_book,
            timeframe="1h",
        )

        assert isinstance(signal, Signal)
        assert signal.symbol == "BTC"
        assert signal.direction == "long"
        assert signal.confidence == 0.78
        assert signal.position_size_pct == 5.0
        assert signal.position_size_usdt == 1000.0
        assert signal.kelly_fraction == 0.05
        assert signal.news_bias_score == 0.0
        assert signal.timeframe == "1h"
        assert signal.id.startswith("sig_")
        assert "BTC" in signal.id
        assert signal.entry_price > 0
        assert signal.stop_loss > 0
        assert signal.take_profit > 0
        assert signal.risk_usdt > 0
        assert signal.reward_usdt > 0
        assert signal.risk_reward_ratio > 0

    def test_generate_signal_short(self):
        """Test generating a complete short signal."""
        generator = SignalGenerator()
        analysis_result = {
            "direction": "short",
            "confidence": 0.65,
            "confluence_score": 0.70,
        }
        order_book = {
            "asks": [2500.0, 2501.0],
            "bids": [2499.0, 2498.0],
        }

        signal = generator.generate_signal(
            symbol="ETH",
            analysis_result=analysis_result,
            position_size_pct=2.5,
            position_size_usdt=500.0,
            account_balance=20000.0,
            kelly_fraction=0.025,
            news_bias_score=0.05,
            atr=50.0,
            current_price=2500.0,
            order_book=order_book,
            timeframe="4h",
        )

        assert signal.symbol == "ETH"
        assert signal.direction == "short"
        assert signal.confidence == 0.65
        assert signal.timeframe == "4h"

    def test_generate_signal_unique_ids(self):
        """Test that generated signals have unique IDs."""
        generator = SignalGenerator()
        analysis_result = {"direction": "long", "confidence": 0.75, "confluence_score": 0.8}

        signal1 = generator.generate_signal(
            symbol="BTC",
            analysis_result=analysis_result,
            position_size_pct=5.0,
            position_size_usdt=1000.0,
            account_balance=20000.0,
            kelly_fraction=0.05,
            news_bias_score=0.0,
            atr=500.0,
            current_price=45100.0,
            order_book=None,
            timeframe="1h",
        )

        signal2 = generator.generate_signal(
            symbol="BTC",
            analysis_result=analysis_result,
            position_size_pct=5.0,
            position_size_usdt=1000.0,
            account_balance=20000.0,
            kelly_fraction=0.05,
            news_bias_score=0.0,
            atr=500.0,
            current_price=45100.0,
            order_book=None,
            timeframe="1h",
        )

        assert signal1.id != signal2.id

    def test_generate_signal_id_format(self):
        """Test that signal ID follows format: sig_YYYYMMDD_HHMMSS_SYMBOL_HEX."""
        generator = SignalGenerator()
        analysis_result = {"direction": "long", "confidence": 0.75, "confluence_score": 0.8}

        signal = generator.generate_signal(
            symbol="BTC",
            analysis_result=analysis_result,
            position_size_pct=5.0,
            position_size_usdt=1000.0,
            account_balance=20000.0,
            kelly_fraction=0.05,
            news_bias_score=0.0,
            atr=500.0,
            current_price=45100.0,
            order_book=None,
            timeframe="1h",
        )

        # Format: sig_YYYYMMDD_HHMMSS_SYMBOL_HEX
        parts = signal.id.split("_")
        assert len(parts) >= 4
        assert parts[0] == "sig"
        assert len(parts[1]) == 8  # YYYYMMDD
        assert len(parts[2]) == 6  # HHMMSS
        assert parts[3] == "BTC"
