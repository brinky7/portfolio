"""
Correlation filter for risk management.

Checks if a symbol is highly correlated with existing open positions
to avoid redundant exposure.
"""


class CorrelationFilter:
    """Filter to detect high correlation with open positions."""

    def is_correlated(self, symbol, open_positions, correlations, threshold=0.7):
        """
        Check if symbol is correlated with any open position.

        Args:
            symbol: Trading symbol to check (e.g., "AAPL")
            open_positions: List of currently open position symbols
            correlations: Dict with correlation values, keyed as "SYMBOL1_SYMBOL2"
            threshold: Correlation threshold above which to consider correlated (default 0.7)

        Returns:
            bool: True if average correlation exceeds threshold, False otherwise
        """
        if not open_positions:
            return False

        correlation_values = []

        for position_symbol in open_positions:
            # Try direct key order first
            key = f"{symbol}_{position_symbol}"
            if key in correlations:
                correlation_values.append(correlations[key])
                continue

            # Try reversed key order
            key_reversed = f"{position_symbol}_{symbol}"
            if key_reversed in correlations:
                correlation_values.append(correlations[key_reversed])
                continue

        # If no correlations found, not correlated
        if not correlation_values:
            return False

        # Calculate average correlation
        avg_correlation = sum(correlation_values) / len(correlation_values)
        return avg_correlation > threshold
