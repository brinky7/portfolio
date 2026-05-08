"""
Async Redis client for Trading Scanner.
Handles all Redis operations: data retrieval, signal publishing, and subscription management.
"""

import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Set
from datetime import datetime

try:
    import aioredis
except ImportError:
    aioredis = None

logger = logging.getLogger(__name__)


class RedisClient:
    """Async Redis client for scanner operations."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        encoding: str = "utf-8"
    ):
        """
        Initialize RedisClient.

        Args:
            host: Redis host address
            port: Redis port
            db: Database number
            encoding: Character encoding
        """
        self.host = host
        self.port = port
        self.db = db
        self.encoding = encoding
        self.redis = None

    async def connect(self) -> None:
        """
        Establish connection to Redis.

        Raises:
            RuntimeError: If aioredis is not installed
            ConnectionError: If connection fails
        """
        if aioredis is None:
            raise RuntimeError("aioredis is not installed")

        try:
            url = f"redis://{self.host}:{self.port}/{self.db}"
            self.redis = await aioredis.from_url(url, encoding=self.encoding)
            logger.info(f"Connected to Redis at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self.redis:
            self.redis.close()
            await self.redis.wait_closed()
            logger.info("Disconnected from Redis")

    async def get_balance(self) -> float:
        """
        Get account balance from Redis.

        Returns:
            Account balance in USDT (0.0 if not found)

        Raises:
            ValueError: If stored value is not a valid float
        """
        try:
            value = await self.redis.get("account:balance")
            if value is None:
                return 0.0
            return float(value)
        except ValueError as e:
            logger.error(f"Invalid balance value: {value}")
            raise ValueError(f"Cannot convert balance to float: {value}") from e

    async def get_open_positions(self) -> List[Dict[str, Any]]:
        """
        Get list of open positions from Redis.

        Returns:
            List of position dicts (empty list if not found)

        Raises:
            json.JSONDecodeError: If stored JSON is invalid
        """
        try:
            value = await self.redis.get("open_positions")
            if value is None:
                return []
            return json.loads(value)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in open_positions: {value}")
            raise

    async def get_whitelist_pairs(self) -> Set[str]:
        """
        Get set of whitelisted trading pairs from Redis.

        Returns:
            Set of symbol strings (empty set if not found)
        """
        try:
            members = await self.redis.smembers("whitelist_pairs")
            return set(members) if members else set()
        except Exception as e:
            logger.error(f"Error retrieving whitelist pairs: {e}")
            raise

    async def get_volatility(self, symbol: str) -> float:
        """
        Get volatility for a symbol from Redis.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")

        Returns:
            Volatility value (0.0 if not found)

        Raises:
            ValueError: If stored value is not a valid float
        """
        try:
            value = await self.redis.get(f"volatility:{symbol}")
            if value is None:
                return 0.0
            return float(value)
        except ValueError as e:
            logger.error(f"Invalid volatility value for {symbol}: {value}")
            raise ValueError(f"Cannot convert volatility to float: {value}") from e

    async def get_ohlcv(self, symbol: str, timeframe: str = "4h") -> List[List[Any]]:
        """
        Get OHLCV candle data for a symbol from Redis.

        Args:
            symbol: Trading pair symbol
            timeframe: Candle timeframe (default: "4h")

        Returns:
            List of OHLCV candles (empty list if not found)

        Raises:
            json.JSONDecodeError: If stored JSON is invalid
        """
        try:
            key = f"ohlcv:{symbol}:{timeframe}"
            value = await self.redis.get(key)
            if value is None:
                return []
            return json.loads(value)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in OHLCV data for {symbol}:{timeframe}: {value}")
            raise

    async def get_correlations(self) -> Dict[str, float]:
        """
        Get correlation matrix from Redis.

        Returns:
            Dict of symbol pairs to correlation values (empty dict if not found)

        Raises:
            json.JSONDecodeError: If stored JSON is invalid
        """
        try:
            value = await self.redis.get("correlations")
            if value is None:
                return {}
            return json.loads(value)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in correlations: {value}")
            raise

    async def get_portfolio_metrics(self) -> Dict[str, float]:
        """
        Get portfolio risk metrics from Redis.

        Returns:
            Dict with keys: variance, max_drawdown, margin_level (empty dict if not found)

        Raises:
            json.JSONDecodeError: If stored JSON is invalid
        """
        try:
            value = await self.redis.get("portfolio_metrics")
            if value is None:
                return {}
            return json.loads(value)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in portfolio_metrics: {value}")
            raise

    async def get_news_bias(self, symbol: str) -> float:
        """
        Get news sentiment bias for a symbol from Redis.

        Args:
            symbol: Trading pair symbol

        Returns:
            News bias value between -1 and 1 (0.0 if not found)

        Raises:
            ValueError: If stored value is not a valid float
        """
        try:
            value = await self.redis.get(f"news_bias:{symbol}")
            if value is None:
                return 0.0
            return float(value)
        except ValueError as e:
            logger.error(f"Invalid news bias value for {symbol}: {value}")
            raise ValueError(f"Cannot convert news bias to float: {value}") from e

    async def publish_signal(self, signal: Dict[str, Any]) -> bool:
        """
        Publish a trading signal to Redis queue and channel.

        Args:
            signal: Signal dict with symbol, side, confidence, etc.

        Returns:
            True if published successfully

        Raises:
            Exception: If Redis operation fails
        """
        try:
            signal_json = json.dumps(signal)

            # Push to queue
            await self.redis.lpush("scanner:signals", signal_json)

            # Publish to channel for real-time subscribers
            await self.redis.publish("scanner:signals", signal_json)

            logger.info(f"Published signal: {signal.get('symbol', 'unknown')} {signal.get('side', 'unknown')}")
            return True
        except Exception as e:
            logger.error(f"Error publishing signal: {e}")
            raise

    async def move_to_dlq(self, signal: Dict[str, Any], error: str) -> bool:
        """
        Move a failed signal to Dead Letter Queue.

        Args:
            signal: Original signal that failed
            error: Error message describing the failure

        Returns:
            True if moved successfully

        Raises:
            Exception: If Redis operation fails
        """
        try:
            dlq_entry = {
                "signal": signal,
                "error": error,
                "timestamp": datetime.utcnow().isoformat(),
                "attempt_count": 1
            }
            dlq_json = json.dumps(dlq_entry)

            await self.redis.lpush("scanner:dlq", dlq_json)

            logger.warning(f"Moved signal to DLQ: {signal.get('symbol', 'unknown')} - {error}")
            return True
        except Exception as e:
            logger.error(f"Error moving to DLQ: {e}")
            raise

    async def get_dlq_length(self) -> int:
        """
        Get the number of messages in Dead Letter Queue.

        Returns:
            Number of DLQ entries
        """
        try:
            length = await self.redis.llen("scanner:dlq")
            return length if length else 0
        except Exception as e:
            logger.error(f"Error getting DLQ length: {e}")
            raise

    async def subscribe_portfolio_updates(
        self,
        callback: Callable[[Dict[str, Any]], Any],
        timeout: Optional[float] = None
    ) -> None:
        """
        Subscribe to portfolio update messages and call callback for each.

        Args:
            callback: Async function to call with each portfolio update message
            timeout: Optional timeout in seconds (None = no timeout)

        Raises:
            Exception: If subscription or message processing fails
        """
        try:
            channels = await self.redis.subscribe("scanner:positions")
            channel = channels[0]

            async def consume():
                async for message in channel.iter():
                    try:
                        data = json.loads(message["data"])
                        if asyncio.iscoroutinefunction(callback):
                            await callback(data)
                        else:
                            callback(data)
                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON in portfolio update: {message.get('data')}")
                    except Exception as e:
                        logger.error(f"Error in portfolio update callback: {e}")

            if timeout:
                await asyncio.wait_for(consume(), timeout=timeout)
            else:
                await consume()

        except asyncio.TimeoutError:
            logger.info("Portfolio subscription timeout (expected in tests)")
        except Exception as e:
            logger.error(f"Error subscribing to portfolio updates: {e}")
            raise

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
