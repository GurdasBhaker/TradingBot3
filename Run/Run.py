from dataclasses import dataclass
from Utilz.MT5_data_class import TimeFrames, mt5_accounts as mt5_acc
from Utilz.Telegram_handler import TelegramConfig as tc
from Utilz.MT5_handler import TimeFrameData
from TradingBots import stochastic

# generate symbols
# symbols = ['USDJPY', 'GBPUSD', 'EURUSD', 'AUDUSD', 'NZDUSD', 'USDCAD']
symbols = ['GBPUSD']

chat_id = tc.gurdas_chat_id
account = mt5_acc.gurdas_115078769


@dataclass(frozen=True)
class Stochastic_63_9_9:
    k = 63
    d = 9
    smooth = 9
    upper_bound = 90
    lower_bound = 10


# Stochastic
stochastic.StochasticOscilator.calculator(
    account,
    symbols,
    TimeFrameData(TimeFrames.M15, sl=30)
)
