"""Frozen research configuration.

TEMPORAL SPLITS — decided BEFORE any exploratory analysis was run, on
2026-09-17, and never modified afterwards:

- TRAIN / DISCOVERY : 2005-01-01 .. 2014-12-31   (Oanda)
- VALIDATION        : 2015-01-01 .. 2018-12-31   (Oanda)
- VAULT (holdout)   : 2019-01-01 .. 2020-05-14   (Oanda)
                      + full 2026-03-12 .. 2026-09-11 getdata slice
The Vault is not read by any exploration or optimization script.  It is
opened once, at the very end, on locked rules (see scripts/open_vault.py).
"""
import pandas as pd

TZ = "America/New_York"

TRAIN_END = pd.Timestamp("2015-01-01", tz=TZ)     # exclusive
VAL_END = pd.Timestamp("2019-01-01", tz=TZ)       # exclusive; vault starts here

# Cost scenarios, expressed in INDEX POINTS per side (entry or exit), for the
# instrument the strategy would actually trade.  spread_half = half bid/ask
# paid on a market order; slip = additional adverse slippage; comm = commission.
# NQ point = $20, tick 0.25 ; MNQ point = $2, tick 0.25 (comm heavier in pts)
# ES point = $50, tick 0.25 ; MES point = $5, tick 0.25
COSTS = {
    "NQ": {
        "base":    {"per_side_pts": 0.25 * 0.5 + 0.25 * 0.5 + 0.065},  # half-spread + 0.5t slip + comm
        "stress1": {"per_side_pts": 0.25 * 0.5 + 0.25 * 1.0 + 0.065},  # 1 tick slip
        "stress15": {"per_side_pts": (0.25 * 0.5 + 0.25 * 0.5 + 0.065) * 1.5},
        "stress2": {"per_side_pts": (0.25 * 0.5 + 0.25 * 0.5 + 0.065) * 2.0},
    },
    "MNQ": {
        "base":    {"per_side_pts": 0.25 * 0.5 + 0.25 * 0.5 + 0.26},
        "stress1": {"per_side_pts": 0.25 * 0.5 + 0.25 * 1.0 + 0.26},
        "stress15": {"per_side_pts": (0.25 * 0.5 + 0.25 * 0.5 + 0.26) * 1.5},
        "stress2": {"per_side_pts": (0.25 * 0.5 + 0.25 * 0.5 + 0.26) * 2.0},
    },
    "ES": {
        "base":    {"per_side_pts": 0.125 + 0.125 + 0.026},
        "stress1": {"per_side_pts": 0.125 + 0.25 + 0.026},
        "stress15": {"per_side_pts": (0.125 + 0.125 + 0.026) * 1.5},
        "stress2": {"per_side_pts": (0.125 + 0.125 + 0.026) * 2.0},
    },
    "MES": {
        "base":    {"per_side_pts": 0.125 + 0.125 + 0.104},
        "stress1": {"per_side_pts": 0.125 + 0.25 + 0.104},
        "stress15": {"per_side_pts": (0.125 + 0.125 + 0.104) * 1.5},
        "stress2": {"per_side_pts": (0.125 + 0.125 + 0.104) * 2.0},
    },
}

POINT_VALUE = {"NQ": 20.0, "MNQ": 2.0, "ES": 50.0, "MES": 5.0}

# Instrument mapping: which cost book applies to which research dataset
DATASET_COSTBOOK = {"NAS100": ("NQ", "MNQ"), "SPX500": ("ES", "MES")}


def split_of(ts_index) -> pd.Series:
    """Label each timestamp TRAIN / VAL / VAULT (NY-time comparison)."""
    ny = ts_index.tz_convert(TZ)
    lab = pd.Series("VAULT", index=ts_index)
    lab[ny < TRAIN_END] = "TRAIN"
    lab[(ny >= TRAIN_END) & (ny < VAL_END)] = "VAL"
    return lab
