"""PHASE 3 — deterministic candidates, real backtests NET of base costs,
parameter sweeps oriented at plateaus.  TRAIN ONLY.

Candidates
----------
C1  Morning fade      : touch of L in [09:30, W_end) ET -> fade to VWAP.
C2  Pre-open fade     : touch of L in [08:00, 09:30) ET -> fade to VWAP.
C3  Reintegration fade: like C1 but requires the signal bar to CLOSE back
                        inside the band (close_m*side < L) after an overshoot.
C4  Afternoon continuation: touch of L in [13:00,15:30) with slope in touch
                        direction -> trade WITH the move, fixed sigma target,
                        1 sigma stop.

Sweeps write results/phase3/<cand>_<dataset>_sweep.csv and plateau reports.
Every family run is logged in the experiment registry.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np
import pandas as pd

from vwapresearch.ingest import OUT_ROOT
from vwapresearch import backtest, candidates, registry
from vwapresearch.config import COSTS, DATASET_COSTBOOK, split_of

RES = os.path.join(os.path.dirname(__file__), "..", "results", "phase3")
os.makedirs(RES, exist_ok=True)


def load(name, split="TRAIN"):
    fr = pd.read_parquet(os.path.join(OUT_ROOT, f"{name}_feat.parquet"))
    lab = split_of(fr.index)
    fr = fr[(lab == split).values]
    ev = pd.read_parquet(os.path.join(OUT_ROOT, f"{name}_events_{split}.parquet"))
    return fr, ev


def sweep_c1(name, fr, ev, cost_pts, windows, out_prefix, reintegration=False):
    grid = {
        "level": [1.5, 2.0, 2.5],
        "stop_sigma": [0.75, 1.0, 1.25, 1.5],
        "time_stop": [45, 90, 180],
        "window": windows,
    }

    def make(p):
        a, b = p["window"]

        def flt(e):
            m = (e["level"] == p["level"]) & (e["ny_minute"] >= a) & (e["ny_minute"] < b)
            if reintegration:
                m &= (e["overshoot"] > 0.15) & (e["close_m"] * e["side"] < e["level"])
            return m

        spec = backtest.ExecSpec(stop_sigma=p["stop_sigma"], target="vwap",
                                 time_stop=p["time_stop"],
                                 cost_per_side_pts=cost_pts, max_trades_day=10)
        return flt, spec

    sw = candidates.sweep(fr, ev, grid, make, fade=True)
    sw["window"] = sw["window"].astype(str)
    sw.to_csv(f"{RES}/{out_prefix}_{name}_sweep.csv", index=False)
    return sw


def sweep_c4(name, fr, ev, cost_pts):
    grid = {
        "level": [1.5, 2.0],
        "stop_sigma": [0.75, 1.0, 1.5],
        "target_sigma": [0.75, 1.0, 1.5],
        "speed_min": [0.0, 0.8],
    }

    def make(p):
        def flt(e):
            return ((e["level"] == p["level"]) & (e["ny_minute"] >= 780)
                    & (e["ny_minute"] < 930)
                    & (e["slope15"] * e["side"] > 0)
                    & (e["speed5"].abs() >= p["speed_min"]))

        spec = backtest.ExecSpec(stop_sigma=p["stop_sigma"], target="pts",
                                 target_pts=None,  # set per-sigma via wrapper below
                                 time_stop=120,
                                 cost_per_side_pts=cost_pts, max_trades_day=10)
        return flt, spec

    # target in sigmas -> implement by converting to pts per event is not
    # supported by ExecSpec directly; approximate with median sigma of the
    # window so the target is fixed in points (documented simplification).
    rows = []
    aft = ev[(ev["ny_minute"] >= 780) & (ev["ny_minute"] < 930)]
    sgm = aft["sg_pts"].median()
    import itertools
    for combo in itertools.product(*grid.values()):
        p = dict(zip(grid.keys(), combo))
        flt, spec = make(p)
        spec.target_pts = p["target_sigma"] * sgm
        tr = candidates.run_candidate(fr, ev, flt, spec, fade=False)
        s = candidates.summarize(tr)
        s.update(p)
        rows.append(s)
    sw = pd.DataFrame(rows)
    sw.to_csv(f"{RES}/C4_{name}_sweep.csv", index=False)
    return sw


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    for name in ["NAS100", "SPX500"]:
        big, micro = DATASET_COSTBOOK[name]
        cost = COSTS[big]["base"]["per_side_pts"]
        fr, ev = load(name)
        if which in ("all", "C1"):
            sw = sweep_c1(name, fr, ev, cost,
                          windows=[(570, 660), (570, 690), (600, 720)],
                          out_prefix="C1")
            best = sw.loc[sw["expectancy_pts"].idxmax()]
            registry.log("phase3", "C1 morning fade L->VWAP", name, "TRAIN",
                         "grid level x stop x timestop x window (108)",
                         int(sw["n"].median()),
                         f"median expectancy {sw['expectancy_pts'].median():.3f} pts, "
                         f"best {best['expectancy_pts']:.3f} @ {dict(best[['level','stop_sigma','time_stop','window']])}",
                         "sweep", "plateau analysis to follow")
            print(name, "C1 done")
        if which in ("all", "C2"):
            sw = sweep_c1(name, fr, ev, cost, windows=[(480, 570), (450, 570), (480, 540)],
                          out_prefix="C2")
            registry.log("phase3", "C2 preopen fade L->VWAP", name, "TRAIN",
                         "grid level x stop x timestop x window (108)",
                         int(sw["n"].median()),
                         f"median expectancy {sw['expectancy_pts'].median():.3f}",
                         "sweep", "")
            print(name, "C2 done")
        if which in ("all", "C3"):
            sw = sweep_c1(name, fr, ev, cost,
                          windows=[(570, 660), (570, 690), (600, 720)],
                          out_prefix="C3", reintegration=True)
            registry.log("phase3", "C3 reintegration fade", name, "TRAIN",
                         "grid as C1, + overshoot>0.15 & close back inside",
                         int(sw["n"].median()),
                         f"median expectancy {sw['expectancy_pts'].median():.3f}",
                         "sweep", "")
            print(name, "C3 done")
        if which in ("all", "C4"):
            sw = sweep_c4(name, fr, ev, cost)
            registry.log("phase3", "C4 afternoon continuation", name, "TRAIN",
                         "grid level x stop x target x speed (36)",
                         int(sw["n"].median()),
                         f"median expectancy {sw['expectancy_pts'].median():.3f}",
                         "sweep", "")
            print(name, "C4 done")


if __name__ == "__main__":
    main()
