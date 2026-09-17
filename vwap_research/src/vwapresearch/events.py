"""Band-touch event extraction with forward outcomes.

An UPPER touch at level L happens on the first bar whose high reaches
vwap + L*sigma while the previous bar stayed below (episode logic with a
hysteresis of HYST*sigma: a new touch of the same level requires price to
have pulled back below L-HYST sigmas in between).  Symmetric for LOWER.

Outcomes are measured from the NEXT bar's open (no same-bar action):
- hit_vwap_k / hit_l1_k : did price reach the (dynamic) VWAP / L1 band within
  k minutes, k in HORIZONS
- t_vwap : minutes until first VWAP touch (NaN if none within max horizon)
- mae_k / mfe_k : max adverse/favorable excursion in POINTS within k minutes
  for the mean-reversion direction (short after upper touch, long after lower)
- stop_first_S_vs_vwap : whether a fixed S-point stop would be hit before the
  dynamic VWAP target (conservative: same-bar tie -> stop first)

Conditioning features are recorded at the TOUCH bar (causal).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

HYST = 0.3
HORIZONS = [5, 15, 30, 60, 120, 240]
MAXH = 240
STOPS_SIGMA = [0.5, 1.0, 1.5]        # stop distances in sigmas beyond entry
LEVELS = [1.0, 1.5, 2.0, 2.5, 3.0]


def extract_touches(df: pd.DataFrame, anchor: str = "sess",
                    levels=LEVELS) -> pd.DataFrame:
    """df: feature frame from features.build_frame (one instrument).
    Returns one row per touch event."""
    need = [f"vwap_{anchor}", f"sigma_{anchor}", "open", "high", "low", "close",
            "session_day", "ny_minute", "n_cross", "speed5", "dw", "atr30",
            "vwap_slope_5", "vwap_slope_15", "vwap_slope_30", "vwap_curv",
            "rv30", "dow", "week_id"]
    sub = df[need].copy()
    sub = sub.rename(columns={f"vwap_{anchor}": "vw", f"sigma_{anchor}": "sg"})
    rows = []
    for day, d in sub.groupby("session_day", sort=True):
        vw = d["vw"].to_numpy()
        sg = d["sg"].to_numpy()
        hi = d["high"].to_numpy(); lo = d["low"].to_numpy()
        op = d["open"].to_numpy(); cl = d["close"].to_numpy()
        n = len(d)
        if n < 40:
            continue
        ts = d.index
        nym = d["ny_minute"].to_numpy()
        for side in (1, -1):            # 1 = upper band, -1 = lower band
            for L in levels:
                band = vw + side * L * sg
                inner = vw + side * (L - HYST) * sg
                armed = True
                touch_no = 0
                i = 25                  # need sigma warm-up
                while i < n - 2:
                    if np.isnan(band[i]):
                        i += 1
                        continue
                    hit = hi[i] >= band[i] if side == 1 else lo[i] <= band[i]
                    if armed and hit:
                        touch_no += 1
                        rows.append(_event_row(
                            d, ts, day, side, L, touch_no, i, vw, sg, hi, lo, op, cl, nym))
                        armed = False
                    elif not armed:
                        back = cl[i] < inner[i] if side == 1 else cl[i] > inner[i]
                        if back:
                            armed = True
                    i += 1
    ev = pd.DataFrame(rows)
    return ev


def _event_row(d, ts, day, side, L, touch_no, i, vw, sg, hi, lo, op, cl, nym):
    n = len(d)
    j0 = i + 1                          # action bar (next bar open)
    entry = op[j0] if j0 < n else cl[i]
    jmax = min(n, j0 + MAXH)
    fhi = hi[j0:jmax]; flo = lo[j0:jmax]; fvw = vw[j0:jmax]
    r = {
        "session_day": day, "time": ts[i], "ny_minute": int(nym[i]),
        "side": side, "level": L, "touch_no": touch_no,
        "entry": entry, "vw": vw[i], "sg": sg[i],
        "overshoot": (hi[i] - (vw[i] + L * sg[i])) / sg[i] if side == 1
                     else ((vw[i] - L * sg[i]) - lo[i]) / sg[i],
        "slope5": d["vwap_slope_5"].iloc[i], "slope15": d["vwap_slope_15"].iloc[i],
        "slope30": d["vwap_slope_30"].iloc[i], "curv": d["vwap_curv"].iloc[i],
        "n_cross": d["n_cross"].iloc[i], "speed5": d["speed5"].iloc[i],
        "dw": d["dw"].iloc[i], "atr30": d["atr30"].iloc[i], "rv30": d["rv30"].iloc[i],
        "dow": d["dow"].iloc[i], "week_id": d["week_id"].iloc[i],
        "close_m": (cl[i] - vw[i]) / sg[i] if sg[i] > 0 else np.nan,
        "sg_pts": sg[i],
    }
    if len(fhi) == 0:
        for k in HORIZONS:
            r[f"hit_vwap_{k}"] = np.nan
            r[f"mae_{k}"] = np.nan
            r[f"mfe_{k}"] = np.nan
        r["t_vwap"] = np.nan
        return r
    # dynamic VWAP hit: short (upper): flo <= fvw ; long (lower): fhi >= fvw
    if side == 1:
        vwap_hit = flo <= fvw
        mae_path = np.maximum.accumulate(fhi) - entry          # adverse for short
        mfe_path = entry - np.minimum.accumulate(flo)
    else:
        vwap_hit = fhi >= fvw
        mae_path = entry - np.minimum.accumulate(flo)
        mfe_path = np.maximum.accumulate(fhi) - entry
    idx_hit = np.flatnonzero(vwap_hit)
    t_vwap = idx_hit[0] + 1 if len(idx_hit) else np.nan
    r["t_vwap"] = t_vwap
    for k in HORIZONS:
        kk = min(k, len(fhi)) - 1
        r[f"hit_vwap_{k}"] = bool(len(idx_hit) and idx_hit[0] <= k - 1)
        r[f"mae_{k}"] = mae_path[kk]
        r[f"mfe_{k}"] = mfe_path[kk]
    # stop-vs-vwap outcomes for sigma-based stops (conservative tie->stop)
    for S in STOPS_SIGMA:
        stop_px = entry + S * r["sg"] if side == 1 else entry - S * r["sg"]
        if side == 1:
            stop_hit = fhi >= stop_px
        else:
            stop_hit = flo <= stop_px
        i_stop = np.flatnonzero(stop_hit)
        i_tp = idx_hit
        s = i_stop[0] if len(i_stop) else 10**9
        t = i_tp[0] if len(i_tp) else 10**9
        r[f"stopfirst_{S}"] = (s <= t) if min(s, t) < 10**9 else np.nan
    return r
