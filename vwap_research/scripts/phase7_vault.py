"""PHASE 7 — THE VAULT.  Run exactly once, on frozen rules.

Rules frozen (identical to phase5, registered before VAL was read):
  PREFADE-S : session-VWAP L2 touch, 07:30-09:30 ET, fade, stop 2.5σ,
              dynamic VWAP target, time-stop 180 min, max 6/day, both sides.
  PREFADE-F : + |speed5| < 0.9.

Vault data: Oanda 2019-01-01 .. 2020-05-14, and getdata 2026-03..2026-09.
Pre-registered expectation (written before opening): the VAL result (alpha
decay) predicts ~zero or negative expectancy.  Whatever comes out is
recorded; nothing is tuned afterwards.  Any post-vault modification would
start a NEW strategy (mission §42) — none will be made.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np
import pandas as pd

from vwapresearch.ingest import OUT_ROOT
from vwapresearch import backtest, candidates, stats, registry
from vwapresearch.config import split_of, COSTS, DATASET_COSTBOOK

RES = os.path.join(os.path.dirname(__file__), "..", "results", "phase7_vault")
VAULT_DIR = os.path.join(OUT_ROOT, "vault")
os.makedirs(RES, exist_ok=True)

SPEC = dict(stop_sigma=2.5, target="vwap", time_stop=180, max_trades_day=6)
BASE = lambda e: (e["level"] == 2.0) & (e["ny_minute"] >= 450) & (e["ny_minute"] < 570)
CANDS = {
    "PREFADE-S": BASE,
    "PREFADE-F": lambda e: BASE(e) & (e["speed5"].abs() < 0.9),
}

SETS = [
    # (label, frame parquet, events parquet, frame filter, cost book)
    ("NAS100_vault_2019_20", "NAS100_feat.parquet", "vault/NAS100_events_VAULT.parquet", "VAULT", "NQ"),
    ("SPX500_vault_2019_20", "SPX500_feat.parquet", "vault/SPX500_events_VAULT.parquet", "VAULT", "ES"),
    ("NAS100_2026", "NAS100_2026_feat.parquet", "vault/NAS100_2026_events_VAULT.parquet", None, "NQ"),
    ("SPX500_2026", "SPX500_2026_feat.parquet", "vault/SPX500_2026_events_VAULT.parquet", None, "ES"),
]

rows = []
for label, fpq, epq, filt, cb in SETS:
    fr = pd.read_parquet(os.path.join(OUT_ROOT, fpq))
    if filt == "VAULT":
        fr = fr[(split_of(fr.index) == "VAULT").values]
    ev = pd.read_parquet(os.path.join(OUT_ROOT, epq))
    cost = COSTS[cb]["base"]["per_side_pts"]
    for cn, flt in CANDS.items():
        spec = backtest.ExecSpec(cost_per_side_pts=0.0, **SPEC)
        tr = candidates.run_candidate(fr, ev, flt, spec, fade=True)
        if len(tr) == 0:
            rows.append({"set": label, "cand": cn, "n": 0})
            continue
        tr.to_parquet(f"{RES}/{cn}_{label}_trades.parquet")
        s = candidates.summarize(tr)
        d = stats.daily_series(tr)
        yr = d.groupby(d.index.year).sum()
        exp_sg = (tr["pnl_pts"] / tr["sigma_entry"]).mean()
        rows.append({
            "set": label, "cand": cn, "n": s["n"],
            "gross_exp_pts": s["expectancy_pts"], "gross_exp_sg": exp_sg,
            "gross_pf": s["profit_factor"], "gross_sharpe": s["sharpe_d"],
            "wr": s["win_rate"], "net_exp_pts": s["expectancy_pts"] - 2 * cost,
            "pos_years": int((yr > 0).sum()), "n_years": len(yr),
            "max_dd": s["max_dd_pts"],
        })
df = pd.DataFrame(rows)
df.to_csv(f"{RES}/vault_results.csv", index=False)
print(df.round(3).to_string(index=False))
for _, r in df.iterrows():
    if r.get("n", 0):
        registry.log("phase7-VAULT", f"{r['cand']} vault opening (single, frozen)",
                     r["set"], "VAULT", "frozen", int(r["n"]),
                     f"gross {r['gross_exp_sg']:+.3f}sg PF {r['gross_pf']:.2f} net {r['net_exp_pts']:+.3f}pts",
                     "recorded", "no post-vault modification permitted")
