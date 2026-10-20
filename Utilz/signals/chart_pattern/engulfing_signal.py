"""
Engulfing candlestick pattern signal with calculation and action generation.
"""

import pandas as pd
from ..base.signal_base import SignalBase, ActionType


class EngulfingSignal(SignalBase):
    """
    Engulfing candlestick pattern signal implementation.
    
    Provides:
    - Bullish and bearish engulfing pattern detection
    - Buy/sell action generation based on engulfing patterns
    """
    
    def __init__(self, min_body_ratio=0.1):
        """
        Initialize engulfing pattern signal.
        
        Args:
            min_body_ratio: Minimum body size relative to range for valid pattern
        """
        super().__init__(
            min_body_ratio=min_body_ratio
        )
    
    def calculate_signal(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate bullish and bearish engulfing candle patterns.
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            DataFrame with Engulf_candle column added
        """
        self.validate_data(df, required_columns=['open', 'high', 'low', 'close'])
        df = df.copy()
        
        min_body_ratio = self.params['min_body_ratio']
        
        # Calculate candle body sizes
        current_body = abs(df['close'] - df['open'])
        prev_body = abs(df['close'].shift(1) - df['open'].shift(1))
        current_range = df['high'] - df['low']
        prev_range = df['high'].shift(1) - df['low'].shift(1)
        
        # Ensure significant body sizes
        current_body_valid = current_body / current_range >= min_body_ratio
        prev_body_valid = prev_body / prev_range >= min_body_ratio
        
        # Bearish engulfing condition
        bear_engulf_condition = (
            (df['high'] > df['high'].shift(1)) &  # Current high > previous high
            (df['close'] < df['close'].shift(1)) &  # Current close < previous close
            (df['close'] < df['open'].shift(1)) &  # Current close < previous open
            (df['open'] > df['close'].shift(1)) &  # Current open > previous close
            current_body_valid &  # Current candle has significant body
            prev_body_valid  # Previous candle has significant body
        )
        
        # Bullish engulfing condition
        bull_engulf_condition = (
            (df['low'] < df['low'].shift(1)) &  # Current low < previous low
            (df['close'] > df['close'].shift(1)) &  # Current close > previous close
            (df['close'] > df['open'].shift(1)) &  # Current close > previous open
            (df['open'] < df['close'].shift(1)) &  # Current open < previous close
            current_body_valid &  # Current candle has significant body
            prev_body_valid  # Previous candle has significant body
        )
        
        # Create the Engulf_candle column
        df['Engulf_candle'] = 0  # Initialize with 0
        df.loc[bear_engulf_condition, 'Engulf_candle'] = -1  # Bearish engulfing
        df.loc[bull_engulf_condition, 'Engulf_candle'] = 1   # Bullish engulfing
        
        return df
    
    def generate_actions(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate buy/sell actions based on engulfing patterns.
        
        Args:
            df: DataFrame with engulfing pattern data
            
        Returns:
            DataFrame with action column added
        """
        df = df.copy()
        
        # Ensure engulfing data exists
        if 'Engulf_candle' not in df.columns:
            df = self.calculate_signal(df)
        
        # Initialize action column
        df['action'] = ActionType.NULL.value
        
        # Buy signal: Bullish engulfing pattern
        buy_condition = df['Engulf_candle'] == 1
        df.loc[buy_condition, 'action'] = ActionType.BUY.value
        
        # Sell signal: Bearish engulfing pattern
        sell_condition = df['Engulf_candle'] == -1
        df.loc[sell_condition, 'action'] = ActionType.SELL.value
        
        return df
    
