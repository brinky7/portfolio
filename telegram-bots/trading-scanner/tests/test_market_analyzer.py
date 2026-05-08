import pytest
import numpy as np
import pandas as pd
from components.market_analyzer import MarketAnalyzer, IndicatorSignal


@pytest.fixture
def sample_ohlcv():
    """Generate sample OHLCV data for testing."""
    n = 100
    close = np.linspace(100, 110, n) + np.random.randn(n) * 0.5
    high = close + np.abs(np.random.randn(n) * 0.3)
    low = close - np.abs(np.random.randn(n) * 0.3)
    open_ = close + np.random.randn(n) * 0.2
    volume = np.random.randint(1000, 10000, n)

    return pd.DataFrame({
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    })


@pytest.fixture
def sample_ohlcv_small():
    """Generate small OHLCV data for testing edge cases."""
    return pd.DataFrame({
        'open': [100, 101, 102],
        'high': [101, 102, 103],
        'low': [99, 100, 101],
        'close': [100.5, 101.5, 102.5],
        'volume': [1000, 1100, 1200]
    })


def test_compute_rsi_empty():
    """Test RSI computation with empty data."""
    analyzer = MarketAnalyzer()
    empty_df = pd.DataFrame({'close': []})

    signal = analyzer.compute_rsi(empty_df)

    assert signal.name == 'RSI'
    assert signal.value == 0
    assert signal.signal == 'neutral'


def test_compute_rsi_bullish(sample_ohlcv):
    """Test RSI computation for bullish signal."""
    analyzer = MarketAnalyzer()

    # Create uptrend data
    bullish_data = sample_ohlcv.copy()
    bullish_data['close'] = np.linspace(100, 150, len(bullish_data))

    signal = analyzer.compute_rsi(bullish_data, period=14)

    assert signal.name == 'RSI'
    assert 0 <= signal.value <= 100
    assert signal.signal in ['overbought', 'oversold', 'neutral']
    assert isinstance(signal.aligned, bool)


def test_compute_rsi_oversold():
    """Test RSI for oversold conditions."""
    analyzer = MarketAnalyzer()

    # Create downtrend data
    downtrend = pd.DataFrame({
        'close': np.linspace(150, 100, 50)
    })

    signal = analyzer.compute_rsi(downtrend, period=14)

    assert signal.value < 30
    assert signal.signal == 'oversold'


def test_compute_rsi_overbought():
    """Test RSI for overbought conditions."""
    analyzer = MarketAnalyzer()

    # Create uptrend data
    uptrend = pd.DataFrame({
        'close': np.linspace(100, 150, 50)
    })

    signal = analyzer.compute_rsi(uptrend, period=14)

    assert signal.value > 70
    assert signal.signal == 'overbought'


def test_compute_macd_empty():
    """Test MACD computation with empty data."""
    analyzer = MarketAnalyzer()
    empty_df = pd.DataFrame({'close': []})

    signal = analyzer.compute_macd(empty_df)

    assert signal.name == 'MACD'
    assert signal.value == 0
    assert signal.signal == 'neutral'


def test_compute_macd_bullish(sample_ohlcv):
    """Test MACD computation for bullish signal."""
    analyzer = MarketAnalyzer()

    bullish_data = sample_ohlcv.copy()
    bullish_data['close'] = np.linspace(100, 150, len(bullish_data))

    signal = analyzer.compute_macd(bullish_data, fast=12, slow=26, signal_period=9)

    assert signal.name == 'MACD'
    assert isinstance(signal.value, (int, float, np.number))
    assert signal.signal in ['bullish', 'bearish', 'bullish_crossover', 'bearish_crossover', 'neutral']
    assert isinstance(signal.aligned, bool)


def test_compute_ichimoku_empty():
    """Test Ichimoku computation with empty data."""
    analyzer = MarketAnalyzer()
    empty_df = pd.DataFrame({'high': [], 'low': []})

    signal = analyzer.compute_ichimoku(empty_df)

    assert signal.name == 'Ichimoku'
    assert signal.value == 0
    assert signal.signal == 'neutral'


def test_compute_ichimoku_insufficient_data():
    """Test Ichimoku with insufficient candles."""
    analyzer = MarketAnalyzer()

    small_data = pd.DataFrame({
        'high': [100, 101, 102],
        'low': [99, 100, 101]
    })

    signal = analyzer.compute_ichimoku(small_data)

    assert signal.name == 'Ichimoku'
    assert signal.signal == 'neutral'


def test_compute_ichimoku_valid(sample_ohlcv):
    """Test Ichimoku with sufficient data."""
    analyzer = MarketAnalyzer()

    signal = analyzer.compute_ichimoku(sample_ohlcv)

    assert signal.name == 'Ichimoku'
    assert signal.signal in [
        'bullish_above_cloud',
        'bearish_below_cloud',
        'bullish_in_cloud',
        'bearish_in_cloud',
        'neutral'
    ]
    assert isinstance(signal.value, (int, float, np.number))


def test_analyze_pair(sample_ohlcv):
    """Test full pair analysis."""
    analyzer = MarketAnalyzer()

    result = analyzer.analyze_pair('BTC/USDT', sample_ohlcv)

    assert result['symbol'] == 'BTC/USDT'
    assert 'indicators' in result
    assert 'rsi' in result['indicators']
    assert 'macd' in result['indicators']
    assert 'ichimoku' in result['indicators']
    assert 'confluence_score' in result
    assert 0 <= result['confluence_score'] <= 3
    assert result['direction'] in ['long', 'short', 'neutral']
    assert 0.5 <= result['confidence'] <= 0.875


def test_analyze_pair_confidence_calculation(sample_ohlcv):
    """Test that confidence is correctly calculated from confluence score."""
    analyzer = MarketAnalyzer()

    result = analyzer.analyze_pair('ETH/USDT', sample_ohlcv)

    expected_confidence = 0.5 + (result['confluence_score'] * 0.125)
    assert abs(result['confidence'] - expected_confidence) < 0.001


def test_indicator_signal_creation():
    """Test IndicatorSignal dataclass."""
    signal = IndicatorSignal(
        name='RSI',
        value=75.5,
        signal='overbought',
        aligned=True
    )

    assert signal.name == 'RSI'
    assert signal.value == 75.5
    assert signal.signal == 'overbought'
    assert signal.aligned is True
