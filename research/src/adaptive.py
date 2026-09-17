"""Seuils de sortie adaptatifs.

Règle proposée (calculable à chaque date avec le seul passé) :

    sigma_mix(t) = w_f * RV_26s(t) + (1 - w_f) * RV_104s(t)      (vol annualisée)
    sigma_Q(t)   = sigma_mix(t) * sqrt(13/52)                     (échelle trimestre)
    D1(t) = clip( k1 * sigma_Q(t) , d1_min , d1_max )
    D2(t) = clip( k2 * sigma_Q(t) , d2_min , d2_max ),  D2 >= min_ratio * D1

k1 et k2 sont calibrés UNIQUEMENT sur la période d'apprentissage (ou re-calibrés
en walk-forward avec les données passées), puis figés : la seule chose qui
s'adapte ensuite est la volatilité observée.
"""
import numpy as np
import pandas as pd

from . import config, data


def sigma_mix(w: pd.DataFrame, fast=None, slow=None, blend=None) -> pd.Series:
    fast = fast or config.VOL_FAST_W
    slow = slow or config.VOL_SLOW_W
    blend = config.VOL_BLEND if blend is None else blend
    rv_f = data.realized_vol(w["log_ret"], fast)
    rv_s = data.realized_vol(w["log_ret"], slow)
    return (blend * rv_f + (1 - blend) * rv_s).rename("sigma_mix")


def thresholds(w: pd.DataFrame, k1: float, k2: float, params=None,
               fast=None, slow=None, blend=None):
    p = params or config.ADAPTIVE
    sq = sigma_mix(w, fast, slow, blend) * np.sqrt(13 / 52)
    d1 = (k1 * sq).clip(*p["d1_bounds"])
    d2 = (k2 * sq).clip(*p["d2_bounds"])
    d2 = pd.concat([d2, p["min_ratio"] * d1], axis=1).max(axis=1)
    return d1.rename("D1"), d2.rename("D2")
