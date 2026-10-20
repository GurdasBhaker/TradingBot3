"""
Bollinger Bands signal with calculation and action generation.
"""

import pandas as pd
from ..base.signal_base import SignalBase, ActionType


class BollingerBandsSignal(SignalBase):
    """
    Bollinger Bands signal implementation.
    
    Provides:
    - Bollinger Bands calculation
    - Buy/sell action generation based on band interactions
    """
    
    def __init__(self, period=20, std_dev=2.0):
        """
        Initialize Bollinger Bands signal.
        
        Args:
            period: Period for moving average and standard deviation (default 20)
            std_dev: Standard deviation multiplier (default 2.0)
        """
        super().__init__(
            period=period,
            std_dev=std_dev
        )
    
    def calculate_signal(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Bollinger Bands (Upper, Middle, Lower).
        
        Args:
            df: DataFrame with close price data
            
        Returns:
            DataFrame with BB_Upper, BB_Middle, BB_Lower columns added
        """
        self.validate_data(df, required_columns=['close'])
        df = df.copy()
        
        period = self.params['period']
        std_dev = self.params['std_dev']
        
        # Calculate middle band (SMA)
        df['BB_Middle'] = df['close'].rolling(window=period).mean()
        
        # Calculate standard deviation
        rolling_std = df['close'].rolling(window=period).std()
        
        # Calculate upper and lower bands
        df['BB_Upper'] = df['BB_Middle'] + (std_dev * rolling_std)
        df['BB_Lower'] = df['BB_Middle'] - (std_dev * rolling_std)
        
        return df
    
    def generate_actions(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate buy/sell actions based on Bollinger Bands.
        
        Args:
            df: DataFrame with Bollinger Bands data
            
        Returns:
            DataFrame with action column added
        """
        df = df.copy()
        
        # Ensure Bollinger Bands data exists
        if 'BB_Upper' not in df.columns:
            df = self.calculate_signal(df)
        
        # Initialize action column
        df['action'] = ActionType.NULL.value
        
        # Calculate previous values for crossover detection
        df['close_prev'] = df['close'].shift(1)
        df['BB_Middle_prev'] = df['BB_Middle'].shift(1)
        df['BB_Lower_prev'] = df['BB_Lower'].shift(1)
        df['BB_Upper_prev'] = df['BB_Upper'].shift(1)
        
        # Buy signal: Price crosses above middle band (trend following)
        buy_condition = (
            (df['close_prev'] <= df['BB_Middle_prev']) &
            (df['close'] > df['BB_Middle'])
        )
        df.loc[buy_condition, 'action'] = ActionType.BUY.value
        
        # Sell signal: Price crosses below middle band (trend following)
        sell_condition = (
            (df['close_prev'] >= df['BB_Middle_prev']) &
            (df['close'] < df['BB_Middle'])
        )
        df.loc[sell_condition, 'action'] = ActionType.SELL.value
        
        # Alternative: Mean reversion signals
        # Buy when price touches lower band (oversold)
        mean_reversion_buy = (
            (df['close_prev'] > df['BB_Lower_prev']) &
            (df['close'] <= df['BB_Lower'])
        )
        
        # Sell when price touches upper band (overbought)
        mean_reversion_sell = (
            (df['close_prev'] < df['BB_Upper_prev']) &
            (df['close'] >= df['BB_Upper'])
        )
        
        # Use trend following as primary, mean reversion as secondary
        df.loc[mean_reversion_buy & ~buy_condition & ~sell_condition, 'action'] = ActionType.BUY.value
        df.loc[mean_reversion_sell & ~buy_condition & ~sell_condition, 'action'] = ActionType.SELL.value
        
        # Hold signal: Price above middle band (uptrend)
        hold_condition = (
            (df['close'] > df['BB_Middle']) &
            ~buy_condition &
            ~sell_condition &
            ~mean_reversion_buy &
            ~mean_reversion_sell
        )
        df.loc[hold_condition, 'action'] = ActionType.HOLD.value
        
        return df
