"""
Signal Generator module for creating and managing trading signals.
Implements signal generation with entry, stop-loss, and take-profit calculations.
"""

import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import ScannerConfig


@dataclass
class Signal:
    """
    Represents a trading signal with entry/exit levels and position sizing.

    Attributes:
        id: Unique signal identifier (sig_YYYYMMDD_HHMMSS_SYMBOL_HEX)
        timestamp: Signal generation timestamp
        symbol: Trading symbol (e.g., 'BTC', 'ETH')
        timeframe: Timeframe (e.g., '1h', '4h', '1d')
        direction: Trade direction ('long' or 'short')
        confidence: Signal confidence (0-1)
        entry_price: Entry price level
        stop_loss: Stop-loss price level
        take_profit: Take-profit price level
        position_size_usdt: Position size in USDT
        position_size_pct: Position size as percentage of account
        kelly_fraction: Kelly Criterion fraction (0-1)
        risk_usdt: Risk amount in USDT
        reward_usdt: Reward amount in USDT
        risk_reward_ratio: Risk/Reward ratio
        confluence_score: Multi-timeframe confluence (0-1)
        news_bias_score: News sentiment bias (-1 to 1)
        order_book_depth: Order book data for entry level
        indicators_state: Dictionary of indicator states
    """

    id: str
    timestamp: datetime
    symbol: str
    timeframe: str
    direction: str
    confidence: float
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size_usdt: float
    position_size_pct: float
    kelly_fraction: float
    risk_usdt: float
    reward_usdt: float
    risk_reward_ratio: float
    confluence_score: float
    news_bias_score: float
    order_book_depth: Optional[Dict] = None
    indicators_state: Optional[Dict] = None

    def to_dict(self) -> Dict:
        """
        Serialize Signal to dictionary for Redis storage.

        Returns:
            Dictionary representation with timestamp as ISO format string
        """
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


class SignalGenerator:
    """
    Generates trading signals with calculated entry, stop-loss, and take-profit levels.

    Methods:
        - calculate_entry_price(): Determine entry price from order book
        - calculate_stop_loss(): Calculate stop-loss with ATR and minimum distance
        - calculate_take_profit(): Calculate take-profit from entry and risk
        - calculate_risk_reward(): Compute risk, reward, and ratio
        - generate_signal(): Create complete signal with all calculations
    """

    def __init__(self, config: ScannerConfig = None):
        """
        Initialize Signal Generator.

        Args:
            config: ScannerConfig instance (uses default if None)
        """
        self.config = config or ScannerConfig()

    def calculate_entry_price(
        self,
        symbol: str,
        direction: str,
        current_price: float,
        order_book: Optional[Dict],
    ) -> float:
        """
        Calculate entry price from order book or current price.

        Rules:
        - Long: use ask price (seller price, we buy at asking price)
        - Short: use bid price (buyer price, we sell at bid price)
        - If no order book: use current price

        Args:
            symbol: Trading symbol
            direction: 'long' or 'short'
            current_price: Current market price
            order_book: Order book dict with 'asks' and 'bids' lists

        Returns:
            Entry price as float
        """
        if order_book is None:
            return current_price

        if direction == "long":
            # For long: buy at ask (seller's price)
            return order_book["asks"][0]
        else:  # short
            # For short: sell at bid (buyer's price)
            return order_book["bids"][0]

    def calculate_stop_loss(
        self,
        symbol: str,
        entry_price: float,
        direction: str,
        atr: float,
        atr_multiplier: float = 2.0,
        min_sl_pct: float = 1.5,
    ) -> float:
        """
        Calculate stop-loss with ATR-based and minimum distance constraints.

        Rules:
        - Long: entry - (atr * multiplier), minimum entry * (1 - min_sl_pct/100)
        - Short: entry + (atr * multiplier), minimum entry * (1 + min_sl_pct/100)

        Args:
            symbol: Trading symbol
            entry_price: Entry price
            direction: 'long' or 'short'
            atr: Average True Range value
            atr_multiplier: ATR multiplier (default 2.0)
            min_sl_pct: Minimum SL distance as percentage (default 1.5%)

        Returns:
            Stop-loss price as float
        """
        atr_distance = atr * atr_multiplier

        if direction == "long":
            calculated_sl = entry_price - atr_distance
            min_sl = entry_price * (1 - min_sl_pct / 100.0)
            # Return the closer (larger) of the two to ensure minimum distance
            return max(calculated_sl, min_sl)
        else:  # short
            calculated_sl = entry_price + atr_distance
            min_sl = entry_price * (1 + min_sl_pct / 100.0)
            # Return the closer (smaller) of the two to ensure minimum distance
            return min(calculated_sl, min_sl)

    def calculate_take_profit(
        self,
        entry_price: float,
        stop_loss: float,
        direction: str,
        risk_reward_ratio: float = 2.0,
    ) -> float:
        """
        Calculate take-profit from entry, stop-loss, and risk/reward ratio.

        Rules:
        - distance_to_sl = |entry - sl|
        - Long: entry + (distance * ratio)
        - Short: entry - (distance * ratio)

        Args:
            entry_price: Entry price
            stop_loss: Stop-loss price
            direction: 'long' or 'short'
            risk_reward_ratio: Risk/Reward ratio (default 2.0)

        Returns:
            Take-profit price as float
        """
        distance = abs(entry_price - stop_loss)

        if direction == "long":
            return entry_price + (distance * risk_reward_ratio)
        else:  # short
            return entry_price - (distance * risk_reward_ratio)

    def calculate_risk_reward(
        self,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
    ) -> Tuple[float, float, float]:
        """
        Calculate risk, reward, and ratio.

        Args:
            entry_price: Entry price
            stop_loss: Stop-loss price
            take_profit: Take-profit price

        Returns:
            Tuple of (risk_usdt, reward_usdt, risk_reward_ratio)
        """
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)

        if risk == 0:
            ratio = float("inf")
        else:
            ratio = reward / risk

        return (risk, reward, ratio)

    def generate_signal(
        self,
        symbol: str,
        analysis_result: Dict,
        position_size_pct: float,
        position_size_usdt: float,
        account_balance: float,
        kelly_fraction: float,
        news_bias_score: float,
        atr: float,
        current_price: float,
        order_book: Optional[Dict],
        timeframe: str,
    ) -> Signal:
        """
        Generate a complete trading signal with all calculations.

        Args:
            symbol: Trading symbol
            analysis_result: Dict with 'direction', 'confidence', 'confluence_score'
            position_size_pct: Position size as percentage
            position_size_usdt: Position size in USDT
            account_balance: Account balance in USDT
            kelly_fraction: Kelly Criterion fraction
            news_bias_score: News sentiment bias
            atr: Average True Range value
            current_price: Current market price
            order_book: Order book data or None
            timeframe: Timeframe (e.g., '1h', '4h')

        Returns:
            Signal object with calculated entry/SL/TP
        """
        direction = analysis_result["direction"]
        confidence = analysis_result["confidence"]
        confluence_score = analysis_result["confluence_score"]

        # Calculate entry price
        entry_price = self.calculate_entry_price(
            symbol=symbol,
            direction=direction,
            current_price=current_price,
            order_book=order_book,
        )

        # Calculate stop-loss
        stop_loss = self.calculate_stop_loss(
            symbol=symbol,
            entry_price=entry_price,
            direction=direction,
            atr=atr,
            atr_multiplier=2.0,
            min_sl_pct=1.5,
        )

        # Calculate take-profit
        take_profit = self.calculate_take_profit(
            entry_price=entry_price,
            stop_loss=stop_loss,
            direction=direction,
            risk_reward_ratio=2.0,
        )

        # Calculate risk and reward
        risk_usdt, reward_usdt, risk_reward_ratio = self.calculate_risk_reward(
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

        # Generate unique signal ID: sig_YYYYMMDD_HHMMSS_SYMBOL_HEX
        now = datetime.now()
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")
        unique_hex = uuid4().hex[:8]
        signal_id = f"sig_{timestamp_str}_{symbol}_{unique_hex}"

        # Create signal
        signal = Signal(
            id=signal_id,
            timestamp=now,
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            confidence=confidence,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size_usdt=position_size_usdt,
            position_size_pct=position_size_pct,
            kelly_fraction=kelly_fraction,
            risk_usdt=risk_usdt,
            reward_usdt=reward_usdt,
            risk_reward_ratio=risk_reward_ratio,
            confluence_score=confluence_score,
            news_bias_score=news_bias_score,
            order_book_depth=order_book,
            indicators_state=None,
        )

        return signal
