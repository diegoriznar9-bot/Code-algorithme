"""Étape 5 : tests de robustesse et bootstrap par blocs.

- heatmap MA x seuil D1 (D2 = 2*D1) : la performance dépend-elle d'un point précis ?
- sensibilité aux frais, au jour de clôture hebdo, à la date de début,
  aux fenêtres de volatilité de la version adaptative, au cash rémunéré
- bootstrap par blocs (26 semaines, 500 tirages, graine fixée)
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
COMMON_START = w.index[207]

BOUNDED = dict(d1_bounds=(0.12, 0.20), d2_bounds=(0.24, 0.40), min_ratio=2.0)

def bounded_adaptive(wf, cost_per_side=cost, fast=None, slow=None):
    d1, d2 = adaptive.thresholds(wf, 0.5, 1.0, params=BOUNDED, fast=fast, slow=slow)
    return strategy.run_strategy(wf, ma=entries.sma(wf, 156), exit_levels=[d1, d2],
                                 cost_per_side=cost_per_side)

def base_run(wf, cost_per_side=cost, ma_n=156, d1=0.20, d2=0.40):
    return strategy.run_strategy(wf, ma=entries.sma(wf, ma_n), exit_levels=[d1, d2],
                                 cost_per_side=cost_per_side)

def summarize(res, start=None, end=None):
    eq = res.equity.loc[start or COMMON_START:end]
    if len(eq) < 20 or eq.iloc[0] <= 0:
        return dict(cagr=np.nan, mdd=np.nan, calmar=np.nan)
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1
    mdd = metrics.drawdown(eq).min()
    return dict(cagr=float(cagr), mdd=float(mdd),
                calmar=float(cagr / abs(mdd)) if mdd < 0 else np.nan)

# ---------------------------------------------------------------------------
# 1) heatmap MA x D1 (D2 = 2*D1)
# ---------------------------------------------------------------------------
print("=== Heatmap MA x D1 (metrique : Calmar sur fenetre commune) ===")
mas = list(range(104, 209, 8))
d1s = [0.10, 0.125, 0.15, 0.175, 0.20, 0.225, 0.25, 0.275, 0.30]
heat_calmar = pd.DataFrame(index=mas, columns=d1s, dtype=float)
heat_cagr = pd.DataFrame(index=mas, columns=d1s, dtype=float)
for m in mas:
    for d1v in d1s:
        s = summarize(base_run(w, ma_n=m, d1=d1v, d2=2 * d1v))
        heat_calmar.loc[m, d1v] = s["calmar"]
        heat_cagr.loc[m, d1v] = s["cagr"]
heat_calmar.to_csv(OUT / "heatmap_ma_d1_calmar.csv")
heat_cagr.to_csv(OUT / "heatmap_ma_d1_cagr.csv")
print(heat_calmar.round(2).to_string())

# ---------------------------------------------------------------------------
# 2) frais / slippage
# ---------------------------------------------------------------------------
print("\n=== Sensibilité aux coûts (par ordre, aller simple) ===")
rows = {}
for cps in [0.0, 0.001, 0.002, 0.005, 0.01, 0.02]:
    rows[f"{cps:.3f}"] = {
        "actuelle_cagr": summarize(base_run(w, cost_per_side=cps))["cagr"],
        "bornee_cagr": summarize(bounded_adaptive(w, cost_per_side=cps))["cagr"],
    }
cost_df = pd.DataFrame(rows).T
print(cost_df.round(4).to_string())
cost_df.to_csv(OUT / "sensitivity_costs.csv")

# ---------------------------------------------------------------------------
# 3) jour de clôture hebdomadaire
# ---------------------------------------------------------------------------
print("\n=== Sensibilité au jour de clôture hebdomadaire ===")
rows = {}
for anchor in ["W-MON", "W-TUE", "W-WED", "W-THU", "W-FRI", "W-SAT", "W-SUN"]:
    wf = data.weekly_frame(daily, anchor=anchor)
    st = wf.index[min(207, len(wf) - 1)]
    b = summarize(base_run(wf), start=st)
    a = summarize(bounded_adaptive(wf), start=st)
    rows[anchor] = {"actuelle_cagr": b["cagr"], "actuelle_mdd": b["mdd"],
                    "bornee_cagr": a["cagr"], "bornee_mdd": a["mdd"]}
day_df = pd.DataFrame(rows).T
print(day_df.round(3).to_string())
day_df.to_csv(OUT / "sensitivity_close_day.csv")

# ---------------------------------------------------------------------------
# 4) date de début d'évaluation
# ---------------------------------------------------------------------------
print("\n=== Sensibilité à la date de début (CAGR / Calmar depuis cette date) ===")
rows = {}
bh_full = strategy.buy_and_hold(w, cost_per_side=cost, start=COMMON_START)
b_full = base_run(w); a_full = bounded_adaptive(w)
for y in ["2014-07-13", "2016-01-01", "2018-01-01", "2020-01-01", "2022-01-01", "2024-01-01"]:
    rows[y] = {
        "BH_cagr": summarize(bh_full, start=y)["cagr"],
        "actuelle_cagr": summarize(b_full, start=y)["cagr"],
        "bornee_cagr": summarize(a_full, start=y)["cagr"],
        "actuelle_calmar": summarize(b_full, start=y)["calmar"],
        "bornee_calmar": summarize(a_full, start=y)["calmar"],
    }
start_df = pd.DataFrame(rows).T
print(start_df.round(3).to_string())
start_df.to_csv(OUT / "sensitivity_start_date.csv")

# ---------------------------------------------------------------------------
# 5) fenêtres de volatilité de la version adaptative
# ---------------------------------------------------------------------------
print("\n=== Sensibilité aux fenêtres de volatilité (adaptative bornée) ===")
rows = {}
for fast in [13, 26, 52]:
    for slow in [52, 104, 156]:
        if slow <= fast:
            continue
        s_all = summarize(bounded_adaptive(w, fast=fast, slow=slow))
        s_v = summarize(bounded_adaptive(w, fast=fast, slow=slow), start="2018-01-01", end="2021-12-31")
        s_t = summarize(bounded_adaptive(w, fast=fast, slow=slow), start="2022-01-01")
        rows[f"f{fast}_s{slow}"] = {"calmar_total": s_all["calmar"],
                                    "calmar_valid": s_v["calmar"], "calmar_test": s_t["calmar"]}
vol_df = pd.DataFrame(rows).T
print(vol_df.round(3).to_string())
vol_df.to_csv(OUT / "sensitivity_vol_windows.csv")

# ---------------------------------------------------------------------------
# 6) bootstrap par blocs
# ---------------------------------------------------------------------------
print("\n=== Bootstrap par blocs (26 sem., 500 tirages) ===")
rng = np.random.default_rng(config.SEED)
rets = w["log_ret"].dropna().values
n = len(rets)
block = config.BLOCK_WEEKS
res_boot = []
for b in range(config.BOOTSTRAP_N):
    starts = rng.integers(0, n - block, size=n // block + 1)
    path = np.concatenate([rets[s:s + block] for s in starts])[:n]
    prices = 100 * np.exp(np.cumsum(path))
    wf = pd.DataFrame({"close": prices}, index=w.index[1:1 + len(prices)])
    wf["high"] = wf["close"]; wf["low"] = wf["close"]
    wf["exec_open"] = wf["close"].shift(-1)  # exécution à la clôture suivante
    wf["log_ret"] = np.log(wf["close"]).diff()
    wf = wf.dropna(subset=["exec_open"])
    st = wf.index[min(207, len(wf) - 1)]
    bh_eq = wf["close"] / wf["close"].iloc[0]
    yrs = (wf.index[-1] - wf.index[0]).days / 365.25
    row = {"bh_cagr": (bh_eq.iloc[-1]) ** (1 / yrs) - 1,
           "bh_mdd": float(metrics.drawdown(bh_eq).min())}
    for name, fn in {"actuelle": base_run, "bornee": bounded_adaptive}.items():
        r = fn(wf)
        s = summarize(r, start=st)
        row[f"{name}_cagr"], row[f"{name}_mdd"] = s["cagr"], s["mdd"]
    res_boot.append(row)
boot = pd.DataFrame(res_boot)
boot.to_csv(OUT / "bootstrap_results.csv", index=False)
q = boot.quantile([0.05, 0.25, 0.5, 0.75, 0.95]).T
print(q.round(3).to_string())
print("\nP(actuelle bat B&H en CAGR) :", float((boot.actuelle_cagr > boot.bh_cagr).mean()))
print("P(bornee bat B&H en CAGR)   :", float((boot.bornee_cagr > boot.bh_cagr).mean()))
print("P(bornee MDD < actuelle MDD):", float((boot.bornee_mdd > boot.actuelle_mdd).mean()))
print("\nOK")
