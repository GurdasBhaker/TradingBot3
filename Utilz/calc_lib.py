import math

import pandas as pd
import warnings
from typing import Optional, List
from TB2.Utilz.signals.trend_following.moving_averages import MovingAverageSignals
from collections import defaultdict
from .signals.signal_factory import SignalFactory
from .signals.base.signal_base import SignalBase


class Calculators:
    """
    Backward compatible interface for all signal calculations.
    Delegates to new modular signal classes internally while maintaining
    the exact same API for existing code.
    """

    @classmethod
    def stochastic_oscilator(cls, df, k, smooth, d):
        """
        Calculate stochastic oscillator - delegates to StochasticSignal.
        Maintains exact same API for backward compatibility.
        """
        try:
            signal = SignalFactory.create_signal('stochastic', k=k, smooth=smooth, d=d)
            result_df = signal.calculate_signal(df)
            return result_df
        except Exception as e:
            warnings.warn(f"Stochastic oscillator calculation failed: {e}")
            # Return empty DataFrame with expected columns for backward compatibility
            empty_df = df.copy()
            empty_df['K%'] = None
            empty_df['D%'] = None
            return empty_df[['K%', 'D%']]

    @classmethod
    def stochastic_signals(cls, df, position, upper_bound, lower_bound):
        """
        Calculate stochastic trading signals - delegates to StochasticSignal.
        Maintains exact same API for backward compatibility.
        """
        try:
            signal = SignalFactory.create_signal('stochastic', upper_bound=upper_bound, lower_bound=lower_bound)
            result_df = signal.calculate_signal(df)
            result_df = signal.generate_actions(result_df)
            # Return the action column for backward compatibility
            return result_df
        except Exception as e:
            warnings.warn(f"Stochastic signals calculation failed: {e}")
            # Return empty Series for backward compatibility
            return pd.Series([None] * len(df), index=df.index, name='action')

    @classmethod
    def overbought_oversold(cls, df, upper_bound, lower_bound):
        """
        Calculate overbought/oversold levels - delegates to StochasticSignal.
        Maintains exact same API for backward compatibility.
        """
        try:
            signal = SignalFactory.create_signal('stochastic', upper_bound=upper_bound, lower_bound=lower_bound)
            result_df = signal.calculate_signal(df)
            # Create overbought/oversold signals based on thresholds
            overbought = result_df['K%'] >= upper_bound
            oversold = result_df['K%'] <= lower_bound
            result_df['overbought_oversold'] = 0  # Neutral
            result_df.loc[overbought, 'overbought_oversold'] = 1  # Overbought
            result_df.loc[oversold, 'overbought_oversold'] = -1  # Oversold
            return result_df
        except Exception as e:
            warnings.warn(f"Overbought/oversold calculation failed: {e}")
            return pd.Series([0] * len(df), index=df.index, name='overbought_oversold')

    @classmethod
    def k_vs_d(cls, df):
        """
        Calculate K% vs D% comparison - delegates to StochasticSignal.
        Maintains exact same API for backward compatibility.
        """
        try:
            signal = SignalFactory.create_signal('stochastic')
            result_df = signal.calculate_signal(df)
            # Create K% vs D% comparison
            k_above_d = result_df['K%'] > result_df['D%']
            result_df['k_vs_d'] = 0  # Neutral
            result_df.loc[k_above_d, 'k_vs_d'] = 1  # K% above D%
            result_df.loc[~k_above_d, 'k_vs_d'] = -1  # K% below D%
            return result_df
        except Exception as e:
            warnings.warn(f"K% vs D% calculation failed: {e}")
            return pd.Series([0] * len(df), index=df.index, name='k_vs_d')

    @classmethod
    def engulfing_candle(cls, df):
        """
        Calculate engulfing candle patterns - delegates to EngulfingSignal.
        Maintains exact same API for backward compatibility.
        """
        try:
            signal = SignalFactory.create_signal('engulfing')
            result_df = signal.calculate_signal(df)
            return result_df
        except Exception as e:
            warnings.warn(f"Engulfing candle calculation failed: {e}")
            return pd.Series([0] * len(df), index=df.index, name='Engulf_candle')

    @classmethod
    def fibonacci_df(cls, dataframe, levels):
        """
        Calculate fibonacci retracement levels - delegates to FibonacciSignals.
        Maintains exact same API for backward compatibility.
        """
        try:
            # FibonacciSignals is not in the SignalFactory registry, so import directly
            from .signals.trend_following.fibonacci import FibonacciSignals
            signal = FibonacciSignals(levels=levels)
            return signal.calculate_retracements(dataframe)
        except Exception as e:
            warnings.warn(f"Fibonacci calculation failed: {e}")
            # Return dataframe with empty fibonacci columns
            result_df = dataframe.copy()
            for level in levels:
                result_df[str(level)] = None
            return result_df

    @classmethod
    def stochastic_turning_df(cls, df, strategy, upper_bound, lower_bound):
        """
        Calculate stochastic turning points - delegates to StochasticSignal.
        Maintains exact same API for backward compatibility.
        """
        try:
            signal = SignalFactory.create_signal('stochastic', upper_bound=upper_bound, lower_bound=lower_bound)
            result_df = signal.calculate_signal(df)
            
            # Calculate turning points based on strategy
            turning_points = pd.Series([0] * len(df), index=df.index, name='turning_points')
            
            if strategy.lower() == 'crossover':
                # Turning points at K% and D% crossovers
                k_cross_up = (result_df['K%'] > result_df['D%']) & (result_df['K%'].shift(1) <= result_df['D%'].shift(1))
                k_cross_down = (result_df['K%'] < result_df['D%']) & (result_df['K%'].shift(1) >= result_df['D%'].shift(1))
                turning_points.loc[k_cross_up] = 1
                turning_points.loc[k_cross_down] = -1
            elif strategy.lower() == 'levels':
                # Turning points at overbought/oversold levels
                enter_overbought = (result_df['K%'] >= upper_bound) & (result_df['K%'].shift(1) < upper_bound)
                enter_oversold = (result_df['K%'] <= lower_bound) & (result_df['K%'].shift(1) > lower_bound)
                turning_points.loc[enter_overbought] = 1
                turning_points.loc[enter_oversold] = -1
            
            return turning_points
        except Exception as e:
            warnings.warn(f"Stochastic turning points calculation failed: {e}")
            return pd.Series([0] * len(df), index=df.index, name='turning_points')

    @classmethod
    def atr(cls, df, period=14):
        """
        Calculate Average True Range - delegates to ATRSignal.
        Returns Series for backward compatibility.
        """
        try:
            signal = SignalFactory.create_signal('atr', period=period)
            return signal.calculate_signal(df)
        except Exception as e:
            warnings.warn(f"ATR calculation failed: {e}")
            return None

    @classmethod
    def chandelier_exit(cls, df, period=22, atr_multiplier=3.0):
        """
        Calculate Chandelier Exit levels - delegates to ATRSignal.
        Maintains exact same API for backward compatibility.
        """
        try:
            signal = SignalFactory.create_signal('atr', period=period, atr_multiplier=atr_multiplier)
            result_df = signal.calculate_signal(df)
            return result_df
        except Exception as e:
            warnings.warn(f"Chandelier Exit calculation failed: {e}")
            # Return DataFrame with empty chandelier columns
            empty_df = df.copy()
            empty_df['Chandelier_Long'] = None
            empty_df['Chandelier_Short'] = None
            return empty_df[['Chandelier_Long', 'Chandelier_Short']]

    @classmethod
    def ma_crossover(cls, df, window, ma_shift=1, shift=1):
        """
        Calculate moving average crossover - delegates to MovingAverageSignal.
        Maintains exact same API for backward compatibility.
        """
        try:
            # Use dual moving average for crossover detection
            signal = SignalFactory.create_signal('moving_average', window=window, crossover_window=window + ma_shift)
            result_df = signal.calculate_signal(df)
            result_df = signal.generate_actions(result_df)
            return result_df
        except Exception as e:
            warnings.warn(f"Moving average crossover calculation failed: {e}")
            return pd.Series([None] * len(df), index=df.index, name='action')
    
    # Additional utility methods for extended functionality

    @classmethod
    def calc_multiple_mas(cls, df, windows, ma_type='ema'):
        return MovingAverageSignals.calculate_multiple_mas(df=df, windows=windows, ma_type=ma_type)

    @classmethod
    def get_available_signals(cls) -> List[str]:
        """
        Get list of all available signal types from the signal factory.
        
        Returns:
            List of available signal type names
        """
        return SignalFactory.get_available_signals()
    
    @classmethod
    def create_signal(cls, signal_type: str, **kwargs) -> SignalBase:
        """
        Create a signal instance using the signal factory.
        
        Args:
            signal_type: Type of signal to create
            **kwargs: Signal-specific parameters
            
        Returns:
            Signal instance
        """
        return SignalFactory.create_signal(signal_type, **kwargs)
    
    @classmethod
    def rsi(cls, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Calculate RSI (Relative Strength Index).
        
        Args:
            df: DataFrame with close price data
            period: Period for RSI calculation
            
        Returns:
            RSI values as Series
        """
        try:
            signal = SignalFactory.create_signal('rsi', period=period)
            result_df = signal.calculate_signal(df)
            return result_df
        except Exception as e:
            warnings.warn(f"RSI calculation failed: {e}")
            return pd.Series([None] * len(df), index=df.index, name='RSI')
    
    @classmethod
    def macd(cls, df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        """
        Calculate MACD (Moving Average Convergence Divergence).
        
        Args:
            df: DataFrame with close price data
            fast: Fast EMA period
            slow: Slow EMA period
            signal: Signal line EMA period
            
        Returns:
            DataFrame with MACD, MACD_signal, and MACD_histogram columns
        """
        try:
            macd_signal = SignalFactory.create_signal('macd', fast_period=fast, slow_period=slow, signal_period=signal)
            result_df = macd_signal.calculate_signal(df)
            return result_df
        except Exception as e:
            warnings.warn(f"MACD calculation failed: {e}")
            empty_df = df.copy()
            empty_df['MACD'] = None
            empty_df['MACD_signal'] = None
            empty_df['MACD_histogram'] = None
            return empty_df[['MACD', 'MACD_signal', 'MACD_histogram']]
    
    @classmethod
    def bollinger_bands(cls, df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
        """
        Calculate Bollinger Bands.
        
        Args:
            df: DataFrame with close price data
            window: Window for moving average
            num_std: Number of standard deviations for bands
            
        Returns:
            DataFrame with BB_upper, BB_middle, BB_lower columns
        """
        try:
            signal = SignalFactory.create_signal('bollinger_bands', period=period, std_dev=std_dev)
            return signal.calculate_signal(df)
        except Exception as e:
            warnings.warn(f"Bollinger Bands calculation failed: {e}")
            empty_df = df.copy()
            empty_df['BB_upper'] = None
            empty_df['BB_middle'] = None
            empty_df['BB_lower'] = None
            return empty_df[['BB_upper', 'BB_middle', 'BB_lower']]

    @classmethod
    def currency_strength(cls, data):
        """
        data: dict of { 'usdjpy': DataFrame(datetime, close), ... }
        returns: dict { 'USD': score, 'JPY': score, ... }
        """
        scores, counts = defaultdict(float), defaultdict(int)

        for sym, df in data.items():
            if len(sym) < 6 or df.empty:
                continue
            sym = sym.upper()
            base, quote = sym[:3], sym[3:6]

            closes = df["close"].dropna().values
            if len(closes) < 2 or closes[0] <= 0 or closes[-1] <= 0:
                continue

            # log return from first to last close
            r = math.log(closes[-1] / closes[0])

            scores[base]  += r
            scores[quote] -= r
            counts[base]  += 1
            counts[quote] += 1

        return {ccy: scores[ccy] / counts[ccy] for ccy in scores if counts[ccy] > 0}