from dataclasses import dataclass
from typing import Dict, List
import numpy as np
import pandas as pd


@dataclass
class IndicatorSignal:
    name: str
    value: float
    signal: str
    aligned: bool


class MarketAnalyzer:

    def compute_rsi(self, df: pd.DataFrame, period: int = 14) -> IndicatorSignal:
        if df.empty or len(df) < period + 1:
            return IndicatorSignal('RSI', 0, 'neutral', False)
        close = df['close'].values
        deltas = np.diff(close)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])
        if avg_loss == 0:
            rsi = 100.0 if avg_gain > 0 else 50.0
        else:
            rsi = 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
        if rsi > 70:
            return IndicatorSignal('RSI', float(rsi), 'overbought', True)
        elif rsi < 30:
            return IndicatorSignal('RSI', float(rsi), 'oversold', True)
        return IndicatorSignal('RSI', float(rsi), 'neutral', False)

    def compute_macd(self, df: pd.DataFrame, fast=12, slow=26, signal_period=9) -> IndicatorSignal:
        if df.empty or len(df) < slow + signal_period:
            return IndicatorSignal('MACD', 0, 'neutral', False)
        close = df['close']
        macd_line = close.ewm(span=fast, adjust=False).mean() - close.ewm(span=slow, adjust=False).mean()
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
        hist = macd_line - signal_line
        cur = float(hist.iloc[-1])
        prev = float(hist.iloc[-2]) if len(hist) > 1 else cur
        if cur > 0 and prev <= 0:
            return IndicatorSignal('MACD', cur, 'bullish_crossover', True)
        elif cur < 0 and prev >= 0:
            return IndicatorSignal('MACD', cur, 'bearish_crossover', True)
        elif cur > 0:
            return IndicatorSignal('MACD', cur, 'bullish', True)
        elif cur < 0:
            return IndicatorSignal('MACD', cur, 'bearish', True)
        return IndicatorSignal('MACD', cur, 'neutral', False)

    def compute_ichimoku(self, df: pd.DataFrame) -> IndicatorSignal:
        if df.empty or len(df) < 52:
            return IndicatorSignal('Ichimoku', 0, 'neutral', False)
        high, low = df['high'].values, df['low'].values
        tenkan = (max(high[-9:]) + min(low[-9:])) / 2
        kijun = (max(high[-26:]) + min(low[-26:])) / 2
        senkou_a = (tenkan + kijun) / 2
        senkou_b = (max(high[-52:]) + min(low[-52:])) / 2
        cloud_top, cloud_bottom = max(senkou_a, senkou_b), min(senkou_a, senkou_b)
        mid = (cloud_top + cloud_bottom) / 2
        price = float(df['close'].iloc[-1])
        if price > cloud_top:
            return IndicatorSignal('Ichimoku', mid, 'bullish_above_cloud', True)
        elif price < cloud_bottom:
            return IndicatorSignal('Ichimoku', mid, 'bearish_below_cloud', True)
        elif price > mid:
            return IndicatorSignal('Ichimoku', mid, 'bullish_in_cloud', True)
        elif price < mid:
            return IndicatorSignal('Ichimoku', mid, 'bearish_in_cloud', True)
        return IndicatorSignal('Ichimoku', mid, 'neutral', False)

    def compute_adx(self, df: pd.DataFrame, period: int = 14) -> IndicatorSignal:
        n = len(df)
        if n < period * 2 + 1:
            return IndicatorSignal('ADX', 0, 'weak', False)
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values

        tr   = np.zeros(n)
        pdm  = np.zeros(n)
        mdm  = np.zeros(n)
        for i in range(1, n):
            tr[i]  = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
            up     = high[i] - high[i-1]
            down   = low[i-1] - low[i]
            pdm[i] = up   if (up > down and up > 0)     else 0.0
            mdm[i] = down if (down > up and down > 0)   else 0.0

        # Wilder smoothing: инициализация суммой первых period, затем рекуррентно
        def wilder_smooth(arr, p):
            res = np.zeros(len(arr))
            res[p] = np.sum(arr[1:p+1])
            for i in range(p+1, len(arr)):
                res[i] = res[i-1] - res[i-1] / p + arr[i]
            return res

        tr_s  = wilder_smooth(tr, period)
        pdm_s = wilder_smooth(pdm, period)
        mdm_s = wilder_smooth(mdm, period)

        with np.errstate(divide='ignore', invalid='ignore'):
            pdi = np.where(tr_s > 0, 100.0 * pdm_s / tr_s, 0.0)
            mdi = np.where(tr_s > 0, 100.0 * mdm_s / tr_s, 0.0)
            dx  = np.where((pdi + mdi) > 0, 100.0 * np.abs(pdi - mdi) / (pdi + mdi), 0.0)

        # ADX: simple average первых period DX, затем Wilder smooth
        dx_valid = dx[period:]
        if len(dx_valid) < period:
            return IndicatorSignal('ADX', 0, 'weak', False)
        adx_vals = np.zeros(len(dx_valid))
        adx_vals[period-1] = np.mean(dx_valid[:period])
        for i in range(period, len(dx_valid)):
            adx_vals[i] = (adx_vals[i-1] * (period - 1) + dx_valid[i]) / period

        adx = float(adx_vals[-1])
        pdi_last = float(pdi[-1])
        mdi_last = float(mdi[-1])

        if adx > 25:
            trend = 'strong_long' if pdi_last > mdi_last else 'strong_short'
            return IndicatorSignal('ADX', adx, trend, True)
        return IndicatorSignal('ADX', adx, 'weak', False)

    def compute_ema(self, df: pd.DataFrame) -> IndicatorSignal:
        if len(df) < 50:
            return IndicatorSignal('EMA', 0, 'neutral', False)
        close = df['close']
        ema20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
        ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
        price = float(close.iloc[-1])
        # EMA20 выше EMA50 и цена выше обеих = бычий тренд
        if ema20 > ema50 and price > ema20:
            return IndicatorSignal('EMA', ema20, 'bullish', True)
        elif ema20 < ema50 and price < ema20:
            return IndicatorSignal('EMA', ema20, 'bearish', True)
        return IndicatorSignal('EMA', ema20, 'neutral', False)

    def compute_bollinger(self, df: pd.DataFrame, period: int = 20, dev: float = 2.0) -> IndicatorSignal:
        if len(df) < period:
            return IndicatorSignal('BB', 0, 'neutral', False)
        close = df['close']
        ma = close.rolling(period).mean()
        std = close.rolling(period).std()
        upper = float((ma + dev * std).iloc[-1])
        lower = float((ma - dev * std).iloc[-1])
        mid = float(ma.iloc[-1])
        price = float(close.iloc[-1])
        bandwidth = (upper - lower) / mid if mid > 0 else 0
        if price > upper:
            return IndicatorSignal('BB', bandwidth, 'breakout_up', True)
        elif price < lower:
            return IndicatorSignal('BB', bandwidth, 'breakout_down', True)
        elif bandwidth < 0.04:
            return IndicatorSignal('BB', bandwidth, 'squeeze', False)
        return IndicatorSignal('BB', bandwidth, 'neutral', False)

    def compute_obv(self, df: pd.DataFrame) -> IndicatorSignal:
        if len(df) < 20:
            return IndicatorSignal('OBV', 0, 'neutral', False)
        close = df['close'].values
        volume = df['volume'].values
        direction = np.sign(np.diff(close))
        obv = np.concatenate([[0], np.cumsum(direction * volume[1:])])
        # Сравниваем последние 10 баров: OBV растёт = подтверждение тренда
        obv_trend = obv[-1] - obv[-10]
        price_trend = close[-1] - close[-10]
        if obv_trend > 0 and price_trend > 0:
            return IndicatorSignal('OBV', float(obv[-1]), 'bullish', True)
        elif obv_trend < 0 and price_trend < 0:
            return IndicatorSignal('OBV', float(obv[-1]), 'bearish', True)
        elif obv_trend > 0 and price_trend < 0:
            return IndicatorSignal('OBV', float(obv[-1]), 'bullish_divergence', True)
        elif obv_trend < 0 and price_trend > 0:
            return IndicatorSignal('OBV', float(obv[-1]), 'bearish_divergence', True)
        return IndicatorSignal('OBV', float(obv[-1]), 'neutral', False)

    def compute_cmf(self, df: pd.DataFrame, period: int = 20) -> IndicatorSignal:
        if len(df) < period:
            return IndicatorSignal('CMF', 0, 'neutral', False)
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        volume = df['volume'].values
        hl_range = high - low
        # Избегаем деления на 0 при high == low
        mfm = np.where(hl_range > 0,
                       ((close - low) - (high - close)) / hl_range,
                       0.0)
        mfv = mfm * volume
        cmf = float(np.sum(mfv[-period:]) / np.sum(volume[-period:])) if np.sum(volume[-period:]) > 0 else 0.0
        if cmf > 0.1:
            return IndicatorSignal('CMF', cmf, 'buying_pressure', True)
        elif cmf < -0.1:
            return IndicatorSignal('CMF', cmf, 'selling_pressure', True)
        return IndicatorSignal('CMF', cmf, 'neutral', False)

    def compute_stochastic(self, df: pd.DataFrame, k_period=14, d_period=3) -> IndicatorSignal:
        if len(df) < k_period + d_period:
            return IndicatorSignal('Stoch', 0, 'neutral', False)
        high = df['high']
        low = df['low']
        close = df['close']
        lowest = low.rolling(k_period).min()
        highest = high.rolling(k_period).max()
        hl_range = highest - lowest
        k = ((close - lowest) / hl_range * 100).where(hl_range > 0, 50)
        k_smooth = k.rolling(d_period).mean()
        d_smooth = k_smooth.rolling(d_period).mean()
        k_val = float(k_smooth.iloc[-1])
        d_val = float(d_smooth.iloc[-1])
        if k_val < 20 and k_val > d_val:
            return IndicatorSignal('Stoch', k_val, 'oversold_turning_up', True)
        elif k_val > 80 and k_val < d_val:
            return IndicatorSignal('Stoch', k_val, 'overbought_turning_down', True)
        elif k_val < 20:
            return IndicatorSignal('Stoch', k_val, 'oversold', False)
        elif k_val > 80:
            return IndicatorSignal('Stoch', k_val, 'overbought', False)
        return IndicatorSignal('Stoch', k_val, 'neutral', False)

    def analyze_pair(self, symbol: str, ohlcv, dataframe: pd.DataFrame = None) -> Dict:
        df = dataframe if dataframe is not None else (ohlcv if isinstance(ohlcv, pd.DataFrame) else pd.DataFrame(ohlcv))

        rsi   = self.compute_rsi(df)
        macd  = self.compute_macd(df)
        ichi  = self.compute_ichimoku(df)
        adx   = self.compute_adx(df)
        ema   = self.compute_ema(df)
        bb    = self.compute_bollinger(df)
        obv   = self.compute_obv(df)
        cmf   = self.compute_cmf(df)
        stoch = self.compute_stochastic(df)

        signals = [rsi, macd, ichi, adx, ema, bb, obv, cmf, stoch]

        bullish_count = sum([
            rsi.signal == 'oversold',
            'bullish' in macd.signal,
            'bullish' in ichi.signal,
            adx.signal == 'strong_long',
            ema.signal == 'bullish',
            bb.signal == 'breakout_up',
            'bullish' in obv.signal,
            cmf.signal == 'buying_pressure',
            'oversold' in stoch.signal,
        ])

        bearish_count = sum([
            rsi.signal == 'overbought',
            'bearish' in macd.signal,
            'bearish' in ichi.signal,
            adx.signal == 'strong_short',
            ema.signal == 'bearish',
            bb.signal == 'breakout_down',
            'bearish' in obv.signal,
            cmf.signal == 'selling_pressure',
            'overbought' in stoch.signal,
        ])

        confluence_score = max(bullish_count, bearish_count)

        # Сигнал только при 4+ совпадениях
        if bullish_count >= 4 and bullish_count > bearish_count:
            direction = 'long'
        elif bearish_count >= 4 and bearish_count > bullish_count:
            direction = 'short'
        else:
            direction = 'neutral'

        # Уверенность: 0.5 + вклад от confluence (из 9 индикаторов)
        confidence = min(0.95, 0.5 + confluence_score * 0.05)

        return {
            'symbol': symbol,
            'indicators': {
                'rsi':   {'value': rsi.value,   'signal': rsi.signal,   'aligned': rsi.aligned},
                'macd':  {'value': macd.value,  'signal': macd.signal,  'aligned': macd.aligned},
                'ichimoku': {'value': ichi.value, 'signal': ichi.signal, 'aligned': ichi.aligned},
                'adx':   {'value': adx.value,   'signal': adx.signal,   'aligned': adx.aligned},
                'ema':   {'value': ema.value,   'signal': ema.signal,   'aligned': ema.aligned},
                'bb':    {'value': bb.value,    'signal': bb.signal,    'aligned': bb.aligned},
                'obv':   {'value': obv.value,   'signal': obv.signal,   'aligned': obv.aligned},
                'cmf':   {'value': cmf.value,   'signal': cmf.signal,   'aligned': cmf.aligned},
                'stoch': {'value': stoch.value, 'signal': stoch.signal, 'aligned': stoch.aligned},
            },
            'bullish_count': bullish_count,
            'bearish_count': bearish_count,
            'confluence_score': confluence_score,
            'direction': direction,
            'confidence': float(confidence),
        }
