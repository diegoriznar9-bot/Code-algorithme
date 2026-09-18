"""Mission 2 — build enriched impulse-event tables (TRAIN only at this stage;
VAL and VAULT tables are built later, at their single read points)."""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import pandas as pd
from vwapresearch.ingest import OUT_ROOT
from vwapresearch import impulse

for name in ["NAS100", "SPX500"]:
    t0 = time.time()
    ev = impulse.build(name, "TRAIN", OUT_ROOT)
    out = os.path.join(OUT_ROOT, f"{name}_impulse_TRAIN.parquet")
    ev.to_parquet(out)
    n_imp = ev["imp_dur"].notna().sum()
    print(f"{name}: {len(ev):,} touch events L>=2, {n_imp:,} with defined impulse "
          f"({time.time()-t0:.0f}s) -> {out}")
