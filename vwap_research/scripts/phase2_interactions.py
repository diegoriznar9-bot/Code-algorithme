"""PHASE 2 — interaction analysis with time-of-day deconfounding (TRAIN only).

Everything in Phase 1 correlates with time of day (sigma grows, touches and
crosses accumulate, slope flattens).  Here each conditioning variable is
re-examined WITHIN fixed time windows, and the cost-viability of each window
is quantified (sigma in points vs realistic round-trip costs).
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np
import pandas as pd
from vwapresearch.ingest import OUT_ROOT

RES = os.path.join(os.path.dirname(__file__), "..", "results", "phase2")
os.makedirs(RES, exist_ok=True)
pd.set_option("display.width", 250)

WINDOWS = {
    "morning(0930-1130)": (570, 690),
    "midday(1130-1300)": (690, 780),
    "afternoon(1300-1530)": (780, 930),
    "preopen(0800-0930)": (480, 570),
    "evening(1800-2400ET)": (1080, 1440),
}


def load(name):
    ev = pd.read_parquet(os.path.join(OUT_ROOT, f"{name}_events_TRAIN.parquet"))
    ev["entry_dist_sigma"] = np.abs(ev["entry"] - ev["vw"]) / ev["sg"]
    ev["rev1s"] = np.where(ev["stopfirst_1.0"] == True, -1.0,
                   np.where(ev["stopfirst_1.0"] == False, ev["entry_dist_sigma"], np.nan))
    ev["slope_signed"] = ev["slope15"] * ev["side"]
    ev["speed_abs"] = ev["speed5"].abs()
    return ev


def tbl(ev, by):
    g = ev.groupby(by, observed=True)
    t = pd.DataFrame({
        "n": g.size(),
        "P60": g["hit_vwap_60"].mean(),
        "P120": g["hit_vwap_120"].mean(),
        "P_stop1s": g["stopfirst_1.0"].mean(),
        "rev1s": g["rev1s"].mean(),
        "sg_pts_med": g["sg_pts"].median(),
    })
    return t.round(3)


def main():
    md = ["# Phase 2 — interactions within time windows (TRAIN only)", ""]
    for name in ["NAS100", "SPX500"]:
        ev = load(name)
        e = ev[ev["level"].isin([1.5, 2.0, 2.5])].copy()
        md.append(f"## {name}")
        # cost viability: sigma in points by window (L2 events)
        md.append("### sigma (points, median) & implied L2->VWAP reward by window")
        rows = []
        for w, (a, b) in WINDOWS.items():
            sub = e[(e["ny_minute"] >= a) & (e["ny_minute"] < b) & (e["level"] == 2.0)]
            if len(sub) == 0:
                continue
            sgm = sub["sg_pts"].median()
            rows.append({"window": w, "n": len(sub), "sigma_pts_med": round(sgm, 2),
                         "reward2s_pts": round(2 * sgm, 2)})
        md.append(pd.DataFrame(rows).to_string(index=False)); md.append("")
        for w, (a, b) in WINDOWS.items():
            sub = e[(e["ny_minute"] >= a) & (e["ny_minute"] < b)].copy()
            if len(sub) < 500:
                continue
            md.append(f"### {w}  ({len(sub):,} events, L1.5/2/2.5)")
            md.append("by level x side:")
            md.append(tbl(sub, ["level", "side"]).to_string())
            sub["touch_b"] = np.minimum(sub["touch_no"], 3)
            md.append("by touch number (3=3+):")
            md.append(tbl(sub, ["touch_b"]).to_string())
            try:
                sub["sslope_q"] = pd.qcut(sub["slope_signed"], 4,
                                          labels=["against", "q2", "q3", "with"])
                md.append("by signed slope quartile:")
                md.append(tbl(sub, ["sslope_q"]).to_string())
            except ValueError:
                pass
            try:
                sub["speed_q"] = pd.qcut(sub["speed_abs"], 4,
                                         labels=["slow", "q2", "q3", "fast"])
                md.append("by |speed| quartile:")
                md.append(tbl(sub, ["speed_q"]).to_string())
            except ValueError:
                pass
            md.append("")
        # afternoon continuation check: MFE in trend direction after touch
        aft = e[(e["ny_minute"] >= 780) & (e["ny_minute"] < 930)].copy()
        aft["with_trend"] = aft["slope_signed"] > 0
        g = aft.groupby(["level", "with_trend"], observed=True)
        cont = pd.DataFrame({
            "n": g.size(),
            "P_novwap_120": 1 - g["hit_vwap_120"].mean(),
            # continuation excursion = MAE of the fade = move AWAY from vwap
            "cont60_med_sg": g.apply(lambda x: (x["mae_60"] / x["sg_pts"]).median(), include_groups=False),
            "rev60_med_sg": g.apply(lambda x: (x["mfe_60"] / x["sg_pts"]).median(), include_groups=False),
        })
        md.append("### Afternoon (13-15:30) continuation vs reversion excursions")
        md.append(cont.round(3).to_string()); md.append("")
    open(os.path.join(RES, "phase2_summary.md"), "w").write("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
