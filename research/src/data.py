"""Chargement des données Coin Metrics et construction des séries hebdomadaires.

Limites connues (documentées dans le rapport) :
- PriceUSD est un prix de clôture quotidien agrégé multi-plateformes (fin de
  journée UTC). Il n'y a pas d'OHLC intrajournalier : le "plus haut hebdo" est
  approximé par le max des clôtures quotidiennes de la semaine, ce qui
  sous-estime légèrement les extrêmes intrajournaliers.
- L'exécution "à l'ouverture de la semaine suivante" est approximée par le prix
  de clôture du lundi suivant : le signal utilise la clôture du dimanche, l'ordre
  est exécuté sur un prix postérieur d'un jour plein => aucun look-ahead,
  hypothèse légèrement conservatrice (une journée de dérive en plus).
"""
import numpy as np
import pandas as pd
from pathlib import Path

from . import config


def load_daily(root: Path) -> pd.DataFrame:
    df = pd.read_csv(root / config.DATA_FILE, parse_dates=["time"], low_memory=False)
    df = df.set_index("time").sort_index()
    cols = [
        "PriceUSD", "CapMrktCurUSD", "CapMVRVCur", "SplyCur", "IssTotNtv",
        "FlowInExUSD", "FlowOutExUSD", "volume_reported_spot_usd_1d", "HashRate",
    ]
    cols = [c for c in cols if c in df.columns]
    out = df[cols].astype(float)
    out = out[out["PriceUSD"].notna()]
    return out


def weekly_frame(daily: pd.DataFrame, anchor: str = None) -> pd.DataFrame:
    """Construit le cadre hebdomadaire.

    close  : dernière clôture quotidienne de la semaine (jour d'ancrage)
    high   : max des clôtures quotidiennes de la semaine (proxy du plus haut)
    low    : min des clôtures quotidiennes de la semaine
    exec_open : prix du 1er jour de la semaine SUIVANTE (prix d'exécution des
                signaux émis à la clôture de cette semaine)
    """
    anchor = anchor or config.WEEK_ANCHOR
    p = daily["PriceUSD"]
    w = pd.DataFrame({
        "close": p.resample(anchor).last(),
        "high": p.resample(anchor).max(),
        "low": p.resample(anchor).min(),
        "n_days": p.resample(anchor).count(),
    })
    w = w[w["n_days"] >= 5]  # ignore les semaines incomplètes en bord de série
    # prix d'exécution : premier prix quotidien strictement postérieur à la clôture
    exec_price = []
    for ts in w.index:
        nxt = p.loc[p.index > ts]
        exec_price.append(nxt.iloc[0] if len(nxt) else np.nan)
    w["exec_open"] = exec_price
    for c in ["CapMrktCurUSD", "CapMVRVCur", "volume_reported_spot_usd_1d"]:
        if c in daily.columns:
            w[c] = daily[c].resample(anchor).last()
    w["log_ret"] = np.log(w["close"]).diff()
    return w.dropna(subset=["close", "exec_open"])


def tbill_weekly(index: pd.DatetimeIndex) -> pd.Series:
    """Taux hebdomadaire du T-bill 3 mois (approximation par moyennes annuelles)."""
    ann = pd.Series({y: r for y, r in config.TBILL_3M_ANNUAL.items()})
    rates = index.year.map(lambda y: ann.get(y, ann.iloc[-1]))
    return pd.Series((1 + np.asarray(rates)) ** (1 / 52) - 1, index=index)


def realized_vol(weekly_ret: pd.Series, window: int) -> pd.Series:
    """Volatilité réalisée annualisée sur `window` semaines (fenêtre passée)."""
    return weekly_ret.rolling(window).std() * np.sqrt(52)
