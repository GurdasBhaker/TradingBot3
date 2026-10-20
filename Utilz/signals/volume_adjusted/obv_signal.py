"""
OBV (On-Balance Volume) signal with calculation and action generation.
"""

import pandas as pd
import numpy as np
from ..base.signal_base import SignalBase, ActionType


class OBVSignal(SignalBase):
    """
    OBV (On-Balance Volume) signal implementation.
    
    Provides:
    - OBV calculation
    - Buy/sell action generation based on OBV trends and crossovers
    """
    
    def __init__(self, ma_period=20):
        """
        Initialize OBV signal.
        
        Args:
            ma_period: Period for OBV moving average (default 20)
        """
        super().__init__(ma_period=ma_period)
    
    def calculate_signal(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate OBV and its moving average.
        
        Args:
            df: DataFrame with close price and volume data
            
        Returns:
            DataFrame with OBV and OBV_MA columns added
        """
        self.validate_data(df, required_columns=['close', 'volume'])
        df = df.copy()
        
        ma_period = self.params['ma_period']
        
        # Calculate price change
        df['price_change'] = df['close'].diff()
        
        # Calculate OBV
        df['OBV_change'] = np.where(
            df['price_change'] > 0, df['volume'],
            np.where(df['price_change'] < 0, -df['volume'], 0)
        )
        
        # Calculate cumulative OBV
        df['OBV'] = df['OBV_change'].cumsum()
        
        # Calculate OBV moving average
        df['OBV_MA'] = df['OBV'].rolling(window=ma_period).mean()
        
        return df
    
    def generate_actions(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate buy/sell actions based on OBV vs OBV moving average.
        
        Args:
            df: DataFrame with OBV data
            
        Returns:
            DataFrame with action column added
        """
        df = df.copy()
        
        # Ensure OBV data exists
        if 'OBV' not in df.columns:
            df = self.calculate_signal(df)
        
        # Initialize action column
        df['action'] = ActionType.NULL.value
        
        # Calculate previous values for crossover detection
        df['OBV_prev'] = df['OBV'].shift(1)
        df['OBV_MA_prev'] = df['OBV_MA'].shift(1)
        
        # Buy signal: OBV crosses above its MA
        buy_condition = (
            (df['OBV_prev'] <= df['OBV_MA_prev']) &
            (df['OBV'] > df['OBV_MA'])
        )
        df.loc[buy_condition, 'action'] = ActionType.BUY.value
        
        # Sell signal: OBV crosses below its MA
        sell_condition = (
            (df['OBV_prev'] >= df['OBV_MA_prev']) &
            (df['OBV'] < df['OBV_MA'])
        )
        df.loc[sell_condition, 'action'] = ActionType.SELL.value
        
        # Hold signal: OBV above its MA (volume supporting uptrend)
        hold_condition = (
            (df['OBV'] > df['OBV_MA']) &
            ~buy_condition &
            ~sell_condition
        )
        df.loc[hold_condition, 'action'] = ActionType.HOLD.value
        
        return df
