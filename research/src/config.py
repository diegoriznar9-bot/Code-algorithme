"""Configuration centrale de l'étude.

Tous les paramètres modifiables par l'utilisateur sont regroupés ici :
frais, slippage, longueur de moyenne mobile, fractions vendues, seuils de
sortie, fenêtres de volatilité, périodes d'apprentissage / validation / test.
"""
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Données
# ---------------------------------------------------------------------------
DATA_FILE = "data/btc_coinmetrics_community_20260917.csv"
PRICE_COL = "PriceUSD"          # prix de référence Coin Metrics (close quotidien UTC)
WEEK_ANCHOR = "W-SUN"           # clôture hebdomadaire le dimanche (UTC)

# Dates des halvings Bitcoin (faits de protocole, vérifiables on-chain)
HALVINGS = ["2012-11-28", "2016-07-09", "2020-04-20", "2024-04-20"]

# ---------------------------------------------------------------------------
# Coûts de transaction (par transaction, aller simple)
# ---------------------------------------------------------------------------
COST_SCENARIOS = {
    "central":    {"fee": 0.0010, "slippage": 0.0010},   # 0.20 % / ordre
    "defavorable": {"fee": 0.0050, "slippage": 0.0050},  # 1.00 % / ordre
    "zero":       {"fee": 0.0, "slippage": 0.0},
}
DEFAULT_COST = "central"

# ---------------------------------------------------------------------------
# Stratégie de référence
# ---------------------------------------------------------------------------
BASELINE = dict(
    ma_weeks=156,                 # SMA 3 ans
    exit_levels=(0.20, 0.40),     # drawdowns depuis le sommet glissant
    exit_fractions=(0.50, 1.00),  # fraction cumulée vendue à chaque seuil
    peak_source="close",          # "close" = plus haute clôture hebdo ; "high" = plus haut quotidien intra-semaine
    peak_updates_after_partial=True,  # le sommet continue d'être mis à jour après la vente partielle
    strict_initial_state=True,    # exige un passage sous la SMA avant la 1re entrée
)

# ---------------------------------------------------------------------------
# Fenêtres de volatilité et stratégie adaptative
# ---------------------------------------------------------------------------
VOL_FAST_W = 26        # volatilité "récente" (semaines)
VOL_SLOW_W = 104       # volatilité "structurelle" (semaines)
VOL_BLEND = 0.5        # poids de la vol rapide dans le mélange
ADAPTIVE = dict(
    k1=0.85,           # seuil 1 = k1 * sigma_trimestriel  (calibré sur l'apprentissage uniquement)
    k2=1.70,           # seuil 2 = k2 * sigma_trimestriel
    d1_bounds=(0.12, 0.32),   # bornes du seuil 1
    d2_bounds=(0.24, 0.55),   # bornes du seuil 2
    min_ratio=1.6,     # D2 >= min_ratio * D1
)

# ---------------------------------------------------------------------------
# Validation chronologique
# ---------------------------------------------------------------------------
TRAIN_END = "2017-12-31"     # apprentissage : 2010 -> 2017 (2 cycles complets)
VALID_END = "2021-12-31"     # validation    : 2018 -> 2021 (cycle 3)
# test hors échantillon      : 2022 -> fin des données (cycle 4/5)

# ---------------------------------------------------------------------------
# Taux sans risque (T-bill 3 mois, moyennes annuelles TB3MS, FRED)
# Valeurs saisies manuellement : l'accès direct à FRED était bloqué par la
# politique réseau de l'environnement. Sources : FRED série TB3MS.
# ---------------------------------------------------------------------------
TBILL_3M_ANNUAL = {
    2010: 0.0014, 2011: 0.0005, 2012: 0.0009, 2013: 0.0006, 2014: 0.0003,
    2015: 0.0005, 2016: 0.0032, 2017: 0.0093, 2018: 0.0194, 2019: 0.0206,
    2020: 0.0036, 2021: 0.0004, 2022: 0.0202, 2023: 0.0507, 2024: 0.0497,
    2025: 0.0420, 2026: 0.0360,
}

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
SEED = 42
BOOTSTRAP_N = 500
BLOCK_WEEKS = 26
