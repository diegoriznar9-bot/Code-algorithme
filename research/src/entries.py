"""Filtres de tendance alternatifs, tous calculables sans look-ahead.

Chaque fonction renvoie soit une ligne de tendance (comparée à la clôture),
soit un booléen `above` directement utilisable par le moteur.
"""
import numpy as np
import pandas as pd


def sma(w: pd.DataFrame, n: int) -> pd.Series:
    return w["close"].rolling(n).mean()


def ema(w: pd.DataFrame, n: int) -> pd.Series:
    # span équivalent à la SMA n (même horizon caractéristique)
    return w["close"].ewm(span=n, min_periods=n).mean()


def multi_horizon(w: pd.DataFrame, horizons=(52, 104, 156)) -> pd.Series:
    """Majorité de moyennes mobiles : haussier si la clôture est au-dessus
    d'au moins 2 des 3 SMA. Interprétable et moins dépendant d'un seul horizon."""
    votes = sum((w["close"] > sma(w, h)).astype(int) for h in horizons)
    valid = sma(w, max(horizons)).notna()
    out = (votes >= 2).astype(float)
    out[~valid] = np.nan
    return out.astype("boolean")


def vol_adjusted_sma(w: pd.DataFrame, n: int = 156, vol_win: int = 26,
                     k: float = 0.5) -> pd.Series:
    """Bande au-dessus de la SMA proportionnelle à la volatilité récente :
    exige un franchissement d'autant plus net que la volatilité est forte
    (protection contre les whipsaws), ligne = SMA * (1 + k * sigma_hebdo)."""
    sig_w = w["log_ret"].rolling(vol_win).std()
    return sma(w, n) * (1 + k * sig_w * np.sqrt(4))  # marge ~1 mois de vol


def kama(w: pd.DataFrame, er_win: int = 26, fast: int = 4, slow: int = 156) -> pd.Series:
    """Moyenne mobile adaptative de Kaufman sur clôtures hebdomadaires."""
    price = w["close"].values
    n = len(price)
    change = np.abs(price - np.roll(price, er_win))
    vol = pd.Series(np.abs(np.diff(price, prepend=price[0]))).rolling(er_win).sum().values
    er = np.where(vol > 0, change / vol, 0.0)
    sc = (er * (2 / (fast + 1) - 2 / (slow + 1)) + 2 / (slow + 1)) ** 2
    out = np.full(n, np.nan)
    start = er_win
    if n > start:
        out[start] = price[start]
        for i in range(start + 1, n):
            out[i] = out[i - 1] + sc[i] * (price[i] - out[i - 1])
    return pd.Series(out, index=w.index)


def log_trend(w: pd.DataFrame, n: int = 156) -> pd.Series:
    """Régression OLS glissante de log(prix) sur le temps (n dernières semaines).
    Haussier si clôture > valeur ajustée du jour ET pente > 0."""
    logp = np.log(w["close"]).values
    t = np.arange(len(logp), dtype=float)
    fit_val = np.full(len(logp), np.nan)
    slope = np.full(len(logp), np.nan)
    for i in range(n - 1, len(logp)):
        x = t[i - n + 1:i + 1]
        y = logp[i - n + 1:i + 1]
        b, a = np.polyfit(x, y, 1)
        fit_val[i] = a + b * t[i]
        slope[i] = b
    above = (logp > fit_val) & (slope > 0)
    out = pd.Series(above.astype(float), index=w.index)
    out[np.isnan(fit_val)] = np.nan
    return out.astype("boolean")


def trend_plus_vol(w: pd.DataFrame, n: int = 156, vol_win: int = 26) -> pd.Series:
    """SMA n + filtre de volatilité : haussier seulement si clôture > SMA et
    volatilité récente inférieure à son quantile 90 % HISTORIQUE (expanding,
    donc sans look-ahead). Évite d'acheter dans les phases de panique."""
    ma_ = sma(w, n)
    sig = w["log_ret"].rolling(vol_win).std() * np.sqrt(52)
    q90 = sig.expanding(104).quantile(0.90)
    above = (w["close"] > ma_) & (sig < q90)
    out = above.astype(float)
    out[ma_.isna() | q90.isna()] = np.nan
    return out.astype("boolean")
