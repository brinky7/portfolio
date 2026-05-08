"""
DataFetcher with retry logic and Redis/CCXT fallback.
Handles fetching OHLCV data, account state, and symbol data with resilience.
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

import aiohttp
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from config import ScannerConfig

logger = logging.getLogger(__name__)


class DataFetcher:
    """Fetches market data with retry logic and Redis/CCXT fallback."""

    def __init__(self, redis_client, ccxt_exchange=None):
        """
        Initialize DataFetcher.

        Args:
            redis_client: AsyncIO Redis client for caching
            ccxt_exchange: CCXT exchange instance (optional, for fallback)
        """
        self.redis_client = redis_client
        self.ccxt_exchange = ccxt_exchange
        self.config = ScannerConfig()
        self._connected = False

    async def connect(self) -> None:
        """Establish connections to Redis and exchange."""
        self._connected = True
        logger.info("DataFetcher connected")

    async def disconnect(self) -> None:
        """Close connections to Redis and exchange."""
        self._connected = False
        logger.info("DataFetcher disconnected")

    @retry(
        stop=stop_after_attempt(ScannerConfig.RETRY_MAX_ATTEMPTS),
        wait=wait_exponential(
            multiplier=ScannerConfig.RETRY_BASE_DELAY_SECONDS,
            min=ScannerConfig.RETRY_BASE_DELAY_SECONDS,
            max=ScannerConfig.RETRY_MAX_DELAY_SECONDS,
        ),
        retry=retry_if_exception_type((asyncio.TimeoutError, aiohttp.ClientError)),
        reraise=True,
    )
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "4h",
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """
        Fetch OHLCV data with Redis cache and CCXT fallback.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            timeframe: Timeframe (e.g., "4h", "1d")
            limit: Number of candles

        Returns:
            List of OHLCV candles as dicts with keys: timestamp, open, high, low, close, volume
        """
        cache_key = f"ohlcv:{symbol}:{timeframe}"

        # Try Redis first
        try:
            cached = await self.redis_client.get(cache_key)
            if cached:
                data = json.loads(cached)
                logger.debug(f"OHLCV {symbol}/{timeframe} from Redis: {len(data)} candles")
                return data
        except Exception as e:
            logger.warning(f"Redis get failed for {cache_key}: {e}")

        # Fallback to CCXT
        if not self.ccxt_exchange:
            logger.error("No CCXT exchange configured for fallback")
            return []

        try:
            ohlcv_data = await self.ccxt_exchange.fetch_ohlcv(
                symbol, timeframe, limit=limit
            )
        except Exception as e:
            logger.error(f"CCXT fetch_ohlcv failed: {e}")
            raise

        # Convert CCXT format [time, open, high, low, close, vol] to dict
        converted = []
        for candle in ohlcv_data:
            converted.append({
                "timestamp": int(candle[0]),
                "open": float(candle[1]),
                "high": float(candle[2]),
                "low": float(candle[3]),
                "close": float(candle[4]),
                "volume": float(candle[5]),
            })

        # Cache result
        try:
            await self.redis_client.set(cache_key, json.dumps(converted), ex=3600)
        except Exception as e:
            logger.warning(f"Failed to cache OHLCV: {e}")

        logger.debug(f"OHLCV {symbol}/{timeframe} from CCXT: {len(converted)} candles")
        return converted

    @retry(
        stop=stop_after_attempt(ScannerConfig.RETRY_MAX_ATTEMPTS),
        wait=wait_exponential(
            multiplier=ScannerConfig.RETRY_BASE_DELAY_SECONDS,
            min=ScannerConfig.RETRY_BASE_DELAY_SECONDS,
            max=ScannerConfig.RETRY_MAX_DELAY_SECONDS,
        ),
        retry=retry_if_exception_type((asyncio.TimeoutError, aiohttp.ClientError)),
        reraise=True,
    )
    async def fetch_account_state(self) -> Dict[str, Any]:
        """
        Fetch account balance and portfolio metrics.

        Returns:
            Dict with balance, portfolio_metrics (VaR, max_dd, margin)
        """
        if not self.ccxt_exchange:
            logger.error("No CCXT exchange configured")
            return {}

        try:
            balance = await self.ccxt_exchange.fetch_balance()
        except Exception as e:
            logger.error(f"Failed to fetch balance: {e}")
            raise

        # Calculate portfolio metrics (placeholder)
        portfolio_metrics = {
            "var_95": 0.0,  # Value at Risk
            "max_drawdown_pct": 0.0,
            "margin_ratio": 0.0,
            "total_balance_usdt": float(balance.get("USDT", {}).get("total", 0.0)),
        }

        return {
            "balance": balance,
            "portfolio_metrics": portfolio_metrics,
        }

    async def fetch_state(self) -> Dict[str, Any]:
        """
        Fetch complete account state.

        Returns:
            Dict with balance, positions, whitelist, correlations, portfolio_metrics,
            volatility, news_biases
        """
        account_data = await self.fetch_account_state()

        return {
            "balance": account_data.get("balance", {}),
            "positions": [],  # Placeholder
            "whitelist": self.config.DEFAULT_SYMBOLS,
            "correlations": {},  # Placeholder
            "portfolio_metrics": account_data.get("portfolio_metrics", {}),
            "volatility": {},  # Filled by volatility analyzer
            "news_biases": {},  # Filled by news analyzer
        }

    async def fetch_symbol_data(
        self, symbol: str, state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Fetch symbol-specific data.

        Args:
            symbol: Trading pair
            state: Current account state

        Returns:
            Dict with ohlcv_4h, ohlcv_1d, volatility, news_bias
        """
        ohlcv_4h = await self.fetch_ohlcv(symbol, timeframe="4h", limit=200)
        ohlcv_1d = await self.fetch_ohlcv(symbol, timeframe="1d", limit=100)

        return {
            "ohlcv_4h": ohlcv_4h,
            "ohlcv_1d": ohlcv_1d,
            "volatility": 0.0,  # Filled by volatility analyzer
            "news_bias": 0.0,  # Filled by news analyzer
        }
