"""Candidate strategy harness.

A candidate = (event filter -> signals) + ExecSpec.  Signals are derived from
the touch-event table (times/sides recorded causally); the backtester then
re-plays execution bar by bar on the feature frame.

Includes a generic grid sweep with plateau diagnostics.
"""
from __future__ import annotations

import itertools
from typing import Callable

import numpy as np
import pandas as pd

from . import backtest, stats


def signals_from_events(ev: pd.DataFrame, fade: bool = True) -> pd.DataFrame:
    """Convert filtered touch events into a signal frame for backtest.run.
    fade=True: trade AGAINST the touch side (upper touch -> short)."""
    side = -ev["side"] if fade else ev["side"]
    limit_px = ev["vw"] + ev["side"] * ev["level"] * ev["sg"]   # band price at touch
    sig = pd.DataFrame({"side": side.values, "limit_px": limit_px.values},
                       index=pd.DatetimeIndex(ev["time"]))
    sig = sig[~sig.index.duplicated(keep="first")].sort_index()
    return sig


def run_candidate(frame: pd.DataFrame, ev: pd.DataFrame, flt: Callable,
                  spec: backtest.ExecSpec, fade: bool = True) -> pd.DataFrame:
    sub = ev[flt(ev)] if flt is not None else ev
    if len(sub) == 0:
        return pd.DataFrame()
    sig = signals_from_events(sub, fade=fade)
    return backtest.run(frame, sig, spec)


def summarize(trades: pd.DataFrame) -> dict:
    if len(trades) == 0:
        return {"n": 0}
    m = stats.trade_metrics(trades["pnl_pts"])
    d = stats.daily_series(trades)
    m["sharpe_d"] = stats.sharpe_daily(d)
    m["sortino_d"] = stats.sortino_daily(d)
    m.update(stats.drawdown_stats(d))
    m["longest_losing_streak"] = stats.losing_streak(trades["pnl_pts"])
    # concentration: PnL share of best trades
    p = trades["pnl_pts"].sort_values(ascending=False)
    tot = p.sum()
    if tot > 0:
        m["share_top5"] = float(p.head(5).sum() / tot)
        m["share_top1pct"] = float(p.head(max(1, int(0.01 * len(p)))).sum() / tot)
        m["pnl_wo_top10"] = float(tot - p.head(10).sum())
    else:
        m["share_top5"] = np.nan; m["share_top1pct"] = np.nan
        m["pnl_wo_top10"] = float(tot - p.head(10).sum())
    return m


def sweep(frame: pd.DataFrame, ev: pd.DataFrame, grid: dict,
          make: Callable[[dict], tuple], fade: bool = True) -> pd.DataFrame:
    """grid: {param: [values]}.  make(params) -> (filter_fn, ExecSpec).
    Returns one row of summary metrics per combination."""
    keys = list(grid)
    rows = []
    for combo in itertools.product(*[grid[k] for k in keys]):
        params = dict(zip(keys, combo))
        flt, spec = make(params)
        tr = run_candidate(frame, ev, flt, spec, fade=fade)
        s = summarize(tr)
        s.update(params)
        rows.append(s)
    return pd.DataFrame(rows)


def plateau_report(sw: pd.DataFrame, metric: str, params: list[str]) -> pd.DataFrame:
    """For each grid point: metric, mean metric of axis-neighbours, share of
    profitable neighbours — a local-robustness diagnostic (mission §37)."""
    sw = sw.reset_index(drop=True)
    vals = {p: sorted(sw[p].unique()) for p in params}
    out = []
    for i, row in sw.iterrows():
        neigh = []
        for p in params:
            v = vals[p]; k = v.index(row[p])
            for kk in (k - 1, k + 1):
                if 0 <= kk < len(v):
                    m = np.ones(len(sw), dtype=bool)
                    for q in params:
                        m &= sw[q] == (v[kk] if q == p else row[q])
                    if m.any():
                        neigh.append(sw.loc[m, metric].iloc[0])
        out.append({
            **{p: row[p] for p in params}, metric: row[metric],
            "neigh_mean": np.nanmean(neigh) if neigh else np.nan,
            "neigh_pos_share": float(np.mean([x > 0 for x in neigh])) if neigh else np.nan,
            "n_trades": row.get("n", np.nan),
        })
    return pd.DataFrame(out)
