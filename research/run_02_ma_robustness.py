"""Étape 2 : robustesse de la SMA 156 face à d'autres longueurs et d'autres filtres.

Protocole anti-sélection rétroactive :
- toutes les variantes sont évaluées sur une fenêtre commune démarrant après le
  warmup du filtre le plus lent (SMA 208) ;
- les métriques sont aussi calculées séparément sur apprentissage / validation /
  test chronologiques : on cherche un PLATEAU de performance autour de 156,
  pas un pic isolé.
"""
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT.parent))
from research.src import config, data, strategy, metrics, entries

pd.set_option("display.width", 250)
OUT = ROOT / "output"
daily = data.load_daily(ROOT)
w = data.weekly_frame(daily)
rf_w = data.tbill_weekly(w.index)
cost = sum(config.COST_SCENARIOS["central"].values())

COMMON_START = w.index[207]  # après warmup SMA208
print("fenêtre d'évaluation commune :", COMMON_START.date(), "->", w.index[-1].date())

SPLITS = [
    ("train_<=2017", COMMON_START, pd.Timestamp(config.TRAIN_END)),
    ("valid_2018_21", pd.Timestamp("2018-01-01"), pd.Timestamp(config.VALID_END)),
    ("test_2022+", pd.Timestamp("2022-01-01"), w.index[-1]),
]

def eval_res(res):
    eq = res.equity.loc[COMMON_START:]
    eq = eq / eq.iloc[0]
    sub = strategy.Result(eq, res.exposure.loc[COMMON_START:], res.trades)
    t = metrics.perf_table(sub, w, rf_weekly=rf_w, cost_per_side=cost)
    row = {k: t[k] for k in ["CAGR", "vol_annualisee", "max_drawdown", "sharpe",
                             "calmar", "temps_investi_pct", "nb_transactions", "valeur_finale"]}
    for label, s, e in SPLITS:
        row[f"cagr_{label}"] = metrics.per_period_returns(eq, [(label, s, e)]).get(label, np.nan)
    return row

rows = {}
# --- balayage des SMA ---
for n in range(104, 209, 8):
    res = strategy.run_strategy(w, ma=entries.sma(w, n), exit_levels=[0.20, 0.40], cost_per_side=cost)
    rows[f"SMA{n}"] = eval_res(res)
# --- alternatives ---
alts = {
    "EMA156": dict(ma=entries.ema(w, 156)),
    "EMA104": dict(ma=entries.ema(w, 104)),
    "MultiHorizon(52/104/156)": dict(above=entries.multi_horizon(w)),
    "SMA156_ajustee_vol": dict(ma=entries.vol_adjusted_sma(w)),
    "KAMA": dict(ma=entries.kama(w)),
    "RegLogTendance156": dict(above=entries.log_trend(w)),
    "SMA156+filtre_vol": dict(above=entries.trend_plus_vol(w)),
}
for name, kw in alts.items():
    res = strategy.run_strategy(w, exit_levels=[0.20, 0.40], cost_per_side=cost, **kw)
    rows[name] = eval_res(res)

# buy & hold sur la même fenêtre
bh = strategy.buy_and_hold(w, cost_per_side=cost, start=COMMON_START)
rows["Buy&Hold"] = eval_res(bh)

df = pd.DataFrame(rows).T
df.to_csv(OUT / "ma_robustness.csv")
print(df.round(3).to_string())
print("\nOK -> output/ma_robustness.csv")
