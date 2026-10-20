from dataclasses import dataclass
import MetaTrader5 as mt
from typing import NamedTuple


@dataclass(frozen=True)
class mt5_accounts:
    # Gurdas 10K acc test
    gurdas_52157323 = dict(
        login=52157323,
        password='Z3MPS!oeeI@rPE',
        server='ICMarketsSC-Demo'
    )

    # Karan 100K acc
    karan_51592486 = dict(
        login=51592486,  # Karan 100K acc testing DEV
        password='39P$X0Fl45',
        server='ICMarketsSC-Demo',
    )

    kai_5035965321 = dict(
        login=5035965321,
        password='@1LhLbLa',
        server='MetaQuotes-Demo',
    )

    kai_96431230 = dict(
        login=96431230,
        password='P-3uGbAy',
        server='MetaQuotes-Demo',
    )


@dataclass(frozen=True)
class MT5ConfigData:
    time_ref = {
        mt.TIMEFRAME_M1: 'M1',
        mt.TIMEFRAME_M5: 'M5',
        mt.TIMEFRAME_M15: 'M15',
        mt.TIMEFRAME_M30: 'M30',
        mt.TIMEFRAME_H1: 'H1',
        mt.TIMEFRAME_H2: 'H2',
        mt.TIMEFRAME_H3: 'H3',
        mt.TIMEFRAME_H4: 'H4',
        mt.TIMEFRAME_H6: 'H6',
        mt.TIMEFRAME_H8: 'H8',
        mt.TIMEFRAME_H12: 'H12',
        mt.TIMEFRAME_D1: 'D1',
        mt.TIMEFRAME_W1: 'W1',
        mt.TIMEFRAME_MN1: 'MN1',
    }

    time_conversion = {
        mt.TIMEFRAME_M1: 1,
        mt.TIMEFRAME_M5: 5,
        mt.TIMEFRAME_M15: 15,
        mt.TIMEFRAME_M30: 30,
        mt.TIMEFRAME_H1: 60,
        mt.TIMEFRAME_H2: 120,
        mt.TIMEFRAME_H3: 180,
        mt.TIMEFRAME_H4: 240,
        mt.TIMEFRAME_H6: 360,
        mt.TIMEFRAME_H8: 480,
        mt.TIMEFRAME_H12: 720,
        mt.TIMEFRAME_D1: 1440,
        mt.TIMEFRAME_W1: 10080,
        mt.TIMEFRAME_MN1: 43200,
    }

    magic = {
        'US30': 1,
        'USTEC': 2,
        'XAUUSD': 3,
        'GBPUSD': 4,
        'AUDUSD': 5,
        'NZDUSD': 6,
        'EURUSD': 8,
        'USDCAD': 9,
        'USDJPY': 10,
        'BTCUSD': 11,
        'GBPJPY': 12,
    }

    point = {
        'US30': 1,
        'BTCUSD': 1,
        'USTEC': 1,
        'XAUUSD': 10,
        'GBPUSD': 10000,
        'AUDUSD': 10000,
        'NZDUSD': 10000,
        'EURGBP': 10000,
        'EURUSD': 10000,
        'USDCAD': 10000,
        'USDJPY': 100,
        'GBPJPY': 100
    }


class TimeFrameData(NamedTuple):
    frames: list
    magic: int


@dataclass(frozen=True)
class TimeFrames:
    M1 = TimeFrameData(frames=[mt.TIMEFRAME_M1, mt.TIMEFRAME_M1], magic=000)
    M5 = TimeFrameData(frames=[mt.TIMEFRAME_M5, mt.TIMEFRAME_M1], magic=100)
    M15 = TimeFrameData(frames=[mt.TIMEFRAME_M15, mt.TIMEFRAME_M1], magic=200)
    M30 = TimeFrameData(frames=[mt.TIMEFRAME_M30, mt.TIMEFRAME_M1], magic=300)
    H1 = TimeFrameData(frames=[mt.TIMEFRAME_H1, mt.TIMEFRAME_M1], magic=400)
    H2 = TimeFrameData(frames=[mt.TIMEFRAME_H2, mt.TIMEFRAME_M1], magic=500)
    H3 = TimeFrameData(frames=[mt.TIMEFRAME_H3, mt.TIMEFRAME_M1], magic=600)
    H4 = TimeFrameData(frames=[mt.TIMEFRAME_H4, mt.TIMEFRAME_M1], magic=700)
    H6 = TimeFrameData(frames=[mt.TIMEFRAME_H6, mt.TIMEFRAME_M1], magic=800)
    H8 = TimeFrameData(frames=[mt.TIMEFRAME_H8, mt.TIMEFRAME_M1], magic=900)
    H12 = TimeFrameData(frames=[mt.TIMEFRAME_H12, mt.TIMEFRAME_M1], magic=1000)
    D1 = TimeFrameData(frames=[mt.TIMEFRAME_D1, mt.TIMEFRAME_M1], magic=1100)
    W1 = TimeFrameData(frames=[mt.TIMEFRAME_W1, mt.TIMEFRAME_M1], magic=1200)
    MN1 = TimeFrameData(frames=[mt.TIMEFRAME_MN1, mt.TIMEFRAME_M1], magic=1300)

    M5_M5 = TimeFrameData(frames=[mt.TIMEFRAME_M5, mt.TIMEFRAME_M5], magic=1400)

