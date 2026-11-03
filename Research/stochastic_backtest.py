"""MT5 stochastic parameter sweep and trade-level CSV export.

Run this file in PyCharm with MetaTrader 5 open and logged in.
This script never sends orders. Requires: pip install MetaTrader5 pandas numpy

Signal rule (explicit baseline, NOT guaranteed to match your custom SignalFactory):
  Long  = %K crosses ABOVE %D, with prior %K <= lower bound.
  Short = %K crosses BELOW %D, with prior %K >= upper bound.
Signal evaluated on a fully closed bar; entry at next bar open.
One trade at a time per individual parameter combination; no overlapping positions.
ATR(14) stop uses the last completed signal candle; TP is 2x initial risk.
Stop loss takes precedence when both SL and TP are touched in one OHLC bar.
OHLC simulation is approximate; constant spread is an optional approximation.
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from itertools import product
from pathlib import Path

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

# ---------------------- EDIT THESE SETTINGS ----------------------
SYMBOLS = ["GBPUSD"]
TIMEFRAMES = {"M15": mt5.TIMEFRAME_M15, "H1": mt5.TIMEFRAME_H1, "D1": mt5.TIMEFRAME_D1}
TIMEFRAME_DELTAS = {"M15": timedelta(minutes=15), "H1": timedelta(hours=1), "D1": timedelta(days=1)}

# Trial ranges; expand these to the K/D/smooth intervals you want.
K_VALUES = range(5, 51, 5)
D_VALUES = range(5, 51, 5)
SMOOTH_VALUES = range(20, 101, 5)
UPPER_BOUNDS = [90]
LOWER_BOUNDS = [10]

ATR_PERIOD = 14
ATR_MULTIPLIERS = [1.5]  # Test alternatives later: [1.0, 1.5, 2.0, 2.5, 3.0]
REWARD_RISK_RATIO = 2.0  # 2R target for each 1R initial ATR stop
ASSUMED_SPREAD_PIPS = 1.5  # 0=ignore spread; e.g. 1.0 for assumed fixed 1 pip spread
WARMUP_DAYS = 500  # allows for D1 trading days and the largest indicator lookback
OUTPUT_DIR = Path(__file__).resolve().parent / "backtest_results"
# ---------------------------------------------------------------

TRADE_COLUMNS = [
    "symbol", "timeframe", "k", "d", "smooth", "upper_bound", "lower_bound",
    "atr_period", "atr_multiplier", "atr_at_entry_pips", "initial_risk_pips", "reward_risk_ratio",
    "signal_time_utc", "entry_time_utc", "entry_price", "direction",
    "stop_loss", "take_profit", "exit_time_utc", "exit_price", "exit_reason",
    "pnl_pips", "realised_R", "bars_held",
]
SUMMARY_COLUMNS = [
    "symbol", "timeframe", "k", "d", "smooth", "upper_bound", "lower_bound",
    "atr_period", "atr_multiplier", "reward_risk_ratio",
    "trades", "wins", "losses", "open_at_end", "win_rate_pct", "net_pips", "net_R",
]


def pip_size(symbol: str) -> float:
    info = mt5.symbol_info(symbol)
    if info is None:
        raise RuntimeError(f"Symbol not found in MT5: {symbol}")
    return float(info.point) * (10 if info.digits in (3, 5) else 1)


def fetch_bars(symbol: str, tf: int, start: datetime, end: datetime) -> pd.DataFrame:
    # MT5 rates timestamps are UTC candle-open times.
    candles = mt5.copy_rates_range(symbol, tf, start, end)
    if candles is None or len(candles) == 0:
        raise RuntimeError(f"No data for {symbol} / {tf}. MT5 says: {mt5.last_error()}")
    frame = pd.DataFrame(candles)
    frame["time"] = pd.to_datetime(frame["time"], unit="s", utc=True)
    frame = frame.sort_values("time").drop_duplicates("time").reset_index(drop=True)
    return frame


def stochastic(frame: pd.DataFrame, k: int, smooth: int, d: int) -> tuple[np.ndarray, np.ndarray]:
    # Standard slow stochastic: raw %K, SMA smoothed %K, SMA %D.
    low = frame["low"].rolling(window=k, min_periods=k).min()
    high = frame["high"].rolling(window=k, min_periods=k).max()
    denominator = (high - low).replace(0, np.nan)
    raw_k = 100.0 * (frame["close"] - low) / denominator
    slow_k = raw_k.rolling(window=smooth, min_periods=smooth).mean()
    line_d = slow_k.rolling(window=d, min_periods=d).mean()
    return slow_k.to_numpy(dtype=float), line_d.to_numpy(dtype=float)


def compute_atr(frame: pd.DataFrame, period: int) -> np.ndarray:
    """Wilder ATR, seeded with the SMA of the first `period` true ranges."""
    prev_close = frame["close"].shift(1)
    true_range = pd.concat([
        frame["high"] - frame["low"],
        (frame["high"] - prev_close).abs(),
        (frame["low"] - prev_close).abs(),
    ], axis=1).max(axis=1).to_numpy(dtype=float)
    atr = np.full(len(true_range), np.nan, dtype=float)
    if len(true_range) < period:
        return atr
    atr[period - 1] = np.mean(true_range[:period])
    for i in range(period, len(true_range)):
        atr[i] = (atr[i - 1] * (period - 1) + true_range[i]) / period
    return atr


def simulate(
    bars: pd.DataFrame, kvals: np.ndarray, dvals: np.ndarray,
    upper: int, lower: int, k: int, d: int, smooth: int,
    symbol: str, timeframe: str, first_entry: pd.Timestamp,
    end: pd.Timestamp, pip: float, atr_values: np.ndarray, atr_multiplier: float,
):
    times = bars["time"].to_numpy()
    opens = bars["open"].to_numpy(dtype=float)
    highs = bars["high"].to_numpy(dtype=float)
    lows = bars["low"].to_numpy(dtype=float)
    spread = ASSUMED_SPREAD_PIPS * pip
    n = len(bars)

    # Crossovers on completed bar i. Execute next bar's open (i+1).
    crosses_up = (kvals[1:-1] > dvals[1:-1]) & (kvals[:-2] <= dvals[:-2]) & (kvals[:-2] <= lower)
    crosses_down = (kvals[1:-1] < dvals[1:-1]) & (kvals[:-2] >= dvals[:-2]) & (kvals[:-2] >= upper)
    signals = np.zeros(n, dtype=np.int8)
    signals[1:-1][crosses_up] = 1
    signals[1:-1][crosses_down] = -1

    idx = 1
    count = wins = losses = unfinished = 0
    net_pips = 0.0
    while idx < n - 1:
        direction = int(signals[idx])
        entry_idx = idx + 1
        if direction == 0 or pd.Timestamp(times[entry_idx]) < first_entry or pd.Timestamp(times[entry_idx]) >= end:
            idx += 1
            continue

        # Signal is confirmed at the close of idx; its ATR is already known
        # before entry at the next candle's open. Never use entry candle data.
        signal_atr = atr_values[idx]
        if not np.isfinite(signal_atr) or signal_atr <= 0:
            idx += 1
            continue
        sl_dist = float(signal_atr) * atr_multiplier
        tp_dist = sl_dist * REWARD_RISK_RATIO

        entry = opens[entry_idx] + (spread if direction == 1 else 0.0)
        sl = entry - direction * sl_dist
        tp = entry + direction * tp_dist
        reason = "OPEN_AT_END"
        exit_price = np.nan
        exit_idx = n - 1
        for j in range(entry_idx, n):
            # OHLC are BID candles in typical MT5 FX data. Short closures occur at ASK.
            exit_open = opens[j] + (spread if direction == -1 else 0.0)
            exit_high = highs[j] + (spread if direction == -1 else 0.0)
            exit_low = lows[j] + (spread if direction == -1 else 0.0)
            if direction == 1:
                # Gap through threshold: fill at open rather than pretend SL/TP filled at target.
                if exit_open <= sl:
                    reason, exit_price = "SL", exit_open
                elif exit_open >= tp:
                    reason, exit_price = "TP", exit_open
                elif exit_low <= sl:
                    reason, exit_price = "SL", sl
                elif exit_high >= tp:
                    reason, exit_price = "TP", tp
            else:
                if exit_open >= sl:
                    reason, exit_price = "SL", exit_open
                elif exit_open <= tp:
                    reason, exit_price = "TP", exit_open
                elif exit_high >= sl:
                    reason, exit_price = "SL", sl
                elif exit_low <= tp:
                    reason, exit_price = "TP", tp
            if reason != "OPEN_AT_END":
                exit_idx = j
                break

        pnl = direction * (exit_price - entry) / pip if reason != "OPEN_AT_END" else np.nan
        realised_r = direction * (exit_price - entry) / sl_dist if reason != "OPEN_AT_END" else np.nan
        count += 1
        if reason == "TP":
            wins += 1
        elif reason == "SL":
            losses += 1
        else:
            unfinished += 1
        if np.isfinite(pnl):
            net_pips += float(pnl)

        yield {
            "symbol": symbol, "timeframe": timeframe, "k": k, "d": d, "smooth": smooth,
            "upper_bound": upper, "lower_bound": lower,
            "atr_period": ATR_PERIOD, "atr_multiplier": atr_multiplier,
            "atr_at_entry_pips": round(float(signal_atr / pip), 4),
            "initial_risk_pips": round(float(sl_dist / pip), 4),
            "reward_risk_ratio": REWARD_RISK_RATIO,
            "signal_time_utc": pd.Timestamp(times[idx]).isoformat(),
            "entry_time_utc": pd.Timestamp(times[entry_idx]).isoformat(),
            "entry_price": round(float(entry), 8), "direction": direction,
            "stop_loss": round(float(sl), 8), "take_profit": round(float(tp), 8),
            "exit_time_utc": pd.Timestamp(times[exit_idx]).isoformat() if reason != "OPEN_AT_END" else "",
            "exit_price": round(float(exit_price), 8) if np.isfinite(exit_price) else "",
            "exit_reason": reason, "pnl_pips": round(float(pnl), 4) if np.isfinite(pnl) else "",
            "realised_R": round(float(realised_r), 6) if np.isfinite(realised_r) else "",
            "bars_held": exit_idx - entry_idx + 1 if reason != "OPEN_AT_END" else "",
        }
        # Do not open overlapping positions within this parameter combination.
        idx = exit_idx + 1


def main():
    if ATR_PERIOD < 1 or REWARD_RISK_RATIO <= 0 or ASSUMED_SPREAD_PIPS < 0 or not ATR_MULTIPLIERS or any(x <= 0 for x in ATR_MULTIPLIERS):
        raise ValueError("ATR period, ATR multipliers and reward/risk must be positive; spread cannot be negative")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    cutoff = (pd.Timestamp(now) - pd.DateOffset(months=3)).to_pydatetime()
    from_date = cutoff - timedelta(days=WARMUP_DAYS)
    # Use the latest complete candle only (fixed D1 duration assumes UTC-based daily bars).
    config_count = len(K_VALUES) * len(D_VALUES) * len(SMOOTH_VALUES) * len(UPPER_BOUNDS) * len(LOWER_BOUNDS) * len(ATR_MULTIPLIERS)
    print(f"Backtest UTC: {cutoff.isoformat()} to {now.isoformat()}; {config_count:,} combinations per symbol/timeframe")

    if not mt5.initialize():
        raise RuntimeError(f"MT5 initialise failed: {mt5.last_error()}. Open MT5 and sign in first.")
    try:
        for symbol in SYMBOLS:
            if not mt5.symbol_select(symbol, True):
                raise RuntimeError(f"Cannot select {symbol}: {mt5.last_error()}")
            pip = pip_size(symbol)
            for tf_name, tf_code in TIMEFRAMES.items():
                raw = fetch_bars(symbol, tf_code, from_date, now)
                raw = raw.loc[raw["time"] + TIMEFRAME_DELTAS[tf_name] <= pd.Timestamp(now)].reset_index(drop=True)
                if raw.empty:
                    raise RuntimeError(f"No complete candles for {symbol}/{tf_name}")
                if raw["time"].min() > pd.Timestamp(cutoff - timedelta(days=10)):
                    print(f"WARNING {symbol}/{tf_name}: limited warmup history, check MT5 chart history")
                if tf_name == "D1" and len(raw) < max(K_VALUES) + max(D_VALUES) + max(SMOOTH_VALUES) + 5:
                    raise RuntimeError("Not enough D1 bars for the specified stochastic periods")
                print(f"Processing {symbol} {tf_name}: {len(raw):,} candles")
                atr_values = compute_atr(raw, ATR_PERIOD)  # once per timeframe, not per parameter set
                trades_path = OUTPUT_DIR / f"{symbol}_{tf_name}_trades.csv"
                summary_path = OUTPUT_DIR / f"{symbol}_{tf_name}_summary.csv"
                with trades_path.open("w", newline="", encoding="utf-8") as trades_file, summary_path.open("w", newline="", encoding="utf-8") as summary_file:
                    writer = csv.DictWriter(trades_file, fieldnames=TRADE_COLUMNS)
                    swriter = csv.DictWriter(summary_file, fieldnames=SUMMARY_COLUMNS)
                    writer.writeheader()
                    swriter.writeheader()
                    # Cache each K lookback and each smoothing result. Do not
                    # recompute rolling low/high for every D and Smooth combination.
                    lows = raw["low"]
                    highs = raw["high"]
                    closes = raw["close"]
                    for k in K_VALUES:
                        rolling_low = lows.rolling(k, min_periods=k).min()
                        rolling_high = highs.rolling(k, min_periods=k).max()
                        raw_k = 100.0 * (closes - rolling_low) / (rolling_high - rolling_low).replace(0, np.nan)
                        for smooth in SMOOTH_VALUES:
                            kvals = raw_k.rolling(smooth, min_periods=smooth).mean().to_numpy(dtype=float)
                            k_series = pd.Series(kvals)
                            for d in D_VALUES:
                                dvals = k_series.rolling(d, min_periods=d).mean().to_numpy(dtype=float)
                                for upper, lower, atr_multiplier in product(UPPER_BOUNDS, LOWER_BOUNDS, ATR_MULTIPLIERS):
                                    trades = wins = losses = open_at_end = 0
                                    net = net_r = 0.0
                                    for trade in simulate(raw, kvals, dvals, upper, lower, k, d, smooth, symbol, tf_name, pd.Timestamp(cutoff), pd.Timestamp(now), pip, atr_values, atr_multiplier):
                                        writer.writerow(trade)
                                        trades += 1
                                        wins += int(trade["exit_reason"] == "TP")
                                        losses += int(trade["exit_reason"] == "SL")
                                        open_at_end += int(trade["exit_reason"] == "OPEN_AT_END")
                                        if trade["pnl_pips"] != "":
                                            net += float(trade["pnl_pips"])
                                            net_r += float(trade["realised_R"])
                                    closed = wins + losses
                                    swriter.writerow({
                                        "symbol": symbol, "timeframe": tf_name,
                                        "k": k, "d": d, "smooth": smooth, "upper_bound": upper, "lower_bound": lower,
                                        "atr_period": ATR_PERIOD, "atr_multiplier": atr_multiplier,
                                        "reward_risk_ratio": REWARD_RISK_RATIO,
                                        "trades": trades, "wins": wins, "losses": losses,
                                        "open_at_end": open_at_end,
                                        "win_rate_pct": round(100 * wins / closed, 2) if closed else "",
                                        "net_pips": round(net, 4), "net_R": round(net_r, 4),
                                    })
                print(f"Saved {trades_path.name} and {summary_path.name}")
    finally:
        mt5.shutdown()
    print(f"Done. CSV files in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
