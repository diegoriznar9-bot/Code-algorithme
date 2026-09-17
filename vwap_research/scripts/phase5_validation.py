"""PHASE 5 — VALIDATION (2015-2018), rules locked on TRAIN.

Locked candidates (frozen BEFORE reading any VAL data):
  PREFADE-S : session-VWAP L2 touch, 07:30-09:30 ET, fade, stop 2.5 sigma,
              dynamic VWAP target, time-stop 180 min, max 6 trades/day,
              both sides, market entry at next 1-min open.
  PREFADE-F : PREFADE-S + slow-arrival filter |speed5| < 0.9.

ACCEPTANCE CRITERIA (written before running, per instrument):
  A1 gross expectancy in sigma units >= +0.08
  A2 >= 3 of 4 VAL years positive (gross)
  A3 gross PF >= 1.10
  A4 net expectancy (era-true fixed point costs, base scenario) > 0 for
     NAS100/NQ; SPX500/ES allowed to be cost-marginal but must improve on
     TRAIN-era net.
Failure of A1-A3 on both instruments kills the candidate family.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np
import pandas as pd

from vwapresearch.ingest import OUT_ROOT
from vwapresearch import backtest, candidates, stats, registry
from vwapresearch.config import split_of, COSTS, DATASET_COSTBOOK

RES = os.path.join(os.path.dirname(__file__), "..", "results", "phase5")
os.makedirs(RES, exist_ok=True)

SPEC = dict(stop_sigma=2.5, target="vwap", time_stop=180, max_trades_day=6)
BASE = lambda e: (e["level"] == 2.0) & (e["ny_minute"] >= 450) & (e["ny_minute"] < 570)
CANDS = {
    "PREFADE-S": BASE,
    "PREFADE-F": lambda e: BASE(e) & (e["speed5"].abs() < 0.9),
}


def report(tr, cost):
    s = candidates.summarize(tr)
    d = stats.daily_series(tr)
    yr = d.groupby(d.index.year).sum()
    exp_sg = (tr["pnl_pts"] / tr["sigma_entry"]).mean()
    net = tr["pnl_pts"] - 2 * cost
    return {
        "n": s["n"], "gross_exp_pts": s["expectancy_pts"], "gross_exp_sg": exp_sg,
        "gross_pf": s["profit_factor"], "gross_sharpe": s["sharpe_d"],
        "wr": s["win_rate"], "pos_years": int((yr > 0).sum()), "n_years": len(yr),
        "net_exp_pts": float(net.mean()),
        "net_total": float(net.sum()), "max_dd_gross": s["max_dd_pts"],
        "share_top5": s.get("share_top5"),
    }


def main():
    rows = []
    for name in ["NAS100", "SPX500"]:
        big, _ = DATASET_COSTBOOK[name]
        cost = COSTS[big]["base"]["per_side_pts"]
        for split in ["TRAIN", "VAL"]:
            fr = pd.read_parquet(os.path.join(OUT_ROOT, f"{name}_feat.parquet"))
            fr = fr[(split_of(fr.index) == split).values]
            ev = pd.read_parquet(os.path.join(OUT_ROOT, f"{name}_events_{split}.parquet"))
            for cn, flt in CANDS.items():
                spec = backtest.ExecSpec(cost_per_side_pts=0.0, **SPEC)
                tr = candidates.run_candidate(fr, ev, flt, spec, fade=True)
                tr.to_parquet(f"{RES}/{cn}_{name}_{split}_trades.parquet")
                r = report(tr, cost)
                r.update({"cand": cn, "dataset": name, "split": split})
                rows.append(r)
                yt = stats.yearly_table(tr)
                yt["net_exp"] = yt["expectancy"] - 2 * cost
                yt.to_csv(f"{RES}/{cn}_{name}_{split}_yearly.csv")
                if split == "VAL":
                    print(f"--- {cn} {name} VAL yearly:")
                    print(yt.round(3).to_string())
    df = pd.DataFrame(rows)[["cand", "dataset", "split", "n", "gross_exp_pts",
                             "gross_exp_sg", "gross_pf", "gross_sharpe", "wr",
                             "pos_years", "n_years", "net_exp_pts", "max_dd_gross"]]
    df.to_csv(f"{RES}/validation_summary.csv", index=False)
    print(df.round(3).to_string(index=False))
    for _, r in df[df["split"] == "VAL"].iterrows():
        ok = (r["gross_exp_sg"] >= 0.08, r["pos_years"] >= 3, r["gross_pf"] >= 1.10)
        registry.log("phase5", f"{r['cand']} VALIDATION", r["dataset"], "VAL",
                     "frozen params", int(r["n"]),
                     f"gross {r['gross_exp_sg']:+.3f}sg PF {r['gross_pf']:.2f} "
                     f"posY {r['pos_years']}/{r['n_years']} net {r['net_exp_pts']:+.3f}pts",
                     "PASS" if all(ok) else "FAIL",
                     f"criteria A1-A3: {ok}")


if __name__ == "__main__":
    main()
