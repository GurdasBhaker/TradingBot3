"""
ADX (Average Directional Index) signal with calculation and action generation.
"""

import pandas as pd
from ..base.signal_base import SignalBase, ActionType


class ADXSignal(SignalBase):
    """
    ADX (Average Directional Index) signal implementation.
    
    Provides:
    - ADX calculation for trend strength
    - Buy/sell action generation based on directional indicators
    """
    
    def __init__(self, period=14, trend_threshold=25):
        """
        Initialize ADX signal.
        
        Args:
            period: Period for ADX calculation (default 14)
            trend_threshold: Threshold for strong trend identification (default 25)
        """
        super().__init__(
            period=period,
            trend_threshold=trend_threshold
        )
    
    def calculate_signal(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate ADX, +DI, and -DI.
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            DataFrame with ADX, Plus_DI, Minus_DI columns added
        """
        self.validate_data(df, required_columns=['high', 'low', 'close'])
        df = df.copy()
        
        period = self.params['period']
        
        # Calculate directional movements
        df['high_diff'] = df['high'].diff()
        df['low_diff'] = df['low'].diff()
        
        # Calculate Plus DM and Minus DM
        df['plus_dm'] = (df['high_diff'].where((df['high_diff'] > df['low_diff']) & (df['high_diff'] > 0), 0))
        df['minus_dm'] = ((-df['low_diff']).where((df['low_diff'] > df['high_diff']) & (df['low_diff'] > 0), 0))
        
        # Calculate True Range
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = (df['high'] - df['close'].shift()).abs()
        df['tr3'] = (df['low'] - df['close'].shift()).abs()
        df['true_range'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        
        # Calculate smoothed values using EMA
        df['plus_dm_smooth'] = df['plus_dm'].ewm(span=period, adjust=False).mean()
        df['minus_dm_smooth'] = df['minus_dm'].ewm(span=period, adjust=False).mean()
        df['true_range_smooth'] = df['true_range'].ewm(span=period, adjust=False).mean()
        
        # Calculate +DI and -DI
        df['Plus_DI'] = 100 * (df['plus_dm_smooth'] / df['true_range_smooth'])
        df['Minus_DI'] = 100 * (df['minus_dm_smooth'] / df['true_range_smooth'])
        
        # Calculate DX
        df['dx'] = 100 * (abs(df['Plus_DI'] - df['Minus_DI']) / (df['Plus_DI'] + df['Minus_DI']))
        df['dx'] = df['dx'].fillna(0)
        
        # Calculate ADX
        df['ADX'] = df['dx'].ewm(span=period, adjust=False).mean()
        
        return df
    
    def generate_actions(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate buy/sell actions based on ADX and directional indicators.
        
        Args:
            df: DataFrame with ADX data
            
        Returns:
            DataFrame with action column added
        """
        df = df.copy()
        
        # Ensure ADX data exists
        if 'ADX' not in df.columns:
            df = self.calculate_signal(df)
        
        trend_threshold = self.params['trend_threshold']
        
        # Initialize action column
        df['action'] = ActionType.NULL.value
        
        # Calculate previous values for crossover detection
        df['Plus_DI_prev'] = df['Plus_DI'].shift(1)
        df['Minus_DI_prev'] = df['Minus_DI'].shift(1)
        
        # Buy signal: +DI crosses above -DI with strong trend (ADX > threshold)
        buy_condition = (
            (df['Plus_DI_prev'] <= df['Minus_DI_prev']) &
            (df['Plus_DI'] > df['Minus_DI']) &
            (df['ADX'] > trend_threshold)
        )
        df.loc[buy_condition, 'action'] = ActionType.BUY.value
        
        # Sell signal: -DI crosses above +DI with strong trend (ADX > threshold)
        sell_condition = (
            (df['Minus_DI_prev'] <= df['Plus_DI_prev']) &
            (df['Minus_DI'] > df['Plus_DI']) &
            (df['ADX'] > trend_threshold)
        )
        df.loc[sell_condition, 'action'] = ActionType.SELL.value
        
        # Hold signal: +DI above -DI with strong trend
        hold_condition = (
            (df['Plus_DI'] > df['Minus_DI']) &
            (df['ADX'] > trend_threshold) &
            ~buy_condition &
            ~sell_condition
        )
        df.loc[hold_condition, 'action'] = ActionType.HOLD.value
        
        return df
