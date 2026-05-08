"""
Scanner configuration module.
Manages all scanner settings including scan cycles, position limits, risk management, and exchange parameters.
"""

import os
from pathlib import Path
from typing import Dict, Any, Tuple, List


class ScannerConfig:
    """Central configuration class for Trading Scanner."""

    # ========== PROJECT PATHS ==========
    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
    STORAGE_DIR = PROJECT_ROOT / "storage" / "scanner"
    LOGS_DIR = PROJECT_ROOT / "logs" / "scanner"

    def __init__(self):
        """Initialize configuration and ensure required directories exist."""
        self._create_directories()

    @staticmethod
    def _create_directories():
        """Create necessary directories if they don't exist."""
        ScannerConfig.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        ScannerConfig.STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    # ========== SCAN CYCLE ==========
    INTERVAL_SECONDS: int = 900  # 15 minutes
    SCAN_TIMEOUT_SECONDS: int = 300  # 5 minutes

    # ========== POSITION LIMITS ==========
    MAX_CONCURRENT_POSITIONS: int = 10
    MAX_SINGLE_COIN_PCT: float = 50.0
    POSITION_SIZE_PCT_NORMAL: Tuple[float, float] = (5.0, 10.0)
    POSITION_SIZE_PCT_HIGH_CONF: float = 15.0
    MIN_ACCOUNT_BALANCE_USDT: float = 10.0

    # ========== SIGNAL FILTERING ==========
    MIN_CONFIDENCE: float = 0.65
    MIN_PROFIT_PCT: float = 1.6
    MAX_CORRELATION: float = 0.7
    MIN_ORDER_BOOK_DEPTH_USDT: float = 50000.0

    # ========== TIMEFRAMES ==========
    TIMEFRAMES: List[str] = ["4h", "1d"]
    OHLCV_CANDLE_LIMIT: int = 200

    # ========== RISK MANAGEMENT ==========
    KELLY_CRITERION_ENABLED: bool = True
    ATR_PERIOD: int = 14
    ATR_STOP_LOSS_MULTIPLIER: float = 2.0
    MIN_SL_PCT: float = 1.5
    RISK_REWARD_RATIO: float = 2.0

    # ========== NEWS SENTIMENT ==========
    NEWS_BIAS_LONG_THRESHOLD: float = -0.5
    NEWS_BIAS_SHORT_THRESHOLD: float = 0.5

    # ========== ERROR HANDLING ==========
    RETRY_MAX_ATTEMPTS: int = 4
    RETRY_BASE_DELAY_SECONDS: float = 0.5
    RETRY_MAX_DELAY_SECONDS: int = 30
    RETRY_JITTER_RANGE: Tuple[float, float] = (0.5, 1.5)

    # ========== LOGGING ==========
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = str(LOGS_DIR / "scanner.log")
    SQLITE_DB_PATH: str = str(STORAGE_DIR / "scanner.db")
    DB_ROTATION_SIZE_MB: int = 1024
    DB_ROTATION_DAYS: int = 1

    # ========== MONITORING ==========
    PROMETHEUS_PORT: int = int(os.getenv("PROMETHEUS_PORT", "9100"))
    METRICS_ENDPOINT: str = "/metrics"
    METRICS_SCRAPE_INTERVAL_SECONDS: int = 15

    # ========== REDIS ==========
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    # Queue and channel names
    REDIS_SCAN_RESULTS_QUEUE: str = "scanner:results"
    REDIS_SIGNAL_QUEUE: str = "scanner:signals"
    REDIS_POSITION_UPDATES_CHANNEL: str = "scanner:positions"
    REDIS_ERROR_QUEUE: str = "scanner:errors"
    REDIS_METRICS_CHANNEL: str = "scanner:metrics"
    REDIS_HEARTBEAT_KEY: str = "scanner:heartbeat"

    # ========== EXCHANGE ==========
    EXCHANGE_NAME: str = "bybit"
    EXCHANGE_SANDBOX: bool = os.getenv("EXCHANGE_SANDBOX", "False").lower() == "true"
    EXCHANGE_TIMEOUT_SECONDS: int = 30

    # ========== SYMBOLS ==========
    DEFAULT_SYMBOLS: List[str] = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]

    @classmethod
    def get_config_dict(cls) -> Dict[str, Any]:
        """
        Return all configuration parameters as a dictionary for debugging.

        Returns:
            Dict containing all configuration settings.
        """
        return {
            "project_root": str(cls.PROJECT_ROOT),
            "storage_dir": str(cls.STORAGE_DIR),
            "logs_dir": str(cls.LOGS_DIR),
            "scan_cycle": {
                "interval_seconds": cls.INTERVAL_SECONDS,
                "timeout_seconds": cls.SCAN_TIMEOUT_SECONDS,
            },
            "position_limits": {
                "max_concurrent_positions": cls.MAX_CONCURRENT_POSITIONS,
                "max_single_coin_pct": cls.MAX_SINGLE_COIN_PCT,
                "position_size_pct_normal": cls.POSITION_SIZE_PCT_NORMAL,
                "position_size_pct_high_conf": cls.POSITION_SIZE_PCT_HIGH_CONF,
                "min_account_balance_usdt": cls.MIN_ACCOUNT_BALANCE_USDT,
            },
            "signal_filtering": {
                "min_confidence": cls.MIN_CONFIDENCE,
                "min_profit_pct": cls.MIN_PROFIT_PCT,
                "max_correlation": cls.MAX_CORRELATION,
                "min_order_book_depth_usdt": cls.MIN_ORDER_BOOK_DEPTH_USDT,
            },
            "timeframes": {
                "timeframes": cls.TIMEFRAMES,
                "ohlcv_candle_limit": cls.OHLCV_CANDLE_LIMIT,
            },
            "risk_management": {
                "kelly_criterion_enabled": cls.KELLY_CRITERION_ENABLED,
                "atr_period": cls.ATR_PERIOD,
                "atr_stop_loss_multiplier": cls.ATR_STOP_LOSS_MULTIPLIER,
                "min_sl_pct": cls.MIN_SL_PCT,
                "risk_reward_ratio": cls.RISK_REWARD_RATIO,
            },
            "news_sentiment": {
                "news_bias_long_threshold": cls.NEWS_BIAS_LONG_THRESHOLD,
                "news_bias_short_threshold": cls.NEWS_BIAS_SHORT_THRESHOLD,
            },
            "error_handling": {
                "retry_max_attempts": cls.RETRY_MAX_ATTEMPTS,
                "retry_base_delay_seconds": cls.RETRY_BASE_DELAY_SECONDS,
                "retry_max_delay_seconds": cls.RETRY_MAX_DELAY_SECONDS,
                "retry_jitter_range": cls.RETRY_JITTER_RANGE,
            },
            "logging": {
                "log_level": cls.LOG_LEVEL,
                "log_file": cls.LOG_FILE,
                "sqlite_db_path": cls.SQLITE_DB_PATH,
                "db_rotation_size_mb": cls.DB_ROTATION_SIZE_MB,
                "db_rotation_days": cls.DB_ROTATION_DAYS,
            },
            "monitoring": {
                "prometheus_port": cls.PROMETHEUS_PORT,
                "metrics_endpoint": cls.METRICS_ENDPOINT,
                "metrics_scrape_interval_seconds": cls.METRICS_SCRAPE_INTERVAL_SECONDS,
            },
            "redis": {
                "host": cls.REDIS_HOST,
                "port": cls.REDIS_PORT,
                "scan_results_queue": cls.REDIS_SCAN_RESULTS_QUEUE,
                "signal_queue": cls.REDIS_SIGNAL_QUEUE,
                "position_updates_channel": cls.REDIS_POSITION_UPDATES_CHANNEL,
                "error_queue": cls.REDIS_ERROR_QUEUE,
                "metrics_channel": cls.REDIS_METRICS_CHANNEL,
                "heartbeat_key": cls.REDIS_HEARTBEAT_KEY,
            },
            "exchange": {
                "exchange_name": cls.EXCHANGE_NAME,
                "exchange_sandbox": cls.EXCHANGE_SANDBOX,
                "exchange_timeout_seconds": cls.EXCHANGE_TIMEOUT_SECONDS,
            },
            "symbols": {
                "default_symbols": cls.DEFAULT_SYMBOLS,
            },
        }


# Initialize configuration singleton
_config = ScannerConfig()
