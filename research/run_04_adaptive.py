"""Étape 4 : calibration (apprentissage seul) et évaluation de la sortie adaptative.

Comparaison sur validation et test :
  - Buy & Hold
  - stratégie actuelle (SMA156, -20 %/-40 % fixes)
  - stratégie adaptative (seuils proportionnels à la volatilité)
  - variante graduelle 3 tranches
  - contrôle simple : sortie sur croisement SMA156 à la baisse
"""
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT.parent))
from research.src import config, data, strategy, metrics, entries, adaptive

pd.set_option("display.width", 250)
OUT = ROOT / "output"
daily = data.load_daily(ROOT)
w = data.weekly_frame(daily)
rf_w = data.tbill_weekly(w.index)
cost = sum(config.COST_SCENARIOS["central"].values())
ma156 = entries.sma(w, 156)
COMMON_START = w.index[207]
TRAIN_END = pd.Timestamp(config.TRAIN_END)
VALID_END = pd.Timestamp(config.VALID_END)


def run_adaptive(k1, k2, fractions=(0.5, 1.0), n_tranches=2, exit_mode="tranches",
                 freeze=False, **kw):
    d1, d2 = adaptive.thresholds(w, k1, k2, **kw)
    if n_tranches == 2:
        levels, fracs = [d1, d2], fractions
    else:  # 3 tranches graduelles
        dm = (d1 + d2) / 2
        levels, fracs = [d1, dm, d2], (1 / 3, 2 / 3, 1.0)
    return strategy.run_strategy(w, ma=ma156, exit_levels=levels, exit_mode=exit_mode,
                                 exit_fractions=fracs, cost_per_side=cost,
                                 freeze_levels_at_entry=freeze)


def score(res, start, end):
    eq = res.equity.loc[start:end]
    if len(eq) < 20:
        return np.nan, np.nan, np.nan
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1
    mdd = metrics.drawdown(eq).min()
    calmar = cagr / abs(mdd) if mdd < 0 else np.nan
    return cagr, mdd, calmar


# ---------------------------------------------------------------------------
# 1) calibration de (k1, k2) sur l'apprentissage SEUL (grille grossière assumée)
# ---------------------------------------------------------------------------
print("=== Calibration de k1 sur l'apprentissage (2014-07 -> 2017-12), k2 = 2*k1 ===")
print("NB : k2 est NON identifiable sur l'apprentissage seul (aucune 2e tranche")
print("déclenchée avant 2018) ; on impose le ratio structurel k2/k1 = 2, identique")
print("au ratio -40/-20 de la règle de référence.")
grid_k1 = [0.5, 0.6, 0.7, 0.85, 1.0, 1.2, 1.4]
train_scores = {}
for k1 in grid_k1:
    res = run_adaptive(k1, 2 * k1)
    c, m, cal = score(res, COMMON_START, TRAIN_END)
    train_scores[k1] = dict(cagr_train=c, mdd_train=m, calmar_train=cal)
gs = pd.DataFrame(train_scores).T
gs.index.name = "k1"
print(gs.round(3).to_string())
gs.to_csv(OUT / "adaptive_grid_train.csv")
best = gs["calmar_train"].idxmax()
print(f"\nMeilleur k1 sur apprentissage (Calmar) : {best}")

# évaluation de TOUTE la grille sur validation/test : sensibilité au choix de k1
test_scores = {}
for k1 in grid_k1:
    res = run_adaptive(k1, 2 * k1)
    c, m, cal = score(res, pd.Timestamp("2022-01-01"), w.index[-1])
    cv, mv, calv = score(res, pd.Timestamp("2018-01-01"), VALID_END)
    test_scores[k1] = dict(calmar_valid=calv, calmar_test=cal, cagr_test=c, mdd_test=m)
ts = pd.DataFrame(test_scores).T
ts.index.name = "k1"
full = pd.concat([gs, ts], axis=1)
full.to_csv(OUT / "adaptive_grid_full.csv")
print("\nGrille complète (apprentissage vs validation vs test) :")
print(full.round(3).to_string())

k1c, k2c = float(best), 2 * float(best)
d1, d2 = adaptive.thresholds(w, k1c, k2c)
pd.DataFrame({"D1": d1, "D2": d2}).to_csv(OUT / "adaptive_thresholds.csv")

# ---------------------------------------------------------------------------
# 2) comparaison finale des stratégies
# ---------------------------------------------------------------------------
print("\n=== Comparaison des stratégies (fenêtre commune 2014-07 ->) ===")
strats = {
    "Buy&Hold": strategy.buy_and_hold(w, cost_per_side=cost, start=COMMON_START),
    "Actuelle_SMA156_20_40": strategy.run_strategy(w, ma=ma156, exit_levels=[0.20, 0.40], cost_per_side=cost),
    "Adaptative_2T": run_adaptive(k1c, k2c),
    "Adaptative_3T_graduelle": run_adaptive(k1c, k2c, n_tranches=3),
    "Adaptative_2T+garde_fou_SMA": run_adaptive(k1c, k2c, exit_mode="tranches+sma"),
    "Adaptative_figee_entree": run_adaptive(k1c, k2c, freeze=True),
    "Adaptative_figee+garde_fou": run_adaptive(k1c, k2c, freeze=True, exit_mode="tranches+sma"),
    "Actuelle+garde_fou_SMA": strategy.run_strategy(w, ma=ma156, exit_levels=[0.20, 0.40],
                                                    exit_mode="tranches+sma", cost_per_side=cost),
    # version prudente : les seuils ne peuvent que se RESSERRER par rapport à -20/-40
    "Adaptative_bornee_0.5": run_adaptive(0.5, 1.0, params=dict(
        d1_bounds=(0.12, 0.20), d2_bounds=(0.24, 0.40), min_ratio=2.0)),
    "Controle_sortie_SMA": strategy.run_strategy(w, ma=ma156, exit_mode="sma", cost_per_side=cost),
}
rows = {}
for name, res in strats.items():
    eq = res.equity.loc[COMMON_START:]
    eq = eq / eq.iloc[0]
    sub = strategy.Result(eq, res.exposure.loc[COMMON_START:], res.trades)
    t = metrics.perf_table(sub, w, rf_weekly=rf_w,
                           bh_eq=strats["Buy&Hold"].equity, cost_per_side=cost)
    for sp, (s, e) in {"train": (COMMON_START, TRAIN_END),
                       "valid": (pd.Timestamp("2018-01-01"), VALID_END),
                       "test": (pd.Timestamp("2022-01-01"), w.index[-1])}.items():
        c, m, cal = score(res, s, e)
        t[f"cagr_{sp}"], t[f"mdd_{sp}"], t[f"calmar_{sp}"] = c, m, cal
    rows[name] = t
    eq.to_csv(OUT / f"equity_{name}.csv")
    res.trades_df().to_csv(OUT / f"trades_{name}.csv", index=False)
cmp = pd.DataFrame(rows)
cmp.to_csv(OUT / "final_comparison.csv")
print(cmp.round(3).to_string())

# ---------------------------------------------------------------------------
# 3) walk-forward annuel de (k1,k2) — recalibration avec le seul passé
# ---------------------------------------------------------------------------
print("\n=== Walk-forward : recalibration annuelle de (k1,k2) ===")
years = range(2018, w.index[-1].year + 1)
chosen = {}
eq_parts = []
prev_end = None
for yr in years:
    cutoff = pd.Timestamp(f"{yr-1}-12-31")
    sc = {}
    for k1 in grid_k1:
        res = run_adaptive(k1, 2 * k1)
        c, m, cal = score(res, COMMON_START, cutoff)
        sc[k1] = cal
    kk = max(sc, key=lambda k: (sc[k] if not np.isnan(sc[k]) else -9))
    chosen[yr] = kk
    res = run_adaptive(kk, 2 * kk)
    seg = res.equity.loc[pd.Timestamp(f"{yr}-01-01"):pd.Timestamp(f"{yr}-12-31")]
    eq_parts.append(seg.pct_change().dropna())
print("  couples retenus par année :", {y: chosen[y] for y in chosen})
wf_ret = pd.concat(eq_parts)
wf_eq = (1 + wf_ret).cumprod()
wf_eq.to_csv(OUT / "equity_walkforward_adaptive.csv")
yrs = (wf_eq.index[-1] - wf_eq.index[0]).days / 365.25
print(f"  CAGR walk-forward 2018+ : {(wf_eq.iloc[-1]) ** (1/yrs) - 1:.2%} ; "
      f"MDD : {metrics.drawdown(wf_eq).min():.1%}")
c_fixed, m_fixed, _ = score(strats['Adaptative_2T'], pd.Timestamp('2018-01-01'), w.index[-1])
print(f"  (vs k figés calibrés <=2017 : CAGR 2018+ {c_fixed:.2%}, MDD {m_fixed:.1%})")

json.dump({"k1": float(k1c), "k2": float(k2c),
           "chosen_walkforward": {str(y): float(chosen[y]) for y in chosen}},
          open(OUT / "adaptive_params.json", "w"), indent=1)
print("\nOK")
