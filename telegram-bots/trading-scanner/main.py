#!/usr/bin/env python3
"""
Trading Scanner Agent main entry point.
Async event loop driver for continuous cryptocurrency scanning.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import ScannerConfig
from core.scanner_agent import ScannerAgent
from monitoring.logger import Logger


class Main:
    """Main entry point for scanner service."""

    def __init__(self):
        self.logger = Logger()
        self.scanner: Optional[ScannerAgent] = None
        self.running = False

    def setup_signal_handlers(self, loop: asyncio.AbstractEventLoop) -> None:
        """Register signal handlers for graceful shutdown."""
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._signal_handler, sig, loop)

    def _signal_handler(self, sig: int, loop: asyncio.AbstractEventLoop) -> None:
        """Handle shutdown signals."""
        self.logger.info(f"Received signal {sig}, shutting down...")
        self.running = False
        loop.stop()

    async def run(self) -> None:
        """Main async entry point."""
        self.running = True

        try:
            self.logger.info("Starting Trading Scanner Agent...")
            self.scanner = ScannerAgent()
            await self.scanner.run_forever()

        except asyncio.CancelledError:
            self.logger.info("Scanner cancelled")
        except Exception as e:
            self.logger.error(f"Fatal error: {e}", exc_info=True)
            sys.exit(1)

    def main(self) -> int:
        """Entry point."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        self.setup_signal_handlers(loop)

        try:
            loop.run_until_complete(self.run())
        except KeyboardInterrupt:
            self.logger.info("Interrupted by user")
        finally:
            loop.close()
            return 0


if __name__ == "__main__":
    from typing import Optional

    main_app = Main()
    sys.exit(main_app.main())
