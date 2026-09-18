"""Mission 2 — backtest réel du candidat REVFADE (TRAIN) + baseline §24.

REVFADE : touch de la bande 2.5σ, contexte requis
          eq120_slope < S  (VWAP plate sur les 2h précédant l'impulsion)
          imp_maxrun >= R  (impulsion soutenue, PAS ultra-directe)
          fenêtre d'entrée W (ET)
Exécution : marché à l'open de la minute suivante, stop K*σ, cible VWAP
dynamique, time-stop TS, max 6 trades/jour, deux sens.
BASELINE : même exécution, AUCUN contexte (tout touch 2.5σ dans W).

Sorties: results/m2/REVFADE_<ds>_sweep.csv + comparaison baseline.
"""
import os, sys, itertools
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np
import pandas as pd

from vwapresearch.ingest import OUT_ROOT
from vwapresearch import backtest, candidates, stats, registry
from vwapresearch.config import split_of, COSTS, DATASET_COSTBOOK

RES = os.path.join(os.path.dirname(__file__), "..", "results", "m2")
os.makedirs(RES, exist_ok=True)

GRID = {
    "S": [0.5, 0.75, 1.0],            # eq120_slope max
    "R": [3, 4, 5],                   # imp_maxrun min
    "K": [2.0, 2.5, 3.0],             # stop sigma
    "TS": [180, 240, 300],            # time stop
    "W": [(240, 810), (450, 810), (570, 810), (570, 690)],
}
CENTER = {"S": 0.75, "R": 4, "K": 2.5, "TS": 240, "W": (450, 810)}


def flt_ctx(p):
    a, b = p["W"]
    return lambda e: ((e["level"] == 2.5) & (e["ny_minute"] >= a) & (e["ny_minute"] < b)
                      & (e["eq120_slope"] < p["S"]) & (e["imp_maxrun"] >= p["R"]))


def flt_base(p):
    a, b = p["W"]
    return lambda e: (e["level"] == 2.5) & (e["ny_minute"] >= a) & (e["ny_minute"] < b)


def spec_of(p, cost=0.0):
    return backtest.ExecSpec(stop_sigma=p["K"], target="vwap", time_stop=p["TS"],
                             cost_per_side_pts=cost, max_trades_day=6)


def run(fr, ev, flt, spec):
    tr = candidates.run_candidate(fr, ev, flt, spec, fade=True)
    if len(tr) < 40:
        return {"n": len(tr)}
    d = stats.daily_series(tr)
    yr = d.groupby(d.index.year).sum()
    return {"n": len(tr), "exp": tr["pnl_pts"].mean(),
            "exp_sg": (tr["pnl_pts"] / tr["sigma_entry"]).mean(),
            "pf": stats.trade_metrics(tr["pnl_pts"])["profit_factor"],
            "sharpe": stats.sharpe_daily(d), "wr": (tr["pnl_pts"] > 0).mean(),
            "posY": int((yr > 0).sum()), "nY": len(yr)}


def main():
    for name in ["NAS100", "SPX500"]:
        big, _ = DATASET_COSTBOOK[name]
        cost = COSTS[big]["base"]["per_side_pts"]
        fr = pd.read_parquet(os.path.join(OUT_ROOT, f"{name}_feat.parquet"))
        fr = fr[(split_of(fr.index) == "TRAIN").values]
        ev = pd.read_parquet(os.path.join(OUT_ROOT, f"{name}_impulse_TRAIN.parquet"))
        ev = ev[ev["imp_dur"].notna()]
        rows = []
        for combo in itertools.product(*GRID.values()):
            p = dict(zip(GRID.keys(), combo))
            r = run(fr, ev, flt_ctx(p), spec_of(p))
            r.update({k: str(v) if k == "W" else v for k, v in p.items()})
            rows.append(r)
        sw = pd.DataFrame(rows)
        sw.to_csv(f"{RES}/REVFADE_{name}_sweep.csv", index=False)
        ok = sw.dropna(subset=["sharpe"])
        print(f"=== {name} sweep ({len(ok)} combos valides) GROSS:")
        print(f"  sharpe: méd {ok['sharpe'].median():.2f} q25 {ok['sharpe'].quantile(.25):.2f} "
              f"q75 {ok['sharpe'].quantile(.75):.2f} | %>0: {(ok['sharpe']>0).mean():.2f} "
              f"| %posY>=8: {(ok['posY']>=8).mean():.2f}")
        print("  top 8:")
        print(ok.sort_values("sharpe", ascending=False).head(8)[
            ["S", "R", "K", "TS", "W", "n", "exp", "exp_sg", "pf", "sharpe", "posY"]].round(3).to_string(index=False))
        # centre + baseline
        rc = run(fr, ev, flt_ctx(CENTER), spec_of(CENTER))
        rb = run(fr, ev, flt_base(CENTER), spec_of(CENTER))
        print(f"  CENTRE  : {rc}")
        print(f"  BASELINE: {rb}")
        registry.log("m2-backtest", "REVFADE (flat-VWAP context + sustained impulse, fade 2.5σ)",
                     name, "TRAIN", f"grid {len(sw)} combos, centre {CENTER}",
                     rc.get("n"), f"centre gross exp_sg {rc.get('exp_sg', float('nan')):+.3f}, "
                     f"sharpe {rc.get('sharpe', float('nan')):.2f}; baseline exp_sg {rb.get('exp_sg', float('nan')):+.3f}",
                     "sweep", "candidat mission 2")


if __name__ == "__main__":
    main()
