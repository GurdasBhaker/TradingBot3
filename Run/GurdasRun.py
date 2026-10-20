# from datetime import datetime
from TB2.Utilz.MT5_data_class import MT5ConfigData as mt5_config, mt5_accounts as mt5_acc, TimeFrames
from apscheduler.schedulers.blocking import BlockingScheduler
from TB2.Utilz.Telegram_handler import TelegramConfig as tc
# from TB2.Utilz.BotList import Register
# import importlib

from TB2.TradingBots import stochastic, EngulfingNote, EngulfingTrade, FibSniper
from TB2.Configurations.configurations import Gurdas_Engulfing, Stochastic_15M_63_9_9, Fibonacci_Sniper


# Create a scheduler
scheduler = BlockingScheduler()

# generate symbols
# symbols = ['GBPJPY', 'USDJPY', 'GBPUSD', 'EURUSD', 'XAUUSD', 'BTCUSD', 'AUDUSD', 'NZDUSD', 'US30', 'USTEC']
symbols = ['USDJPY', 'GBPUSD', 'EURUSD', 'AUDUSD', 'NZDUSD', 'USDCAD']

chat_id = tc.gurdas_chat_id
account = mt5_acc.gurdas_52157323


# Stochastic
stochastic_configs = Stochastic_15M_63_9_9.time_frame_config
for item in stochastic_configs:
    scheduler.add_job(
        stochastic.StochasticOscilator.calculator, 'cron', minute='*/15', misfire_grace_time=30, args=[
            account, symbols, item.timeframe.frames, Stochastic_15M_63_9_9, chat_id
        ]
    )

# Fibonacci
fib_configs = Fibonacci_Sniper.time_frame_config
for item in fib_configs:
    scheduler.add_job(
        fib_sniper.FibonacciSniperBot.calculator, 'cron', minute='*/5', misfire_grace_time=30, args=[
            account, symbols, item.timeframe.frames, Fibonacci_Sniper, chat_id
        ]
    )


# Dictionary mapping timeframes to their execution hours
engulfing_schedules = {
    "H4": "22, 23, 2,6,10,14,18",  # Every 4 hours starting 10 PM
    "H8": "22, 23, 6,14",  # Every 8 hours starting 10 PM
    "H12": "22, 23, 10",
}

# Iterate through each timeframe and add scheduled jobs dynamically
for timeframe, schedule in engulfing_schedules.items():
    scheduler.add_job(
        EngulfingTrade.EngulfingCandleBot.calculator,
        'cron',
        hour=schedule,
        misfire_grace_time=60,
        args=[
            account,
            symbols,
            getattr(TimeFrames, timeframe).frames,  # Dynamically get the correct timeframe
            Gurdas_Engulfing,
            chat_id
        ]
    )


# for timeframe, schedule in engulfing_schedules.items():
#     EngulfingTrade.EngulfingCandleBot.calculator(
#         account,
#         symbols,
#         getattr(TimeFrames, timeframe).frames,  # Dynamically get the correct timeframe
#         Gurdas_Engulfing,
#         chat_id
#     )


try:
    # Start the scheduler
    scheduler.start()
except KeyboardInterrupt:
    # Handle keyboard interrupt (Ctrl+C) to gracefully exit
    pass
