"""
Parabolic SAR signal with calculation and action generation.
"""

import pandas as pd
import numpy as np
from ..base.signal_base import SignalBase, ActionType


class ParabolicSARSignal(SignalBase):
    """
    Parabolic SAR signal implementation.
    
    Provides:
    - Parabolic SAR calculation
    - Buy/sell action generation based on SAR crossovers
    """
    
    def __init__(self, initial_af=0.02, max_af=0.20, af_step=0.02):
        """
        Initialize Parabolic SAR signal.
        
        Args:
            initial_af: Initial acceleration factor (default 0.02)
            max_af: Maximum acceleration factor (default 0.20)
            af_step: Acceleration factor step (default 0.02)
        """
        super().__init__(
            initial_af=initial_af,
            max_af=max_af,
            af_step=af_step
        )
    
    def calculate_signal(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Parabolic SAR.
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            DataFrame with SAR column added
        """
        self.validate_data(df, required_columns=['high', 'low', 'close'])
        df = df.copy()
        
        initial_af = self.params['initial_af']
        max_af = self.params['max_af']
        af_step = self.params['af_step']
        
        # Initialize arrays
        n = len(df)
        sar = np.zeros(n)
        trend = np.zeros(n)  # 1 for uptrend, -1 for downtrend
        af = np.zeros(n)
        ep = np.zeros(n)  # extreme point
        
        # Initialize first values
        sar[0] = df['low'].iloc[0]
        trend[0] = 1
        af[0] = initial_af
        ep[0] = df['high'].iloc[0]
        
        for i in range(1, n):
            # Previous values
            prev_sar = sar[i-1]
            prev_trend = trend[i-1]
            prev_af = af[i-1]
            prev_ep = ep[i-1]
            
            high = df['high'].iloc[i]
            low = df['low'].iloc[i]
            
            if prev_trend == 1:  # Uptrend
                # Calculate SAR
                sar[i] = prev_sar + prev_af * (prev_ep - prev_sar)
                
                # Check for trend reversal
                if low <= sar[i]:
                    # Switch to downtrend
                    trend[i] = -1
                    sar[i] = prev_ep
                    af[i] = initial_af
                    ep[i] = low
                else:
                    # Continue uptrend
                    trend[i] = 1
                    
                    # Update extreme point and acceleration factor
                    if high > prev_ep:
                        ep[i] = high
                        af[i] = min(prev_af + af_step, max_af)
                    else:
                        ep[i] = prev_ep
                        af[i] = prev_af
                    
                    # Ensure SAR doesn't exceed previous low
                    if i >= 2:
                        sar[i] = min(sar[i], df['low'].iloc[i-1], df['low'].iloc[i-2])
            
            else:  # Downtrend
                # Calculate SAR
                sar[i] = prev_sar + prev_af * (prev_ep - prev_sar)
                
                # Check for trend reversal
                if high >= sar[i]:
                    # Switch to uptrend
                    trend[i] = 1
                    sar[i] = prev_ep
                    af[i] = initial_af
                    ep[i] = high
                else:
                    # Continue downtrend
                    trend[i] = -1
                    
                    # Update extreme point and acceleration factor
                    if low < prev_ep:
                        ep[i] = low
                        af[i] = min(prev_af + af_step, max_af)
                    else:
                        ep[i] = prev_ep
                        af[i] = prev_af
                    
                    # Ensure SAR doesn't fall below previous high
                    if i >= 2:
                        sar[i] = max(sar[i], df['high'].iloc[i-1], df['high'].iloc[i-2])
        
        df['SAR'] = sar
        df['SAR_Trend'] = trend
        
        return df
    
    def generate_actions(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate buy/sell actions based on Parabolic SAR crossovers.
        
        Args:
            df: DataFrame with SAR data
            
        Returns:
            DataFrame with action column added
        """
        df = df.copy()
        
        # Ensure SAR data exists
        if 'SAR' not in df.columns:
            df = self.calculate_signal(df)
        
        # Initialize action column
        df['action'] = ActionType.NULL.value
        
        # Calculate previous values for crossover detection
        df['close_prev'] = df['close'].shift(1)
        df['SAR_prev'] = df['SAR'].shift(1)
        
        # Buy signal: Price crosses above SAR
        buy_condition = (
            (df['close_prev'] <= df['SAR_prev']) &
            (df['close'] > df['SAR'])
        )
        df.loc[buy_condition, 'action'] = ActionType.BUY.value
        
        # Sell signal: Price crosses below SAR
        sell_condition = (
            (df['close_prev'] >= df['SAR_prev']) &
            (df['close'] < df['SAR'])
        )
        df.loc[sell_condition, 'action'] = ActionType.SELL.value
        
        # Hold signal: Price above SAR (uptrend)
        hold_condition = (
            (df['close'] > df['SAR']) &
            ~buy_condition &
            ~sell_condition
        )
        df.loc[hold_condition, 'action'] = ActionType.HOLD.value
        
        return df
