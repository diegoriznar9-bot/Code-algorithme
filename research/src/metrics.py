"""Mesures de performance et de risque."""
import numpy as np
import pandas as pd

WEEKS = 52


def drawdown(eq: pd.Series) -> pd.Series:
    return eq / eq.cummax() - 1.0


def ulcer_index(eq: pd.Series) -> float:
    dd = drawdown(eq) * 100
    return float(np.sqrt((dd ** 2).mean()))


def max_dd_duration_weeks(eq: pd.Series) -> int:
    peak_idx = eq.cummax()
    at_peak = eq >= peak_idx * (1 - 1e-12)
    longest = cur = 0
    for flag in at_peak.values:
        cur = 0 if flag else cur + 1
        longest = max(longest, cur)
    return int(longest)


def perf_table(res, w: pd.DataFrame, rf_weekly: pd.Series | None = None,
               bh_eq: pd.Series | None = None, cost_per_side: float = 0.0) -> dict:
    eq = res.equity.dropna()
    r = eq.pct_change().dropna()
    n_years = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / n_years) - 1
    vol = r.std() * np.sqrt(WEEKS)
    rf = rf_weekly.reindex(r.index).fillna(0.0) if rf_weekly is not None else pd.Series(0.0, index=r.index)
    ex = r - rf
    sharpe = float(ex.mean() / r.std() * np.sqrt(WEEKS)) if r.std() > 0 else np.nan
    downside = r[r < 0].std()
    sortino = float(ex.mean() * WEEKS / (downside * np.sqrt(WEEKS))) if downside and downside > 0 else np.nan
    mdd = drawdown(eq).min()
    calmar = float(cagr / abs(mdd)) if mdd < 0 else np.nan

    out = {
        "valeur_finale": float(eq.iloc[-1] / eq.iloc[0]),
        "rendement_total": float(eq.iloc[-1] / eq.iloc[0] - 1),
        "CAGR": float(cagr),
        "vol_annualisee": float(vol),
        "max_drawdown": float(mdd),
        "duree_max_dd_semaines": max_dd_duration_weeks(eq),
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "ulcer_index": ulcer_index(eq),
        "exposition_moyenne": float(res.exposure.mean()),
        "temps_investi_pct": float((res.exposure > 0.01).mean()),
    }
    tdf = res.trades_df()
    out["nb_transactions"] = len(tdf)
    if len(tdf):
        # rendement par position (achat -> liquidation complète)
        pos_rets, spent, recovered = [], None, 0.0
        for _, t in tdf.iterrows():
            if t.side == "buy":
                spent, recovered = t.btc * t.price, 0.0
            elif spent:
                recovered += t.btc * t.price
                if t.btc_after <= 1e-12:
                    pos_rets.append(recovered / spent - 1)
                    spent = None
        if spent is not None:  # position encore ouverte : valorisée au dernier cours
            last_close = w["close"].reindex(res.equity.index).iloc[-1]
            recovered += tdf.iloc[-1].btc_after * last_close
            pos_rets.append(recovered / spent - 1)
        out["nb_positions_closes"] = len(pos_rets)
        out["taux_reussite"] = float(np.mean([1 if x > 0 else 0 for x in pos_rets])) if pos_rets else np.nan
        out["rendement_moyen_position"] = float(np.mean(pos_rets)) if pos_rets else np.nan
        turnover_usd = float((tdf.btc * tdf.price).sum())
        out["turnover_x_capital"] = turnover_usd
        out["couts_payes_pct_capital_initial"] = turnover_usd * cost_per_side
    if bh_eq is not None:
        bh_r = bh_eq.pct_change().reindex(r.index).dropna()
        rr = r.reindex(bh_r.index)
        up = bh_r > 0
        out["capture_hausse"] = float(rr[up].mean() / bh_r[up].mean()) if up.any() else np.nan
        out["capture_baisse"] = float(rr[~up].mean() / bh_r[~up].mean()) if (~up).any() else np.nan
    return out


def per_period_returns(eq: pd.Series, bounds: list) -> dict:
    """CAGR par sous-période. bounds = [(label, start, end), ...]"""
    out = {}
    for label, s, e in bounds:
        sub = eq.loc[s:e]
        if len(sub) < 10:
            continue
        yrs = (sub.index[-1] - sub.index[0]).days / 365.25
        out[label] = float((sub.iloc[-1] / sub.iloc[0]) ** (1 / max(yrs, 1e-9)) - 1)
    return out
