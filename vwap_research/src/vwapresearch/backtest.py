"""Minimal, conservative 1-minute backtester for VWAP strategies.

Execution model
---------------
- A signal generated at bar t (using info up to t's close) enters at bar
  t+1 OPEN, adjusted by `slip_entry` points against the trade.
- Stop: fixed price set at entry (points or sigma-based).  Checked on every
  bar via high/low.  If stop and target are both reachable within the same
  bar, the STOP is assumed to fill first (pessimistic).
- Target: either a fixed price, or the DYNAMIC session VWAP (target price
  re-evaluated each bar; filled at the bar's current VWAP value when the
  bar's range crosses it, with `slip_exit` against the trade).
- Optional time stop (exit at close of the k-th bar after entry).
- Forced flat at `eod_minute` NY time (default 16:55 ET session close proxy)
  at bar close.
- One position at a time; signals arriving while in position are dropped.
- `max_trades_day` caps entries per session_day.

Costs: `cost_per_side_pts` is subtracted twice (entry+exit) from each trade
PnL; slippage points are additionally applied inside the fills where stated.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class ExecSpec:
    stop_sigma: Optional[float] = None      # stop distance in sigmas at entry
    stop_pts: Optional[float] = None        # or fixed points
    target: str = "vwap"                    # "vwap" | "l1" | "pts"
    target_pts: Optional[float] = None
    time_stop: Optional[int] = None         # minutes
    eod_minute: int = 1015                  # 16:55 ET
    max_trades_day: int = 100
    cost_per_side_pts: float = 0.0
    slip_entry_pts: float = 0.0
    slip_exit_pts: float = 0.0
    entry_mode: str = "next_open"           # "next_open" | "limit_band"
    # limit_band: resting limit at the signal bar's band price, filled during
    # the signal bar itself (requires the event filter to guarantee an
    # overshoot beyond the limit so the fill is credible); management starts
    # on the signal bar, same-bar stop counted pessimistically.


def run(frame: pd.DataFrame, signals: pd.DataFrame, spec: ExecSpec,
        anchor: str = "sess") -> pd.DataFrame:
    """signals: DataFrame indexed by bar time with columns side (1 long /
    -1 short) and optionally stop_sigma_override.  Returns trades."""
    f = frame
    vw = f[f"vwap_{anchor}"].to_numpy()
    sg = f[f"sigma_{anchor}"].to_numpy()
    op = f["open"].to_numpy(); hi = f["high"].to_numpy()
    lo = f["low"].to_numpy(); cl = f["close"].to_numpy()
    nym = f["ny_minute"].to_numpy()
    sess = pd.factorize(f["session_day"])[0]
    pos_of_time = pd.Series(np.arange(len(f)), index=f.index)

    sig_pos = pos_of_time.reindex(signals.index).dropna().astype(int)
    trades = []
    busy_until = -1
    day_count = {}
    for t_sig, i in sig_pos.items():
        if i + 1 >= len(f) or i <= 0:
            continue
        if i <= busy_until:
            continue
        side = int(signals.loc[t_sig, "side"])
        day = sess[i]
        if day_count.get(day, 0) >= spec.max_trades_day:
            continue
        if spec.entry_mode == "limit_band":
            j = i
            entry = float(signals.loc[t_sig, "limit_px"]) + side * spec.slip_entry_pts
        else:
            j = i + 1
            if sess[j] != day:                  # next bar in another session
                continue
            entry = op[j] + side * spec.slip_entry_pts
        s_sig = sg[i]
        if spec.stop_pts is not None:
            stop_d = spec.stop_pts
        else:
            stop_d = (signals.loc[t_sig, "stop_sigma_override"]
                      if "stop_sigma_override" in signals.columns and
                      not np.isnan(signals.loc[t_sig].get("stop_sigma_override", np.nan))
                      else spec.stop_sigma) * s_sig
        stop_px = entry - side * stop_d
        fixed_tp = None
        if spec.target == "pts":
            fixed_tp = entry + side * spec.target_pts
        elif spec.target == "l1":
            pass                                # dynamic band, below
        exit_px = None; exit_i = None; reason = None
        mae = 0.0; mfe = 0.0
        k = j
        while k < len(f) and sess[k] == day:
            # track excursions vs entry
            mae = max(mae, side * (entry - (lo[k] if side == 1 else hi[k])) * 1.0) \
                if side == 1 else max(mae, (hi[k] - entry))
            mfe = max(mfe, (hi[k] - entry) if side == 1 else (entry - lo[k]))
            # stop first (pessimistic)
            if side == 1 and lo[k] <= stop_px:
                exit_px = min(stop_px, op[k]) - spec.slip_exit_pts
                exit_i = k; reason = "stop"; break
            if side == -1 and hi[k] >= stop_px:
                exit_px = max(stop_px, op[k]) + spec.slip_exit_pts
                exit_i = k; reason = "stop"; break
            # dynamic targets
            if spec.target == "vwap":
                tp = vw[k]
            elif spec.target == "l1":
                # L1 band on the entry side: short exits at vwap+1σ, long at vwap-1σ
                tp = vw[k] - side * sg[k]
            else:
                tp = fixed_tp
            hit_tp = (hi[k] >= tp) if side == 1 else (lo[k] <= tp)
            if hit_tp:
                base = max(tp, op[k]) if side == 1 else min(tp, op[k])
                exit_px = base - side * spec.slip_exit_pts
                exit_i = k; reason = "target"; break
            if spec.time_stop is not None and k - j + 1 >= spec.time_stop:
                exit_px = cl[k] - side * spec.slip_exit_pts
                exit_i = k; reason = "time"; break
            if nym[k] >= spec.eod_minute:
                exit_px = cl[k] - side * spec.slip_exit_pts
                exit_i = k; reason = "eod"; break
            k += 1
        if exit_px is None:                     # session ended
            exit_i = k - 1
            exit_px = cl[exit_i] - side * spec.slip_exit_pts
            reason = "sess_end"
        pnl = side * (exit_px - entry) - 2 * spec.cost_per_side_pts
        trades.append({
            "t_signal": t_sig, "t_entry": f.index[j], "t_exit": f.index[exit_i],
            "side": side, "entry": entry, "exit": exit_px, "reason": reason,
            "pnl_pts": pnl, "gross_pts": side * (exit_px - entry),
            "mae": mae, "mfe": mfe, "bars_held": exit_i - j + 1,
            "session_day": f["session_day"].iloc[i], "sigma_entry": s_sig,
        })
        busy_until = exit_i
        day_count[day] = day_count.get(day, 0) + 1
    return pd.DataFrame(trades)
