"""
Signal factory for creating and managing individual signal instances.
"""

from typing import Dict, Type, Any, List 
from Utilz.signals.base.signal_base import SignalBase
from Utilz.signals.mean_reversion.rsi_signal import RSISignal
from Utilz.signals.mean_reversion.stochastic_signal import StochasticSignal
from Utilz.signals.mean_reversion.cci_signal import CCISignal
from Utilz.signals.trend_following.macd_signal import MACDSignal
from Utilz.signals.trend_following.moving_average_signal import MovingAverageSignal
from Utilz.signals.trend_following.moving_averages import MovingAverageSignals
from Utilz.signals.trend_following.atr_signal import ATRSignal
from Utilz.signals.trend_following.bollinger_bands_signal import BollingerBandsSignal
from Utilz.signals.trend_following.adx_signal import ADXSignal
from Utilz.signals.trend_following.parabolic_sar_signal import ParabolicSARSignal
from Utilz.signals.chart_pattern.engulfing_signal import EngulfingSignal
from Utilz.signals.chart_pattern.doji_signal import DojiSignal
from Utilz.signals.volume_adjusted.obv_signal import OBVSignal


class SignalFactory:
    """
    Factory class for creating and managing signal instances.
    
    Provides easy access to all available signals with consistent interface.
    """
    
    # Registry of available signals
    SIGNAL_REGISTRY: Dict[str, Type[SignalBase]] = {
        # Mean reversion signals
        'rsi': RSISignal,
        'stochastic': StochasticSignal,
        'cci': CCISignal,
        
        # Trend following signals
        'macd': MACDSignal,
        'moving_average': MovingAverageSignal,
        'ma': MovingAverageSignals,  # Alias adding in need proper fix
        'atr': ATRSignal,
        'bollinger_bands': BollingerBandsSignal,
        'bb': BollingerBandsSignal,  # Alias
        'adx': ADXSignal,
        'parabolic_sar': ParabolicSARSignal,
        'sar': ParabolicSARSignal,  # Alias
        
        # Chart pattern signals
        'engulfing': EngulfingSignal,
        'doji': DojiSignal,
        
        # Volume adjusted signals
        'obv': OBVSignal,
    }
    
    @classmethod
    def create_signal(cls, signal_type: str, **kwargs) -> SignalBase:
        """
        Create a signal instance.
        
        Args:
            signal_type: Type of signal to create
            **kwargs: Signal-specific parameters
            
        Returns:
            Signal instance
            
        Raises:
            ValueError: If signal type is not recognized
        """
        signal_type = signal_type.lower()
        
        if signal_type not in cls.SIGNAL_REGISTRY:
            available_signals = ', '.join(cls.SIGNAL_REGISTRY.keys())
            raise ValueError(f"Unknown signal type: {signal_type}. Available signals: {available_signals}")
        
        signal_class = cls.SIGNAL_REGISTRY[signal_type]
        return signal_class(**kwargs)
    
    @classmethod
    def get_available_signals(cls) -> List[str]:
        """
        Get list of available signal types.
        
        Returns:
            List of signal type names
        """
        return list(cls.SIGNAL_REGISTRY.keys())
    
    @classmethod
    def create_signal_bundle(cls, signal_configs: Dict[str, Dict[str, Any]]) -> Dict[str, SignalBase]:
        """
        Create multiple signals from configuration.
        
        Args:
            signal_configs: Dictionary of signal_name -> signal_config
                           Example: {
                               'rsi_14': {'signal_type': 'rsi', 'period': 14},
                               'macd_default': {'signal_type': 'macd'},
                               'ma_20': {'signal_type': 'ma', 'window': 20}
                           }
        
        Returns:
            Dictionary of signal_name -> signal_instance
        """
        signals = {}
        
        for signal_name, config in signal_configs.items():
            if 'signal_type' not in config:
                raise ValueError(f"Signal config for '{signal_name}' must include 'signal_type'")
            
            signal_type = config.pop('signal_type')
            signals[signal_name] = cls.create_signal(signal_type, **config)
        
        return signals
    
    @classmethod
    def register_signal(cls, signal_type: str, signal_class: Type[SignalBase]) -> None:
        """
        Register a new signal type.
        
        Args:
            signal_type: Name for the signal type
            signal_class: Signal class that inherits from SignalBase
        """
        if not issubclass(signal_class, SignalBase):
            raise ValueError(f"Signal class must inherit from SignalBase")
        
        cls.SIGNAL_REGISTRY[signal_type.lower()] = signal_class


