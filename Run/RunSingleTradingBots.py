from TB2.Utilz.MT5_data_class import MT5ConfigData as mt5_config, mt5_accounts as mt5_acc
from TB2.Utilz.MT5_handler import MetaTrader5_handler as mt5_handler
from TB2.Utilz.Telegram_handler import TelegramConfig as tc
from TB2.Utilz.BotRegister import BotRegister
from datetime import datetime
import MetaTrader5 as mt
import importlib

# Default symbols, customise as needed in individual function
# symbols = ['GBPJPY', 'USDJPY', 'GBPUSD', 'EURUSD', 'XAUUSD', 'BTCUSD', 'AUDUSD', 'NZDUSD', 'US30', 'USTEC']
# symbols = ['USDJPY', 'GBPUSD', 'EURUSD', 'BTCUSD', 'AUDUSD', 'NZDUSD', 'USDCAD']
# symbols = ['US30', 'USTEC', 'XAUUSD']
symbols = ['NZDUSD']

bot_id = BotRegister.EngulfingNotificationAll
chat_id = tc.karan_chat_id
account = mt5_acc.karan_51592486

year = 2025
month = 2
day = 13
hour = 18
minute = 1
second = 00

#date_time = datetime(year, month, day, hour, minute, second)
date_time = None


def load_class(module_name, class_name):
    """Dynamically import a module and return the class."""
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def load_bot(bot_id):
    # Load the bot and config classes from the Register
    bot_class = load_class(bot_id["module"], bot_id["class"])
    config_class = load_class(bot_id["config_module"], bot_id["config_class"])

    return bot_class, config_class


# Bots
def run_bot(bot_id):
    bot, config = load_bot(bot_id)
    for timeframe_config in config.time_frame_config:
        time = timeframe_config.timeframe
        time_frame_string = mt5_config.time_ref[time.frames[0]]
        bot.calculator(account, symbols, time.frames, config, chat_id)


run_bot(bot_id)
