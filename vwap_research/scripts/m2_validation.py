"""Mission 2 — VALIDATION (2015-2018), lecture unique, règles gelées.

Candidats verrouillés AVANT lecture de VAL (2026-09-18) :
  M2-CTX  : touch bande 2.5σ session-VWAP, 09:30-13:30 ET,
            eq120_slope < 0.75 (VWAP plate sur les 2h avant impulsion)
            imp_maxrun >= 4 (impulsion soutenue),
            fade, stop 2.5σ, cible VWAP dynamique, time-stop 240, max 6/j.
  M2-BASE : idem SANS les deux conditions de contexte (baseline §24).

CRITÈRES pré-enregistrés (par instrument, bruts) :
  A1 exp_sg >= +0.08 ; A2 >= 3/4 années positives ; A3 PF >= 1.10.
Attente préalable notée : décroissance probable (précédent mission 1) ;
l'apport du contexte est déjà incohérent inter-instruments en TRAIN.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import pandas as pd

from vwapresearch.ingest import OUT_ROOT
from vwapresearch import backtest, candidates, stats, registry, impulse
from vwapresearch.config import split_of

RES = os.path.join(os.path.dirname(__file__), "..", "results", "m2")

SPEC = backtest.ExecSpec(stop_sigma=2.5, target="vwap", time_stop=240,
                         cost_per_side_pts=0.0, max_trades_day=6)
CANDS = {
    "M2-CTX": lambda e: ((e["level"] == 2.5) & (e["ny_minute"] >= 570) & (e["ny_minute"] < 810)
                         & (e["eq120_slope"] < 0.75) & (e["imp_maxrun"] >= 4)),
    "M2-BASE": lambda e: (e["level"] == 2.5) & (e["ny_minute"] >= 570) & (e["ny_minute"] < 810),
}

rows = []
for name in ["NAS100", "SPX500"]:
    vev_path = os.path.join(OUT_ROOT, f"{name}_impulse_VAL.parquet")
    if not os.path.exists(vev_path):
        ev = impulse.build(name, "VAL", OUT_ROOT)
        ev.to_parquet(vev_path)
    ev = pd.read_parquet(vev_path)
    ev = ev[ev["imp_dur"].notna()]
    fr = pd.read_parquet(os.path.join(OUT_ROOT, f"{name}_feat.parquet"))
    fr = fr[(split_of(fr.index) == "VAL").values]
    for cn, flt in CANDS.items():
        tr = candidates.run_candidate(fr, ev, flt, SPEC, fade=True)
        tr.to_parquet(f"{RES}/{cn}_{name}_VAL_trades.parquet")
        d = stats.daily_series(tr)
        yr = d.groupby(d.index.year).sum()
        esg = (tr["pnl_pts"] / tr["sigma_entry"]).mean()
        pf = stats.trade_metrics(tr["pnl_pts"])["profit_factor"]
        r = {"cand": cn, "instr": name, "n": len(tr), "exp_sg": esg,
             "exp_pts": tr["pnl_pts"].mean(), "pf": pf,
             "sharpe": stats.sharpe_daily(d), "posY": int((yr > 0).sum()),
             "nY": len(yr), "yearly": dict(zip(yr.index, yr.round(0).astype(int)))}
        rows.append(r)
        ok = (esg >= 0.08, r["posY"] >= 3, pf >= 1.10)
        registry.log("m2-VAL", f"{cn} validation unique", name, "VAL", "gelé",
                     len(tr), f"exp_sg {esg:+.3f} PF {pf:.2f} posY {r['posY']}/{r['nY']}",
                     "PASS" if all(ok) else "FAIL", f"A1-A3: {ok}")
df = pd.DataFrame(rows)
df.to_csv(f"{RES}/m2_validation.csv", index=False)
print(df.drop(columns="yearly").round(3).to_string(index=False))
for r in rows:
    print(r["cand"], r["instr"], "par an:", r["yearly"])
