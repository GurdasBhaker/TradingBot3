from datetime import datetime
from TB2.Utilz.MT5_data_class import MT5ConfigData as mt5_config, mt5_accounts as mt5_acc
from apscheduler.schedulers.blocking import BlockingScheduler
from TB2.Utilz.Telegram_handler import TelegramConfig as tc
from TB2.Utilz.BotList import Register
import importlib

# Create a scheduler
scheduler = BlockingScheduler()

# generate symbols
symbols = ['GBPJPY', 'USDJPY', 'GBPUSD', 'EURUSD', 'XAUUSD', 'BTCUSD', 'AUDUSD', 'NZDUSD', 'US30', 'USTEC']
# symbols = ['USDJPY', 'GBPUSD', 'EURUSD', 'BTCUSD', 'AUDUSD', 'NZDUSD', 'USDCAD']

chat_id = tc.karan_chat_id
account = mt5_acc.karan_51592486


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
for item in Register.KaranBots:
    bot, config = load_bot(item)
    for timeframe_config in config.time_frame_config:
        time = timeframe_config.timeframe
        time_frame_string = mt5_config.time_ref[time.frames[0]]
        scheduler.add_job(
            bot.calculator,
            'cron',
            minute='*',
            misfire_grace_time=30,
            args=[account, symbols, time.frames, config, chat_id]
        )

        print(f'Ran {item["class"]} on {time_frame_string} at {datetime.now()}')


try:
    # Start the scheduler
    scheduler.start()
except KeyboardInterrupt:
    # Handle keyboard interrupt (Ctrl+C) to gracefully exit
    pass
