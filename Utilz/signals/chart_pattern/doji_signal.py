"""
Doji candlestick pattern signal with calculation and action generation.
"""

import pandas as pd
from ..base.signal_base import SignalBase, ActionType


class DojiSignal(SignalBase):
    """
    Doji candlestick pattern signal implementation.
    
    Provides:
    - Doji pattern detection
    - Buy/sell action generation based on doji patterns
    """
    
    def __init__(self, threshold=0.1):
        """
        Initialize Doji pattern signal.
        
        Args:
            threshold: Threshold for body size relative to range (0.1 = 10%)
        """
        super().__init__(threshold=threshold)
    
    def calculate_signal(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Doji candle patterns.
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            DataFrame with Doji column added
        """
        self.validate_data(df, required_columns=['open', 'high', 'low', 'close'])
        df = df.copy()
        
        threshold = self.params['threshold']
        
        # Calculate candle body and range
        body_size = abs(df['close'] - df['open'])
        candle_range = df['high'] - df['low']
        
        # Avoid division by zero
        body_ratio = body_size / candle_range.replace(0, float('inf'))
        
        # Doji condition: small body relative to range
        doji_condition = body_ratio <= threshold
        
        df['Doji'] = 0
        df.loc[doji_condition, 'Doji'] = 1
        
        return df
    
    def generate_actions(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate buy/sell actions based on Doji patterns.
        
        Args:
            df: DataFrame with Doji pattern data
            
        Returns:
            DataFrame with action column added
        """
        df = df.copy()
        
        # Ensure Doji data exists
        if 'Doji' not in df.columns:
            df = self.calculate_signal(df)
        
        # Initialize action column
        df['action'] = ActionType.NULL.value
        
        # Doji patterns are typically reversal signals
        # We'll use simple trend context for action generation
        df['close_prev'] = df['close'].shift(1)
        df['close_2prev'] = df['close'].shift(2)
        
        # Determine trend context
        uptrend = df['close_prev'] > df['close_2prev']
        downtrend = df['close_prev'] < df['close_2prev']
        
        # Buy signal: Doji after downtrend (potential reversal)
        buy_condition = (df['Doji'] == 1) & downtrend
        df.loc[buy_condition, 'action'] = ActionType.BUY.value
        
        # Sell signal: Doji after uptrend (potential reversal)
        sell_condition = (df['Doji'] == 1) & uptrend
        df.loc[sell_condition, 'action'] = ActionType.SELL.value
        
        return df
