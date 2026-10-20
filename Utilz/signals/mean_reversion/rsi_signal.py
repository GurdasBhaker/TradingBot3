"""
RSI (Relative Strength Index) signal with calculation and action generation.
"""

import pandas as pd
from Utilz.signals.base.signal_base import SignalBase, ActionType


class RSISignal(SignalBase):
    """
    RSI (Relative Strength Index) signal implementation.
    
    Provides:
    - RSI calculation
    - Buy/sell action generation based on overbought/oversold levels
    """
    
    def __init__(self, period=14, overbought=70, oversold=30):
        """
        Initialize RSI signal.
        
        Args:
            period: Period for RSI calculation (default 14)
            overbought: Overbought threshold (default 70)
            oversold: Oversold threshold (default 30)
        """
        super().__init__(
            period=period,
            overbought=overbought,
            oversold=oversold
        )
    
    def calculate_signal(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate RSI (Relative Strength Index).
        
        Args:
            df: DataFrame with close price data
            
        Returns:
            DataFrame with RSI column added
        """
        self.validate_data(df, required_columns=['close'])
        df = df.copy()
        
        period = self.params['period']
        
        # Calculate price changes
        delta = df['close'].diff()
        
        # Separate gains and losses
        gains = delta.where(delta > 0, 0)
        losses = -delta.where(delta < 0, 0)
        
        # Calculate average gains and losses using EMA
        avg_gains = gains.ewm(span=period, adjust=False).mean()
        avg_losses = losses.ewm(span=period, adjust=False).mean()
        
        # Calculate RSI
        rs = avg_gains / avg_losses
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # Handle division by zero (when avg_losses = 0)
        df['RSI'] = df['RSI'].fillna(100)
        
        return df
    
    def generate_actions(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate buy/sell actions based on RSI overbought/oversold levels.
        
        Args:
            df: DataFrame with RSI data
            
        Returns:
            DataFrame with action column added
        """
        df = df.copy()
        
        # Ensure RSI data exists
        if 'RSI' not in df.columns:
            df = self.calculate_signal(df)
        
        overbought = self.params['overbought']
        oversold = self.params['oversold']
        
        # Initialize action column
        df['action'] = ActionType.NULL.value
        
        # Generate actions based on crossovers for better timing
        df['RSI_prev'] = df['RSI'].shift(1)
        
        # Buy signal: RSI crosses above oversold level (bullish)
        buy_condition = (
            (df['RSI_prev'] <= oversold) &
            (df['RSI'] > oversold)
        )
        df.loc[buy_condition, 'action'] = ActionType.BUY.value
        
        # Sell signal: RSI crosses below overbought level (bearish)
        sell_condition = (
            (df['RSI_prev'] >= overbought) &
            (df['RSI'] < overbought)
        )
        df.loc[sell_condition, 'action'] = ActionType.SELL.value
        
        # Hold signal: RSI in middle range
        hold_condition = (
            (df['RSI'] > oversold) &
            (df['RSI'] < overbought) &
            ~buy_condition &
            ~sell_condition
        )
        df.loc[hold_condition, 'action'] = ActionType.HOLD.value
        
        return df
    
