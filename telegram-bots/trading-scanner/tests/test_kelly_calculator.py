"""
Tests for Kelly Criterion calculator and position sizing.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from components.kelly_calculator import KellyCalculator
from config import ScannerConfig


class TestKellyFraction:
    """Kelly Criterion fraction calculation tests."""

    def test_kelly_fraction_basic(self):
        """Test basic Kelly Criterion: p=0.6, b=2.0 → ~0.4"""
        calc = KellyCalculator()
        # f* = (p * b - (1 - p)) / b
        # f* = (0.6 * 2.0 - 0.4) / 2.0 = (1.2 - 0.4) / 2.0 = 0.8 / 2.0 = 0.4
        result = calc.kelly_fraction(win_prob=0.6, reward_loss_ratio=2.0)
        assert abs(result - 0.4) < 0.001

    def test_kelly_fraction_conservative(self):
        """Test conservative case: p=0.5, b=2.0 → ~0.25"""
        calc = KellyCalculator()
        # f* = (0.5 * 2.0 - 0.5) / 2.0 = (1.0 - 0.5) / 2.0 = 0.5 / 2.0 = 0.25
        result = calc.kelly_fraction(win_prob=0.5, reward_loss_ratio=2.0)
        assert abs(result - 0.25) < 0.001

    def test_kelly_fraction_negative_result_returns_zero(self):
        """Test that negative Kelly results are clamped to 0"""
        calc = KellyCalculator()
        # p=0.4, b=2.0
        # f* = (0.4 * 2.0 - 0.6) / 2.0 = (0.8 - 0.6) / 2.0 = 0.2 / 2.0 = 0.1 (positive)
        # p=0.3, b=2.0
        # f* = (0.3 * 2.0 - 0.7) / 2.0 = (0.6 - 0.7) / 2.0 = -0.1 / 2.0 = -0.05
        result = calc.kelly_fraction(win_prob=0.3, reward_loss_ratio=2.0)
        assert result == 0.0

    def test_kelly_fraction_high_confidence_high_reward(self):
        """Test high confidence with high reward ratio: p=0.7, b=3.0"""
        calc = KellyCalculator()
        # f* = (0.7 * 3.0 - 0.3) / 3.0 = (2.1 - 0.3) / 3.0 = 1.8 / 3.0 = 0.6
        result = calc.kelly_fraction(win_prob=0.7, reward_loss_ratio=3.0)
        assert abs(result - 0.6) < 0.001


class TestAdjustKellyForConfidence:
    """Kelly Criterion confidence adjustment tests."""

    def test_adjust_kelly_low_confidence(self):
        """Test low confidence (< 0.75): should return unchanged"""
        calc = KellyCalculator()
        kelly_frac = 0.1
        result = calc.adjust_kelly_for_confidence(kelly_frac, confidence=0.70)
        assert result == kelly_frac

    def test_adjust_kelly_medium_confidence(self):
        """Test medium confidence (< 0.75): should return unchanged"""
        calc = KellyCalculator()
        kelly_frac = 0.12
        result = calc.adjust_kelly_for_confidence(kelly_frac, confidence=0.74)
        assert result == kelly_frac

    def test_adjust_kelly_high_confidence(self):
        """Test high confidence (>= 0.75): multiply by 1.5"""
        calc = KellyCalculator()
        kelly_frac = 0.1
        result = calc.adjust_kelly_for_confidence(kelly_frac, confidence=0.80)
        # 0.1 * 1.5 = 0.15
        assert abs(result - 0.15) < 0.001

    def test_adjust_kelly_max_cap_at_015(self):
        """Test that adjusted Kelly is capped at 0.15 (15%)"""
        calc = KellyCalculator()
        kelly_frac = 0.12
        result = calc.adjust_kelly_for_confidence(kelly_frac, confidence=0.85)
        # 0.12 * 1.5 = 0.18, but capped at 0.15
        assert abs(result - 0.15) < 0.001

    def test_adjust_kelly_high_confidence_low_kelly(self):
        """Test high confidence with low Kelly: 0.08 * 1.5 = 0.12 (not capped)"""
        calc = KellyCalculator()
        kelly_frac = 0.08
        result = calc.adjust_kelly_for_confidence(kelly_frac, confidence=0.80)
        assert abs(result - 0.12) < 0.001


class TestApplyPortfolioConstraints:
    """Portfolio constraint application tests."""

    def test_apply_constraints_no_constraint(self):
        """Test with no constraints triggered"""
        calc = KellyCalculator()
        # position_size_pct=5%, symbol='BTC', no open positions, 1000 balance
        size, constraint = calc.apply_portfolio_constraints(
            position_size_pct=5.0,
            symbol="BTC",
            open_positions={},
            account_balance=1000.0,
        )
        assert size == 5.0
        assert constraint == "none"

    def test_apply_constraints_single_coin_limit(self):
        """Test max 50% per coin constraint"""
        calc = KellyCalculator()
        # Try to allocate 55% to BTC when max is 50%
        size, constraint = calc.apply_portfolio_constraints(
            position_size_pct=55.0,
            symbol="BTC",
            open_positions={},
            account_balance=1000.0,
        )
        assert size == 50.0
        assert constraint == "single_coin_max"

    def test_apply_constraints_single_coin_with_existing_position(self):
        """Test single coin constraint with existing position"""
        calc = KellyCalculator()
        # BTC already has 30% of portfolio, trying to add 25% more → would be 55%
        # Should be capped at 50% total, so new position is 20%
        open_positions = {"BTC": 30.0}
        size, constraint = calc.apply_portfolio_constraints(
            position_size_pct=25.0,
            symbol="BTC",
            open_positions=open_positions,
            account_balance=1000.0,
        )
        assert size == 20.0
        assert constraint == "single_coin_max"

    def test_apply_constraints_portfolio_cushion(self):
        """Test max 95% in portfolio (5% cushion) constraint"""
        calc = KellyCalculator()
        # Portfolio already at 90%, trying to add 8% → would be 98%, exceeds 95%
        # Should reduce to 5%
        open_positions = {"BTC": 45.0, "ETH": 45.0}
        size, constraint = calc.apply_portfolio_constraints(
            position_size_pct=8.0,
            symbol="ADA",
            open_positions=open_positions,
            account_balance=1000.0,
        )
        assert size == 5.0
        assert constraint == "portfolio_max"

    def test_apply_constraints_multiple_coins(self):
        """Test with multiple existing positions, no constraint"""
        calc = KellyCalculator()
        open_positions = {"BTC": 20.0, "ETH": 15.0, "ADA": 10.0}
        size, constraint = calc.apply_portfolio_constraints(
            position_size_pct=10.0,
            symbol="SOL",
            open_positions=open_positions,
            account_balance=1000.0,
        )
        # 20 + 15 + 10 + 10 = 55% < 95%, and 10 < 50%
        assert size == 10.0
        assert constraint == "none"

    def test_apply_constraints_at_boundary_single_coin(self):
        """Test exactly at 50% single coin limit"""
        calc = KellyCalculator()
        size, constraint = calc.apply_portfolio_constraints(
            position_size_pct=50.0,
            symbol="BTC",
            open_positions={},
            account_balance=1000.0,
        )
        assert size == 50.0
        assert constraint == "none"

    def test_apply_constraints_at_boundary_portfolio(self):
        """Test exactly at 95% portfolio limit"""
        calc = KellyCalculator()
        open_positions = {"BTC": 50.0, "ETH": 45.0}
        size, constraint = calc.apply_portfolio_constraints(
            position_size_pct=5.0,
            symbol="ADA",
            open_positions=open_positions,
            account_balance=1000.0,
        )
        # 50 + 45 + 5 = 100%, exceeds 95%
        # Should reduce to 0% (100 - 95 = 5, but would be 100, so cap at 5)
        assert size == 0.0
        assert constraint == "portfolio_max"


class TestCalculatePositionSizeUsdt:
    """Position size in USDT calculation tests."""

    def test_calculate_position_size_usdt_basic(self):
        """Test basic position size calculation"""
        calc = KellyCalculator()
        # balance=1000, position_size_pct=10 → 100 USDT
        result = calc.calculate_position_size_usdt(
            balance=1000.0, position_size_pct=10.0
        )
        assert abs(result - 100.0) < 0.01

    def test_calculate_position_size_usdt_fractional(self):
        """Test fractional position size"""
        calc = KellyCalculator()
        # balance=5000, position_size_pct=2.5 → 125 USDT
        result = calc.calculate_position_size_usdt(
            balance=5000.0, position_size_pct=2.5
        )
        assert abs(result - 125.0) < 0.01

    def test_calculate_position_size_usdt_large_balance(self):
        """Test with large balance"""
        calc = KellyCalculator()
        # balance=50000, position_size_pct=15 → 7500 USDT
        result = calc.calculate_position_size_usdt(
            balance=50000.0, position_size_pct=15.0
        )
        assert abs(result - 7500.0) < 0.01

    def test_calculate_position_size_usdt_zero(self):
        """Test with zero position size"""
        calc = KellyCalculator()
        result = calc.calculate_position_size_usdt(balance=1000.0, position_size_pct=0.0)
        assert result == 0.0

    def test_calculate_position_size_usdt_max(self):
        """Test with 100% position (edge case)"""
        calc = KellyCalculator()
        result = calc.calculate_position_size_usdt(
            balance=1000.0, position_size_pct=100.0
        )
        assert abs(result - 1000.0) < 0.01
