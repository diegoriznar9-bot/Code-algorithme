"""Étape 1 : données, sanity checks, stratégie de référence et ses variantes d'interprétation."""
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT.parent))
from research.src import config, data, strategy, metrics, entries

pd.set_option("display.width", 200)
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)

daily = data.load_daily(ROOT)
w = data.weekly_frame(daily)
print("=== Données ===")
print(f"quotidien : {daily.index[0].date()} -> {daily.index[-1].date()}  ({len(daily)} jours)")
print(f"hebdo     : {w.index[0].date()} -> {w.index[-1].date()}  ({len(w)} semaines)")
print("\nPoints de contrôle (comparaison à des sources externes, cf. rapport) :")
for d in ["2013-11-30", "2015-01-14", "2017-12-17", "2018-12-15", "2021-11-08",
          "2022-11-21", "2024-04-20", "2025-12-31", daily.index[-1].strftime('%Y-%m-%d')]:
    try:
        print(f"  {d} : {daily.loc[d, 'PriceUSD']:.2f} USD")
    except KeyError:
        pass

rf_w = data.tbill_weekly(w.index)
ma156 = entries.sma(w, 156)

print("\n=== Stratégie de référence (SMA156, -20 %/-40 %, coûts centraux) ===")
cost = sum(config.COST_SCENARIOS["central"].values())
base = strategy.run_strategy(w, ma=ma156, exit_levels=[0.20, 0.40],
                             cost_per_side=cost)
bh = strategy.buy_and_hold(w, cost_per_side=cost)
tdf = base.trades_df()
print(tdf[["date", "side", "reason", "price", "fraction"]].to_string(index=False))

tbl = metrics.perf_table(base, w, rf_weekly=rf_w, bh_eq=bh.equity, cost_per_side=cost)
tbl_bh = metrics.perf_table(bh, w, rf_weekly=rf_w, cost_per_side=cost)
cmp = pd.DataFrame({"strategie": tbl, "buy_hold": tbl_bh})
print(cmp.round(4).to_string())

print("\n=== Variantes d'interprétation des règles ambiguës ===")
variants = {
    "peak=close, maj apres partiel (defaut)": dict(),
    "peak=high intra-semaine": dict(peak_source="high"),
    "peak fige apres vente partielle": dict(peak_updates_after_partial=False),
    "etat initial non strict (achat des le debut si > SMA)": dict(strict_initial_state=False),
    "execution a la cloture du signal (borne optimiste)": None,  # traité ci-dessous
}
rows = {}
for name, kw in variants.items():
    if kw is None:
        w2 = w.copy(); w2["exec_open"] = w2["close"].shift(-1)  # ~ cloture+1 sem ? non: voir note
        continue
    r = strategy.run_strategy(w, ma=ma156, exit_levels=[0.20, 0.40], cost_per_side=cost, **kw)
    t = metrics.perf_table(r, w, rf_weekly=rf_w, bh_eq=bh.equity, cost_per_side=cost)
    rows[name] = {k: t[k] for k in ["CAGR", "max_drawdown", "sharpe", "nb_transactions", "valeur_finale"]}
print(pd.DataFrame(rows).T.round(4).to_string())

print("\n=== Scénarios de coûts ===")
for scen, c in config.COST_SCENARIOS.items():
    cps = c["fee"] + c["slippage"]
    r = strategy.run_strategy(w, ma=ma156, exit_levels=[0.20, 0.40], cost_per_side=cps)
    t = metrics.perf_table(r, w, rf_weekly=rf_w, cost_per_side=cps)
    print(f"  {scen:12s} ({cps*100:.1f}%/ordre) : CAGR={t['CAGR']:.2%}  VF={t['valeur_finale']:.1f}x  MDD={t['max_drawdown']:.1%}")

print("\n=== Variante cash rémunéré (T-bill 3M) ===")
r = strategy.run_strategy(w, ma=ma156, exit_levels=[0.20, 0.40], cost_per_side=cost, cash_rate=rf_w)
t = metrics.perf_table(r, w, rf_weekly=rf_w, cost_per_side=cost)
print(f"  CAGR={t['CAGR']:.2%}  VF={t['valeur_finale']:.1f}x  (vs {tbl['CAGR']:.2%} sans rémunération)")

# sauvegardes pour les étapes suivantes
base.equity.to_csv(OUT / "equity_baseline.csv")
bh.equity.to_csv(OUT / "equity_buyhold.csv")
tdf.to_csv(OUT / "trades_baseline.csv", index=False)
json.dump({"baseline": tbl, "buy_hold": tbl_bh}, open(OUT / "metrics_step1.json", "w"), indent=1, default=float)
print("\nOK - fichiers écrits dans output/")
