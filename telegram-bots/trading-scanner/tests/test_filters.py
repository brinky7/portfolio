"""
Tests for correlation and news sentiment filters.
"""
import pytest
from components.correlation_filter import CorrelationFilter
from components.news_filter import NewsFilter


class TestCorrelationFilter:
    """Test suite for CorrelationFilter."""

    def test_is_correlated_empty_positions(self):
        """Should return False when no open positions."""
        cf = CorrelationFilter()
        result = cf.is_correlated("AAPL", [], {})
        assert result is False

    def test_is_correlated_below_threshold(self):
        """Should return False when average correlation below threshold."""
        cf = CorrelationFilter()
        open_positions = ["BTC", "ETH"]
        correlations = {
            "AAPL_BTC": 0.3,
            "AAPL_ETH": 0.4
        }
        result = cf.is_correlated("AAPL", open_positions, correlations, threshold=0.7)
        assert result is False

    def test_is_correlated_above_threshold(self):
        """Should return True when average correlation above threshold."""
        cf = CorrelationFilter()
        open_positions = ["BTC", "ETH"]
        correlations = {
            "AAPL_BTC": 0.8,
            "AAPL_ETH": 0.9
        }
        result = cf.is_correlated("AAPL", open_positions, correlations, threshold=0.7)
        assert result is True

    def test_is_correlated_reverse_key(self):
        """Should find correlations with reversed key order."""
        cf = CorrelationFilter()
        open_positions = ["BTC", "ETH"]
        correlations = {
            "BTC_AAPL": 0.8,
            "ETH_AAPL": 0.9
        }
        result = cf.is_correlated("AAPL", open_positions, correlations, threshold=0.7)
        assert result is True


class TestNewsFilter:
    """Test suite for NewsFilter."""

    def test_news_aligned_long_bullish(self):
        """Long position should align with bullish news (positive bias)."""
        nf = NewsFilter()
        result = nf.is_news_aligned("long", 0.7, long_threshold=-0.5)
        assert result is True

    def test_news_aligned_long_bearish(self):
        """Long position should NOT align with bearish news (negative bias)."""
        nf = NewsFilter()
        result = nf.is_news_aligned("long", -0.7, long_threshold=-0.5)
        assert result is False

    def test_news_aligned_long_neutral(self):
        """Long position should align with neutral news."""
        nf = NewsFilter()
        result = nf.is_news_aligned("long", 0.0, long_threshold=-0.5)
        assert result is True

    def test_news_aligned_short_bearish(self):
        """Short position should align with bearish news (negative bias)."""
        nf = NewsFilter()
        result = nf.is_news_aligned("short", -0.7, short_threshold=0.5)
        assert result is True

    def test_news_aligned_short_bullish(self):
        """Short position should NOT align with bullish news (positive bias)."""
        nf = NewsFilter()
        result = nf.is_news_aligned("short", 0.7, short_threshold=0.5)
        assert result is False

    def test_news_aligned_neutral_direction(self):
        """Neutral direction should always return True."""
        nf = NewsFilter()
        result_positive = nf.is_news_aligned("neutral", 0.8)
        result_negative = nf.is_news_aligned("neutral", -0.8)
        result_zero = nf.is_news_aligned("neutral", 0.0)
        assert result_positive is True
        assert result_negative is True
        assert result_zero is True
