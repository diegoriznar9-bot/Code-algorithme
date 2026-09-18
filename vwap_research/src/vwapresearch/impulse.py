"""Focused event study: EQUILIBRIUM -> DIRECT IMPULSE -> EXTREME VWAP
EXTENSION (mission 2).

For every band-touch event (levels >= 2.0 from the existing extraction),
this module walks the 1-minute frame to characterize:

IMPULSE  (from `start` = last bar before the touch whose signed deviation
          side*m <= START_M, i.e. price was last near/beyond VWAP on the
          touch side; capped at MAX_LOOKBACK bars):
  imp_dur        minutes (bars) from start to touch
  imp_amp_sg     signed amplitude in touch sigmas: side*(close_i-close_s)/sg_i
  imp_speed      imp_amp_sg / imp_dur
  imp_retr_frac  max adverse retracement of the path start->touch, as a
                 fraction of the running favourable move (0 = perfectly direct)
  imp_retr_atr   same retracement in ATR30 units
  imp_eff        efficiency ratio |net| / path-length of closes
  imp_maxrun     longest run of consecutive bars in impulse direction
  imp_nopp       number of opposite-direction bars

EQUILIBRIUM  (window [start-W, start) for W in EQ_WINDOWS):
  eqW_absm       mean |m| (distance to VWAP in sigmas)
  eqW_inside     share of bars with |m| < 0.5
  eqW_ncross     sign changes of (close - vwap)
  eqW_slope      |vwap_t - vwap_{t-W}| / sigma at start
  eqW_eff        efficiency ratio of closes (low = balanced two-way market)

OUTCOMES (pure forward drift, no stop/target):
  fret_H         fade return in touch sigmas at horizon H in {15,30,60,120}
                 (positive = price moved back toward VWAP)

Existing event columns (hit_vwap_k, t_vwap, mae_k, mfe_k, stopfirst_S,
ny_minute, touch_no, ...) are preserved.  All features use bars strictly
up to the touch bar close — causal by construction.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

START_M = 0.25          # impulse starts where side*m was last <= this
MAX_LOOKBACK = 480      # bars
EQ_WINDOWS = (60, 120, 180)
HORIZONS = (15, 30, 60, 120, 240)


def enrich(frame: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    f = frame
    cl = f["close"].to_numpy("float64")
    m = f["m"].to_numpy("float64")
    vw = f["vwap_sess"].to_numpy("float64")
    atr = f["atr30"].to_numpy("float64")
    sess = pd.factorize(f["session_day"])[0]
    pos_of_time = pd.Series(np.arange(len(f)), index=f.index)
    n = len(f)

    ev = events[events["level"] >= 2.0].copy().reset_index(drop=True)
    ipos = pos_of_time.reindex(pd.DatetimeIndex(ev["time"])).to_numpy()
    ok = np.isfinite(ipos)
    ev = ev[ok].reset_index(drop=True)
    ipos = ipos[ok].astype(int)

    out = {k: np.full(len(ev), np.nan) for k in
           ["imp_dur", "imp_amp_sg", "imp_speed", "imp_retr_frac",
            "imp_retr_atr", "imp_eff", "imp_maxrun", "imp_nopp"]
           + [f"eq{W}_{x}" for W in EQ_WINDOWS
              for x in ["absm", "inside", "ncross", "slope", "eff"]]
           + [f"fret_{H}" for H in HORIZONS]}

    side = ev["side"].to_numpy()
    sg = ev["sg"].to_numpy()

    for k in range(len(ev)):
        i = ipos[k]
        s_dir = side[k]
        # ---- find impulse start
        lo = max(0, i - MAX_LOOKBACK)
        seg_m = m[lo:i + 1] * s_dir
        near = np.flatnonzero(seg_m[:-1] <= START_M)
        # also require same session for the start
        if len(near):
            s = lo + near[-1]
            if sess[s] != sess[i]:
                s = -1
        else:
            s = -1
        if s >= 0 and i - s >= 2:
            seg = cl[s:i + 1]
            net = s_dir * (seg[-1] - seg[0])
            path = np.abs(np.diff(seg)).sum()
            fav = s_dir * (seg - seg[0])
            runmax = np.maximum.accumulate(fav)
            retr = (runmax - fav)
            max_retr = retr.max()
            amp = max(net, 1e-9)
            d1 = np.sign(np.diff(seg)) * s_dir
            # longest favourable run
            best = cur = 0
            nopp = 0
            for x in d1:
                if x > 0:
                    cur += 1
                    best = max(best, cur)
                else:
                    cur = 0
                    if x < 0:
                        nopp += 1
            out["imp_dur"][k] = i - s
            out["imp_amp_sg"][k] = net / sg[k] if sg[k] > 0 else np.nan
            out["imp_speed"][k] = out["imp_amp_sg"][k] / (i - s)
            out["imp_retr_frac"][k] = max_retr / max(runmax[-1], 1e-9)
            out["imp_retr_atr"][k] = max_retr / atr[i] if atr[i] > 0 else np.nan
            out["imp_eff"][k] = net / path if path > 0 else np.nan
            out["imp_maxrun"][k] = best
            out["imp_nopp"][k] = nopp
            # ---- equilibrium windows ending at s
            for W in EQ_WINDOWS:
                a = s - W
                if a < 0 or sess[a] != sess[s]:
                    # allow crossing into previous session? equilibrium can
                    # span the overnight; require same *futures* session only
                    if a < 0:
                        continue
                w_m = m[a:s]
                w_cl = cl[a:s]
                if np.isnan(w_m).all():
                    continue
                out[f"eq{W}_absm"][k] = np.nanmean(np.abs(w_m))
                out[f"eq{W}_inside"][k] = np.nanmean(np.abs(w_m) < 0.5)
                sgn = np.sign(w_cl - vw[a:s])
                out[f"eq{W}_ncross"][k] = np.count_nonzero(np.diff(sgn))
                out[f"eq{W}_slope"][k] = abs(vw[s] - vw[a]) / sg[k] if sg[k] > 0 else np.nan
                pth = np.abs(np.diff(w_cl)).sum()
                out[f"eq{W}_eff"][k] = abs(w_cl[-1] - w_cl[0]) / pth if pth > 0 else np.nan
        # ---- forward drift
        for H in HORIZONS:
            j = i + H
            if j < n and sess[j] == sess[i]:
                out[f"fret_{H}"][k] = -s_dir * (cl[j] - ev["entry"].iloc[k]) / sg[k]

    for c, v in out.items():
        ev[c] = v
    return ev


def build(name: str, split: str, out_root: str) -> pd.DataFrame:
    """split: TRAIN | VAL | VAULT (Oanda 2019-20) | VAULT2026 (getdata)."""
    from .config import split_of
    if split in ("TRAIN", "VAL"):
        fr = pd.read_parquet(os.path.join(out_root, f"{name}_feat.parquet"))
        fr = fr[(split_of(fr.index) == split).values]
        ev = pd.read_parquet(os.path.join(out_root, f"{name}_events_{split}.parquet"))
    elif split == "VAULT":
        fr = pd.read_parquet(os.path.join(out_root, f"{name}_feat.parquet"))
        fr = fr[(split_of(fr.index) == "VAULT").values]
        ev = pd.read_parquet(os.path.join(out_root, "vault", f"{name}_events_VAULT.parquet"))
    elif split == "VAULT2026":
        fr = pd.read_parquet(os.path.join(out_root, f"{name}_2026_feat.parquet"))
        ev = pd.read_parquet(os.path.join(out_root, "vault", f"{name}_2026_events_VAULT.parquet"))
    else:
        raise ValueError(split)
    return enrich(fr, ev)
