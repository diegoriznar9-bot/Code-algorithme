"""PHASE 3b — full pre-open fade grid with wide stops (TRAIN only, gross +
net).  Plateau detection on gross Sharpe; net figures use era-true fixed
point costs (documented: cost/sigma ratio improves mechanically with index
level, so TRAIN-era net is the WORST case)."""
import os, sys, itertools, ast
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np
import pandas as pd

from vwapresearch.ingest import OUT_ROOT
from vwapresearch import backtest, candidates, stats, registry
from vwapresearch.config import split_of, COSTS, DATASET_COSTBOOK

RES = os.path.join(os.path.dirname(__file__), "..", "results", "phase3")
os.makedirs(RES, exist_ok=True)

GRID = {
    "level": [1.5, 2.0, 2.5],
    "stop_sigma": [2.0, 2.5, 3.0],
    "time_stop": [120, 180, 240],
    "window": [(420, 570), (450, 570), (480, 570)],
    "target": ["vwap", "l1"],
}


def run_all(name):
    big, _ = DATASET_COSTBOOK[name]
    cost = COSTS[big]["base"]["per_side_pts"]
    fr = pd.read_parquet(os.path.join(OUT_ROOT, f"{name}_feat.parquet"))
    fr = fr[(split_of(fr.index) == "TRAIN").values]
    ev = pd.read_parquet(os.path.join(OUT_ROOT, f"{name}_events_TRAIN.parquet"))
    rows = []
    for combo in itertools.product(*GRID.values()):
        p = dict(zip(GRID.keys(), combo))
        a, b = p["window"]
        flt = (lambda pp, aa, bb: lambda e: (e["level"] == pp) &
               (e["ny_minute"] >= aa) & (e["ny_minute"] < bb))(p["level"], a, b)
        spec = backtest.ExecSpec(stop_sigma=p["stop_sigma"], target=p["target"],
                                 time_stop=p["time_stop"], cost_per_side_pts=0.0,
                                 max_trades_day=6)
        tr = candidates.run_candidate(fr, ev, flt, spec, fade=True)
        if len(tr) < 50:
            continue
        d = stats.daily_series(tr)
        yr = d.groupby(d.index.year).sum()
        g = candidates.summarize(tr)
        rows.append({**{k: (str(v) if k == "window" else v) for k, v in p.items()},
                     "n": g["n"], "gross_exp": g["expectancy_pts"],
                     "gross_pf": g["profit_factor"], "gross_sharpe": g["sharpe_d"],
                     "net_exp": g["expectancy_pts"] - 2 * cost,
                     "pos_years": int((yr > 0).sum()), "n_years": len(yr),
                     "wr": g["win_rate"], "max_dd": g["max_dd_pts"],
                     "share_top5": g.get("share_top5", np.nan)})
    sw = pd.DataFrame(rows)
    sw.to_csv(f"{RES}/PREB_{name}_grid.csv", index=False)
    return sw


for name in ["NAS100", "SPX500"]:
    sw = run_all(name)
    print(f"=== {name}: top 12 by gross_sharpe")
    cols = ["level", "stop_sigma", "time_stop", "window", "target", "n",
            "gross_exp", "net_exp", "gross_pf", "gross_sharpe", "pos_years"]
    print(sw.sort_values("gross_sharpe", ascending=False).head(12)[cols].round(3).to_string(index=False))
    print(f"--- distribution of gross_sharpe: median {sw['gross_sharpe'].median():.2f}, "
          f"q25 {sw['gross_sharpe'].quantile(.25):.2f}, q75 {sw['gross_sharpe'].quantile(.75):.2f}, "
          f"share>0: {(sw['gross_sharpe']>0).mean():.2f}, share posYears>=8: {(sw['pos_years']>=8).mean():.2f}")
    registry.log("phase3b", "PRE-open fade full grid (wide stops)", name, "TRAIN",
                 f"{len(sw)} combos", int(sw["n"].median()),
                 f"median gross sharpe {sw['gross_sharpe'].median():.2f}; share combos sharpe>0 {(sw['gross_sharpe']>0).mean():.2f}",
                 "sweep", "plateau check")
