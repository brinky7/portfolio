"""
News sentiment filter for directional alignment.

Checks if a trading direction aligns with the news bias sentiment.
"""


class NewsFilter:
    """Filter to validate trading direction against news sentiment."""

    def is_news_aligned(self, direction, news_bias_score, long_threshold=-0.5, short_threshold=0.5):
        """
        Check if trading direction aligns with news sentiment bias.

        Args:
            direction: Trading direction - "long", "short", or "neutral"
            news_bias_score: Sentiment score from -1.0 (bearish) to +1.0 (bullish)
            long_threshold: Minimum bias score for long alignment (default -0.5)
            short_threshold: Maximum bias score for short alignment (default 0.5)

        Returns:
            bool: True if direction aligns with sentiment, False otherwise
        """
        if direction == "neutral":
            return True

        if direction == "long":
            return news_bias_score > long_threshold

        if direction == "short":
            return news_bias_score < short_threshold

        return False
