"""
Structured logging module for trading scanner.
Provides JSON-formatted logging to both console and file with SQLite database integration.
"""

import logging
import logging.handlers
from typing import Optional, Any, Dict
from pathlib import Path

from pythonjsonlogger import jsonlogger

from config import ScannerConfig
from core.database import Database


class StructuredLogger:
    """
    Structured logger with JSON formatting for console and file output.
    All logs are also persisted to SQLite database.
    """

    def __init__(self, db: Database):
        """
        Initialize structured logger with JSON formatting.

        Args:
            db: Database instance for persisting logs
        """
        self.db = db
        self.logger = logging.getLogger("scanner")
        self.logger.setLevel(getattr(logging, ScannerConfig.LOG_LEVEL))

        # Remove any existing handlers
        self.logger.handlers.clear()

        # Console handler with JSON formatting
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, ScannerConfig.LOG_LEVEL))
        console_formatter = jsonlogger.JsonFormatter(
            "%(timestamp)s %(level)s %(signal_id)s %(message)s %(data)s %(error)s"
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        # File handler with JSON formatting (if LOG_FILE is configured)
        if ScannerConfig.LOG_FILE:
            log_file_path = Path(ScannerConfig.LOG_FILE)
            log_file_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.handlers.RotatingFileHandler(
                str(log_file_path),
                maxBytes=ScannerConfig.DB_ROTATION_SIZE_MB * 1024 * 1024,
                backupCount=5,
            )
            file_handler.setLevel(getattr(logging, ScannerConfig.LOG_LEVEL))
            file_formatter = jsonlogger.JsonFormatter(
                "%(timestamp)s %(level)s %(signal_id)s %(message)s %(data)s %(error)s"
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)

    async def debug(
        self,
        signal_id: Optional[str],
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log debug message.

        Args:
            signal_id: Signal ID for correlation
            message: Log message
            data: Optional additional data dict
        """
        await self._log("DEBUG", signal_id, message, data=data)

    async def info(
        self,
        signal_id: Optional[str],
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log info message.

        Args:
            signal_id: Signal ID for correlation
            message: Log message
            data: Optional additional data dict
        """
        await self._log("INFO", signal_id, message, data=data)

    async def warning(
        self,
        signal_id: Optional[str],
        message: str,
        error: Optional[str] = None,
    ) -> None:
        """
        Log warning message.

        Args:
            signal_id: Signal ID for correlation
            message: Log message
            error: Optional error details
        """
        await self._log("WARNING", signal_id, message, error=error)

    async def error(
        self,
        signal_id: Optional[str],
        message: str,
        error: str,
    ) -> None:
        """
        Log error message.

        Args:
            signal_id: Signal ID for correlation
            message: Log message
            error: Error details/traceback
        """
        await self._log("ERROR", signal_id, message, error=error)

    async def _log(
        self,
        level: str,
        signal_id: Optional[str],
        message: str,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Internal method to log messages to both console/file and database.

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR)
            signal_id: Signal ID for correlation
            message: Log message
            data: Optional additional data dict
            error: Optional error details
        """
        # Log to database
        log_method = getattr(self.db, f"log_{level.lower()}")
        await log_method(
            message=message,
            agent="scanner",
            signal_id=signal_id,
            data=data if level == "DEBUG" or level == "INFO" else None,
            error=error if error else None,
        )

        # Log to console/file via Python logger
        log_level = getattr(logging, level)
        extra = {
            "timestamp": None,  # Will be added by JSON formatter
            "level": level,
            "signal_id": signal_id or "",
            "data": data or "",
            "error": error or "",
        }

        self.logger.log(log_level, message, extra=extra)
