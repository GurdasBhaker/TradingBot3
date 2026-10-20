"""
Fibonacci retracement and extension signals for trend following.
"""

import pandas as pd
from ..base.signal_base import SignalBase


class FibonacciSignals(SignalBase):
    """
    Fibonacci retracement and extension calculations.
    
    Provides:
    - Fibonacci retracement levels
    - Support/resistance based on Fibonacci levels
    """
    
    def __init__(self, levels=None):
        """
        Initialize Fibonacci signals.
        
        Args:
            levels: List of Fibonacci levels (default: common retracement levels)
        """
        if levels is None:
            levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
        
        super().__init__(levels=levels)
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Main calculate method for base class compliance.
        Calculates Fibonacci retracement levels.
        
        Args:
            df: DataFrame with high and low data
            
        Returns:
            DataFrame with Fibonacci level columns added
        """
        return self.calculate_retracements(df)
    
    def calculate_retracements(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Fibonacci retracement levels based on high and low.
        
        Args:
            df: DataFrame with 'high' and 'low' columns
            
        Returns:
            DataFrame with Fibonacci level columns added
        """
        # Validate that we have high and low columns
        required_columns = ['high', 'low']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            raise ValueError(f"Missing required columns for Fibonacci calculation: {missing_columns}")
        
        df = df.copy()
        levels = self.params['levels']
        
        # Calculate Fibonacci levels
        for level in levels:
            column_name = str(level)
            df[column_name] = df['low'] + ((df['high'] - df['low']) * level)
        
        return df
    
    def calculate_extensions(self, df: pd.DataFrame, extension_levels=None) -> pd.DataFrame:
        """
        Calculate Fibonacci extension levels.
        
        Args:
            df: DataFrame with 'high' and 'low' columns
            extension_levels: List of extension levels (default: common extensions)
            
        Returns:
            DataFrame with Fibonacci extension columns added
        """
        if extension_levels is None:
            extension_levels = [1.272, 1.414, 1.618, 2.0, 2.618]
        
        # Validate that we have high and low columns
        required_columns = ['high', 'low']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            raise ValueError(f"Missing required columns for Fibonacci calculation: {missing_columns}")
        
        df = df.copy()
        
        # Calculate Fibonacci extension levels
        for level in extension_levels:
            column_name = f"ext_{level}"
            df[column_name] = df['low'] + ((df['high'] - df['low']) * level)
        
        return df
    
    def calculate_dynamic_levels(self, df: pd.DataFrame, lookback_period: int = 20) -> pd.DataFrame:
        """
        Calculate dynamic Fibonacci levels based on rolling high/low.
        
        Args:
            df: DataFrame with OHLC data
            lookback_period: Period for rolling high/low calculation
            
        Returns:
            DataFrame with dynamic Fibonacci level columns added
        """
        self.validate_data(df, required_columns=['high', 'low'])
        df = df.copy()
        levels = self.params['levels']
        
        # Calculate rolling high and low
        rolling_high = df['high'].rolling(window=lookback_period).max()
        rolling_low = df['low'].rolling(window=lookback_period).min()
        
        # Calculate dynamic Fibonacci levels
        for level in levels:
            column_name = f"dyn_{level}"
            df[column_name] = rolling_low + ((rolling_high - rolling_low) * level)
        
        return df
    
    def identify_support_resistance(self, df: pd.DataFrame, tolerance: float = 0.001) -> pd.DataFrame:
        """
        Identify when price is near Fibonacci levels (support/resistance).
        
        Args:
            df: DataFrame with Fibonacci levels and close price
            tolerance: Tolerance for level proximity (as percentage)
            
        Returns:
            DataFrame with support/resistance signals added
        """
        self.validate_data(df, required_columns=['close'])
        df = df.copy()
        levels = self.params['levels']
        
        # Initialize support/resistance columns
        df['fib_support'] = 0
        df['fib_resistance'] = 0
        df['fib_level_hit'] = 0
        
        # Check proximity to each Fibonacci level
        for level in levels:
            level_col = str(level)
            if level_col in df.columns:
                # Calculate percentage difference from Fibonacci level
                price_diff = abs(df['close'] - df[level_col]) / df[level_col]
                
                # Mark when price is near the level
                near_level = price_diff <= tolerance
                
                # Determine if it's acting as support or resistance
                df.loc[near_level & (df['close'] >= df[level_col]), 'fib_support'] = level
                df.loc[near_level & (df['close'] < df[level_col]), 'fib_resistance'] = level
                df.loc[near_level, 'fib_level_hit'] = level
        
        return df 