"""
ATR (Average True Range) signal with calculation and action generation.
"""

import pandas as pd
from ..base.signal_base import SignalBase, ActionType


class ATRSignal(SignalBase):
    """
    ATR (Average True Range) signal implementation.
    
    Provides:
    - ATR calculation
    - Chandelier Exit-based buy/sell action generation
    """
    
    def __init__(self, period=14, atr_multiplier=3.0):
        """
        Initialize ATR signal.
        
        Args:
            period: Period for ATR calculation
            atr_multiplier: Multiplier for Chandelier Exit calculation
        """
        super().__init__(period=period, atr_multiplier=atr_multiplier)
    
    def calculate_signal(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate ATR and Chandelier Exit levels.
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            DataFrame with ATR, Chandelier_Long, Chandelier_Short columns added
        """
        self.validate_data(df, required_columns=['high', 'low', 'close'])
        df = df.copy()
        
        period = self.params['period']
        atr_multiplier = self.params['atr_multiplier']
        
        # Calculate True Range components
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        
        # True Range is the maximum of the three components
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        
        # ATR is EMA of True Range
        df['ATR'] = true_range.ewm(span=period, adjust=False).mean()
        
        # Calculate highest high and lowest low over the period
        highest_high = df['high'].rolling(window=period).max()
        lowest_low = df['low'].rolling(window=period).min()
        
        # Calculate Chandelier Exit levels
        df['Chandelier_Long'] = highest_high - atr_multiplier * df['ATR']
        df['Chandelier_Short'] = lowest_low + atr_multiplier * df['ATR']
        
        return df
    
    def generate_actions(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate buy/sell actions based on Chandelier Exit levels.
        
        Args:
            df: DataFrame with ATR and Chandelier Exit data
            
        Returns:
            DataFrame with action column added
        """
        df = df.copy()
        
        # Ensure ATR data exists
        if 'Chandelier_Long' not in df.columns:
            df = self.calculate_signal(df)
        
        # Initialize action column
        df['action'] = ActionType.NULL.value
        
        # Calculate previous values for crossover detection
        df['close_prev'] = df['close'].shift(1)
        df['Chandelier_Long_prev'] = df['Chandelier_Long'].shift(1)
        df['Chandelier_Short_prev'] = df['Chandelier_Short'].shift(1)
        
        # Buy signal: Price crosses above Chandelier Long
        buy_condition = (
            (df['close_prev'] <= df['Chandelier_Long_prev']) &
            (df['close'] > df['Chandelier_Long'])
        )
        df.loc[buy_condition, 'action'] = ActionType.BUY.value
        
        # Sell signal: Price crosses below Chandelier Short
        sell_condition = (
            (df['close_prev'] >= df['Chandelier_Short_prev']) &
            (df['close'] < df['Chandelier_Short'])
        )
        df.loc[sell_condition, 'action'] = ActionType.SELL.value
        
        # Hold signal: Price above Chandelier Long (uptrend)
        hold_condition = (
            (df['close'] > df['Chandelier_Long']) &
            ~buy_condition &
            ~sell_condition
        )
        df.loc[hold_condition, 'action'] = ActionType.HOLD.value
        
        return df
