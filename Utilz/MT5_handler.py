from TB2.Utilz.MT5_data_class import MT5ConfigData as mt5_config
import math
from datetime import timedelta, datetime
import pandas as pd
import MetaTrader5 as mt


class MetaTrader5_handler:

    @classmethod
    def start_mt5(cls, login_acc):
        # login_acc needs to be a dictionary with the following keys
        # login_acc = {login:mt5 login, password:mt5 password, server:mt5 server}

        # Initialize mt
        mt.initialize()

        # establish connection to MetaTrader 5 terminal
        if not mt.initialize():
            print("initialize() failed, error code =", mt.last_error())
            quit()

        # Log in to the trade account
        mt.login(login_acc['login'], login_acc['password'], login_acc['server'])

    @classmethod
    def trade(cls, symbol, settings, position, action, **kwargs):
        # action == Open Close Adjust (adjust is adjusting tp or sl)
        # Amount of pips allowed to trade if price not filled
        # magic = ID for trade unique to each position and symbol combo
        # Lot size unique to each position and Symbol set in config
        deviation = kwargs.get('deviation', 5)
        magic = kwargs.get('magic', 1)
        lot = kwargs.get('lot', settings.lot)
        sl = kwargs.get('sl', 0.0)
        tp = kwargs.get('tp', 0.0)

        # Setting Results to return if none
        result = {}

        # set order details for long or short
        if position == 1:
            open_order_type = mt.ORDER_TYPE_BUY
            close_order_type = mt.ORDER_TYPE_SELL
            open_price = mt.symbol_info_tick(symbol).ask
            close_price = mt.symbol_info_tick(symbol).bid

        else:
            open_order_type = mt.ORDER_TYPE_SELL
            close_order_type = mt.ORDER_TYPE_BUY
            open_price = mt.symbol_info_tick(symbol).bid
            close_price = mt.symbol_info_tick(symbol).ask

        if action == 'Open':
            # Request details
            request = {
                "action": mt.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": lot,
                "type": open_order_type,
                "price": open_price,
                "sl": sl,
                "tp": tp,
                "deviation": deviation,
                "magic": magic,
                "comment": '',
                "type_time": mt.ORDER_TIME_GTC,
                "type_filling": mt.ORDER_FILLING_IOC,
            }

            # Send a trading request to MT5
            send_order = mt.order_send(request)
            result.update({1: send_order})

        elif action == 'Close':
            # Fetch all open orders with a specific Magic Number
            positions = mt.positions_get(symbol=symbol, magic=magic)
            positions = [i for i in positions if i.magic == magic]

            # Close all open orders with the specified Magic Number
            for position in positions:
                ticket = position.ticket

                request = {
                    "action": mt.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": lot,
                    "type": close_order_type,
                    'position': ticket,
                    "price": close_price,
                    "sl": 0.0,
                    "tp": 0.0,
                    "deviation": deviation,
                    "magic": magic,
                    "comment": '',
                    "type_time": mt.ORDER_TIME_GTC,
                    "type_filling": mt.ORDER_FILLING_IOC,
                }

                # send a trading request
                send_order = mt.order_send(request)
                result.update({ticket: send_order})

        elif action == 'Adjust':
            # Fetch all open orders with a specific Magic Number
            positions = mt.positions_get(symbol=symbol, magic=magic)
            positions = [i for i in positions if i.magic == magic]

            # Adjust SL/TP for each position with the given Magic Number
            for position in positions:
                ticket = position.ticket

                request = {
                    "action": mt.TRADE_ACTION_SLTP,
                    "symbol": symbol,
                    "volume": lot,
                    "type": open_order_type,
                    "position": ticket,
                    "price_open": open_price,
                    "sl": sl,
                    "tp": tp,
                    "deviation": deviation,
                    "magic": magic,
                    "comment": '',
                    "type_time": mt.ORDER_TIME_GTC,
                    "type_filling": mt.ORDER_FILLING_FOK,
                    "ENUM_ORDER_STATE": mt.ORDER_FILLING_RETURN,
                }

                # Send the modification request
                send_order = mt.order_send(request)
                result[ticket] = send_order

        return result

    @classmethod
    def order(cls, symbol, settings, action, **kwargs):
        # action == Open Close Adjust (adjust is adjusting tp or sl)
        # Amount of pips allowed to trade if price not filled
        # magic = ID for trade unique to each position and symbol combo
        # Lot size unique to each position and Symbol set in config
        deviation = kwargs.get('deviation', 5)
        magic = kwargs.get('magic', 1)
        lot = kwargs.get('lot', settings.lot)
        sl = kwargs.get('sl', 0.0)
        tp = kwargs.get('tp', 0.0)
        price = kwargs.get('price', 0.0)
        action_type = kwargs.get('action_type', 'Limit')
        position = kwargs.get('position', 1)

        # Setting Results to return if none
        result = {}

        # set order details for long or short
        if position == 1:
            if action_type == 'Stop':
                open_order_type = mt.ORDER_TYPE_BUY_STOP
            else:
                open_order_type = mt.ORDER_TYPE_BUY_LIMIT

        else:
            if action_type == 'Stop':
                open_order_type = mt.ORDER_TYPE_SELL_STOP
            else:
                open_order_type = mt.ORDER_TYPE_SELL_LIMIT

        if action == 'Open':
            # Request details
            request = {
                "action": mt.TRADE_ACTION_PENDING,
                "symbol": symbol,
                "volume": lot,
                "type": open_order_type,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": deviation,
                "magic": magic,
                "comment": '',
                "type_time": mt.ORDER_TIME_GTC,
                "type_filling": mt.ORDER_FILLING_IOC,
            }

            # Send a trading request to MT5
            send_order = mt.order_send(request)
            result.update({1: send_order})

        elif action == 'Close':
            # Fetch all open orders with a specific Magic Number
            orders = mt.orders_get(symbol=symbol, magic=magic)
            orders = [i for i in orders if i.magic == magic]

            # Close all open orders with the specified Magic Number
            for order in orders:
                ticket = order.ticket

                request = {
                    "action": mt.TRADE_ACTION_REMOVE,
                    "symbol": symbol,
                    'order': ticket,
                    "magic": magic
                }

                # send a trading request
                send_order = mt.order_send(request)
                result.update({ticket: send_order})

        return result

    @classmethod
    def get_prices(cls, symbol, time_frame, start_pos, count, date_time=None):
        divisor = mt5_config.time_conversion[time_frame]
        #print(f'{symbol} {time_frame} {start_pos} {count} {date_time}')

        if date_time is None:
            raw_prices1 = mt.copy_rates_from_pos(symbol, time_frame, start_pos, count)
        else:
            # Get the candles used at the time stated date_time
            time_now = datetime.now()
            time_difference = (time_now - date_time).total_seconds() / 60
            divisor = mt5_config.time_conversion[time_frame]
            start_position = abs(math.floor(time_difference / divisor) - 1 + start_pos)
            raw_prices1 = mt.copy_rates_from_pos(symbol, time_frame, start_position, count)

        if raw_prices1 is None:
            raise Exception(f'No data collected for {symbol} for {mt5_config.time_ref[time_frame]}')

        # Create a DataFrame from the obtained data
        prices = pd.DataFrame(raw_prices1)
        prices['Date_Time'] = pd.to_datetime(prices['time'], unit='s')

        # Get Server Time from the Latest Candle convert to UTC
        # last_candle_time = prices["time"].iloc[-1]

        # Convert to current pc time
        # if date_time is None:
        #     time_now = datetime.now()-timedelta(minutes=start_pos * divisor)
        #     broker_utc_offset = round(((last_candle_time - time_now).total_seconds()) / 3600)
        # else:
        #     time_now = date_time - timedelta(minutes=(start_pos - 1) * divisor)
        #     broker_utc_offset = round(((last_candle_time - time_now).total_seconds()) / 3600)
        # prices["UTC_Time"] = prices["time"] - timedelta(hours=2)
        prices['Time'] = prices['Date_Time'].dt.time

        return prices

    @classmethod
    def active_positions(cls, symbol, magic):
        active_positions = mt.positions_get(symbol=symbol, magic=magic)

        if active_positions is None:
            return []

        active_positions = [trade._asdict() for trade in active_positions if trade.magic == magic]
        active_positions = pd.DataFrame(active_positions)

        # Checks active trades exists
        if len(active_positions) > 0:
            active_positions['Date_Time'] = pd.to_datetime(active_positions['time'], unit='s')
            active_positions.sort_values(by="Date_Time", inplace=True)
            active_positions = active_positions.loc[
                (active_positions['symbol'] == symbol) &
                (active_positions['magic'] == magic)
                ]
        else:
            active_positions = []

        return active_positions

    @classmethod
    def get_history(cls, symbol, magic, from_date, to_date):
        history = mt.history_deals_get(from_date, to_date)
        history_dict_list = [trade._asdict() for trade in history]
        historical_df = pd.DataFrame(history_dict_list)

        if len(historical_df) > 0:
            historical_df['Date_Time'] = pd.to_datetime(historical_df['time'], unit='s')
            historical_df.sort_values(by="Date_Time", inplace=True)
            historical_df = historical_df.loc[
                (historical_df['symbol'] == symbol) &
                (historical_df['magic'] == magic)
                ]
        else:
            historical_df = []

        return historical_df

    @classmethod
    def is_market_closed(cls,symbol):
        # """Check if the market is closed for a given symbol."""
        # symbol_info = mt.symbol_info(symbol)
        # if symbol_info is None:
        #     raise Exception(f"Symbol {symbol} not found!")
        #
        # # Trade Mode Check (0 = Full Access, 1 = Close Only, 2 = Disabled)
        # if symbol_info.trade_mode == 2:
        #     return True  # Market is closed
        # return False  # Market is open
        if ((datetime.now() >= datetime.now().replace(hour=22, minute=0, second=0)) and
                (datetime.now() <= datetime.now().replace(hour=22, minute=59, second=59))):
            return True
        else:
            return False

    @classmethod
    def trade_commentry(cls, trading_result, symbol, position):

        position_string = {1: 'Long', -1: 'Short'}

        if len(trading_result) > 0:
            for trade in trading_result.keys():
                if trading_result[trade] is None:
                    print(f'Error in executing trade {position_string[position]} {position} check configuration')
                else:
                    print(f'{len(trading_result)} {symbol} {position_string[position]} trade(s) taken',
                          '\n'.join([trading_result[key].comment for key in trading_result.keys()]))

    @classmethod
    def create_magic(cls, setting, timeframe, symbol):

        for time in setting.time_frame_config:
            if time.timeframe.frames == timeframe:
                frame_magic = time.timeframe.magic

        created_magic = setting.bot_magic + frame_magic + mt5_config.magic[symbol]

        return created_magic

    @classmethod
    def generate_lot(cls, setting, timeframe, symbol):

        frame_lot = None
        for time in setting.time_frame_config:
            if time.timeframe.frames == timeframe:
                frame_lot = time.lot
                return frame_lot

        if frame_lot is None:
            return setting.bot_lot

    @classmethod
    def get_sl(cls, settings, timeframe, symbol):
        frame_sl = None
        for time in settings.time_frame_config:
            if time.timeframe.frames == timeframe:
                frame_sl = time.sl
                return frame_sl

        if frame_sl is None:
            return settings.sl


