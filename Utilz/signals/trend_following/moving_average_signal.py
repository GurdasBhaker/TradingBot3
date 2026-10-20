"""
Moving Average signal with calculation and action generation.
"""

import pandas as pd
from ..base.signal_base import SignalBase, ActionType


class MovingAverageSignal(SignalBase):
    """
    Moving Average signal implementation.
    
    Provides:
    - Moving average calculation (SMA, EMA)
    - Buy/sell action generation based on price vs MA and MA crossovers
    """
    
    def __init__(self, window=20, ma_type='sma', crossover_window=None):
        """
        Initialize moving average signal.
        
        Args:
            window: Period for moving average calculation
            ma_type: Type of moving average ('sma' or 'ema')
            crossover_window: Second MA window for crossover signals (optional)
        """
        super().__init__(
            window=window, 
            ma_type=ma_type,
            crossover_window=crossover_window
        )
    
    def calculate_signal(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate moving average(s).
        
        Args:
            df: DataFrame with close price data
            
        Returns:
            DataFrame with MA columns added
        """
        self.validate_data(df, required_columns=['close'])
        df = df.copy()
        
        window = self.params['window']
        ma_type = self.params['ma_type']
        crossover_window = self.params.get('crossover_window')
        
        # Calculate primary moving average
        if ma_type.lower() == 'ema':
            df['MA'] = df['close'].ewm(span=window, adjust=False).mean()
        else:  # SMA
            df['MA'] = df['close'].rolling(window=window).mean()
        
        # Calculate secondary MA for crossover if specified
        if crossover_window:
            if ma_type.lower() == 'ema':
                df['MA2'] = df['close'].ewm(span=crossover_window, adjust=False).mean()
            else:  # SMA
                df['MA2'] = df['close'].rolling(window=crossover_window).mean()
            
            # Calculate previous values for crossover detection
            df['MA_prev'] = df['MA'].shift(1)
            df['MA2_prev'] = df['MA2'].shift(1)
        
        # Calculate previous close for trend detection
        df['close_prev'] = df['close'].shift(1)
        df['MA_prev_single'] = df['MA'].shift(1)
        
        return df
    
    def generate_actions(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate buy/sell actions based on moving average signals.
        
        Args:
            df: DataFrame with MA data
            
        Returns:
            DataFrame with action column added
        """
        df = df.copy()
        
        # Ensure MA data exists
        if 'MA' not in df.columns:
            df = self.calculate_signal(df)
        
        crossover_window = self.params.get('crossover_window')
        
        # Initialize action column
        df['action'] = ActionType.NULL.value
        
        if crossover_window and 'MA2' in df.columns:
            # Crossover strategy: fast MA vs slow MA
            self._generate_crossover_actions(df)
        else:
            # Price vs MA strategy
            self._generate_price_ma_actions(df)
        
        return df
    
    def _generate_crossover_actions(self, df: pd.DataFrame) -> None:
        """Generate actions based on MA crossovers."""
        
        # Buy signal: Fast MA crosses above Slow MA
        buy_condition = (
            (df['MA_prev'] <= df['MA2_prev']) &
            (df['MA'] > df['MA2'])
        )
        df.loc[buy_condition, 'action'] = ActionType.BUY.value
        
        # Sell signal: Fast MA crosses below Slow MA
        sell_condition = (
            (df['MA_prev'] >= df['MA2_prev']) &
            (df['MA'] < df['MA2'])
        )
        df.loc[sell_condition, 'action'] = ActionType.SELL.value
        
        # Hold signal: Fast MA above Slow MA (uptrend)
        hold_condition = (
            (df['MA'] > df['MA2']) &
            ~buy_condition &
            ~sell_condition
        )
        df.loc[hold_condition, 'action'] = ActionType.HOLD.value
    
    def _generate_price_ma_actions(self, df: pd.DataFrame) -> None:
        """Generate actions based on price vs MA."""
        
        # Buy signal: Price crosses above MA
        buy_condition = (
            (df['close_prev'] <= df['MA_prev_single']) &
            (df['close'] > df['MA'])
        )
        df.loc[buy_condition, 'action'] = ActionType.BUY.value
        
        # Sell signal: Price crosses below MA
        sell_condition = (
            (df['close_prev'] >= df['MA_prev_single']) &
            (df['close'] < df['MA'])
        )
        df.loc[sell_condition, 'action'] = ActionType.SELL.value
        
        # Hold signal: Price above MA (uptrend)
        hold_condition = (
            (df['close'] > df['MA']) &
            ~buy_condition &
            ~sell_condition
        )
        df.loc[hold_condition, 'action'] = ActionType.HOLD.value
    
