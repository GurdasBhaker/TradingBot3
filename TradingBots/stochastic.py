from datetime import datetime

from TB2.Utilz.MT5_handler import MetaTrader5_handler as mt5_handler
from TB2.Utilz.MT5_data_class import MT5ConfigData as mt5_config
from TB2.Utilz.Telegram_handler import Message, TelegramConfig as tc
from TB2.Utilz.calc_lib import Calculators as calc
import MetaTrader5 as mt


class StochasticOscilator:

    @classmethod
    def calculator(cls, account, symbols, time_frame, settings, chat_id=None, date_time=None):

        mt5_handler.start_mt5(account)

        analytic_timeframe = time_frame[0]
        trading_timeframe = time_frame[1]

        signal_str = {1: 'Long', -1: 'Short'}
        direction = {1: 'Oversold', -1: 'Overbought'}
        strategies = [1, -1]

        for symbol in symbols:
            is_market_closed = mt5_handler.is_market_closed(symbol)

            if is_market_closed:
                continue

            magic = mt5_handler.create_magic(settings, time_frame, symbol)
            # get bars starting from now in UTC time zone, create DataFrame out of the obtained data
            prices = mt5_handler.get_prices(symbol, analytic_timeframe, 1, 100, date_time)
            trading_price = mt5_handler.get_prices(symbol, analytic_timeframe, 0, 1, date_time)

            # Run for all strategy types set above 1 (Long) and -1 (Short)
            for strategy in strategies:
                # Run Oscilator Stoch
                stoch_df = calc.stochastic_oscilator(prices, settings.k, settings.smooth, settings.d)

                # Create trading dataframe
                stochastic_signals = calc.stochastic_signals(
                    stoch_df, strategy, settings.upper_bound, settings.lower_bound
                )

                # Getting latest trade indicator of stoch by symbol with the data the determines the trade
                stochastic_signals.sort_values(by="Date_Time", inplace=True)
                latest_position = stochastic_signals["Position"].iloc[-1]

                if latest_position != 0:
                    print(f"Latest Position: {latest_position}, Strategy: {strategy}, symbol: {symbol}")

                active_positions = mt5_handler.active_positions(symbol, magic)

                trading_result = []
                if strategy == latest_position:
                    open_price = mt.symbol_info_tick(symbol).bid
                    sl_pips = mt5_handler.get_sl(settings, time_frame, symbol)
                    sl = round(
                        open_price - (sl_pips * mt5_config.point[symbol] * strategy),5
                    )
                    lot = mt5_handler.generate_lot(settings, time_frame, symbol)
                    trading_result = mt5_handler.trade(
                        symbol,
                        settings,
                        strategy,
                        'Open',
                        sl=sl,
                        magic=magic,
                        lot=lot
                    )

                    # Send Notification
                    time_hit = trading_price['Date_Time'].values[0]
                    stoch_hit = (f'{mt5_config.time_ref[analytic_timeframe]} {symbol} {direction[strategy]} '
                                         f'{signal_str[strategy]} Stochastic trade at {time_hit}, Open Trade Requested')
                    print(stoch_hit)
                    Message.send_message(stoch_hit, tc.token, chat_id)

                elif strategy * -1 == latest_position and len(active_positions) > 0:
                    lot = mt5_handler.generate_lot(settings, time_frame, symbol)
                    trading_result = mt5_handler.trade(
                        symbol,
                        settings,
                        strategy,
                        'Close',
                        magic=magic,
                        lot=lot
                    )

                    # need to fix
                    time_hit = trading_price['Date_Time'].values[0]
                    stoch_hit = (f'{mt5_config.time_ref[analytic_timeframe]} {symbol} {direction[strategy]} '
                                 f'{signal_str[strategy]} Stochastic trade at {time_hit}, Close Trade Requested')
                    print(stoch_hit)

                    # Message.send_message(stoch_hit, tc.token, chat_id)

                mt5_handler.trade_commentry(trading_result, symbol, strategy)

        # if date_time is None:
        #     print(f'It ran Stochastic Oscilator {str(datetime.now())} for {mt5_config.time_ref[analytic_timeframe]}')
        # else:
        #     print(f'It ran Stochastic Oscilator {str(date_time)} for {mt5_config.time_ref[analytic_timeframe]}')


