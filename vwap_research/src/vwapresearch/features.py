"""Session labelling, VWAP anchors, bands and per-bar features.

All computations are strictly causal: every value on the row stamped t uses
information available at the CLOSE of minute bar t.  Any strategy acting on
these features trades no earlier than the next bar.

Definitions
-----------
session_day : the CME-style futures day, 18:00 ET (prev cal day) -> 17:00 ET,
              labelled by the calendar date of its RTH morning.
week_id     : ISO week of session_day's start; weekly VWAP anchors at the
              first bar of the week's first session (Sunday 18:00 ET).
VWAP        : cumulative sum(price*tickvol)/sum(tickvol) from the anchor bar,
              price = (H+L+C)/3.  NOTE: tick volume, not true traded volume
              (documented limitation of the CFD dataset).
sigma       : sqrt( cum sum(v*p^2)/cum v - vwap^2 ), the volume-weighted
              dispersion of price around the running VWAP — the classic
              "VWAP standard deviation band" width.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import TZ


# ----------------------------------------------------------------- sessions
def add_sessions(df: pd.DataFrame) -> pd.DataFrame:
    """Add session/day/week labels and NY/Paris clock columns."""
    out = df.copy()
    ny = out.index.tz_convert(TZ)
    paris = out.index.tz_convert("Europe/Paris")
    # futures day: shift NY time back by 18h -> session date = calendar date+1
    # for bars >= 18:00; equivalently add 6h and take the date.
    sess_date = (ny + pd.Timedelta(hours=6)).normalize()
    out["session_day"] = sess_date.date
    out["ny_minute"] = ny.hour * 60 + ny.minute          # minute of NY day
    out["paris_date"] = paris.date
    out["ny_date"] = ny.date
    out["dow"] = sess_date.dayofweek.values
    # ISO week id of the session date (Mon=0): sessions Sun 18:00..Fri 17:00
    iso = sess_date.isocalendar()
    out["week_id"] = (iso["year"] * 100 + iso["week"]).values
    out["is_rth"] = (out["ny_minute"] >= 570) & (out["ny_minute"] < 960)  # 09:30..16:00
    # maintenance window 17:00-18:00 ET excluded upstream by data (no bars)
    return out


# ------------------------------------------------------------------- vwaps
def _group_vwap(px: np.ndarray, vol: np.ndarray, gid: np.ndarray):
    """Cumulative VWAP and sigma per contiguous group id array."""
    v = vol.astype("float64")
    pv = px * v
    pv2 = px * px * v
    # reset cumulative sums at group boundaries
    new = np.empty(len(gid), dtype=bool)
    new[0] = True
    new[1:] = gid[1:] != gid[:-1]
    idx_new = np.flatnonzero(new)
    cs_v = np.cumsum(v)
    cs_pv = np.cumsum(pv)
    cs_pv2 = np.cumsum(pv2)
    base_v = np.zeros(len(gid)); base_pv = np.zeros(len(gid)); base_pv2 = np.zeros(len(gid))
    # value of cumsum just before each group start, propagated forward
    grp_no = np.cumsum(new) - 1
    starts_v = np.where(idx_new > 0, cs_v[idx_new - 1], 0.0)
    starts_pv = np.where(idx_new > 0, cs_pv[idx_new - 1], 0.0)
    starts_pv2 = np.where(idx_new > 0, cs_pv2[idx_new - 1], 0.0)
    base_v = starts_v[grp_no]
    base_pv = starts_pv[grp_no]
    base_pv2 = starts_pv2[grp_no]
    cv = cs_v - base_v
    cv = np.where(cv <= 0, np.nan, cv)
    vwap = (cs_pv - base_pv) / cv
    var = (cs_pv2 - base_pv2) / cv - vwap * vwap
    sigma = np.sqrt(np.clip(var, 0.0, None))
    return vwap, sigma


def add_vwaps(df: pd.DataFrame) -> pd.DataFrame:
    """Add VWAP/sigma for anchors: session (18:00 ET), midnight NY,
    midnight Paris, RTH open (09:30 ET), and weekly."""
    out = df.copy()
    px = ((out["high"] + out["low"] + out["close"]) / 3.0).to_numpy("float64")
    vol = out["volume"].to_numpy("float64")

    def as_gid(series) -> np.ndarray:
        return pd.factorize(series)[0]

    anchors = {
        "sess": as_gid(out["session_day"]),
        "nyd": as_gid(out["ny_date"]),
        "par": as_gid(out["paris_date"]),
        "week": as_gid(out["week_id"]),
    }
    for name, gid in anchors.items():
        vwap, sigma = _group_vwap(px, vol, gid)
        out[f"vwap_{name}"] = vwap
        out[f"sigma_{name}"] = sigma

    # RTH-anchored: group = session_day but only bars >= 09:30; NaN before.
    rth_mask = (out["ny_minute"] >= 570).to_numpy()
    gid_r = as_gid(out["session_day"]).astype("int64").copy()
    vwap_r = np.full(len(out), np.nan)
    sigma_r = np.full(len(out), np.nan)
    if rth_mask.any():
        vw, sg = _group_vwap(px[rth_mask], vol[rth_mask], gid_r[rth_mask])
        vwap_r[rth_mask] = vw
        sigma_r[rth_mask] = sg
    out["vwap_rth"] = vwap_r
    out["sigma_rth"] = sigma_r
    return out


# ---------------------------------------------------------------- features
def add_features(df: pd.DataFrame, main: str = "sess") -> pd.DataFrame:
    """Derived causal features for the main VWAP anchor."""
    out = df.copy()
    vw = out[f"vwap_{main}"]
    sg = out[f"sigma_{main}"].replace(0.0, np.nan)
    close = out["close"]

    out["m"] = (close - vw) / sg                     # band multiple of close
    out["m_high"] = (out["high"] - vw) / sg
    out["m_low"] = (out["low"] - vw) / sg

    # VWAP slope over horizons, normalized by sigma (per-anchor scale)
    for k in [5, 15, 30]:
        out[f"vwap_slope_{k}"] = (vw - vw.shift(k)) / sg
    out["vwap_curv"] = out["vwap_slope_5"] - (vw.shift(5) - vw.shift(10)) / sg

    # crosses of VWAP within session so far
    above = (close > vw).astype("int8")
    grp = out.groupby("session_day", sort=False)
    chg = above.diff().abs().fillna(0)
    chg[grp.cumcount() == 0] = 0
    out["n_cross"] = chg.groupby(out["session_day"], sort=False).cumsum()

    # arrival speed: 5-min price change normalized by 30-min realized vol
    ret1 = np.log(close).diff()
    rv30 = ret1.rolling(30, min_periods=10).std()
    out["speed5"] = (np.log(close) - np.log(close.shift(5))) / (rv30 * np.sqrt(5))

    # 1-min ATR(30) in points and 30-min realized vol
    tr = np.maximum(out["high"] - out["low"],
                    np.maximum((out["high"] - close.shift()).abs(),
                               (out["low"] - close.shift()).abs()))
    out["atr30"] = tr.rolling(30, min_periods=10).mean()
    out["rv30"] = rv30

    # distance of session VWAP to weekly VWAP, in session sigmas
    out["dw"] = (out[f"vwap_{main}"] - out["vwap_week"]) / sg

    # minutes since RTH open (negative before)
    out["min_since_open"] = out["ny_minute"] - 570

    # intraday cummax/cummin so far (for prev-day/overnight levels use daily agg)
    out["day_high"] = grp["high"].cummax()
    out["day_low"] = grp["low"].cummin()
    return out


# ------------------------------------------------------- per-day aggregates
def day_table(df: pd.DataFrame) -> pd.DataFrame:
    """One row per session_day with prev-day and overnight context.
    All values known by 09:30 ET of the session (no look-ahead when merged
    on bars at/after the open)."""
    g = df.groupby("session_day", sort=True)
    rth = df[df["is_rth"]]
    gr = rth.groupby("session_day", sort=True)
    tab = pd.DataFrame({
        "rth_open_px": gr["open"].first(),
        "rth_close_px": gr["close"].last(),
        "rth_high": gr["high"].max(),
        "rth_low": gr["low"].min(),
        "sess_first_px": g["open"].first(),
    })
    on = df[~df["is_rth"] & (df["ny_minute"].lt(570) | df["ny_minute"].ge(1080))]
    gon = on.groupby("session_day", sort=True)
    tab["on_high"] = gon["high"].max()
    tab["on_low"] = gon["low"].min()
    tab["prev_rth_high"] = tab["rth_high"].shift(1)
    tab["prev_rth_low"] = tab["rth_low"].shift(1)
    tab["prev_rth_close"] = tab["rth_close_px"].shift(1)
    tab["prev_rth_range"] = tab["prev_rth_high"] - tab["prev_rth_low"]
    tab["gap_open"] = tab["rth_open_px"] - tab["prev_rth_close"]
    tab["on_range"] = tab["on_high"] - tab["on_low"]
    # 14-day ATR of RTH ranges (shifted: known before the day starts)
    tab["atr14_d"] = (tab["rth_high"] - tab["rth_low"]).shift(1).rolling(14, min_periods=7).mean()
    return tab


def build_frame(m1: pd.DataFrame) -> pd.DataFrame:
    df = add_sessions(m1)
    df = add_vwaps(df)
    df = add_features(df)
    return df
