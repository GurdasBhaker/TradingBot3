"""
Simple signal performance analyzer.
"""

import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from Utilz.signals.signal_factory import SignalFactory
from Utilz.MT5_data_class import mt5_accounts


class SimpleAnalyzer:
    """Simple signal performance analyzer."""
    
    def __init__(self):
        self.data = None
        
    def get_data(self, symbol="EURUSD", bars=500, timeframe=mt5.TIMEFRAME_H1):
        """Get MT5 data."""
        # Connect to MT5
        if not mt5.initialize():
            return None
            
        account = mt5_accounts.kai_96431230
        mt5.login(account['login'], account['password'], account['server'])
        
        # Get data
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
        mt5.shutdown()
        
        if rates is None:
            return None
            
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        self.data = df[['time', 'open', 'high', 'low', 'close']].copy()
        return self.data
    
    def analyze_signal(self, signal_type, **params):
        """Analyze one signal."""
        if self.data is None:
            return None
            
        # Create signal
        signal = SignalFactory.create_signal(signal_type, **params)
        
        # Calculate signal and actions
        df = signal.calculate_signal(self.data.copy())
        df = signal.generate_actions(df)
        
        # Calculate returns
        df['return_1h'] = (df['close'].shift(-1) / df['close'] - 1) * 100
        df['return_10h'] = (df['close'].shift(-10) / df['close'] - 1) * 100
        
        # Signal-to-signal returns
        signals = df[df['action'].isin(['buy', 'sell'])].copy()
        if len(signals) > 1:
            signals['next_return'] = 0.0
            for i in range(len(signals) - 1):
                current_price = signals.iloc[i]['close']
                next_price = signals.iloc[i + 1]['close']
                current_action = signals.iloc[i]['action']
                
                if current_action == 'buy':
                    ret = (next_price / current_price - 1) * 100
                else:  # sell
                    ret = (current_price / next_price - 1) * 100
                    
                signals.iloc[i, signals.columns.get_loc('next_return')] = ret
        
        # Simple stats
        if len(signals) > 0:
            returns = signals['next_return'][:-1]  # exclude last signal
            stats = {
                'total_signals': len(signals),
                'buy_signals': len(signals[signals['action'] == 'buy']),
                'sell_signals': len(signals[signals['action'] == 'sell']),
                'total_return': returns.sum(),
                'win_rate': (returns > 0).mean() * 100,
                'avg_return': returns.mean()
            }
        else:
            stats = {'total_signals': 0}
            
        return {'data': df, 'signals': signals, 'stats': stats}
    
    def compare_signals(self):
        """Compare the three main signals."""
        results = {}
        
        # Moving Average
        results['MA'] = self.analyze_signal('moving_average', window=20)
        
        # Engulfing
        results['Engulfing'] = self.analyze_signal('engulfing')
        
        # Stochastic  
        results['Stochastic'] = self.analyze_signal('stochastic', k=14, d=3)
        
        # Print comparison
        print("Signal Comparison:")
        print("-" * 40)
        for name, result in results.items():
            if result and result['stats']['total_signals'] > 0:
                stats = result['stats']
                print(f"{name}:")
                print(f"  Signals: {stats['total_signals']}")
                print(f"  Total Return: {stats['total_return']:.2f}%")
                print(f"  Win Rate: {stats['win_rate']:.1f}%")
                print(f"  Avg Return: {stats['avg_return']:.2f}%")
            else:
                print(f"{name}: No signals generated")
            print()
        
        return results


# Simple usage
if __name__ == "__main__":
    analyzer = SimpleAnalyzer()
    
    # Get data
    print("Getting MT5 data...")
    data = analyzer.get_data("EURUSD", 500)  # Default H1 timeframe
    # Or specify different timeframe: data = analyzer.get_data("EURUSD", 500, mt5.TIMEFRAME_M15)
    
    if data is not None:
        print(f"Got {len(data)} bars")
        
        # Compare signals
        results = analyzer.compare_signals()
    else:
        print("Failed to get data")
