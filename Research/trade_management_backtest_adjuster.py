"""GBPUSD M15 qualified stochastic configurations: Chandelier/BE management replay.

Does NOT search the original 924,000 parameter combinations. Loads the prior summary,
selects qualifying rows, and replays ONLY those configurations with new exit rules.
A new exit can change the next eligible stochastic entry; thus signals are reconstructed
once per distinct K/D/smooth/bounds setting rather than naively modifying old trade rows.

Dependencies: pandas, numpy; MetaTrader5 only when --source mt5 is selected.
Never sends orders.

Example (use the EXACT original backtest date window and broker history):
 python trade_management_backtest_adjuster.py --summary GBPUSD_M15_summary.csv \
    --source mt5 --start 2026-08-06T00:00:00Z --end 2026-11-06T00:00:00Z \
    --chandelier-periods 10,14,20 --chandelier-multipliers 1.5,2,2.5 \
    --breakeven-triggers off,1.0 --top-n 100

For full eligible grid remove --top-n. For CSV prices provide --m15-csv and --m1-csv,
with time/open/high/low/close columns; time can be UTC ISO strings or Unix seconds.
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from itertools import product
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

CONFIG = ["symbol", "timeframe", "k", "d", "smooth", "upper_bound", "lower_bound",
          "atr_period", "atr_multiplier", "reward_risk_ratio"]
RESULT_FIELDS = CONFIG + ["management", "chandelier_period", "chandelier_multiplier",
                          "breakeven_trigger_R", "closed", "wins", "losses", "scratch",
                          "open_at_end", "win_rate_pct", "net_pips", "net_R", "avg_R",
                          "max_drawdown_R", "baseline_net_R", "delta_net_R", "delta_vs_m1_baseline_R", "baseline_replay_gap_R",
                          "ambiguous_bars", "m1_resolved", "fallback_stop_first",
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
        if not args.m15_csv or not args.m1_csv:
            raise ValueError("CSV mode requires --m15-csv and --m1-csv")
        m15 = prepare_bars(pd.read_csv(args.m15_csv), "M15")
        m1 = prepare_bars(pd.read_csv(args.m1_csv), "M1")
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
            data1 = mt5.copy_rates_range(args.symbol, mt5.TIMEFRAME_M1,
                                        (args.start - pd.Timedelta(minutes=1)).to_pydatetime(),
                                        end.to_pydatetime())
            if data15 is None or not len(data15):
                raise RuntimeError(f"MT5 missing M15 bars: {mt5.last_error()}")
            if data1 is None or not len(data1):
                print("WARNING: MT5 did not supply M1 history; ambiguous bars use SL-first.")
                data1 = pd.DataFrame(columns=["time", "open", "high", "low", "close"])
            m15 = prepare_bars(pd.DataFrame(data15), "M15")
            m1 = (prepare_bars(pd.DataFrame(data1), "M1") if len(data1)
                  else pd.DataFrame(columns=["time", "open", "high", "low", "close"]))
        finally:
            mt5.shutdown()
    m15 = m15.loc[(m15.time >= warmup_start) & (m15.time + pd.Timedelta(minutes=15) <= end)].reset_index(drop=True)
    if m15.empty:
        raise RuntimeError("No closed M15 bars in date window")
    m1 = m1.loc[(m1.time >= args.start) & (m1.time + pd.Timedelta(minutes=1) <= end)].reset_index(drop=True)
    return m15, m1


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
            return "baseline_m1_corrected"
        return "chandelier" + ("_breakeven" if self.be_trigger is not None else "")


def m1_resolve(m1_map: dict, bar_open: pd.Timestamp, direction: int, sl: float,
               tp: float, spread: float):
    """Return (side, execution_price, resolution). Require ALL 15 M1 candles.

    Missing M1 minutes or both barriers inside a single minute => stop first.
    Uses the same BID prices and fixed spread approximation as the original.
    """
    # Checking full 15-minute coverage prevents false certainty with missing earlier minutes.
    samples = [m1_map.get((bar_open + pd.Timedelta(minutes=i)).value) for i in range(15)]
    if any(s is None for s in samples):
        return "SL", sl, "M1_INCOMPLETE_SL_FIRST"
    for op, hi, lo in samples:
        op += spread if direction == -1 else 0
        hi += spread if direction == -1 else 0
        lo += spread if direction == -1 else 0
        if direction == 1:
            if op <= sl: return "SL", op, "M1_GAP_STOP"
            if op >= tp: return "TP", op, "M1_GAP_TARGET"
            stop, target = lo <= sl, hi >= tp
        else:
            if op >= sl: return "SL", op, "M1_GAP_STOP"
            if op <= tp: return "TP", op, "M1_GAP_TARGET"
            stop, target = hi >= sl, lo <= tp
        if stop and target: return "SL", sl, "M1_BOTH_SL_FIRST"
        if stop: return "SL", sl, "M1_STOP_FIRST"
        if target: return "TP", tp, "M1_TARGET_FIRST"
    return "SL", sl, "M1_UNRESOLVED_SL_FIRST"


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


def replay(row, indices, directions, market, ats, chand, m1_map, variant, args, pip):
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
                side, price, resolution = m1_resolve(m1_map, ts[j], direction, sl, tp, spread)
                if resolution.startswith("M1_") and resolution not in (
                    "M1_INCOMPLETE_SL_FIRST", "M1_BOTH_SL_FIRST", "M1_UNRESOLVED_SL_FIRST"):
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
                  ambiguous_bars=ambiguities, m1_resolved=resolved,
                  fallback_stop_first=fallback,
                  entries_replayed=closed + open_end,
                  original_closed=int(row.wins + row.losses))
    return result, trades


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--summary", type=Path, default=Path("GBPUSD_M15_summary.csv"))
    p.add_argument("--trades", type=Path, help="Optional original trades CSV for validation/documentation")
    p.add_argument("--source", choices=["mt5", "csv"], default="mt5")
    p.add_argument("--m15-csv", type=Path)
    p.add_argument("--m1-csv", type=Path)
    p.add_argument("--symbol", default="GBPUSD")
    p.add_argument("--start", required=True, type=parse_utc, help="EXACT original trading-window start, UTC")
    p.add_argument("--end", required=True, type=parse_utc, help="EXACT original trading-window end, UTC")
    p.add_argument("--min-closed", type=int, default=13,
                   help="13 means strictly >12; use 12 to include all previous summary rows")
    p.add_argument("--chandelier-periods", default="10,14,20,30")
    p.add_argument("--chandelier-multipliers", default="1.5,2,2.5,3")
    p.add_argument("--breakeven-triggers", default="off,1.0", help="'off' or R multiples, comma-separated")
    p.add_argument("--top-n", type=int, default=0,
                   help="0: ALL eligible; otherwise largest original Net R first (quick trials only)")
    p.add_argument("--spread-pips", type=float, default=1.5)
    p.add_argument("--pip", type=float, default=0.0001, help="GBPUSD standard pip")
    p.add_argument("--warmup-days", type=int, default=500)
    p.add_argument("--export-trades", action="store_true",
                   help="Produce potentially VERY LARGE per-trade output; off by default")
    p.add_argument("--output", type=Path, default=Path("trade_management_results"))
    args = p.parse_args(argv)
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
    bars, m1 = load_prices(args, warmup, args.end)
    if bars.time.min() > warmup + pd.Timedelta(days=2):
        print("WARNING: limited M15 warmup history; ensure original ATR/stochastic warmup agrees.")
    print(f"Market data: {len(bars):,} M15 and {len(m1):,} M1 bars")
    ats = {x: wilders_atr(bars, x) for x in set(map(int, frame.atr_period)) | set(periods)}
    chand = {per: (bars.high.rolling(per, min_periods=per).max().to_numpy(float),
                   bars.low.rolling(per, min_periods=per).min().to_numpy(float)) for per in periods}
    m1map = {t.value: (float(o), float(h), float(l)) for t, o, h, l in
             zip(m1.time, m1.open, m1.high, m1.low)}
    args.output.mkdir(parents=True, exist_ok=True)
    outpath = args.output / "managed_summary.csv"
    bestpath = args.output / "best_improvements.csv"
    overviewpath = args.output / "management_overview.csv"
    market = (bars.open.to_numpy(float), bars.high.to_numpy(float),
              bars.low.to_numpy(float), bars.close.to_numpy(float), bars.time.tolist())
    variant_stats = defaultdict(lambda: {"tested": 0, "improved": 0, "delta_sum": 0.0, "managed_positive": 0})
    tradepath = args.output / "managed_trades.csv"
    # Group related stochastic setups: compute their signals ONCE, then replay only eligible configs.
    groupcols = ["k", "d", "smooth", "upper_bound", "lower_bound"]
    groupcount = frame.groupby(groupcols, sort=False).ngroups
    with outpath.open("w", newline="", encoding="utf8") as f, bestpath.open("w", newline="", encoding="utf8") as bf:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        bestwriter = csv.DictWriter(bf, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        bestwriter.writeheader()
        tf = tradepath.open("w", newline="", encoding="utf8") if args.export_trades else None
        try:
            twriter = csv.DictWriter(tf, fieldnames=TRADE_FIELDS) if tf else None
            if twriter: twriter.writeheader()
            start_wall = time.monotonic()
            for num, (key, grp) in enumerate(frame.groupby(groupcols, sort=False), start=1):
                k, d, smooth, upper, lower = map(int, key)
                si, sd = candidate_signals(bars, k, d, smooth, upper, lower, args.start, args.end)
                for row in grp.itertuples(index=False):
                    best_result = None
                    for variant in variants:
                        result, trades = replay(row, si, sd, market, ats, chand, m1map, variant, args, args.pip)
                        if variant.period is None:
                            corrected_baseline_R = result["net_R"]
                        result["delta_vs_m1_baseline_R"] = round(result["net_R"] - corrected_baseline_R, 5)
                        result["baseline_replay_gap_R"] = round(corrected_baseline_R - float(row.net_R), 5)
                        writer.writerow(result)
                        if variant.period is not None:
                            signature = (variant.period, variant.multiple, variant.be_trigger)
                            st = variant_stats[signature]
                            st["tested"] += 1
                            st["delta_sum"] += result["delta_vs_m1_baseline_R"]
                            st["improved"] += int(result["delta_vs_m1_baseline_R"] > 0)
                            st["managed_positive"] += int(result["net_R"] > 0)
                            if (result["closed"] >= args.min_closed and result["delta_vs_m1_baseline_R"] > 0
                                and (best_result is None or result["delta_vs_m1_baseline_R"] > best_result["delta_vs_m1_baseline_R"])):
                                best_result = result
                        if twriter: twriter.writerows(trades)
                    if best_result is not None:
                        bestwriter.writerow(best_result)
                if num % 25 == 0 or num == groupcount:
                    f.flush()
                    elapsed = time.monotonic() - start_wall
                    print(f"Stochastic groups {num:,}/{groupcount:,} ({num/groupcount:.1%}); {elapsed:.0f}s elapsed", flush=True)
        finally:
            if tf: tf.close()
    with overviewpath.open("w", newline="", encoding="utf8") as vf:
        vw = csv.writer(vf)
        vw.writerow(["chandelier_period", "chandelier_multiplier", "breakeven_trigger_R",
                     "tested", "improved", "pct_improved", "avg_delta_R", "pct_managed_profitable"])
        for (period, mult, be), st in sorted(variant_stats.items(), key=lambda x: (x[0][0], x[0][1], -1 if x[0][2] is None else x[0][2])):
            count = st["tested"]
            vw.writerow([period, mult, be if be is not None else "off", count,
                         st["improved"], round(100*st["improved"]/count, 2),
                         round(st["delta_sum"]/count, 5),
                         round(100*st["managed_positive"]/count, 2)])
    print(f"Saved {outpath}, {bestpath}, {overviewpath}")
    if args.export_trades: print(f"Saved {tradepath}")
    print("IMPORTANT: Compare baseline_m1_corrected results to original summary before interpreting improvements.")
    print("Management exits change entry eligibility; M1-only refinements also affect the baseline.")
    print("Profitability across many management variants can be overfit: validate on unseen weeks.")


if __name__ == "__main__":
    main()
