# from datetime import datetime
from TB2.Utilz.MT5_data_class import MT5ConfigData as mt5_config, mt5_accounts as mt5_acc
from apscheduler.schedulers.blocking import BlockingScheduler
from TB2.Utilz.Telegram_handler import TelegramConfig as tc
from TB2.Utilz.MT5_data_class import TimeFrames
from TB2.TradingBots import (stochastic, EngulfingStochasticNote, EngulfingStochasticTrade, EngulfingNote,
                             stochastic_notification)
from TB2.Configurations.configurations import (
    EngulfingStochasticNotificationAll, EngulfingStochasticTradeAll, Stochastic_63_9_9, EngulfingNotificationAll,
    Stochastic_63_9_9_AllNotifications
)


# Create a scheduler
scheduler = BlockingScheduler()

# generate symbols
symbols = ['GBPJPY', 'USDJPY', 'GBPUSD', 'EURUSD', 'XAUUSD', 'BTCUSD', 'AUDUSD', 'NZDUSD', 'US30', 'USTEC']
# symbols = ['USDJPY', 'GBPUSD', 'EURUSD', 'BTCUSD', 'AUDUSD', 'NZDUSD', 'USDCAD']

chat_id = tc.karan_chat_id
account = mt5_acc.karan_51592486

# Stochastic
scheduler.add_job(
    stochastic.StochasticOscilator.calculator,
    'cron',
    minute='*/5',
    misfire_grace_time=30,
    args=[
        account,
        ['US30', 'USTEC'],
        TimeFrames.M5.frames,
        Stochastic_63_9_9,
        chat_id
    ]
    )

# Stochastic Notifications 5 min
scheduler.add_job(
    stochastic_notification.StochasticOscilatorNotification.calculator,
    'cron',
    minute='*/5',
    misfire_grace_time=30,
    args=[
        account,
        ['US30', 'USTEC'],
        TimeFrames.M5.frames,
        Stochastic_63_9_9_AllNotifications,
        tc.karan_stoch_chat_id
    ]
    )

# Stochastic Notifications 15 min
scheduler.add_job(
    stochastic_notification.StochasticOscilatorNotification.calculator,
    'cron',
    minute='*/15',
    misfire_grace_time=30,
    args=[
        account,
        ['USDJPY', 'XAUUSD'],
        TimeFrames.M15.frames,
        Stochastic_63_9_9_AllNotifications,
        tc.karan_stoch_chat_id
    ]
    )

# # Stochastic Notifications 1H - 4H
# stochastic_schedules = {
#     "H1": "*",  # Every hour
#     "H2": "*/2",  # Every 2 hours
#     "H4": "*/4",  # Every 4 hours
#
# }
#
# # Iterate through each timeframe and add scheduled jobs dynamically
# for timeframe, schedule in stochastic_schedules.items():
#     scheduler.add_job(
#         stochastic_notification.StochasticOscilatorNotification.calculator,
#         'cron',
#         hour=schedule,
#         misfire_grace_time=60,
#         args=[
#             account,
#             symbols,
#             getattr(TimeFrames, timeframe).frames,  # Dynamically get the correct timeframe
#             Stochastic_63_9_9_AllNotifications,
#             tc.karan_stoch_chat_id
#         ]
#     )

# Stochastic Engulfing Notifications
# take trade tp -0.629 sl 1, trade at .25 and .5 1 lot
engulfing_timeframes = EngulfingStochasticNotificationAll.time_frame_config
for item in engulfing_timeframes:
    scheduler.add_job(
        EngulfingStochasticNote.EngulfingStochasticCandle.calculator,
        'cron',
        minute='*',
        misfire_grace_time=30,
        args=[
            account,
            symbols,
            item.timeframe.frames,
            EngulfingStochasticNotificationAll,
            chat_id
        ]
    )
#
# gold and indices start new candles at different times. so changing it for currencies and indices split.
symbols1 = ['GBPJPY', 'USDJPY', 'GBPUSD', 'EURUSD', 'BTCUSD', 'AUDUSD', 'NZDUSD']
symbols2 = ['XAUUSD', 'US30', 'USTEC']

# Dictionary mapping timeframes to their execution hours
engulfing_schedules1 = {
    "H4": "22,2,6,10,14,18",  # Every 4 hours starting 10 PM
    "H6": "22,4,10,16",
    "H8": "22,6,14",  # Every 8 hours starting 10 PM
    "H12": "22, 10",
    "D1": "22"        # Once a day at 10 PM
}

engulfing_schedules2 = {
    "H4": "23,2,6,10,14,18",  # Every 4 hours starting 10 PM
    "H6": "23,4,10,16",
    "H8": "23,6,14",  # Every 8 hours starting 10 PM
    "H12": "23, 10",
    "D1": "23"        # Once a day at 10 PM
}

# Iterate through each timeframe and add scheduled jobs dynamically
for timeframe, schedule in engulfing_schedules1.items():
    scheduler.add_job(
        EngulfingStochasticTrade.EngulfingStochasticBot.calculator,
        'cron',
        hour=schedule,
        minute='1',
        misfire_grace_time=60,
        args=[
            account,
            symbols1,
            getattr(TimeFrames, timeframe).frames,  # Dynamically get the correct timeframe
            EngulfingStochasticTradeAll,
            chat_id
        ]
    )

# Iterate through each timeframe and add scheduled jobs dynamically
for timeframe, schedule in engulfing_schedules2.items():
    scheduler.add_job(
        EngulfingStochasticTrade.EngulfingStochasticBot.calculator,
        'cron',
        hour=schedule,
        minute='1',
        misfire_grace_time=60,
        args=[
            account,
            symbols2,
            getattr(TimeFrames, timeframe).frames,  # Dynamically get the correct timeframe
            EngulfingStochasticTradeAll,
            chat_id
        ]
    )


try:
    # Start the scheduler
    scheduler.start()
except KeyboardInterrupt:
    # Handle keyboard interrupt (Ctrl+C) to gracefully exit
    pass
