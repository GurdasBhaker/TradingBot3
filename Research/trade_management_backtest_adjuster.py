"""Configurable-symbol M15 qualified stochastic configurations: Chandelier/BE management replay.

Does NOT search the original 924,000 parameter combinations. Loads the prior summary,
selects qualifying rows, and replays ONLY those configurations with new exit rules.
A new exit can change the next eligible stochastic entry; thus signals are reconstructed
once per distinct K/D/smooth/bounds setting rather than naively modifying old trade rows.

Dependencies: pandas, numpy; MetaTrader5 only when --source mt5 is selected.
Never sends orders.

Example (dates optional: defaults to the most recent rolling three months):
 python trade_management_backtest_adjuster.py --symbol GBPUSD --top-n 100

For full eligible grid remove --top-n. For CSV prices provide --m15-csv and --m5-csv,
with time/open/high/low/close columns; time can be UTC ISO strings or Unix seconds.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from itertools import product
from pathlib import Path
import time

import numpy as np
import pandas as pd

DEFAULT_SYMBOL = "GBPUSD"  # Change this to EURUSD, GBPJPY, etc. for PyCharm runs.

CONFIG = ["symbol", "timeframe", "k", "d", "smooth", "upper_bound", "lower_bound",
          "atr_period", "atr_multiplier", "reward_risk_ratio"]
RESULT_FIELDS = CONFIG + ["management", "chandelier_period", "chandelier_multiplier",
                          "breakeven_trigger_R", "closed", "wins", "losses", "scratch",
                          "open_at_end", "win_rate_pct", "net_pips", "net_R", "avg_R",
                          "max_drawdown_R", "baseline_net_R", "delta_net_R", "delta_vs_m5_baseline_R", "baseline_replay_gap_R",
                          "ambiguous_bars", "m5_resolved", "fallback_stop_first",
                          "entries_replayed", "original_closed"]
TRADE_FIELDS = CONFIG + ["management", "chandelier_period", "chandelier_multiplier",
                         "breakeven_trigger_R", "entry_time_utc", "exit_time_utc", "direction",
                         "entry_price", "initial_sl", "initial_tp", "final_sl", "exit_price",
                         "exit_reason", "pnl_pips", "realised_R", "ambiguity_resolution"]


def parse_utc(value: str) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def parse_grid(raw: str, cast=float):
    return [cast(v.strip()) for v in raw.split(",") if v.strip()]


def prepare_bars(df: pd.DataFrame, label: str) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).lower().strip() for c in df.columns]
    for c in ("time", "open", "high", "low", "close"):
        if c not in df.columns:
            raise ValueError(f"{label} missing required column {c}")
    if pd.api.types.is_numeric_dtype(df["time"]):
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    else:
        df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.sort_values("time").drop_duplicates("time", keep="last").reset_index(drop=True)
    for c in ("open", "high", "low", "close"):
        df[c] = pd.to_numeric(df[c], errors="raise")
    if df.empty:
        raise ValueError(f"{label} has no bars")
    if df[["open", "high", "low", "close"]].isna().any().any():
        raise ValueError(f"{label} contains missing OHLC prices")
    return df


def load_prices(args, warmup_start: pd.Timestamp, end: pd.Timestamp):
    if args.source == "csv":
        if not args.m15_csv or not args.m5_csv:
            raise ValueError("CSV mode requires --m15-csv and --m5-csv")
        m15 = prepare_bars(pd.read_csv(args.m15_csv), "M15")
        m5 = prepare_bars(pd.read_csv(args.m5_csv), "M5")
    else:
        try:
            import MetaTrader5 as mt5
        except ImportError as ex:
            raise RuntimeError("Install MetaTrader5 or choose --source csv") from ex
        if not mt5.initialize():
            raise RuntimeError(f"MT5 connection failed: {mt5.last_error()}")
        try:
            if not mt5.symbol_select(args.symbol, True):
                raise RuntimeError(f"MT5 symbol selection failed: {args.symbol}")
            data15 = mt5.copy_rates_range(args.symbol, mt5.TIMEFRAME_M15,
                                         warmup_start.to_pydatetime(), end.to_pydatetime())
            data5 = mt5.copy_rates_range(args.symbol, mt5.TIMEFRAME_M5,
                                        (args.start - pd.Timedelta(minutes=5)).to_pydatetime(),
                                        end.to_pydatetime())
            if data15 is None or not len(data15):
                raise RuntimeError(f"MT5 missing M15 bars: {mt5.last_error()}")
            m15 = prepare_bars(pd.DataFrame(data15), "M15")
            if data5 is None or len(data5) == 0:
                print("WARNING: MT5 did not supply M5 history; ambiguous bars use SL-first.")
                # Keep a timezone-aware datetime column, including when empty.
                # An object-typed empty time column raises TypeError during date filtering.
                m5 = pd.DataFrame({
                    "time": pd.DatetimeIndex([], tz="UTC"),
                    "open": pd.Series(dtype="float64"),
                    "high": pd.Series(dtype="float64"),
                    "low": pd.Series(dtype="float64"),
                    "close": pd.Series(dtype="float64"),
                })
            else:
                m5 = prepare_bars(pd.DataFrame(data5), "M5")
        finally:
            mt5.shutdown()
    m15 = m15.loc[(m15.time >= warmup_start) & (m15.time + pd.Timedelta(minutes=15) <= end)].reset_index(drop=True)
    if m15.empty:
        raise RuntimeError("No closed M15 bars in date window")
    if not m5.empty:
        m5 = m5.loc[(m5.time >= args.start) &
                    (m5.time + pd.Timedelta(minutes=5) <= end)].reset_index(drop=True)
    return m15, m5


def wilders_atr(bars: pd.DataFrame, period: int) -> np.ndarray:
    h, l, c = (bars[x].to_numpy(float) for x in ("high", "low", "close"))
    tr = np.maximum(h - l, np.maximum(np.abs(h - np.r_[c[0], c[:-1]]),
                                       np.abs(l - np.r_[c[0], c[:-1]])))
    atr = np.full(len(tr), np.nan)
    if len(tr) >= period:
        atr[period - 1] = np.mean(tr[:period])
        for i in range(period, len(tr)):
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


def candidate_signals(bars, k: int, d: int, smooth: int, upper: int, lower: int,
                      first: pd.Timestamp, end: pd.Timestamp):
    lows = bars.low.rolling(k, min_periods=k).min()
    highs = bars.high.rolling(k, min_periods=k).max()
    raw_k = 100 * (bars.close - lows) / (highs - lows).replace(0, np.nan)
    kval = raw_k.rolling(smooth, min_periods=smooth).mean().to_numpy(float)
    dval = pd.Series(kval).rolling(d, min_periods=d).mean().to_numpy(float)
    crosses_up = (kval[1:-1] > dval[1:-1]) & (kval[:-2] <= dval[:-2]) & (kval[:-2] <= lower)
    crosses_down = (kval[1:-1] < dval[1:-1]) & (kval[:-2] >= dval[:-2]) & (kval[:-2] >= upper)
    sig = crosses_up.astype(np.int8) - crosses_down.astype(np.int8)
    valid = ((bars.time.iloc[2:] >= first) & (bars.time.iloc[2:] < end)).to_numpy()
    chosen = np.flatnonzero((sig != 0) & valid)
    return chosen + 1, sig[chosen]


@dataclass(frozen=True)
class Variant:
    period: int | None
    multiple: float | None
    be_trigger: float | None

    @property
    def name(self):
        if self.period is None:
            return "baseline_m5_corrected"
        return "chandelier" + ("_breakeven" if self.be_trigger is not None else "")


def m5_resolve(m5_map: dict, bar_open: pd.Timestamp, direction: int, sl: float,
               tp: float, spread: float):
    """Return (side, execution_price, resolution). Require ALL 3 M5 candles.

    Missing M5 bars or both barriers inside one 5-minute candle => stop first.
    Uses the same BID prices and fixed spread approximation as the original.
    """
    # Require three consecutive 5-minute candles to avoid false ordering certainty when data is missing.
    samples = [m5_map.get((bar_open + pd.Timedelta(minutes=5*i)).value) for i in range(3)]
    if any(s is None for s in samples):
        return "SL", sl, "M5_INCOMPLETE_SL_FIRST"
    for op, hi, lo in samples:
        op += spread if direction == -1 else 0
        hi += spread if direction == -1 else 0
        lo += spread if direction == -1 else 0
        if direction == 1:
            if op <= sl: return "SL", op, "M5_GAP_STOP"
            if op >= tp: return "TP", op, "M5_GAP_TARGET"
            stop, target = lo <= sl, hi >= tp
        else:
            if op >= sl: return "SL", op, "M5_GAP_STOP"
            if op <= tp: return "TP", op, "M5_GAP_TARGET"
            stop, target = hi >= sl, lo <= tp
        if stop and target: return "SL", sl, "M5_BOTH_SL_FIRST"
        if stop: return "SL", sl, "M5_STOP_FIRST"
        if target: return "TP", tp, "M5_TARGET_FIRST"
    return "SL", sl, "M5_UNRESOLVED_SL_FIRST"


def hit_exit(direction, op, hi, lo, sl, tp, spread):
    """M15 OHLC barrier check; short exits are ASK (BID+spread)."""
    if direction == -1:
        op, hi, lo = op + spread, hi + spread, lo + spread
    if direction == 1:
        if op <= sl: return "SL", op, False
        if op >= tp: return "TP", op, False
        stop, target = lo <= sl, hi >= tp
    else:
        if op >= sl: return "SL", op, False
        if op <= tp: return "TP", op, False
        stop, target = hi >= sl, lo <= tp
    if stop and target: return "SL", sl, True
    if stop: return "SL", sl, False
    if target: return "TP", tp, False
    return None, None, False


def replay(row, indices, directions, market, ats, chand, m5_map, variant, args, pip):
    """Replay original signals for ONE already-qualified parameter set and variant."""
    o, hi, lo, cl, ts = market
    n = len(ts)
    spread = args.spread_pips * pip
    atr = ats[int(row.atr_period)]
    chand_atr = ats[variant.period] if variant.period is not None else None
    # chandelier HH/LL use previous COMPLETED candle only, never the current bar.
    ch_high, ch_low = chand.get(variant.period, (None, None))
    next_entry = 0
    wins = losses = scratch = open_end = ambiguities = resolved = fallback = 0
    pnl_total = r_total = peak = drawdown = 0.0
    trades = []
    for sidx, dvec in zip(indices, directions):
        entidx = int(sidx) + 1
        if entidx < next_entry:
            continue
        direction = int(dvec)
        signal_atr = atr[int(sidx)]
        if not np.isfinite(signal_atr) or signal_atr <= 0:
            continue
        initial_dist = float(signal_atr) * float(row.atr_multiplier)
        entry = o[entidx] + (spread if direction == 1 else 0)
        sl = entry - direction * initial_dist
        tp = entry + direction * initial_dist * float(row.reward_risk_ratio)
        initial_sl = sl
        exit_idx = n - 1
        exit_price = np.nan
        reason = "OPEN_AT_END"
        resolution = ""
        for j in range(entidx, n):
            # Trail based on data available BEFORE bar j. Never widen the stop.
            if variant.period is not None and j > entidx:
                previous = j - 1
                a = chand_atr[previous]
                hh, ll = ch_high[previous], ch_low[previous]
                if np.isfinite(a) and np.isfinite(hh) and np.isfinite(ll):
                    proposed = (hh - variant.multiple * a if direction == 1
                                else ll + variant.multiple * a)
                    sl = max(sl, proposed) if direction == 1 else min(sl, proposed)
            if variant.be_trigger is not None and j > entidx:
                # Break even triggered only by previous COMPLETED candle close.
                previous_close_at_exit_side = cl[j - 1] + (spread if direction == -1 else 0)
                favorable = direction * (previous_close_at_exit_side - entry)
                if favorable >= variant.be_trigger * initial_dist:
                    sl = max(sl, entry) if direction == 1 else min(sl, entry)
            side, price, both = hit_exit(direction, o[j], hi[j], lo[j], sl, tp, spread)
            if both:
                ambiguities += 1
                side, price, resolution = m5_resolve(m5_map, ts[j], direction, sl, tp, spread)
                if resolution.startswith("M5_") and resolution not in (
                    "M5_INCOMPLETE_SL_FIRST", "M5_BOTH_SL_FIRST", "M5_UNRESOLVED_SL_FIRST"):
                    resolved += 1
                else:
                    fallback += 1
            if side:
                exit_idx, reason, exit_price = j, side, price
                # Chandelier / BE stop can be above/below entry => stop exit can be profitable.
                if side == "SL" and variant.period is not None:
                    reason = "MANAGED_STOP"
                break
        next_entry = exit_idx + 2  # source skips signals on the exit candle itself
        if reason == "OPEN_AT_END":
            open_end += 1
            pnl = np.nan
            rr = np.nan
        else:
            pnl = direction * (exit_price - entry) / pip
            rr = direction * (exit_price - entry) / initial_dist
            pnl_total += pnl
            r_total += rr
            peak = max(peak, r_total)
            drawdown = max(drawdown, peak - r_total)
            if rr > 1e-8: wins += 1
            elif rr < -1e-8: losses += 1
            else: scratch += 1
        if args.export_trades:
            out = {k: getattr(row, k) for k in CONFIG}
            out.update(management=variant.name, chandelier_period=variant.period or "",
                       chandelier_multiplier=variant.multiple if variant.multiple is not None else "",
                       breakeven_trigger_R=variant.be_trigger if variant.be_trigger is not None else "",
                       entry_time_utc=ts[entidx].isoformat(),
                       exit_time_utc=ts[exit_idx].isoformat() if reason != "OPEN_AT_END" else "",
                       direction=direction, entry_price=round(entry, 8),
                       initial_sl=round(initial_sl, 8), initial_tp=round(tp, 8),
                       final_sl=round(sl, 8),
                       exit_price=round(float(exit_price), 8) if np.isfinite(exit_price) else "",
                       exit_reason=reason, pnl_pips=round(float(pnl), 5) if np.isfinite(pnl) else "",
                       realised_R=round(float(rr), 6) if np.isfinite(rr) else "",
                       ambiguity_resolution=resolution)
            trades.append(out)
    closed = wins + losses + scratch
    result = {k: getattr(row, k) for k in CONFIG}
    result.update(management=variant.name,
                  chandelier_period=variant.period or "",
                  chandelier_multiplier=variant.multiple if variant.multiple is not None else "",
                  breakeven_trigger_R=variant.be_trigger if variant.be_trigger is not None else "",
                  closed=closed, wins=wins, losses=losses, scratch=scratch,
                  open_at_end=open_end,
                  win_rate_pct=round(100 * wins / closed, 2) if closed else "",
                  net_pips=round(pnl_total, 5), net_R=round(r_total, 5),
                  avg_R=round(r_total / closed, 5) if closed else "",
                  max_drawdown_R=round(drawdown, 5),
                  baseline_net_R=float(row.net_R),
                  delta_net_R=round(r_total - float(row.net_R), 5),
                  ambiguous_bars=ambiguities, m5_resolved=resolved,
                  fallback_stop_first=fallback,
                  entries_replayed=closed + open_end,
                  original_closed=int(row.wins + row.losses))
    return result, trades



# Optional JIT acceleration: score all 33 management variants in one compiled call.
# The existing Python replay remains the reference implementation and is used to
# materialise the selected trades (and as a fallback without Numba).
try:
    from numba import njit
except ImportError:
    njit = None

if njit is not None:
    @njit(cache=True)
    def _score_variants_numba(indices, directions, opens, highs, lows, closes,
                              atr_entry, ch_atrs, ch_highs, ch_lows,
                              var_period_index, var_multiple, var_be,
                              entry_multiple, reward_risk, spread, pip,
                              m5_op, m5_hi, m5_lo, m5_present):
        # Columns: closed, wins, losses, scratch, open, net_pips, net_R,
        # max_drawdown_R, ambiguities, resolved, fallbacks, entries.
        scores = np.zeros((len(var_multiple), 12), dtype=np.float64)
        n = len(opens)
        for v in range(len(var_multiple)):
            ci = var_period_index[v]
            next_entry = 0
            total_r = 0.0
            peak = 0.0
            for si in range(len(indices)):
                sidx = int(indices[si])
                entidx = sidx + 1
                if entidx < next_entry:
                    continue
                direction = int(directions[si])
                signal_atr = atr_entry[sidx]
                if not np.isfinite(signal_atr) or signal_atr <= 0.0:
                    continue
                initial_dist = signal_atr * entry_multiple
                entry = opens[entidx] + (spread if direction == 1 else 0.0)
                sl = entry - direction * initial_dist
                tp = entry + direction * initial_dist * reward_risk
                exit_idx = n - 1
                exit_price = np.nan
                exited = False
                for j in range(entidx, n):
                    if ci >= 0 and j > entidx:
                        prev = j - 1
                        a = ch_atrs[ci, prev]
                        hh = ch_highs[ci, prev]
                        ll = ch_lows[ci, prev]
                        if np.isfinite(a) and np.isfinite(hh) and np.isfinite(ll):
                            proposed = (hh - var_multiple[v] * a if direction == 1
                                        else ll + var_multiple[v] * a)
                            if direction == 1:
                                sl = max(sl, proposed)
                            else:
                                sl = min(sl, proposed)
                    if not np.isnan(var_be[v]) and j > entidx:
                        prior_exit_close = closes[j - 1] + (spread if direction == -1 else 0.0)
                        favorable = direction * (prior_exit_close - entry)
                        if favorable >= var_be[v] * initial_dist:
                            if direction == 1:
                                sl = max(sl, entry)
                            else:
                                sl = min(sl, entry)
                    op = opens[j] + (spread if direction == -1 else 0.0)
                    hi = highs[j] + (spread if direction == -1 else 0.0)
                    lo = lows[j] + (spread if direction == -1 else 0.0)
                    if direction == 1:
                        if op <= sl:
                            exit_price = op
                            exited = True
                        elif op >= tp:
                            exit_price = op
                            exited = True
                        else:
                            stop = lo <= sl
                            target = hi >= tp
                            if stop or target:
                                exited = True
                                exit_price = sl if stop else tp
                    else:
                        if op >= sl:
                            exit_price = op
                            exited = True
                        elif op <= tp:
                            exit_price = op
                            exited = True
                        else:
                            stop = hi >= sl
                            target = lo <= tp
                            if stop or target:
                                exited = True
                                exit_price = sl if stop else tp
                    if exited:
                        # Only OHLC-internal double touches require M5 resolution.
                        if not ((direction == 1 and op <= sl) or (direction == 1 and op >= tp) or
                                (direction == -1 and op >= sl) or (direction == -1 and op <= tp)):
                            if direction == 1:
                                both = lo <= sl and hi >= tp
                            else:
                                both = hi >= sl and lo <= tp
                            if both:
                                scores[v, 8] += 1.0
                                # All three candles are required even if the first gives an answer.
                                if not (m5_present[j, 0] and m5_present[j, 1] and m5_present[j, 2]):
                                    scores[v, 10] += 1.0
                                    exit_price = sl
                                else:
                                    resolution = 0  # 0 fallback; 1 confirmed M5 first touch
                                    exit_price = sl
                                    for m in range(3):
                                        mop = m5_op[j, m] + (spread if direction == -1 else 0.0)
                                        mhi = m5_hi[j, m] + (spread if direction == -1 else 0.0)
                                        mlo = m5_lo[j, m] + (spread if direction == -1 else 0.0)
                                        if direction == 1:
                                            if mop <= sl:
                                                exit_price = mop
                                                resolution = 1
                                                break
                                            if mop >= tp:
                                                exit_price = mop
                                                resolution = 1
                                                break
                                            ms = mlo <= sl
                                            mt = mhi >= tp
                                        else:
                                            if mop >= sl:
                                                exit_price = mop
                                                resolution = 1
                                                break
                                            if mop <= tp:
                                                exit_price = mop
                                                resolution = 1
                                                break
                                            ms = mhi >= sl
                                            mt = mlo <= tp
                                        if ms and mt:
                                            exit_price = sl
                                            break
                                        if ms:
                                            exit_price = sl
                                            resolution = 1
                                            break
                                        if mt:
                                            exit_price = tp
                                            resolution = 1
                                            break
                                    if resolution == 1:
                                        scores[v, 9] += 1.0
                                    else:
                                        scores[v, 10] += 1.0
                        exit_idx = j
                        break
                next_entry = exit_idx + 2
                scores[v, 11] += 1.0
                if not exited:
                    scores[v, 4] += 1.0
                    continue
                r = direction * (exit_price - entry) / initial_dist
                pnl = direction * (exit_price - entry) / pip
                scores[v, 0] += 1.0
                scores[v, 5] += pnl
                scores[v, 6] += r
                total_r += r
                if r > 1e-8:
                    scores[v, 1] += 1.0
                elif r < -1e-8:
                    scores[v, 2] += 1.0
                else:
                    scores[v, 3] += 1.0
                peak = max(peak, total_r)
                scores[v, 7] = max(scores[v, 7], peak - total_r)
        return scores


def build_accelerator_inputs(bars, m5_map, variants, atrs, chand):
    """Build contiguous arrays ONCE; do not allocate M5 objects for each replay."""
    arrays = tuple(np.ascontiguousarray(bars[x].to_numpy(dtype=np.float64))
                   for x in ("open", "high", "low", "close"))
    size = len(bars)
    m5_op = np.zeros((size, 3), dtype=np.float64)
    m5_hi = np.zeros((size, 3), dtype=np.float64)
    m5_lo = np.zeros((size, 3), dtype=np.float64)
    m5_present = np.zeros((size, 3), dtype=np.bool_)
    step = pd.Timedelta(minutes=5).value
    for i, ts in enumerate(bars.time):
        base = ts.value
        for m in range(3):
            candle = m5_map.get(base + step*m)
            if candle is not None:
                m5_op[i, m], m5_hi[i, m], m5_lo[i, m] = candle
                m5_present[i, m] = True
    chand_periods = sorted(chand)
    ch_idx = {p:i for i,p in enumerate(chand_periods)}
    n = len(bars)
    ch_atrs = np.ascontiguousarray(np.stack([atrs[p] for p in chand_periods]))
    ch_highs = np.ascontiguousarray(np.stack([chand[p][0] for p in chand_periods]))
    ch_lows = np.ascontiguousarray(np.stack([chand[p][1] for p in chand_periods]))
    indices = np.array([ch_idx[v.period] if v.period is not None else -1 for v in variants], dtype=np.int64)
    multiple = np.array([v.multiple if v.multiple is not None else 0.0 for v in variants], dtype=np.float64)
    be = np.array([v.be_trigger if v.be_trigger is not None else np.nan for v in variants], dtype=np.float64)
    return arrays, (ch_atrs, ch_highs, ch_lows), (indices, multiple, be), (m5_op, m5_hi, m5_lo, m5_present)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--summary", type=Path, default=None,
                   help="Summary CSV (default: backtest_results/{SYMBOL}_M15_summary.csv next to script)")
    p.add_argument("--trades", type=Path, help="Optional original trades CSV for validation/documentation")
    p.add_argument("--source", choices=["mt5", "csv"], default="mt5")
    p.add_argument("--m15-csv", type=Path)
    p.add_argument("--m5-csv", type=Path)
    p.add_argument("--symbol", default=DEFAULT_SYMBOL, help="MT5 symbol, e.g. GBPUSD or EURUSD")
    p.add_argument("--start", type=parse_utc, help="Original trading-window start UTC (default: 3 calendar months before --end)")
    p.add_argument("--end", type=parse_utc, help="Original trading-window end UTC (default: current UTC time)")
    p.add_argument("--min-closed", type=int, default=13,
                   help="13 means strictly >12; use 12 to include all previous summary rows")
    p.add_argument("--chandelier-periods", default="10,14,20,30")
    p.add_argument("--chandelier-multipliers", default="1.5,2,2.5,3")
    p.add_argument("--breakeven-triggers", default="off,1.0", help="'off' or R multiples, comma-separated")
    p.add_argument("--no-accelerate", action="store_true", help="Use original Python replay instead of Numba compiled scoring")
    p.add_argument("--top-n", type=int, default=0,
                   help="0: ALL eligible; otherwise largest original Net R first (quick trials only)")
    p.add_argument("--spread-pips", type=float, default=1.5)
    p.add_argument("--pip", type=float, default=None, help="Pip size; defaults to MT5 symbol digits or 0.01 for JPY pairs / 0.0001 for other FX pairs in CSV mode")
    p.add_argument("--warmup-days", type=int, default=500)

    p.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "trade_management_results")
    args = p.parse_args(argv)
    args.symbol = args.symbol.strip().upper()
    if not args.symbol or not args.symbol.replace(".", "").replace("_", "").isalnum():
        p.error("--symbol must be a nonempty currency/instrument symbol")
    if args.summary is None:
        args.summary = Path(__file__).resolve().parent / "backtest_results" / f"{args.symbol}_M15_summary.csv"
    if args.pip is None:
        if args.source == "mt5":
            try:
                import MetaTrader5 as mt5
                if not mt5.initialize():
                    raise RuntimeError(f"MT5 connection failed while detecting pip size: {mt5.last_error()}")
                try:
                    info = mt5.symbol_info(args.symbol)
                    if info is None:
                        raise ValueError(f"Symbol not found in MT5: {args.symbol}; pass --pip explicitly")
                    args.pip = float(info.point) * (10 if info.digits in (3, 5) else 1)
                finally:
                    mt5.shutdown()
            except ImportError as ex:
                raise RuntimeError("Install MetaTrader5 or use --source csv with --pip") from ex
        else:
            args.pip = 0.01 if "JPY" in args.symbol else 0.0001
            print(f"CSV mode inferred pip size {args.pip} for {args.symbol}; pass --pip to override.")
    # Always export trades for each SELECTED management variant only.
    args.export_trades = True
    if args.start is None or args.end is None:
        # Matches the original stochastic backtest's rolling three-calendar-month window.
        # For exact comparison, supply BOTH timestamps from the original backtest log.
        args.end = args.end if args.end is not None else pd.Timestamp.now(tz="UTC")
        args.start = args.start if args.start is not None else args.end - pd.DateOffset(months=3)
        print("NOTE: Using an inferred rolling window, which may differ from the original run.")
        print("      For a like-for-like comparison, pass the original --start and --end timestamps.")
    print(f"Trading window (UTC): {args.start.isoformat()} to {args.end.isoformat()}")
    if args.start >= args.end:
        p.error("--start must be before --end")
    if args.spread_pips < 0 or args.pip <= 0:
        p.error("pip must be >0 and spread must be >=0")
    periods = parse_grid(args.chandelier_periods, int)
    multiples = parse_grid(args.chandelier_multipliers, float)
    breaks = [None if x.strip().lower() == "off" else float(x) for x in args.breakeven_triggers.split(",")]
    if not periods or not multiples or any(x < 1 for x in periods) or any(x <= 0 for x in multiples) or any(x is not None and x <= 0 for x in breaks):
        p.error("Chandelier periods/multipliers and break-even trigger must be positive")
    variants = [Variant(None, None, None)] + [Variant(per, mul, be) for per, mul, be in product(periods, multiples, breaks)]
    if not args.summary.is_file():
        raise FileNotFoundError(
            f"Summary CSV not found: {args.summary}\n"
            f"Place {args.symbol}_M15_summary.csv in the backtest_results folder next to this script, "
            "or pass --summary with its full path."
        )
    print(f"Reading summary: {args.summary.resolve()}")
    frame = pd.read_csv(args.summary)
    missing = set(CONFIG + ["wins", "losses", "net_R"]) - set(frame.columns)
    if missing:
        raise ValueError(f"Summary missing columns: {sorted(missing)}")
    frame = frame.loc[(frame.symbol == args.symbol) & (frame.timeframe == "M15") &
                      ((frame.wins + frame.losses) >= args.min_closed)].copy()
    if args.top_n:
        frame = frame.nlargest(args.top_n, "net_R")
    if frame.empty:
        raise ValueError("No qualifying configurations")
    print(f"Qualified configurations: {len(frame):,}; management variants incl baseline: {len(variants)}; replay cases: {len(frame)*len(variants):,}")
    if args.trades is not None:
        if not args.trades.exists():
            raise FileNotFoundError(args.trades)
        print(f"Original trades file available: {args.trades} (not used as a fixed entry schedule)")
    warmup = args.start - pd.Timedelta(days=args.warmup_days)
    bars, m5 = load_prices(args, warmup, args.end)
    if bars.time.min() > warmup + pd.Timedelta(days=2):
        print("WARNING: limited M15 warmup history; ensure original ATR/stochastic warmup agrees.")
    print(f"Market data: {len(bars):,} M15 and {len(m5):,} M5 bars")
    ats = {x: wilders_atr(bars, x) for x in set(map(int, frame.atr_period)) | set(periods)}
    chand = {per: (bars.high.rolling(per, min_periods=per).max().to_numpy(float),
                   bars.low.rolling(per, min_periods=per).min().to_numpy(float)) for per in periods}
    m5map = {t.value: (float(o), float(h), float(l)) for t, o, h, l in
             zip(m5.time, m5.open, m5.high, m5.low)}
    args.output.mkdir(parents=True, exist_ok=True)
    # Never overwrite an earlier run. Every CSV gets the same UTC run suffix.
    # A per-run directory is reserved atomically, so even concurrent launches
    # cannot collide with an existing run or leave results in old file names.
    while True:
        run_suffix = "adj_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%fZ")
        run_dir = args.output / run_suffix
        try:
            run_dir.mkdir(parents=True, exist_ok=False)
            break
        except FileExistsError:
            continue
    # Exactly two outputs, with the currency pair as a prefix, and unique adj timestamp.
    outpath = run_dir / f"{args.symbol}_M15_summary_{run_suffix}.csv"
    tradepath = run_dir / f"{args.symbol}_M15_trades_{run_suffix}.csv"
    print(f"Output folder: {run_dir}")
    market = (bars.open.to_numpy(float), bars.high.to_numpy(float),
              bars.low.to_numpy(float), bars.close.to_numpy(float), bars.time.tolist())
    accelerated = njit is not None and not args.no_accelerate
    if accelerated:
        fast_market, fast_chand, fast_variants, fast_m5 = build_accelerator_inputs(
            bars, m5map, variants, ats, chand)
        print("Fast path enabled: Numba compiled variant scoring; trade details replayed once for the winner.")
    else:
        print("Fast path disabled (Numba not installed or --no-accelerate). Install with: pip install numba")
    groupcols = ["k", "d", "smooth", "upper_bound", "lower_bound"]
    groupcount = frame.groupby(groupcols, sort=False).ngroups
    with (outpath.open("x", newline="", encoding="utf8") as f,
          tradepath.open("x", newline="", encoding="utf8") as tf):
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        twriter = csv.DictWriter(tf, fieldnames=TRADE_FIELDS)
        writer.writeheader()
        twriter.writeheader()
        start_wall = time.monotonic()
        for num, (key, grp) in enumerate(frame.groupby(groupcols, sort=False), start=1):
            k, d, smooth, upper, lower = map(int, key)
            si, sd = candidate_signals(bars, k, d, smooth, upper, lower, args.start, args.end)
            si_fast = np.ascontiguousarray(si, dtype=np.int64) if accelerated else None
            sd_fast = np.ascontiguousarray(sd, dtype=np.int8) if accelerated else None
            for row in grp.itertuples(index=False):
                if accelerated:
                    scores = _score_variants_numba(
                        si_fast, sd_fast, *fast_market,
                        np.ascontiguousarray(ats[int(row.atr_period)]),
                        *fast_chand, *fast_variants,
                        float(row.atr_multiplier), float(row.reward_risk_ratio),
                        args.spread_pips * args.pip, args.pip, *fast_m5)
                    base_R = round(float(scores[0, 6]), 5)
                    best_i = 0
                    best_R = base_R
                    for i in range(1, len(variants)):
                        candidate_R = round(float(scores[i, 6]), 5)
                        if (scores[i, 0] >= args.min_closed and
                                candidate_R - base_R > 0 and candidate_R > best_R):
                            best_i, best_R = i, candidate_R
                    # Replay only the selected variant to export trade-level records.
                    selected_result, selected_trades = replay(
                        row, si, sd, market, ats, chand, m5map,
                        variants[best_i], args, args.pip)
                    selected_result["delta_vs_m5_baseline_R"] = round(selected_result["net_R"] - base_R, 5)
                    selected_result["baseline_replay_gap_R"] = round(base_R - float(row.net_R), 5)
                else:
                    selected_result = None
                    selected_trades = []
                    corrected_baseline_R = None
                    for variant in variants:
                        # No trade dictionaries for the 32 discarded variants.
                        args.export_trades = False
                        result, _ = replay(row, si, sd, market, ats, chand,
                                           m5map, variant, args, args.pip)
                        if variant.period is None:
                            corrected_baseline_R = result["net_R"]
                            selected_result = result
                            best_variant = variant
                        result["delta_vs_m5_baseline_R"] = round(result["net_R"] - corrected_baseline_R, 5)
                        result["baseline_replay_gap_R"] = round(corrected_baseline_R - float(row.net_R), 5)
                        if (variant.period is not None and result["closed"] >= args.min_closed
                                and result["delta_vs_m5_baseline_R"] > 0
                                and result["net_R"] > selected_result["net_R"]):
                            selected_result = result
                            best_variant = variant
                    args.export_trades = True
                    _, selected_trades = replay(row, si, sd, market, ats, chand,
                                                m5map, best_variant, args, args.pip)
                writer.writerow(selected_result)
                twriter.writerows(selected_trades)
            if num % 25 == 0 or num == groupcount:
                f.flush()
                tf.flush()
                elapsed = time.monotonic() - start_wall
                print(f"Stochastic groups {num:,}/{groupcount:,} ({num/groupcount:.1%}); {elapsed:.0f}s elapsed", flush=True)
    print(f"Saved summary: {outpath}")
    print(f"Saved trades:  {tradepath}")
    print("IMPORTANT: Compare baseline_m5_corrected results to original summary before interpreting improvements.")
    print("Management exits change entry eligibility; M5-only refinements also affect the baseline.")
    print("Profitability across many management variants can be overfit: validate on unseen weeks.")


if __name__ == "__main__":
    main()
