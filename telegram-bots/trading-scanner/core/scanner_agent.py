"""
ScannerAgent: Main orchestrator for async crypto pair scanning.
Coordinates data fetching, analysis, filtering, sizing, and signal publishing.
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import ScannerConfig
from components.data_fetcher import DataFetcher
from components.market_analyzer import MarketAnalyzer
from components.signal_generator import SignalGenerator, Signal
from components.correlation_filter import CorrelationFilter
from components.kelly_calculator import KellyCalculator
from components.news_filter import NewsFilter
from core.database import Database
from core.redis_client import RedisClient
from monitoring.logger import StructuredLogger
from monitoring.prometheus_metrics import PrometheusMetrics


class ScannerAgent:
    """
    Async scanner that analyzes 150+ crypto pairs every 15 minutes.
    Generates Kelly-Criterion-sized signals for Supervisor/Executor agents.
    """

    def __init__(self, config: Optional[ScannerConfig] = None, redis_client: Optional[RedisClient] = None, ccxt_exchange=None):
        self.config = config or ScannerConfig()
        self.db = Database(str(self.config.SQLITE_DB_PATH))
        self.logger = StructuredLogger(db=self.db)
        self.redis = redis_client or RedisClient(
            host=self.config.REDIS_HOST,
            port=self.config.REDIS_PORT
        )
        self.data_fetcher = DataFetcher(redis_client=self.redis.client, ccxt_exchange=ccxt_exchange)
        self.market_analyzer = MarketAnalyzer()
        self.signal_generator = SignalGenerator(config=self.config)
        self.correlation_filter = CorrelationFilter()
        self.kelly_calc = KellyCalculator()
        self.news_filter = NewsFilter()
        self.metrics = PrometheusMetrics()

        self.is_running = False
        self.cycle_count = 0
        self.whitelist_pairs: Set[str] = set()
        self.portfolio_state: Dict = {}

    async def initialize(self) -> None:
        """Initialize Redis, database, and Prometheus."""
        self.logger.info("ScannerAgent initializing...")
        await self.redis.connect()
        await self.db.connect()
        await self.db.initialize_schema()
        self.metrics.start_server(self.config.PROMETHEUS_PORT)
        self.logger.info("ScannerAgent ready")

    async def shutdown(self) -> None:
        """Gracefully close connections."""
        self.is_running = False
        self.logger.info("ScannerAgent shutting down...")
        await self.redis.disconnect()
        await self.db.disconnect()
        self.metrics.stop_server()
        self.logger.info("ScannerAgent shutdown complete")

    async def fetch_state_from_redis(self) -> Dict:
        """
        Fetch current portfolio state from Redis via data_fetcher.
        Returns dict with balance, whitelist, and other portfolio metrics.
        """
        try:
            account_state = await self.data_fetcher.fetch_account_state()
            # Try portfolio_metrics first, fall back to balance
            total_balance = account_state.get("portfolio_metrics", {}).get("total_balance_usdt") or account_state.get("balance", 0.0)

            # Get whitelist from Redis (or use default symbols)
            whitelist = self.config.DEFAULT_SYMBOLS

            state = {
                "balance": total_balance,
                "positions": [],  # Placeholder: fetch from trading agent state
                "whitelist": whitelist,
            }

            return state
        except Exception as e:
            self.logger.error(f"Error fetching Redis state: {e}")
            raise

    async def analyze_pairs(self, state: Dict, whitelist: List[str]) -> List[Dict]:
        """
        Analyze all pairs in parallel: fetch OHLCV, compute indicators.
        Returns list of analysis results (one per symbol).
        """
        tasks = []
        for symbol in whitelist:
            tasks.append(self._analyze_single_pair(symbol))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions, log them
        analysis_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                symbol = whitelist[i]
                self.logger.warning(f"Analysis failed for {symbol}: {result}")
                continue
            if result:
                analysis_results.append(result)

        return analysis_results

    async def _analyze_single_pair(self, symbol: str) -> Optional[Dict]:
        """Analyze a single pair using 4h timeframe."""
        try:
            import pandas as pd

            # Fetch OHLCV for 4h
            ohlcv_data = await self.data_fetcher.fetch_ohlcv(
                symbol, "4h", limit=self.config.OHLCV_CANDLE_LIMIT
            )

            if not ohlcv_data:
                self.logger.debug(f"No OHLCV data for {symbol}")
                return None

            # Convert to DataFrame for analysis (handle both list and dict formats)
            if isinstance(ohlcv_data[0], (list, tuple)):
                # CCXT format: [[timestamp, open, high, low, close, volume], ...]
                df = pd.DataFrame(
                    ohlcv_data,
                    columns=["time", "open", "high", "low", "close", "volume"]
                )
            else:
                # Dict format
                df = pd.DataFrame(ohlcv_data)
                df = df.rename(columns={
                    "timestamp": "time",
                    "open": "open",
                    "high": "high",
                    "low": "low",
                    "close": "close",
                    "volume": "volume"
                })

            # Use MarketAnalyzer to analyze pair
            analysis = await self.market_analyzer.analyze_pair(symbol, ohlcv_data, dataframe=df)

            if not analysis:
                return None

            return {
                "symbol": symbol,
                "timeframe": "4h",
                "direction": analysis.get("direction", "neutral"),
                "confidence": analysis.get("confidence", 0.0),
                "confluence_score": analysis.get("confluence_score", 0),
                "indicators": analysis.get("indicators", {}),
                "current_price": float(df["close"].iloc[-1]) if len(df) > 0 else 0.0,
            }
        except Exception as e:
            self.logger.warning(f"Error analyzing {symbol}: {e}")
            return None

    async def filter_signals(
        self, analysis: List[Dict], state: Dict
    ) -> List[Dict]:
        """
        Apply filters: confidence, position limits.
        """
        filtered = []
        positions = state.get("positions", [])
        open_count = len(positions)

        for analysis_result in analysis:
            symbol = analysis_result["symbol"]

            # Filter 1: Position limit
            if open_count >= self.config.MAX_CONCURRENT_POSITIONS:
                self.logger.debug(f"{symbol}: max positions reached")
                continue

            # Filter 2: Confidence threshold
            if analysis_result["confidence"] < self.config.MIN_CONFIDENCE:
                self.logger.debug(f"{symbol}: low confidence {analysis_result['confidence']:.2f}")
                continue

            # Filter 3: Direction should not be neutral
            if analysis_result["direction"] == "neutral":
                self.logger.debug(f"{symbol}: neutral direction")
                continue

            filtered.append(analysis_result)
            self.logger.info(f"{symbol}: signal passed filters (conf={analysis_result['confidence']:.2f}, dir={analysis_result['direction']})")

        return filtered

    async def size_positions(
        self, signals: List[Dict], balance: float, positions: List[Dict]
    ) -> List[Signal]:
        """
        Apply Kelly Criterion sizing with portfolio constraints.
        Generate Signal objects with entry/SL/TP.
        """
        sized_signals = []

        for signal_data in signals:
            symbol = signal_data["symbol"]
            direction = signal_data["direction"]
            confidence = signal_data["confidence"]
            current_price = signal_data.get("current_price", 0.0)

            # Kelly fraction (use confidence as win probability, default RR ratio)
            kelly_frac = self.kelly_calc.kelly_fraction(
                confidence, reward_loss_ratio=self.config.RISK_REWARD_RATIO
            )

            # Adjust for confidence
            kelly_frac = self.kelly_calc.adjust_kelly_for_confidence(kelly_frac, confidence)

            # Position size
            position_size_pct = kelly_frac * 100

            # Caps
            position_size_pct = min(position_size_pct, self.config.POSITION_SIZE_PCT_HIGH_CONF)
            position_size_usdt = (position_size_pct / 100) * balance

            if position_size_usdt < 1.0:  # Minimum position
                self.logger.debug(f"{symbol}: position too small ({position_size_usdt:.2f} USDT)")
                continue

            # Check single-coin limit
            coin_exposure = sum(
                p.get("size_usdt", 0) for p in positions if p.get("symbol") == symbol
            )
            if coin_exposure + position_size_usdt > (balance * self.config.MAX_SINGLE_COIN_PCT / 100):
                self.logger.warning(f"{symbol}: would exceed single-coin limit")
                continue

            # Calculate entry/SL/TP
            entry_price = current_price
            atr = signal_data.get("atr", current_price * 0.02)  # Default 2% if no ATR

            sl = self.signal_generator.calculate_stop_loss(
                symbol, entry_price, direction, atr,
                atr_multiplier=self.config.ATR_STOP_LOSS_MULTIPLIER,
                min_sl_pct=self.config.MIN_SL_PCT
            )
            tp = self.signal_generator.calculate_take_profit(
                entry_price, sl, direction,
                risk_reward_ratio=self.config.RISK_REWARD_RATIO
            )

            risk_usdt, reward_usdt, rr_ratio = self.signal_generator.calculate_risk_reward(
                entry_price, sl, tp
            )

            # Create Signal object
            signal_obj = Signal(
                id=f"sig_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{symbol}_{self.cycle_count:03d}",
                timestamp=datetime.utcnow(),
                symbol=symbol,
                timeframe="4h",
                direction=direction,
                confidence=confidence,
                entry_price=entry_price,
                stop_loss=sl,
                take_profit=tp,
                position_size_usdt=position_size_usdt,
                position_size_pct=position_size_pct,
                kelly_fraction=kelly_frac,
                risk_usdt=risk_usdt,
                reward_usdt=reward_usdt,
                risk_reward_ratio=rr_ratio,
                confluence_score=signal_data.get("confluence_score", 0),
                news_bias_score=0.0,
                order_book_depth={},
                indicators_state=signal_data.get("indicators", {}),
            )

            sized_signals.append(signal_obj)
            self.logger.info(f"Sized {symbol}: {position_size_pct:.1f}% ({position_size_usdt:.2f} USDT)")

        return sized_signals

    async def publish_signals_to_redis(self, signals: List[Signal]) -> None:
        """Publish sized signals to Redis queue and pub/sub."""
        import json

        for signal in signals:
            try:
                signal_dict = signal.to_dict()
                signal_json = json.dumps(signal_dict)
                print(f"[DEBUG] Publishing signal: {signal.id}, dict keys: {list(signal_dict.keys())[:5]}")

                # Push to queue
                await self.redis.rpush(
                    self.config.REDIS_SIGNAL_QUEUE,
                    signal_json
                )
                print(f"[DEBUG] Signal {signal.id} pushed to queue")

                # Publish to channel
                await self.redis.publish(
                    "new_signals",
                    signal.symbol
                )
                print(f"[DEBUG] Signal {signal.id} published to channel")

                self.logger.info(f"Published signal {signal.id} for {signal.symbol}")

            except Exception as e:
                print(f"[DEBUG ERROR] Publishing failed: {e}")
                self.logger.error(f"Error publishing signal {signal.id}: {e}")

    async def scan_cycle(self) -> None:
        """Execute one complete scan cycle: fetch, analyze, filter, size, publish."""
        cycle_start = datetime.utcnow()
        self.cycle_count += 1

        try:
            self.logger.info(f"Cycle {self.cycle_count} starting...")

            # 1. Fetch state
            state = await self.fetch_state_from_redis()
            balance = state.get("balance", 0)
            whitelist = state.get("whitelist", self.config.DEFAULT_SYMBOLS)
            print(f"[DEBUG] Balance: {balance}, Whitelist: {whitelist}")

            if not whitelist:
                self.logger.warning("No whitelist pairs available")
                return

            if balance < self.config.MIN_ACCOUNT_BALANCE_USDT:
                self.logger.warning(f"Insufficient balance: {balance} USDT")
                return

            # 2. Analyze pairs in parallel
            analysis = await self.analyze_pairs(state, whitelist)
            print(f"[DEBUG] Analysis results: {len(analysis)} pairs")
            self.logger.info(f"Analyzed {len(analysis)} pairs")

            if not analysis:
                self.logger.info("No analysis results")
                return

            # 3. Filter signals
            filtered = await self.filter_signals(analysis, state)
            print(f"[DEBUG] Filtered results: {len(filtered)} signals")
            self.logger.info(f"Filtered to {len(filtered)} signals")

            if not filtered:
                self.logger.info("No signals passed filters")
                return

            # 4. Size positions
            positions = state.get("positions", [])
            sized = await self.size_positions(filtered, balance, positions)
            print(f"[DEBUG] Sized signals: {len(sized)} positions")
            self.logger.info(f"Sized {len(sized)} positions")

            if not sized:
                self.logger.info("No signals sized")
                return

            # 5. Publish to Redis
            print(f"[DEBUG] Publishing {len(sized)} signals to Redis")
            await self.publish_signals_to_redis(sized)

            # 6. Log metrics
            cycle_time = (datetime.utcnow() - cycle_start).total_seconds()
            self.logger.info(f"Cycle {self.cycle_count} complete in {cycle_time:.2f}s")

        except Exception as e:
            print(f"[DEBUG ERROR] Cycle {self.cycle_count} failed: {e}")
            self.logger.error(f"Cycle {self.cycle_count} failed: {e}", exc_info=True)

    async def run_forever(self) -> None:
        """Main loop: run scan cycles every 15 minutes."""
        self.is_running = True

        try:
            await self.initialize()

            while self.is_running:
                await self.scan_cycle()

                # Sleep until next cycle
                await asyncio.sleep(self.config.INTERVAL_SECONDS)

        except asyncio.CancelledError:
            self.logger.info("ScannerAgent cancelled")
        except Exception as e:
            self.logger.error(f"Fatal error in ScannerAgent: {e}", exc_info=True)
        finally:
            await self.shutdown()
