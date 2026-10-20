"""
Moving Average and crossover signals for trend following.
"""

import pandas as pd
from ..base.signal_base import SignalBase


class MovingAverageSignals(SignalBase):
    """
    Moving Average and crossover signal calculations.
    
    Provides:
    - Moving average crossover signals
    - Various MA types (SMA, EMA)
    """
    
    def __init__(self, window=20, ma_shift=1, shift=1, ma_type='sma'):
        """
        Initialize moving average signals.
        
        Args:
            window: Period for moving average calculation
            ma_shift: Shift for second moving average
            shift: Shift for crossover detection
            ma_type: Type of moving average ('sma' or 'ema')
        """
        super().__init__(
            window=window, 
            ma_shift=ma_shift, 
            shift=shift, 
            ma_type=ma_type
        )
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Main calculate method for base class compliance.
        Calculates moving average crossover signals.
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            DataFrame with MA crossover signals added
        """
        self.validate_data(df, required_columns=['close'])
        return self.calculate_crossover(df)
    
    def calculate_crossover(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate moving average crossover signals.
        
        Args:
            df: DataFrame with close price data
            
        Returns:
            DataFrame with MA crossover signals and columns added
        """
        self.validate_data(df, required_columns=['close'])
        df = df.copy()
        
        window = self.params['window']
        ma_shift = self.params['ma_shift']
        shift = self.params['shift']
        ma_type = self.params['ma_type']
        
        # Calculate moving averages
        if ma_type.lower() == 'ema':
            df['MA1'] = df['close'].ewm(span=window, adjust=False).mean()
            df['MA2'] = df['close'].ewm(span=window, adjust=False).mean().shift(ma_shift)
        else:  # SMA
            df['MA1'] = df['close'].rolling(window=window).mean()
            df['MA2'] = df['close'].rolling(window=window).mean().shift(ma_shift)
        
        # Calculate shifted values for crossover detection
        df['MA1_shifted'] = df['MA1'].shift(shift)
        df['MA2_shifted'] = df['MA2'].shift(shift)
        
        # Initialize signal column
        df['Signal'] = 0
        
        # Bearish crossover: MA1 crosses below MA2
        df.loc[
            (df['MA1_shifted'] >= df['MA2_shifted']) &
            (df['MA1'] <= df['MA2']), 'Signal'
        ] = -1
        
        # Bullish crossover: MA1 crosses above MA2
        df.loc[
            (df['MA1_shifted'] <= df['MA2_shifted']) &
            (df['MA1'] > df['MA2']), 'Signal'
        ] = 1
        
        # Mark crossover occurrences
        df['Cross'] = 0
        df.loc[df['Signal'] != 0, 'Cross'] = 1
        
        return df
    
    def calculate_single_ma(self, df: pd.DataFrame, window: int = None, ma_type: str = None) -> pd.DataFrame:
        """
        Calculate a single moving average.
        
        Args:
            df: DataFrame with close price data
            window: Period for MA (uses instance default if None)
            ma_type: Type of MA (uses instance default if None)
            
        Returns:
            DataFrame with MA column added
        """
        self.validate_data(df, required_columns=['close'])
        df = df.copy()
        
        window = window or self.params['window']
        ma_type = ma_type or self.params['ma_type']
        
        if ma_type.lower() == 'ema':
            df['MA'] = df['close'].ewm(span=window, adjust=False).mean()
        else:  # SMA
            df['MA'] = df['close'].rolling(window=window).mean()
        
        return df
    
    @staticmethod
    def calculate_multiple_mas(df: pd.DataFrame, windows: list, ma_type: str = None) -> pd.DataFrame:
        """
        Calculate multiple moving averages.
        
        Args:
            df: DataFrame with close price data
            windows: List of periods for MAs
            ma_type: Type of MA (uses instance default if None)
            
        Returns:
            DataFrame with multiple MA columns added
        """
        if 'close' not in df.columns:
            # optionally auto-rename 'Close' -> 'close'
            if 'Close' in df.columns:
                df = df.rename(columns={'Close': 'close'})
            else:
                raise ValueError("DataFrame must have a 'close' column")

        out = df.copy()
        for window in windows:
            if str(ma_type).lower() == 'ema':
                out[f'EMA_{window}'] = out['close'].ewm(span=window, adjust=False).mean()
            else:
                out[f'SMA_{window}'] = out['close'].rolling(window=window).mean()

        return out
