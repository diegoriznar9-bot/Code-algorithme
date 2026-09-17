"""Performance and robustness statistics."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as sps


def trade_metrics(pnl: pd.Series, point_value: float = 1.0) -> dict:
    """Per-trade metrics; pnl in points."""
    pnl = pnl.dropna()
    n = len(pnl)
    if n == 0:
        return {"n": 0}
    w = pnl[pnl > 0]; l = pnl[pnl <= 0]
    gross_w = w.sum(); gross_l = -l.sum()
    m = {
        "n": n,
        "total_pts": pnl.sum(),
        "expectancy_pts": pnl.mean(),
        "median_pts": pnl.median(),
        "win_rate": len(w) / n,
        "avg_win": w.mean() if len(w) else np.nan,
        "avg_loss": l.mean() if len(l) else np.nan,
        "payoff": (w.mean() / -l.mean()) if len(w) and len(l) and l.mean() != 0 else np.nan,
        "profit_factor": gross_w / gross_l if gross_l > 0 else np.inf,
        "skew": pnl.skew(), "kurtosis": pnl.kurtosis(),
        "worst": pnl.min(), "best": pnl.max(),
    }
    m["t_stat"] = pnl.mean() / (pnl.std(ddof=1) / np.sqrt(n)) if n > 2 and pnl.std() > 0 else np.nan
    return m


def daily_series(trades: pd.DataFrame) -> pd.Series:
    d = trades.groupby("session_day")["pnl_pts"].sum()
    d.index = pd.to_datetime(d.index)
    return d.sort_index()


def sharpe_daily(daily: pd.Series, periods: int = 252) -> float:
    if len(daily) < 10 or daily.std() == 0:
        return np.nan
    return float(daily.mean() / daily.std(ddof=1) * np.sqrt(periods))


def sortino_daily(daily: pd.Series, periods: int = 252) -> float:
    dn = daily[daily < 0]
    if len(daily) < 10 or len(dn) == 0 or dn.std() == 0:
        return np.nan
    return float(daily.mean() / dn.std(ddof=1) * np.sqrt(periods))


def drawdown_stats(daily: pd.Series) -> dict:
    eq = daily.cumsum()
    peak = eq.cummax()
    dd = eq - peak
    max_dd = dd.min()
    # longest drawdown in days
    under = dd < 0
    longest = 0; cur = 0
    for u in under:
        cur = cur + 1 if u else 0
        longest = max(longest, cur)
    return {"max_dd_pts": float(max_dd), "avg_dd_pts": float(dd[dd < 0].mean()) if (dd < 0).any() else 0.0,
            "longest_dd_days": longest,
            "recovery_factor": float(eq.iloc[-1] / -max_dd) if max_dd < 0 else np.inf}


def losing_streak(pnl: pd.Series) -> int:
    longest = 0; cur = 0
    for x in pnl:
        cur = cur + 1 if x <= 0 else 0
        longest = max(longest, cur)
    return longest


def block_bootstrap_ci(daily: pd.Series, stat_fn, n_boot: int = 2000,
                       block: int = 10, seed: int = 42):
    """Circular block bootstrap CI on a daily PnL series."""
    rng = np.random.default_rng(seed)
    x = daily.to_numpy()
    n = len(x)
    if n < 2 * block:
        return (np.nan, np.nan)
    vals = []
    nblocks = int(np.ceil(n / block))
    for _ in range(n_boot):
        starts = rng.integers(0, n, nblocks)
        idx = (starts[:, None] + np.arange(block)[None, :]).ravel() % n
        bs = pd.Series(x[idx[:n]])
        vals.append(stat_fn(bs))
    vals = np.array(vals)
    return (float(np.nanpercentile(vals, 2.5)), float(np.nanpercentile(vals, 97.5)))


def deflated_sharpe(sr_annual: float, n_days: int, skew: float, kurt: float,
                    n_trials: int, sr_benchmark: float = 0.0) -> float:
    """Bailey & Lopez de Prado Deflated Sharpe Ratio (probability that the
    observed Sharpe would exceed the expected max of `n_trials` unskilled
    trials).  sr_annual annualized from daily; internally converted to daily.
    kurt = excess kurtosis (pandas convention); converted to raw."""
    if n_days < 20 or np.isnan(sr_annual):
        return np.nan
    sr = sr_annual / np.sqrt(252)          # daily SR
    em = 0.5772156649
    n_t = max(int(n_trials), 2)
    z1 = sps.norm.ppf(1 - 1.0 / n_t)
    z2 = sps.norm.ppf(1 - 1.0 / (n_t * np.e))
    # expected max SR of unskilled trials, in daily units, assuming trial SR
    # std ~ sqrt(1/n_days) (variance of SR estimator under SR=0)
    sr_std_trials = np.sqrt(1.0 / n_days)
    sr_max = sr_benchmark + sr_std_trials * ((1 - em) * z1 + em * z2)
    g3 = skew if not np.isnan(skew) else 0.0
    g4 = (kurt + 3.0) if not np.isnan(kurt) else 3.0
    denom = np.sqrt(max(1e-12, (1 - g3 * sr + (g4 - 1) / 4.0 * sr ** 2) / (n_days - 1)))
    return float(sps.norm.cdf((sr - sr_max) / denom))


def yearly_table(trades: pd.DataFrame, point_value: float = 1.0) -> pd.DataFrame:
    t = trades.copy()
    t["year"] = pd.to_datetime(t["session_day"]).dt.year
    rows = []
    for y, g in t.groupby("year"):
        m = trade_metrics(g["pnl_pts"])
        d = daily_series(g)
        rows.append({"year": y, "trades": m["n"], "pnl_pts": m["total_pts"],
                     "expectancy": m["expectancy_pts"], "win_rate": m["win_rate"],
                     "PF": m["profit_factor"], "sharpe": sharpe_daily(d),
                     "max_dd": drawdown_stats(d)["max_dd_pts"] if len(d) > 5 else np.nan})
    return pd.DataFrame(rows).set_index("year")


def monthly_table(trades: pd.DataFrame) -> pd.DataFrame:
    t = trades.copy()
    t["ym"] = pd.to_datetime(t["session_day"]).dt.to_period("M")
    return t.groupby("ym")["pnl_pts"].agg(["count", "sum", "mean"])
