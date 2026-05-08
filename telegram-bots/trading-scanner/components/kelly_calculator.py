"""
Kelly Criterion calculator and position sizing module.
Implements Kelly Criterion for optimal bet sizing and applies portfolio constraints.
"""

import sys
from pathlib import Path
from typing import Dict, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import ScannerConfig


class KellyCalculator:
    """
    Kelly Criterion calculator for position sizing with portfolio constraints.

    Implements:
    - Kelly Criterion fraction calculation: f* = (p * b - (1 - p)) / b
    - Confidence-based adjustment (increase sizing for high-confidence trades)
    - Portfolio constraints (single coin max, portfolio cushion)
    - Position size conversion to USDT
    """

    def __init__(self, config: ScannerConfig = None):
        """
        Initialize Kelly Calculator.

        Args:
            config: ScannerConfig instance (uses default if None)
        """
        self.config = config or ScannerConfig()
        self.max_single_coin_pct = self.config.MAX_SINGLE_COIN_PCT
        self.max_portfolio_allocation = 95.0  # Keep 5% cushion
        self.max_adjusted_kelly = 0.15  # 15% cap for adjusted Kelly

    def kelly_fraction(self, win_prob: float, reward_loss_ratio: float) -> float:
        """
        Calculate Kelly Criterion fraction for position sizing.

        Formula: f* = (p * b - (1 - p)) / b

        Args:
            win_prob: Probability of win (0-1)
            reward_loss_ratio: Reward/Loss ratio (b-value)

        Returns:
            Kelly fraction as float (0-1), clamped to >= 0
        """
        kelly_fraction_result = (win_prob * reward_loss_ratio - (1 - win_prob)) / reward_loss_ratio
        return max(0.0, kelly_fraction_result)

    def adjust_kelly_for_confidence(
        self, kelly_frac: float, confidence: float
    ) -> float:
        """
        Adjust Kelly fraction based on signal confidence.

        High confidence (>= 0.75) multiplies by 1.5, capped at 15%.
        Low confidence returns unchanged.

        Args:
            kelly_frac: Base Kelly fraction (0-1)
            confidence: Signal confidence (0-1)

        Returns:
            Adjusted Kelly fraction, capped at max_adjusted_kelly (0.15)
        """
        if confidence >= 0.75:
            adjusted = kelly_frac * 1.5
            return min(adjusted, self.max_adjusted_kelly)
        return kelly_frac

    def apply_portfolio_constraints(
        self,
        position_size_pct: float,
        symbol: str,
        open_positions: Dict[str, float],
        account_balance: float,
    ) -> Tuple[float, str]:
        """
        Apply portfolio constraints to position size.

        Constraints:
        1. Single coin max: 50% of portfolio
        2. Portfolio max: 95% allocated (5% cushion)

        Args:
            position_size_pct: Desired position size (% of portfolio)
            symbol: Trading symbol (e.g., 'BTC')
            open_positions: Dict of open positions {symbol: pct_of_portfolio}
            account_balance: Account balance in USDT (for logging)

        Returns:
            Tuple of (adjusted_size_pct, constraint_name)
            constraint_name: 'none', 'single_coin_max', or 'portfolio_max'
        """
        current_symbol_exposure = open_positions.get(symbol, 0.0)
        total_portfolio_usage = sum(open_positions.values())

        # Constraint 1: Single coin max (50%)
        if current_symbol_exposure + position_size_pct > self.max_single_coin_pct:
            adjusted_size = self.max_single_coin_pct - current_symbol_exposure
            return (max(0.0, adjusted_size), "single_coin_max")

        # Constraint 2: Portfolio max (95% usage, keep 5% cushion)
        if total_portfolio_usage + position_size_pct > self.max_portfolio_allocation:
            available_pct = self.max_portfolio_allocation - total_portfolio_usage
            return (max(0.0, available_pct), "portfolio_max")

        return (position_size_pct, "none")

    def adjust_for_market_conditions(
        self, kelly_frac: float, adx: float, cmf: float
    ) -> float:
        """Scale Kelly by ADX (trend strength) and CMF (money flow)."""
        if adx < 15:
            return 0.0  # флет — не торгуем
        multiplier = 1.0
        if adx > 35:
            multiplier *= 1.3
        elif adx > 25:
            multiplier *= 1.1
        if cmf > 0.1:
            multiplier *= 1.2
        elif cmf < -0.1:
            multiplier *= 0.8
        return min(kelly_frac * multiplier, self.max_adjusted_kelly)

    def calculate_position_size_usdt(
        self, balance: float, position_size_pct: float
    ) -> float:
        """
        Convert position size percentage to USDT amount.

        Args:
            balance: Account balance in USDT
            position_size_pct: Position size as percentage (0-100)

        Returns:
            Position size in USDT
        """
        return balance * (position_size_pct / 100.0)

    def calculate_complete_position_size(
        self,
        win_prob: float,
        reward_loss_ratio: float,
        confidence: float,
        symbol: str,
        open_positions: Dict[str, float],
        account_balance: float,
    ) -> Tuple[float, float, str]:
        """
        Calculate complete position size with all steps applied.

        Args:
            win_prob: Probability of winning trade (0-1)
            reward_loss_ratio: Reward/Loss ratio
            confidence: Signal confidence (0-1)
            symbol: Trading symbol
            open_positions: Current open positions dict
            account_balance: Account balance in USDT

        Returns:
            Tuple of (position_size_pct, position_size_usdt, constraint_applied)
        """
        # Step 1: Calculate base Kelly fraction
        kelly_frac = self.kelly_fraction(win_prob, reward_loss_ratio)

        # Step 2: Adjust for confidence
        adjusted_kelly = self.adjust_kelly_for_confidence(kelly_frac, confidence)

        # Step 3: Convert to percentage (Kelly fraction is already 0-1)
        position_size_pct = adjusted_kelly * 100.0

        # Step 4: Apply portfolio constraints
        final_size_pct, constraint = self.apply_portfolio_constraints(
            position_size_pct, symbol, open_positions, account_balance
        )

        # Step 5: Convert to USDT
        position_size_usdt = self.calculate_position_size_usdt(
            account_balance, final_size_pct
        )

        return (final_size_pct, position_size_usdt, constraint)
