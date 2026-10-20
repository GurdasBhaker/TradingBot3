"""
Ichimoku Cloud signals for trend following analysis.
"""

import pandas as pd
import numpy as np
from ..base.signal_base import SignalBase


class IchimokuSignals(SignalBase):
    """
    Ichimoku Cloud signal calculations.
    
    Provides:
    - Tenkan-sen (Conversion Line)
    - Kijun-sen (Base Line)
    - Senkou Span A (Leading Span A)
    - Senkou Span B (Leading Span B)
    - Chikou Span (Lagging Span)
    - Cloud analysis
    - Trend signals
    """
    
    def __init__(self, tenkan_period=9, kijun_period=26, senkou_b_period=52, displacement=26):
        """
        Initialize Ichimoku signals.
        
        Args:
            tenkan_period: Period for Tenkan-sen (default 9)
            kijun_period: Period for Kijun-sen (default 26)
            senkou_b_period: Period for Senkou Span B (default 52)
            displacement: Displacement for future spans (default 26)
        """
        super().__init__(
            tenkan_period=tenkan_period,
            kijun_period=kijun_period,
            senkou_b_period=senkou_b_period,
            displacement=displacement
        )
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Main calculate method for base class compliance.
        Calculates all Ichimoku components.
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            DataFrame with Ichimoku columns added
        """
        self.validate_data(df, required_columns=['high', 'low', 'close'])
        return self.calculate_ichimoku(df)
    
    def calculate_ichimoku(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all Ichimoku Cloud components.
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            DataFrame with all Ichimoku columns added
        """
        self.validate_data(df, required_columns=['high', 'low', 'close'])
        df = df.copy()
        
        tenkan_period = self.params['tenkan_period']
        kijun_period = self.params['kijun_period']
        senkou_b_period = self.params['senkou_b_period']
        displacement = self.params['displacement']
        
        # Calculate Tenkan-sen (Conversion Line)
        tenkan_high = df['high'].rolling(window=tenkan_period).max()
        tenkan_low = df['low'].rolling(window=tenkan_period).min()
        df['Tenkan_sen'] = (tenkan_high + tenkan_low) / 2
        
        # Calculate Kijun-sen (Base Line)
        kijun_high = df['high'].rolling(window=kijun_period).max()
        kijun_low = df['low'].rolling(window=kijun_period).min()
        df['Kijun_sen'] = (kijun_high + kijun_low) / 2
        
        # Calculate Senkou Span A (Leading Span A)
        df['Senkou_span_A'] = ((df['Tenkan_sen'] + df['Kijun_sen']) / 2).shift(displacement)
        
        # Calculate Senkou Span B (Leading Span B)
        senkou_b_high = df['high'].rolling(window=senkou_b_period).max()
        senkou_b_low = df['low'].rolling(window=senkou_b_period).min()
        df['Senkou_span_B'] = ((senkou_b_high + senkou_b_low) / 2).shift(displacement)
        
        # Calculate Chikou Span (Lagging Span)
        df['Chikou_span'] = df['close'].shift(-displacement)
        
        return df
    
    def calculate_cloud_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate cloud-based signals.
        
        Args:
            df: DataFrame with Ichimoku data
            
        Returns:
            DataFrame with cloud signals added
        """
        df = df.copy()
        
        # Ensure Ichimoku data exists
        if 'Senkou_span_A' not in df.columns:
            df = self.calculate_ichimoku(df)
        
        # Determine cloud color
        df['Cloud_color'] = 0  # 0 = neutral, 1 = bullish (green), -1 = bearish (red)
        df.loc[df['Senkou_span_A'] > df['Senkou_span_B'], 'Cloud_color'] = 1
        df.loc[df['Senkou_span_A'] < df['Senkou_span_B'], 'Cloud_color'] = -1
        
        # Price position relative to cloud
        df['Price_vs_cloud'] = 0  # 0 = in cloud, 1 = above cloud, -1 = below cloud
        
        cloud_top = df[['Senkou_span_A', 'Senkou_span_B']].max(axis=1)
        cloud_bottom = df[['Senkou_span_A', 'Senkou_span_B']].min(axis=1)
        
        df.loc[df['close'] > cloud_top, 'Price_vs_cloud'] = 1
        df.loc[df['close'] < cloud_bottom, 'Price_vs_cloud'] = -1
        
        return df
    
    def calculate_tenkan_kijun_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Tenkan-sen and Kijun-sen crossover signals.
        
        Args:
            df: DataFrame with Ichimoku data
            
        Returns:
            DataFrame with TK crossover signals added
        """
        df = df.copy()
        
        # Ensure Ichimoku data exists
        if 'Tenkan_sen' not in df.columns:
            df = self.calculate_ichimoku(df)
        
        # Calculate previous values for crossover detection
        df['Tenkan_prev'] = df['Tenkan_sen'].shift(1)
        df['Kijun_prev'] = df['Kijun_sen'].shift(1)
        
        # Initialize signal column
        df['TK_Cross'] = 0
        
        # Bullish crossover: Tenkan crosses above Kijun (Golden Cross)
        df.loc[
            (df['Tenkan_prev'] <= df['Kijun_prev']) &
            (df['Tenkan_sen'] > df['Kijun_sen']), 'TK_Cross'
        ] = 1
        
        # Bearish crossover: Tenkan crosses below Kijun (Death Cross)
        df.loc[
            (df['Tenkan_prev'] >= df['Kijun_prev']) &
            (df['Tenkan_sen'] < df['Kijun_sen']), 'TK_Cross'
        ] = -1
        
        return df
    
    def calculate_price_vs_lines(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate price position relative to Tenkan and Kijun lines.
        
        Args:
            df: DataFrame with Ichimoku data
            
        Returns:
            DataFrame with price vs lines signals added
        """
        df = df.copy()
        
        # Ensure Ichimoku data exists
        if 'Tenkan_sen' not in df.columns:
            df = self.calculate_ichimoku(df)
        
        # Price vs Tenkan-sen
        df['Price_vs_Tenkan'] = 0
        df.loc[df['close'] > df['Tenkan_sen'], 'Price_vs_Tenkan'] = 1
        df.loc[df['close'] < df['Tenkan_sen'], 'Price_vs_Tenkan'] = -1
        
        # Price vs Kijun-sen
        df['Price_vs_Kijun'] = 0
        df.loc[df['close'] > df['Kijun_sen'], 'Price_vs_Kijun'] = 1
        df.loc[df['close'] < df['Kijun_sen'], 'Price_vs_Kijun'] = -1
        
        return df
    
    def calculate_chikou_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Chikou Span signals.
        
        Args:
            df: DataFrame with Ichimoku data
            
        Returns:
            DataFrame with Chikou signals added
        """
        df = df.copy()
        
        # Ensure Ichimoku data exists
        if 'Chikou_span' not in df.columns:
            df = self.calculate_ichimoku(df)
        
        displacement = self.params['displacement']
        
        # Compare Chikou span with price from displacement periods ago
        df['Price_displaced'] = df['close'].shift(displacement)
        
        # Initialize signal column
        df['Chikou_signal'] = 0
        
        # Bullish: Chikou span above price
        df.loc[df['Chikou_span'] > df['Price_displaced'], 'Chikou_signal'] = 1
        
        # Bearish: Chikou span below price
        df.loc[df['Chikou_span'] < df['Price_displaced'], 'Chikou_signal'] = -1
        
        return df
    
    def calculate_trend_strength(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate overall trend strength based on Ichimoku components.
        
        Args:
            df: DataFrame with Ichimoku data
            
        Returns:
            DataFrame with trend strength signals added
        """
        df = df.copy()
        
        # Ensure all signals exist
        if 'TK_Cross' not in df.columns:
            df = self.calculate_tenkan_kijun_signals(df)
        if 'Price_vs_cloud' not in df.columns:
            df = self.calculate_cloud_signals(df)
        if 'Price_vs_Tenkan' not in df.columns:
            df = self.calculate_price_vs_lines(df)
        if 'Chikou_signal' not in df.columns:
            df = self.calculate_chikou_signals(df)
        
        # Calculate trend strength by summing individual signals
        df['Ichimoku_strength'] = (
            df['Price_vs_cloud'] +
            df['Price_vs_Tenkan'] +
            df['Price_vs_Kijun'] +
            df['Chikou_signal'] +
            df['Cloud_color']
        )
        
        # Generate overall trend signal
        df['Ichimoku_trend'] = 0
        df.loc[df['Ichimoku_strength'] >= 3, 'Ichimoku_trend'] = 1  # Strong bullish
        df.loc[df['Ichimoku_strength'] <= -3, 'Ichimoku_trend'] = -1  # Strong bearish
        
        return df
    
    def calculate_cloud_breakouts(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate cloud breakout signals.
        
        Args:
            df: DataFrame with Ichimoku data
            
        Returns:
            DataFrame with cloud breakout signals added
        """
        df = df.copy()
        
        # Ensure cloud signals exist
        if 'Price_vs_cloud' not in df.columns:
            df = self.calculate_cloud_signals(df)
        
        # Calculate previous cloud position
        df['Price_vs_cloud_prev'] = df['Price_vs_cloud'].shift(1)
        
        # Initialize breakout signal
        df['Cloud_breakout'] = 0
        
        # Bullish breakout: Price breaks above cloud
        df.loc[
            (df['Price_vs_cloud_prev'] <= 0) &
            (df['Price_vs_cloud'] == 1), 'Cloud_breakout'
        ] = 1
        
        # Bearish breakout: Price breaks below cloud
        df.loc[
            (df['Price_vs_cloud_prev'] >= 0) &
            (df['Price_vs_cloud'] == -1), 'Cloud_breakout'
        ] = -1
        
        return df
    
    def calculate_all_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all Ichimoku-related signals.
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            DataFrame with all Ichimoku signals added
        """
        df = self.calculate_ichimoku(df)
        df = self.calculate_cloud_signals(df)
        df = self.calculate_tenkan_kijun_signals(df)
        df = self.calculate_price_vs_lines(df)
        df = self.calculate_chikou_signals(df)
        df = self.calculate_trend_strength(df)
        df = self.calculate_cloud_breakouts(df)
        
        return df 