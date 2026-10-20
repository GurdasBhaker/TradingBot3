"""
Stochastic Oscillator signal with calculation and action generation.
"""

import pandas as pd
from ..base.signal_base import SignalBase, ActionType


class StochasticSignal(SignalBase):
    """
    Stochastic Oscillator signal implementation.
    
    Provides:
    - Stochastic %K and %D calculation
    - Buy/sell action generation based on crossovers and levels
    """
    
    def __init__(self, k=14, smooth=3, d=3, upper_bound=80, lower_bound=20):
        """
        Initialize stochastic signal.
        
        Args:
            k: Period for %K calculation
            smooth: Smoothing period for %K
            d: Period for %D calculation
            upper_bound: Overbought threshold
            lower_bound: Oversold threshold
        """
        super().__init__(
            k=k, 
            smooth=smooth, 
            d=d, 
            upper_bound=upper_bound, 
            lower_bound=lower_bound
        )
    
    def calculate_signal(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate stochastic oscillator (%K, %D).
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            DataFrame with K%, D%, and helper columns added
        """
        self.validate_data(df, required_columns=['high', 'low', 'close'])
        df = df.copy()
        
        k = self.params['k']
        smooth = self.params['smooth']
        d = self.params['d']
        
        # Calculate highest high and lowest low over k periods
        df['HVAL'] = df['high'].rolling(window=k).max()
        df['LVAL'] = df['low'].rolling(window=k).min()
        
        # Calculate raw %K
        df['K'] = ((df['close'] - df['LVAL']) / (df['HVAL'] - df['LVAL'])) * 100
        
        # Smooth %K to get %K
        df['K%'] = df['K'].rolling(window=smooth).mean()
        
        # Calculate %D as moving average of %K
        df['D%'] = df['K%'].rolling(window=d).mean()
        
        # Calculate previous values for crossover detection
        df['K%_prev'] = df['K%'].shift(1)
        df['D%_prev'] = df['D%'].shift(1)
        
        return df
    
    def generate_actions(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate buy/sell actions based on stochastic crossovers and levels.
        
        Args:
            df: DataFrame with stochastic data
            
        Returns:
            DataFrame with action column added
        """
        df = df.copy()
        
        # Ensure stochastic data exists
        if 'K%' not in df.columns:
            df = self.calculate_signal(df)
        
        upper_bound = self.params['upper_bound']
        lower_bound = self.params['lower_bound']
        
        # Initialize action column
        df['action'] = ActionType.NULL.value
        
        # Buy signal: K% crosses above D% in oversold region
        buy_condition = (
            (df['K%_prev'] <= lower_bound) &  # Was in oversold
            (df['K%_prev'] <= df['D%_prev']) &  # K% was below D%
            (df['K%'] > df['D%'])  # K% crosses above D%
        )
        df.loc[buy_condition, 'action'] = ActionType.BUY.value
        
        # Sell signal: K% crosses below D% in overbought region
        sell_condition = (
            (df['K%_prev'] >= upper_bound) &  # Was in overbought
            (df['K%_prev'] >= df['D%_prev']) &  # K% was above D%
            (df['K%'] < df['D%'])  # K% crosses below D%
        )
        df.loc[sell_condition, 'action'] = ActionType.SELL.value
        
        # Alternative: Exit signals at extreme levels
        # Exit long when reaching overbought
        exit_long_condition = (
            (df['K%'] >= upper_bound) |
            (df['D%'] >= upper_bound)
        )
        
        # Exit short when reaching oversold
        exit_short_condition = (
            (df['K%'] <= lower_bound) |
            (df['D%'] <= lower_bound)
        )
        
        # Hold signal: In neutral zone with favorable momentum
        hold_condition = (
            (df['K%'] > lower_bound) &
            (df['K%'] < upper_bound) &
            (df['D%'] > lower_bound) &
            (df['D%'] < upper_bound) &
            ~buy_condition &
            ~sell_condition
        )
        df.loc[hold_condition, 'action'] = ActionType.HOLD.value
        
        return df
    
