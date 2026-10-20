"""
ATR (Average True Range) and related trend following signals.
"""

import pandas as pd
from ..base.signal_base import SignalBase


class ATRSignals(SignalBase):
    """
    ATR and related trend-following signal calculations.
    
    Provides:
    - Average True Range calculation
    - Chandelier Exit levels
    """
    
    def __init__(self, period=14, atr_multiplier=3.0):
        """
        Initialize ATR signals.
        
        Args:
            period: Period for ATR calculation
            atr_multiplier: Multiplier for Chandelier Exit calculation
        """
        super().__init__(period=period, atr_multiplier=atr_multiplier)
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Main calculate method for base class compliance.
        Calculates ATR.
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            DataFrame with ATR column added
        """
        self.validate_data(df, required_columns=['high', 'low', 'close'])
        return self.calculate_atr(df)

    def calculate_atr(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Average True Range (ATR) with selectable smoothing.
        Params expected in self.params:
          - period: int (e.g., 14)
          - method: str in {'ema', 'wilder'}  # default 'ema'
        Returns the input df with:
          - 'TR'           : True Range
          - 'ATR_EMA'      : EMA-smoothed TR (alpha = 2/(period+1))
          - 'ATR_Wilder'   : Wilder-smoothed TR (alpha = 1/period)
          - 'ATR'          : Alias to the chosen method (for convenience)
        """

        self.validate_data(df, required_columns=['high', 'low', 'close'])
        out = df.copy()

        period = int(self.params.get('period', 14))
        method = str(self.params.get('method', 'ema')).lower()

        # True Range
        high_low = (out['high'] - out['low']).abs()
        high_close = (out['high'] - out['close'].shift(1)).abs()
        low_close = (out['low'] - out['close'].shift(1)).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        out['TR'] = tr

        # EMA ATR (alpha = 2/(period+1))
        out['ATR_EMA'] = tr.ewm(span=period, adjust=False).mean()

        # Wilder ATR (alpha = 1/period)
        out['ATR_Wilder'] = tr.ewm(alpha=1 / period, adjust=False).mean()

        # Choose default ATR alias
        if method == 'wilder':
            out['ATR'] = out['ATR_Wilder']
        else:
            out['ATR'] = out['ATR_EMA']

        return out

    def calculate_chandelier_exit(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Chandelier Exit levels for long and short positions.
        
        Args:
            df: DataFrame with 'high', 'low', 'close' columns
            
        Returns:
            DataFrame with Chandelier_Long and Chandelier_Short columns added
        """
        self.validate_data(df, required_columns=['high', 'low', 'close'])
        df = df.copy()
        
        period = self.params['period']
        atr_multiplier = self.params['atr_multiplier']
        
        # Calculate ATR if not already present
        if 'ATR' not in df.columns:
            df = self.calculate_atr(df)
        
        # Calculate highest high and lowest low over the period
        highest_high = df['high'].rolling(window=period).max()
        lowest_low = df['low'].rolling(window=period).min()
        
        # Calculate Chandelier Exit levels
        df['Chandelier_Long'] = highest_high - atr_multiplier * df['ATR']
        df['Chandelier_Short'] = lowest_low + atr_multiplier * df['ATR']
        
        return df
    
    def get_atr_series(self, df: pd.DataFrame) -> pd.Series:
        """
        Get ATR as a pandas Series (for backward compatibility).
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            Series with ATR values
        """
        period = self.params['period']
        
        # Calculate True Range components
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        
        # True Range is the maximum of the three components
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        
        # ATR is EMA of True Range
        atr = true_range.ewm(span=period, adjust=False).mean()
        
        return atr 