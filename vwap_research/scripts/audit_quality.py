"""Data-quality audit: coverage, gaps, holidays, suspicious bars.

Writes results/data_audit.md.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import pandas as pd
import numpy as np
from vwapresearch.ingest import OUT_ROOT

RES = os.path.join(os.path.dirname(__file__), "..", "results")
os.makedirs(RES, exist_ok=True)

lines = ["# Data audit", ""]
for name in ["NAS100", "SPX500", "NAS100_2026", "SPX500_2026"]:
    df = pd.read_parquet(os.path.join(OUT_ROOT, f"{name}_m1.parquet"))
    ny = df.index.tz_convert("America/New_York")
    d = pd.DataFrame({"v": df["volume"].values, "c": df["close"].values}, index=ny)
    lines.append(f"## {name}")
    lines.append(f"- rows: {len(df):,} ; span {ny[0]} .. {ny[-1]}")
    # per-year row counts and coverage vs theoretical ~ 23h * 60 * 5.5d/wk
    per_year = d.groupby(d.index.year)["v"].agg(["count", "sum"])
    per_year["rows/day"] = (per_year["count"] /
        d.groupby(d.index.year).apply(lambda x: x.index.normalize().nunique()))
    lines.append("")
    lines.append("| year | rows | mean rows/traded day | tick vol sum |")
    lines.append("|---|---|---|---|")
    for y, r in per_year.iterrows():
        lines.append(f"| {y} | {int(r['count']):,} | {r['rows/day']:.0f} | {int(r['sum']):,} |")
    # gaps > 90 min excluding weekend Fri17-Sun18 ET
    ts = d.index
    diffs = ts.to_series().diff()
    gap = diffs[diffs > pd.Timedelta("90min")]
    # classify weekend gaps: gap start Friday>=16:00 or Saturday
    n_weekend = 0; big = []
    for end_time, delta in gap.items():
        start_time = end_time - delta
        if (start_time.dayofweek == 4 and start_time.hour >= 16) or start_time.dayofweek == 5:
            n_weekend += 1
        else:
            big.append((start_time, end_time, delta))
    lines.append(f"- non-weekend gaps >90min: {len(big)} (weekend gaps: {n_weekend})")
    big_sorted = sorted(big, key=lambda x: -x[2])[:12]
    for s, e, dl in big_sorted:
        lines.append(f"    - {s} -> {e}  ({dl})")
    # suspicious bars: 1-min |log ret| > 2%
    lr = np.abs(np.log(d["c"]).diff())
    n_ext = int((lr > 0.02).sum())
    lines.append(f"- 1-min |log return| > 2%: {n_ext} bars; max = {lr.max()*100:.2f}% at {lr.idxmax()}")
    # zero-volume bars
    lines.append(f"- zero/negative tick-volume bars: {int((d['v']<=0).sum())}")
    lines.append("")

open(os.path.join(RES, "data_audit.md"), "w").write("\n".join(lines))
print("\n".join(lines))
