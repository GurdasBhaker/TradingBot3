"""
MACD (Moving Average Convergence Divergence) signal with calculation and action generation.
"""

import pandas as pd
import numpy as np
from ..base.signal_base import SignalBase, ActionType


class MACDSignal(SignalBase):
    """
    MACD (Moving Average Convergence Divergence) signal implementation.
    
    Provides:
    - MACD line, signal line, and histogram calculation
    - Buy/sell action generation based on crossovers
    """
    
    def __init__(self, fast_period=12, slow_period=26, signal_period=9):
        """
        Initialize MACD signal.
        
        Args:
            fast_period: Period for fast EMA (default 12)
            slow_period: Period for slow EMA (default 26)
            signal_period: Period for signal line EMA (default 9)
        """
        super().__init__(
            fast_period=fast_period,
            slow_period=slow_period,
            signal_period=signal_period
        )
    
    def calculate_signal(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate MACD line, signal line, and histogram.
        
        Args:
            df: DataFrame with close price data
            
        Returns:
            DataFrame with MACD, Signal, and Histogram columns added
        """
        self.validate_data(df, required_columns=['close'])
        df = df.copy()
        
        fast_period = self.params['fast_period']
        slow_period = self.params['slow_period']
        signal_period = self.params['signal_period']
        
        # Calculate EMAs
        ema_fast = df['close'].ewm(span=fast_period, adjust=False).mean()
        ema_slow = df['close'].ewm(span=slow_period, adjust=False).mean()
        
        # Calculate MACD line
        df['MACD'] = ema_fast - ema_slow
        
        # Calculate Signal line (EMA of MACD)
        df['MACD_Signal'] = df['MACD'].ewm(span=signal_period, adjust=False).mean()
        
        # Calculate Histogram
        df['MACD_Histogram'] = df['MACD'] - df['MACD_Signal']
        
        # Calculate previous values for crossover detection
        df['MACD_prev'] = df['MACD'].shift(1)
        df['Signal_prev'] = df['MACD_Signal'].shift(1)
        df['Histogram_prev'] = df['MACD_Histogram'].shift(1)
        
        return df
    
    def generate_actions(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate buy/sell actions based on MACD crossovers.
        
        Args:
            df: DataFrame with MACD data
            
        Returns:
            DataFrame with action column added
        """
        df = df.copy()
        
        # Ensure MACD data exists
        if 'MACD' not in df.columns:
            df = self.calculate_signal(df)
        
        # Initialize action column
        df['action'] = ActionType.NULL.value
        
        # Buy signal: MACD crosses above Signal line
        buy_condition = (
            (df['MACD_prev'] <= df['Signal_prev']) &
            (df['MACD'] > df['MACD_Signal'])
        )
        df.loc[buy_condition, 'action'] = ActionType.BUY.value
        
        # Sell signal: MACD crosses below Signal line
        sell_condition = (
            (df['MACD_prev'] >= df['Signal_prev']) &
            (df['MACD'] < df['MACD_Signal'])
        )
        df.loc[sell_condition, 'action'] = ActionType.SELL.value
        
        # Hold signal: MACD above signal line (bullish trend)
        hold_condition = (
            (df['MACD'] > df['MACD_Signal']) &
            ~buy_condition &
            ~sell_condition
        )
        df.loc[hold_condition, 'action'] = ActionType.HOLD.value
        
        return df
    
