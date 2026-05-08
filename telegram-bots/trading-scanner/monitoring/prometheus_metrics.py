"""
Prometheus metrics collectors for Trading Scanner.
Provides comprehensive monitoring of scan cycles, signals, errors, and queue depths.
"""

from aioprometheus import Counter, Gauge, Histogram, Summary
from typing import Optional


class PrometheusMetrics:
    """Prometheus metrics collector for Trading Scanner."""

    def __init__(self):
        """Initialize all Prometheus metrics."""
        # ========== COUNTERS ==========
        self.signals_total = Counter(
            name="signals_total",
            help="Total number of signals generated",
            labels={"symbol": "", "direction": "", "status": ""},
        )

        self.scan_cycles_total = Counter(
            name="scan_cycles_total",
            help="Total number of scan cycles completed",
        )

        self.scan_cycle_errors_total = Counter(
            name="scan_cycle_errors_total",
            help="Total number of scan cycle errors",
        )

        self.retry_attempts_total = Counter(
            name="retry_attempts_total",
            help="Total number of retry attempts",
            labels={"error_type": ""},
        )

        self.filter_drops_total = Counter(
            name="filter_drops_total",
            help="Total number of signals filtered out",
            labels={"reason": ""},
        )

        self.dlq_pushes_total = Counter(
            name="dlq_pushes_total",
            help="Total number of signals pushed to DLQ",
        )

        # ========== GAUGES ==========
        self.redis_queue_depth = Gauge(
            name="redis_queue_depth",
            help="Current depth of Redis signal queue",
        )

        self.dlq_queue_depth = Gauge(
            name="dlq_queue_depth",
            help="Current depth of Dead Letter Queue",
        )

        self.error_rate = Gauge(
            name="error_rate",
            help="Current error rate (0-1)",
        )

        self.signals_in_flight = Gauge(
            name="signals_in_flight",
            help="Number of signals currently being processed",
        )

        # ========== HISTOGRAMS ==========
        self.scan_latency_seconds = Histogram(
            name="scan_latency_seconds",
            help="Scan cycle latency in seconds",
            buckets=[1, 5, 10, 30, 60, 120, 300],
        )

        self.indicator_latency_seconds = Histogram(
            name="indicator_latency_seconds",
            help="Indicator calculation latency in seconds",
            buckets=[0.1, 0.5, 1, 2, 5, 10],
        )

        # ========== SUMMARIES ==========
        self.signal_confidence = Summary(
            name="signal_confidence",
            help="Distribution of signal confidence scores",
        )

        self.position_size_pct = Summary(
            name="position_size_pct",
            help="Distribution of position sizes in percent",
        )

    async def record_scan_start(self) -> None:
        """Record the start of a scan cycle."""
        # Increment signals_in_flight as marker of active cycle
        await self.signals_in_flight.set(1)

    async def record_scan_complete(
        self,
        duration: float,
        error_count: int = 0,
        signal_count: int = 0,
    ) -> None:
        """
        Record completion of a scan cycle.

        Args:
            duration: Scan duration in seconds
            error_count: Number of errors during scan
            signal_count: Number of signals generated
        """
        await self.scan_cycles_total.inc()
        await self.scan_latency_seconds.observe(duration)

        if error_count > 0:
            await self.scan_cycle_errors_total.inc(error_count)

        # Reset in-flight marker
        await self.signals_in_flight.set(0)

    async def record_signal_generated(
        self,
        symbol: str,
        direction: str,
        confidence: float,
        status: str = "generated",
    ) -> None:
        """
        Record a signal generation.

        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            direction: Signal direction ('long' or 'short')
            confidence: Confidence score (0-1)
            status: Signal status ('generated', 'filtered', 'executed')
        """
        await self.signals_total.inc(
            {
                "symbol": symbol,
                "direction": direction,
                "status": status,
            }
        )
        await self.signal_confidence.observe(confidence)

    async def record_signal_filtered(self, reason: str) -> None:
        """
        Record a signal that was filtered out.

        Args:
            reason: Reason for filtering (e.g., 'low_confidence', 'high_correlation')
        """
        await self.filter_drops_total.inc({"reason": reason})

    async def record_signal_error(self) -> None:
        """Record a signal processing error."""
        await self.scan_cycle_errors_total.inc()

    async def record_retry_attempt(self, error_type: str) -> None:
        """
        Record a retry attempt.

        Args:
            error_type: Type of error that triggered retry
        """
        await self.retry_attempts_total.inc({"error_type": error_type})

    async def record_dlq_push(self) -> None:
        """Record a signal pushed to Dead Letter Queue."""
        await self.dlq_pushes_total.inc()

    async def update_queue_depths(
        self,
        scan_signals_depth: int,
        dlq_depth: int,
    ) -> None:
        """
        Update queue depth metrics.

        Args:
            scan_signals_depth: Current depth of scan signals queue
            dlq_depth: Current depth of DLQ
        """
        await self.redis_queue_depth.set(scan_signals_depth)
        await self.dlq_queue_depth.set(dlq_depth)

    async def record_indicator_latency(self, duration_seconds: float) -> None:
        """
        Record indicator calculation latency.

        Args:
            duration_seconds: Latency in seconds
        """
        await self.indicator_latency_seconds.observe(duration_seconds)

    async def record_position_size(self, size_pct: float) -> None:
        """
        Record position size.

        Args:
            size_pct: Position size as percentage of account
        """
        await self.position_size_pct.observe(size_pct)

    async def update_error_rate(self, error_rate: float) -> None:
        """
        Update current error rate.

        Args:
            error_rate: Error rate as fraction (0-1)
        """
        await self.error_rate.set(error_rate)

    async def update_signals_in_flight(self, count: int) -> None:
        """
        Update the number of signals currently in flight.

        Args:
            count: Number of signals being processed
        """
        await self.signals_in_flight.set(count)
