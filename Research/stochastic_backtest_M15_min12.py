"""MT5 stochastic parameter sweep and trade-level CSV export.

Run this file in PyCharm with MetaTrader 5 open and logged in.
This script never sends orders. Requires: pip install MetaTrader5 pandas numpy

Speed optimisations: reuse market arrays and precompute eligible crossover indices once
per stochastic setup, rather than scanning all candles 924,000 times.

Signal rule (explicit baseline, NOT guaranteed to match your custom SignalFactory):
  Long  = %K crosses ABOVE %D, with prior %K <= lower bound.
  Short = %K crosses BELOW %D, with prior %K >= upper bound.
Signal evaluated on a fully closed bar; entry at next bar open.
One trade at a time per individual parameter combination; no overlapping positions.
ATR(period) stop uses the last completed signal candle; TP uses the swept reward/risk ratio.
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
TIMEFRAMES = {"M15": mt5.TIMEFRAME_M15}
TIMEFRAME_DELTAS = {"M15": timedelta(minutes=15)}

# M15 search: K 5..100, D and smoothing 5..50, all in steps of 5.
K_VALUES = range(5, 101, 5)
D_VALUES = range(5, 51, 5)
SMOOTH_VALUES = range(5, 51, 5)
UPPER_BOUNDS = [90]
LOWER_BOUNDS = [10]

ATR_PERIODS = range(10, 21, 2)  # 10, 12, 14, 16, 18, 20
ATR_MULTIPLIERS = [round(x / 10, 1) for x in range(10, 21)]  # 1.0, 1.1, ..., 2.0
REWARD_RISK_RATIOS = [1.0, 1.1, 1.2, 1.3, 1.5, 1.8, 2.0]
MIN_CLOSED_TRADES = 12  # Only include combinations with at least 12 completed trades in summary
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


def candidate_signals(kvals: np.ndarray, dvals: np.ndarray, upper: int, lower: int,
                      valid_entries: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Compute crossover candidates ONCE per stochastic configuration."""
    crosses_up = ((kvals[1:-1] > dvals[1:-1])
                  & (kvals[:-2] <= dvals[:-2]) & (kvals[:-2] <= lower))
    crosses_down = ((kvals[1:-1] < dvals[1:-1])
                    & (kvals[:-2] >= dvals[:-2]) & (kvals[:-2] >= upper))
    directions = crosses_up.astype(np.int8) - crosses_down.astype(np.int8)
    eligible = np.flatnonzero((directions != 0) & valid_entries[2:])
    return eligible + 1, directions[eligible]


def simulate_fast(
    market: dict, signal_indices: np.ndarray, signal_directions: np.ndarray,
    upper: int, lower: int, k: int, d: int, smooth: int,
    symbol: str, timeframe: str, pip: float, atr_values: np.ndarray,
    atr_period: int, atr_multiplier: float, reward_risk_ratio: float,
):
    """Only inspect candidate signals, skipping signals while a trade is open."""
    times = market["times"]
    opens = market["opens"]
    highs = market["highs"]
    lows = market["lows"]
    spread = ASSUMED_SPREAD_PIPS * pip
    n = len(opens)
    next_allowed_signal = 1

    for idx, direction_np in zip(signal_indices, signal_directions):
        idx = int(idx)
        if idx < next_allowed_signal:
            continue
        direction = int(direction_np)
        entry_idx = idx + 1
        signal_atr = atr_values[idx]
        if not np.isfinite(signal_atr) or signal_atr <= 0:
            continue
        sl_dist = float(signal_atr) * atr_multiplier
        tp_dist = sl_dist * reward_risk_ratio
        entry = opens[entry_idx] + (spread if direction == 1 else 0.0)
        sl = entry - direction * sl_dist
        tp = entry + direction * tp_dist
        reason = "OPEN_AT_END"
        exit_price = np.nan
        exit_idx = n - 1
        for j in range(entry_idx, n):
            exit_open = opens[j] + (spread if direction == -1 else 0.0)
            exit_high = highs[j] + (spread if direction == -1 else 0.0)
            exit_low = lows[j] + (spread if direction == -1 else 0.0)
            if direction == 1:
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
        yield {
            "symbol": symbol, "timeframe": timeframe, "k": k, "d": d, "smooth": smooth,
            "upper_bound": upper, "lower_bound": lower,
            "atr_period": atr_period, "atr_multiplier": atr_multiplier,
            "atr_at_entry_pips": round(float(signal_atr / pip), 4),
            "initial_risk_pips": round(float(sl_dist / pip), 4),
            "reward_risk_ratio": reward_risk_ratio,
            "signal_time_utc": times[idx].isoformat(),
            "entry_time_utc": times[entry_idx].isoformat(),
            "entry_price": round(float(entry), 8), "direction": direction,
            "stop_loss": round(float(sl), 8), "take_profit": round(float(tp), 8),
            "exit_time_utc": times[exit_idx].isoformat() if reason != "OPEN_AT_END" else "",
            "exit_price": round(float(exit_price), 8) if np.isfinite(exit_price) else "",
            "exit_reason": reason, "pnl_pips": round(float(pnl), 4) if np.isfinite(pnl) else "",
            "realised_R": round(float(realised_r), 6) if np.isfinite(realised_r) else "",
            "bars_held": exit_idx - entry_idx + 1 if reason != "OPEN_AT_END" else "",
        }
        next_allowed_signal = exit_idx + 1


def main():
    if (not ATR_PERIODS or any(x < 1 for x in ATR_PERIODS)
            or not REWARD_RISK_RATIOS or any(x <= 0 for x in REWARD_RISK_RATIOS)
            or ASSUMED_SPREAD_PIPS < 0
            or not ATR_MULTIPLIERS or any(x <= 0 for x in ATR_MULTIPLIERS)):
        raise ValueError("ATR period, ATR multipliers and reward/risk must be positive; spread cannot be negative")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    cutoff = (pd.Timestamp(now) - pd.DateOffset(months=3)).to_pydatetime()
    from_date = cutoff - timedelta(days=WARMUP_DAYS)
    # Use the latest complete candle only (fixed D1 duration assumes UTC-based daily bars).
    config_count = len(K_VALUES) * len(D_VALUES) * len(SMOOTH_VALUES) * len(UPPER_BOUNDS) * len(LOWER_BOUNDS) * len(ATR_PERIODS) * len(ATR_MULTIPLIERS) * len(REWARD_RISK_RATIOS)
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
                atr_by_period = {period: compute_atr(raw, period) for period in ATR_PERIODS}
                market = {
                    "times": raw["time"].tolist(),
                    "opens": raw["open"].to_numpy(dtype=float),
                    "highs": raw["high"].to_numpy(dtype=float),
                    "lows": raw["low"].to_numpy(dtype=float),
                }
                # Entry occurs at signal index + 1; ignore warmup signals.
                valid_entries = ((raw["time"] >= pd.Timestamp(cutoff))
                                 & (raw["time"] < pd.Timestamp(now))).to_numpy(dtype=bool)
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
                                for upper, lower in product(UPPER_BOUNDS, LOWER_BOUNDS):
                                    signal_indices, signal_directions = candidate_signals(
                                        kvals, dvals, upper, lower, valid_entries
                                    )
                                    if len(signal_indices) == 0:
                                        continue  # Every ATR/RR combination would have zero trades.
                                    for atr_period, atr_multiplier, reward_risk_ratio in product(
                                        ATR_PERIODS, ATR_MULTIPLIERS, REWARD_RISK_RATIOS
                                    ):
                                        trades = wins = losses = open_at_end = 0
                                        net = net_r = 0.0
                                        for trade in simulate_fast(market, signal_indices, signal_directions, upper, lower, k, d, smooth, symbol, tf_name, pip, atr_by_period[atr_period], atr_period, atr_multiplier, reward_risk_ratio):
                                            writer.writerow(trade)
                                            trades += 1
                                            wins += int(trade["exit_reason"] == "TP")
                                            losses += int(trade["exit_reason"] == "SL")
                                            open_at_end += int(trade["exit_reason"] == "OPEN_AT_END")
                                            if trade["pnl_pips"] != "":
                                                net += float(trade["pnl_pips"])
                                                net_r += float(trade["realised_R"])
                                        closed = wins + losses
                                        if closed < MIN_CLOSED_TRADES:
                                            continue  # Exclude combinations with fewer than 12 closed trades from summary.
                                        swriter.writerow({
                                            "symbol": symbol, "timeframe": tf_name,
                                            "k": k, "d": d, "smooth": smooth, "upper_bound": upper, "lower_bound": lower,
                                            "atr_period": atr_period, "atr_multiplier": atr_multiplier,
                                            "reward_risk_ratio": reward_risk_ratio,
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
