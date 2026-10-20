from dataclasses import dataclass
from typing import NamedTuple
from TradingBot3.Utilz.MT5_data_class import TimeFrames


class TimeFrameData(NamedTuple):
    timeframe: list
    lot: float = 1.0
    sl: float = 0.0
    tp: float = 0.0


@dataclass(frozen=True)
class Stochastic_15M_63_9_9:
    # 63, 9, 9
    k = 63
    d = 9
    smooth = 9
    lot = 1.0
    upper_bound = 90
    lower_bound = 10
    bot_magic = 10000
    time_frame_config = [
        TimeFrameData(TimeFrames.M15, sl=30),
    ]

