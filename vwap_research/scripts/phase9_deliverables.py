"""PHASE 9 — assemble CSV deliverables (mission §90)."""
import os, sys, json, glob
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np
import pandas as pd
from vwapresearch import stats

R = os.path.join(os.path.dirname(__file__), "..", "results")
D = os.path.join(R, "deliverables")
os.makedirs(D, exist_ok=True)

frames = []
for f in glob.glob(f"{R}/phase5/*_trades.parquet") + glob.glob(f"{R}/phase7_vault/*_trades.parquet"):
    base = os.path.basename(f).replace("_trades.parquet", "")
    cand = base.split("_")[0]
    rest = base[len(cand) + 1:]
    tr = pd.read_parquet(f)
    tr["candidate"] = cand
    tr["dataset_period"] = rest
    frames.append(tr)
allt = pd.concat(frames, ignore_index=True)
allt["t_signal"] = pd.to_datetime(allt["t_signal"], utc=True)
allt = allt.sort_values(["candidate", "dataset_period", "t_entry"])
allt.to_csv(f"{D}/all_trades.csv", index=False)

# daily pnl per candidate/dataset (gross pts)
d = (allt.groupby(["candidate", "dataset_period", "session_day"])["pnl_pts"]
     .sum().reset_index())
d.to_csv(f"{D}/daily_pnl.csv", index=False)

# monthly and annual
allt["ym"] = pd.to_datetime(allt["session_day"]).dt.to_period("M").astype(str)
allt["year"] = pd.to_datetime(allt["session_day"]).dt.year
allt["pnl_sg"] = allt["pnl_pts"] / allt["sigma_entry"]
m = allt.groupby(["candidate", "dataset_period", "ym"]).agg(
    trades=("pnl_pts", "count"), pnl_pts=("pnl_pts", "sum"),
    exp_pts=("pnl_pts", "mean"), exp_sg=("pnl_sg", "mean"))
m.to_csv(f"{D}/monthly_stats.csv")
y = allt.groupby(["candidate", "dataset_period", "year"]).agg(
    trades=("pnl_pts", "count"), pnl_pts=("pnl_pts", "sum"),
    exp_pts=("pnl_pts", "mean"), exp_sg=("pnl_sg", "mean"),
    win_rate=("pnl_pts", lambda x: (x > 0).mean()))
y.to_csv(f"{D}/annual_stats.csv")

# per-hour (signal ET half-hours)
allt["t_sig_ny"] = allt["t_signal"].dt.tz_convert("America/New_York")
allt["halfhour"] = allt["t_sig_ny"].dt.hour.astype(str) + ":" + \
    np.where(allt["t_sig_ny"].dt.minute < 30, "00", "30")
h = allt.groupby(["candidate", "halfhour"]).agg(
    trades=("pnl_pts", "count"), exp_pts=("pnl_pts", "mean"), exp_sg=("pnl_sg", "mean"))
h.to_csv(f"{D}/per_hour_stats.csv")

# per-side
s = allt.groupby(["candidate", "dataset_period", "side"]).agg(
    trades=("pnl_pts", "count"), exp_pts=("pnl_pts", "mean"), exp_sg=("pnl_sg", "mean"))
s.to_csv(f"{D}/per_side_stats.csv")

# MAE/MFE
allt[["candidate", "dataset_period", "t_entry", "side", "mae", "mfe", "pnl_pts"]].to_csv(
    f"{D}/mae_mfe.csv", index=False)

# equity + drawdown (sigma units, PREFADE-S, both datasets pooled per instrument)
for instr in ["NAS100", "SPX500"]:
    t = allt[(allt["candidate"] == "PREFADE-S") &
             (allt["dataset_period"].str.startswith(instr))].sort_values("t_entry")
    dn = t.groupby("session_day")["pnl_sg"].sum()
    dn.index = pd.to_datetime(dn.index)
    eq = dn.sort_index().cumsum()
    dd = eq - eq.cummax()
    pd.DataFrame({"equity_sg": eq, "drawdown_sg": dd}).to_csv(f"{D}/equity_{instr}.csv")

# final configuration
config = {
    "note": "Aucune stratégie n'est recommandée pour le trading réel (voir rapport).",
    "candidates_locked": {
        "PREFADE-S": {
            "instruments_researched": ["NQ/MNQ via NAS100 CFD proxy", "ES/MES via SPX500 CFD proxy"],
            "session": "CME futures day 18:00 ET -> 17:00 ET",
            "timezone": "America/New_York",
            "timeframe": "1 minute",
            "vwap": "session VWAP anchored 18:00 ET, price=(H+L+C)/3, weights=tick volume",
            "bands": "vwap +/- L * sigma, sigma = sqrt(cum w var of price around running vwap)",
            "setup": "first/any touch of the 2.0 sigma band between 07:30:00 and 09:29:59 ET",
            "entry": "market at next 1-min open, direction = toward VWAP (fade)",
            "stop": "2.5 * sigma(at signal) from entry, fixed",
            "target": "dynamic session VWAP (limit re-priced each bar)",
            "time_stop": "180 minutes",
            "eod_exit": "16:55 ET (never reached given time-stop)",
            "position_size": "1 contract (research), no scale-in",
            "max_trades_day": 6, "daily_loss_limit": "none in research build",
            "no_trade": "outside 07:30-09:30 ET window; sigma warmup < 25 bars",
        },
        "PREFADE-F": "PREFADE-S + filter |speed5| < 0.9 (arrivee lente)",
    },
    "splits": {"TRAIN": "2005-2014", "VAL": "2015-2018",
               "VAULT": "2019-01..2020-05-14 + 2026-03..2026-09"},
    "costs_base_per_side_pts": {"NQ": 0.315, "MNQ": 0.51, "ES": 0.276, "MES": 0.354},
}
json.dump(config, open(f"{D}/final_config.json", "w"), indent=1, ensure_ascii=False)
print("deliverables:", sorted(os.listdir(D)))
