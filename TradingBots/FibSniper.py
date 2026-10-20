from datetime import datetime
from TB2.Utilz.MT5_handler import MetaTrader5_handler as mt5_handler
from TB2.Utilz.calc_lib import Calculators as calc
from TB2.Utilz.MT5_data_class import MT5ConfigData as mt5_config
import pandas as pd


class FibonacciSniperBot:

    @classmethod
    def calculator(cls, account, symbols, time_frame, settings, chat_id=None, date_time=None):

        mt5_handler.start_mt5(account)

        analytic_timeframe = time_frame[0]
        levels = [1, 0.9, 0.75, 0.5, 0.25, 0.1, 0]
        window = 4

        for symbol in symbols:
            # Generate magic number
            magic = mt5_handler.create_magic(settings, time_frame, symbol)
            # get bars starting from now in UTC time zone, create DataFrame out of the obtained data
            # convert time in seconds into the datetime format
            prices = mt5_handler.get_prices(symbol, analytic_timeframe, 1, 100, date_time)

            # Create trading dataframe
            trade_df = prices[
                ['Date_Time', 'high', 'low', 'close']
            ].copy()

            trade_df = calc.ma_crossover(trade_df, window)

            signal_df = trade_df.copy()

            signal_df = signal_df.loc[signal_df['Cross'] != 0].tail(3)
            min_date_time = signal_df['Date_Time'].min()
            max_date_time = signal_df['Date_Time'].max()

            # Only need the last candle
            last_candle = trade_df.loc[trade_df['Date_Time'].idxmax()].to_frame().T

            if last_candle['Cross'].values[0] == 1:
                trade_df = trade_df.loc[
                    (trade_df['Date_Time'] >= min_date_time) &
                    (trade_df['Date_Time'] <= max_date_time)
                ]

                fib_df = pd.DataFrame()
                fib_df['Date_Time'] = max_date_time
                fib_df['low'] = trade_df['low'].min()
                fib_df['high'] = trade_df['high'].max()
                fib_df['Signal'] = last_candle['Signal'].values[0] * -1

                # Create the Fibonacci levels
                fib_levels = calc.fibonacci_df(fib_df, levels)

                if fib_levels['Signal'].values[0] == 1:
                    # Long position order
                    entry = fib_levels['0.1'].values[0]
                    sl = fib_levels['0'].values[0]
                    tp = fib_levels['1'].values[0]
                else:
                    # Short position order
                    entry = fib_levels['0.9'].values[0]
                    sl = fib_levels['1'].values[0]
                    tp = fib_levels['0'].values[0]

                # Close old orders
                mt5_handler.order(
                    symbol,
                    settings,
                    'Close',
                    action_type='Limit',
                    magic=magic
                )

                # Open new orders
                lot = mt5_handler.generate_lot(settings, time_frame, symbol)
                trading_result = mt5_handler.order(
                    symbol,
                    settings,
                    'Open',
                    position=fib_levels['Signal'].values[0],
                    action_type='Limit',
                    price=entry,
                    sl=sl,
                    tp=tp,
                    lot=lot,
                    magic=magic
                )

                mt5_handler.trade_commentry(trading_result, symbol, fib_levels['Signal'].values[0])

        if date_time is None:
            print(f'It ran Fibonacci Sniper Bot {str(datetime.now())} for {mt5_config.time_ref[analytic_timeframe]}')
        else:
            print(f'It ran Fibonacci Sniper Bot {str(date_time)} for {mt5_config.time_ref[analytic_timeframe]}')








