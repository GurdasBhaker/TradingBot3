"""
Base class for all technical analysis signals.
Provides standard interface for signal calculation and action generation.
"""

from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, Any, Union, Generator, Tuple
from enum import Enum


class ActionType(Enum):
    """Enumeration for trading actions"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    NULL = None


class SignalBase(ABC):
    """
    Base class for all technical signals.
    Provides common interface for signal calculation and action generation.
    """
    
    def __init__(self, **kwargs):
        """
        Initialize signal with parameters.
        
        Args:
            **kwargs: Signal-specific parameters
        """
        self.params = kwargs
    
    @abstractmethod
    def calculate_signal(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate the signal values and add columns to dataframe.
        
        Args:
            df: DataFrame with OHLC data (columns: open, high, low, close)
            
        Returns:
            DataFrame with signal columns added
            
        Raises:
            ValueError: If required data columns are missing
        """
        pass
    
    @abstractmethod
    def generate_actions(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate buy/sell/hold actions based on signal values.
        
        Args:
            df: DataFrame with signal data (output from calculate_signal)
            
        Returns:
            DataFrame with action column added
            
        Raises:
            ValueError: If required signal columns are missing
        """
        pass
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Legacy method for backward compatibility.
        Calls calculate_signal.
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            DataFrame with signal columns added
        """
        return self.calculate_signal(df)
    
    def validate_data(self, df: pd.DataFrame, required_columns = ['Date_Time', 'close']) -> bool:
        """
        Basic data validation. Override if needed.
        
        Args:
            df: Input dataframe
            
        Returns:
            True if data is valid
            
        Raises:
            ValueError: If required columns are missing
        """
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        if len(df) == 0:
            raise ValueError("DataFrame is empty")
            
        return True
    
    def get_params(self) -> Dict[str, Any]:
        """
        Get signal parameters.
        
        Returns:
            Dictionary of signal parameters
        """
        return self.params.copy()
    
    def __repr__(self) -> str:
        """String representation of the signal"""
        class_name = self.__class__.__name__
        params_str = ", ".join([f"{k}={v}" for k, v in self.params.items()])
        return f"{class_name}({params_str})" 