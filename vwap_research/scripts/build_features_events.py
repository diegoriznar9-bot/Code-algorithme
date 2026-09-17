"""Build feature frames and touch-event tables for all datasets.

Events are saved split by TRAIN / VAL / VAULT.  Exploration scripts read
ONLY the TRAIN files; candidate validation reads VAL; the VAULT files live
under clean/vault/ and are read exclusively by scripts/open_vault.py.
"""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import pandas as pd

from vwapresearch.ingest import OUT_ROOT
from vwapresearch import features, events
from vwapresearch.config import split_of

VAULT_DIR = os.path.join(OUT_ROOT, "vault")
os.makedirs(VAULT_DIR, exist_ok=True)

for name in ["NAS100", "SPX500", "NAS100_2026", "SPX500_2026"]:
    t0 = time.time()
    m1 = pd.read_parquet(os.path.join(OUT_ROOT, f"{name}_m1.parquet"))
    fr = features.build_frame(m1)
    fr.to_parquet(os.path.join(OUT_ROOT, f"{name}_feat.parquet"))
    ev = events.extract_touches(fr)
    ev["split"] = split_of(pd.DatetimeIndex(ev["time"])).values
    if name.endswith("_2026"):
        ev["split"] = "VAULT"          # entire 2026 slice is holdout
    for sp, gg in ev.groupby("split"):
        if sp == "VAULT":
            gg.to_parquet(os.path.join(VAULT_DIR, f"{name}_events_VAULT.parquet"))
        else:
            gg.to_parquet(os.path.join(OUT_ROOT, f"{name}_events_{sp}.parquet"))
    print(f"{name}: frame {len(fr):,} rows, events {len(ev):,} "
          f"({dict(ev['split'].value_counts())}) in {time.time()-t0:.0f}s")
