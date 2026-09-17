"""PHASE 3 (focused) — pre-open fade candidate, TRAIN only.

Phenomenon (from phase-2bis pure-drift map): extensions beyond the session
VWAP bands during 08:00-09:30 ET revert by +0.2..+0.5 sigma within 1-2h on
both NAS100 and SPX500, monotonically in level and horizon.

This script sweeps the deterministic implementation and writes:
- results/phase3/PRE_<ds>_sweep.csv         (full grid, net of base costs)
- results/phase3/PRE_<ds>_plateau.csv       (neighbour diagnostics)
- results/phase3/PRE_<ds>_yearly_center.csv (yearly table of centre params)
- by-side and gross/net comparison for the centre point
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np
import pandas as pd

from vwapresearch.ingest import OUT_ROOT
from vwapresearch import backtest, candidates, registry, stats
from vwapresearch.config import COSTS, DATASET_COSTBOOK, split_of

RES = os.path.join(os.path.dirname(__file__), "..", "results", "phase3")
os.makedirs(RES, exist_ok=True)

GRID = {
    "level": [1.5, 2.0, 2.5],
    "stop_sigma": [1.0, 1.5, 2.0],
    "time_stop": [120, 180, 240],
    "window": [(420, 570), (450, 570), (480, 570)],
}
CENTER = {"level": 2.0, "stop_sigma": 1.5, "time_stop": 180, "window": (450, 570)}


def make_factory(cost_pts):
    def make(p):
        a, b = p["window"]

        def flt(e):
            return (e["level"] == p["level"]) & (e["ny_minute"] >= a) & (e["ny_minute"] < b)

        spec = backtest.ExecSpec(stop_sigma=p["stop_sigma"], target="vwap",
                                 time_stop=p["time_stop"],
                                 cost_per_side_pts=cost_pts, max_trades_day=6)
        return flt, spec
    return make


def main():
    for name in ["NAS100", "SPX500"]:
        big, micro = DATASET_COSTBOOK[name]
        cost = COSTS[big]["base"]["per_side_pts"]
        fr = pd.read_parquet(os.path.join(OUT_ROOT, f"{name}_feat.parquet"))
        fr = fr[(split_of(fr.index) == "TRAIN").values]
        ev = pd.read_parquet(os.path.join(OUT_ROOT, f"{name}_events_TRAIN.parquet"))
        make = make_factory(cost)
        sw = candidates.sweep(fr, ev, GRID, make, fade=True)
        sw["window"] = sw["window"].astype(str)
        sw.to_csv(f"{RES}/PRE_{name}_sweep.csv", index=False)
        pl = candidates.plateau_report(
            sw.assign(window=sw["window"]), "expectancy_pts",
            ["level", "stop_sigma", "time_stop"])
        pl.to_csv(f"{RES}/PRE_{name}_plateau.csv", index=False)
        # centre point detail
        flt, spec = make(CENTER)
        tr = candidates.run_candidate(fr, ev, flt, spec, fade=True)
        tr.to_parquet(f"{RES}/PRE_{name}_center_trades.parquet")
        yt = stats.yearly_table(tr)
        yt.to_csv(f"{RES}/PRE_{name}_yearly_center.csv")
        # gross variant
        spec_g = backtest.ExecSpec(**{**spec.__dict__, "cost_per_side_pts": 0.0})
        trg = candidates.run_candidate(fr, ev, flt, spec_g, fade=True)
        # by side
        sides = {}
        for lab, sgn in [("short_upper", -1), ("long_lower", 1)]:
            s = candidates.summarize(tr[tr["side"] == sgn])
            sides[lab] = {k: s.get(k) for k in ["n", "expectancy_pts", "win_rate", "profit_factor", "sharpe_d"]}
        summary = {
            "net": {k: candidates.summarize(tr).get(k) for k in
                    ["n", "expectancy_pts", "win_rate", "profit_factor", "sharpe_d", "max_dd_pts", "share_top5", "pnl_wo_top10", "total_pts"]},
            "gross": {k: candidates.summarize(trg).get(k) for k in ["expectancy_pts", "profit_factor", "sharpe_d"]},
            "sides": sides,
        }
        print(f"=== {name} centre {CENTER}")
        print(pd.DataFrame(summary["net"], index=["net"]).round(3).to_string())
        print(pd.DataFrame(summary["gross"], index=["gross"]).round(3).to_string())
        print(pd.DataFrame(sides).round(3).to_string())
        print("yearly:")
        print(yt.round(2).to_string())
        registry.log("phase3", "PRE preopen fade to VWAP", name, "TRAIN",
                     f"grid {sum(1 for _ in __import__('itertools').product(*GRID.values()))} combos, centre {CENTER}",
                     int(summary["net"]["n"] or 0),
                     f"net exp {summary['net']['expectancy_pts']:.3f} pts, sharpe {summary['net']['sharpe_d']}",
                     "sweep", "focused after pure-drift map")


if __name__ == "__main__":
    main()
