"""Empirical timezone audit of raw Oanda naive timestamps.

Method: the US cash-equity open (09:30 America/New_York) produces the largest
systematic spike in 1-minute activity (tick volume and |return|).  We locate
that spike separately in winter (Jan-Feb, EST) and summer (Jun-Jul, EDT)
months on the NAIVE timestamps:

- true America/New_York stamps -> spike at 09:30 in BOTH seasons
- UTC stamps                   -> 14:30 winter / 13:30 summer
- fixed EST (UTC-5, histdata)  -> 09:30 winter / 08:30 summer
- Europe/London                -> 14:30 winter / 14:30 summer
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import pandas as pd
import numpy as np
from vwapresearch.ingest import load_oanda_raw

for inst in ["NAS100_USD", "SPX500_USD"]:
    df = load_oanda_raw(inst)
    df["ret"] = np.abs(np.log(df["close"]).diff())
    df["mod"] = df.index.hour * 60 + df.index.minute
    for label, months in [("winter(Jan-Feb)", [1, 2]), ("summer(Jun-Jul)", [6, 7])]:
        sub = df[df.index.month.isin(months)]
        by_min_v = sub.groupby("mod")["volume"].mean()
        by_min_r = sub.groupby("mod")["ret"].mean()
        top_v = by_min_v.sort_values(ascending=False).head(4)
        top_r = by_min_r.sort_values(ascending=False).head(4)
        fmt = lambda s: ", ".join(f"{m//60:02d}:{m%60:02d}" for m in s.index)
        print(f"{inst} {label}: top volume minutes: {fmt(top_v)} | top |ret| minutes: {fmt(top_r)}")
