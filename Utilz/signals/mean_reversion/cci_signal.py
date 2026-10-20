"""
CCI (Commodity Channel Index) signal with calculation and action generation.
"""

import pandas as pd
import numpy as np
from ..base.signal_base import SignalBase, ActionType


class CCISignal(SignalBase):
    """
    CCI (Commodity Channel Index) signal implementation.
    
    Provides:
    - CCI calculation
    - Buy/sell action generation based on overbought/oversold levels
    """
    
    def __init__(self, period=20, overbought=100, oversold=-100):
        """
        Initialize CCI signal.
        
        Args:
            period: Period for CCI calculation (default 20)
            overbought: Overbought threshold (default 100)
            oversold: Oversold threshold (default -100)
        """
        super().__init__(
            period=period,
            overbought=overbought,
            oversold=oversold
        )
    
    def calculate_signal(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate CCI (Commodity Channel Index).
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            DataFrame with CCI column added
        """
        self.validate_data(df, required_columns=['high', 'low', 'close'])
        df = df.copy()
        
        period = self.params['period']
        
        # Calculate Typical Price
        df['TP'] = (df['high'] + df['low'] + df['close']) / 3
        
        # Calculate Simple Moving Average of Typical Price
        df['SMA_TP'] = df['TP'].rolling(window=period).mean()
        
        # Calculate Mean Absolute Deviation
        df['MAD'] = df['TP'].rolling(window=period).apply(
            lambda x: np.mean(np.abs(x - x.mean())), raw=True
        )
        
        # Calculate CCI
        df['CCI'] = (df['TP'] - df['SMA_TP']) / (0.015 * df['MAD'])
        
        # Handle division by zero
        df['CCI'] = df['CCI'].fillna(0)
        
        return df
    
    def generate_actions(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate buy/sell actions based on CCI overbought/oversold levels.
        
        Args:
            df: DataFrame with CCI data
            
        Returns:
            DataFrame with action column added
        """
        df = df.copy()
        
        # Ensure CCI data exists
        if 'CCI' not in df.columns:
            df = self.calculate_signal(df)
        
        overbought = self.params['overbought']
        oversold = self.params['oversold']
        
        # Initialize action column
        df['action'] = ActionType.NULL.value
        
        # Calculate previous CCI for crossover detection
        df['CCI_prev'] = df['CCI'].shift(1)
        
        # Buy signal: CCI crosses above oversold level
        buy_condition = (
            (df['CCI_prev'] <= oversold) &
            (df['CCI'] > oversold)
        )
        df.loc[buy_condition, 'action'] = ActionType.BUY.value
        
        # Sell signal: CCI crosses below overbought level
        sell_condition = (
            (df['CCI_prev'] >= overbought) &
            (df['CCI'] < overbought)
        )
        df.loc[sell_condition, 'action'] = ActionType.SELL.value
        
        # Hold signal: CCI in middle range
        hold_condition = (
            (df['CCI'] > oversold) &
            (df['CCI'] < overbought) &
            ~buy_condition &
            ~sell_condition
        )
        df.loc[hold_condition, 'action'] = ActionType.HOLD.value
        
        return df
