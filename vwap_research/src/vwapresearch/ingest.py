"""Ingestion of raw 1-minute data into clean, timezone-aware parquet.

Sources
-------
1. Oanda CFD M1 bars (via FutureSharks/financial-data snapshot, commit recorded
   in rawdata/financial-data.commit):
   - NAS100_USD : Nasdaq-100 index CFD, proxy for NQ/MNQ
   - SPX500_USD : S&P 500 index CFD, proxy for ES/MES
   Columns: time, close, high, low, open, volume  (volume = tick count)
   Coverage: 2005-01 .. 2020-05.  Timestamps: naive; timezone determined
   empirically (see audit script) and asserted here.

2. getdata.finance free samples (2026-03 .. 2026-09), UTC timestamps,
   volume of unknown exact provenance (CFD feed).  Used ONLY as a modern,
   source-disjoint sanity slice, never for discovery.

Output: parquet files with a tz-aware UTC DatetimeIndex and columns
open, high, low, close, volume (float32/int32).
"""
from __future__ import annotations

import glob
import os

import numpy as np
import pandas as pd

RAW_ROOT = os.environ.get(
    "VWAP_RAW_ROOT",
    "/tmp/claude-0/-home-user-Code-algorithme/52b9c537-fcdc-5aa1-b44b-e4820fe5c205/scratchpad/rawdata",
)
OUT_ROOT = os.environ.get(
    "VWAP_DATA_ROOT",
    "/tmp/claude-0/-home-user-Code-algorithme/52b9c537-fcdc-5aa1-b44b-e4820fe5c205/scratchpad/clean",
)

OANDA_INSTRUMENTS = {"NAS100_USD": "NAS100", "SPX500_USD": "SPX500"}

# Established by scripts/audit_timezone.py: on the NAIVE timestamps the US
# cash-open activity spike sits at 14:30 in winter months and 13:30 in summer
# months, exactly the UTC clock times of 09:30 America/New_York under EST/EDT.
# Hence the raw stamps are UTC.  See results/data_audit.md.
OANDA_TZ = "UTC"


def load_oanda_raw(instrument: str) -> pd.DataFrame:
    files = sorted(glob.glob(os.path.join(RAW_ROOT, "oanda", instrument, "*", "*.csv")))
    if not files:
        raise FileNotFoundError(f"no raw files for {instrument} under {RAW_ROOT}")
    parts = [pd.read_csv(f) for f in files]
    df = pd.concat(parts, ignore_index=True)
    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values("time").drop_duplicates(subset="time", keep="last")
    df = df.set_index("time")[["open", "high", "low", "close", "volume"]]
    return df


def clean_oanda(instrument: str, tz: str = OANDA_TZ) -> pd.DataFrame:
    df = load_oanda_raw(instrument)
    df.index = df.index.tz_localize(tz)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    # Basic sanity: positive prices, high>=low, high>=open/close>=low (tolerate
    # tiny float noise), volume >= 0.
    bad = (
        (df["high"] < df["low"])
        | (df["low"] <= 0)
        | (df["volume"] < 0)
        | (df["high"] < df[["open", "close"]].max(axis=1) - 1e-9)
        | (df["low"] > df[["open", "close"]].min(axis=1) + 1e-9)
    )
    df = df[~bad]
    for c in ["open", "high", "low", "close"]:
        df[c] = df[c].astype("float64")
    df["volume"] = df["volume"].astype("int64")
    return df


def load_getdata(sample: str) -> pd.DataFrame:
    path = os.path.join(RAW_ROOT, "getdata", f"{sample}_1m.csv")
    df = pd.read_csv(path)
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    df = (
        df.set_index("datetime")[["open", "high", "low", "close", "volume"]]
        .sort_index()
    )
    df = df[~df.index.duplicated(keep="last")]
    df["volume"] = df["volume"].astype("int64")
    return df


def build_all() -> None:
    os.makedirs(OUT_ROOT, exist_ok=True)
    for src, name in OANDA_INSTRUMENTS.items():
        df = clean_oanda(src)
        out = os.path.join(OUT_ROOT, f"{name}_m1.parquet")
        df.to_parquet(out)
        print(f"{name}: {len(df):,} rows {df.index[0]} .. {df.index[-1]} -> {out}")
    for sample in ["NAS100", "SPX500"]:
        df = load_getdata(sample)
        out = os.path.join(OUT_ROOT, f"{sample}_2026_m1.parquet")
        df.to_parquet(out)
        print(f"{sample}_2026: {len(df):,} rows {df.index[0]} .. {df.index[-1]} -> {out}")


if __name__ == "__main__":
    build_all()
