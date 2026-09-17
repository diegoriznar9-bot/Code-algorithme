"""PHASE 1 — descriptive cartography of VWAP band-touch behaviour.

READS ONLY TRAIN EVENTS (2005-2014).  Produces results/phase1/*.csv and a
summary markdown.  No strategy, no optimization here: base rates and
conditional rates with sample sizes.

Edge proxy used throughout ("rev1s"): expected outcome, in sigmas, of the
canonical fade entered at next-bar open with a 1.0σ stop and dynamic-VWAP
target within 240 min: +reward if VWAP reached first (reward = |entry-vwap|
at touch in σ ≈ level), -1.0 if the stop is hit first, 0 contribution
(censored) if neither within horizon.  This is a screening statistic only;
real backtests come in phase 3.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np
import pandas as pd
from vwapresearch.ingest import OUT_ROOT

RES = os.path.join(os.path.dirname(__file__), "..", "results", "phase1")
os.makedirs(RES, exist_ok=True)
pd.set_option("display.width", 200)


def load_train(name):
    ev = pd.read_parquet(os.path.join(OUT_ROOT, f"{name}_events_TRAIN.parquet"))
    ev["entry_dist_sigma"] = np.abs(ev["entry"] - ev["vw"]) / ev["sg"]
    # screening edge in sigmas (censored -> NaN)
    ev["rev1s"] = np.where(ev["stopfirst_1.0"] == True, -1.0,
                   np.where(ev["stopfirst_1.0"] == False, ev["entry_dist_sigma"], np.nan))
    # ET hour bucket
    ev["hour_et"] = ev["ny_minute"] // 60
    ev["tod"] = pd.cut(ev["ny_minute"],
        bins=[0, 240, 480, 570, 600, 630, 690, 780, 900, 960, 1020, 1440],
        labels=["00-04", "04-08", "08-0930", "0930-10", "10-1030", "1030-1130",
                "1130-13", "13-15", "15-16", "16-17", "17-24"], right=False)
    return ev


def cell_table(ev, by, min_n=100):
    g = ev.groupby(by, observed=True)
    tab = pd.DataFrame({
        "n": g.size(),
        "P_vwap_30": g["hit_vwap_30"].mean(),
        "P_vwap_60": g["hit_vwap_60"].mean(),
        "P_vwap_120": g["hit_vwap_120"].mean(),
        "med_t_vwap": g["t_vwap"].median(),
        "P_stopfirst_1s": g["stopfirst_1.0"].mean(),
        "rev1s_mean": g["rev1s"].mean(),
        "mae60_med_sg": (g.apply(lambda x: (x["mae_60"] / x["sg_pts"]).median(), include_groups=False)),
        "mfe60_med_sg": (g.apply(lambda x: (x["mfe_60"] / x["sg_pts"]).median(), include_groups=False)),
    })
    return tab


def main():
    md = ["# Phase 1 — descriptive results (TRAIN 2005-2014 only)", ""]
    for name in ["NAS100", "SPX500"]:
        ev = load_train(name)
        md.append(f"## {name}  ({len(ev):,} touch events)")
        # 1. base rates by level & side
        t = cell_table(ev, ["level", "side"])
        t.to_csv(f"{RES}/{name}_base_level_side.csv")
        md += ["", f"### Base rates by level & side", t.round(3).to_string(), ""]
        # 2. by time of day (L2 only, both sides)
        e2 = ev[ev["level"] == 2.0]
        t = cell_table(e2, ["tod", "side"])
        t.to_csv(f"{RES}/{name}_L2_tod.csv")
        md += [f"### L2 by time of day", t.round(3).to_string(), ""]
        # 3. by touch number
        e2b = e2.copy(); e2b["touch_bucket"] = np.minimum(e2b["touch_no"], 4)
        t = cell_table(e2b, ["touch_bucket", "side"])
        t.to_csv(f"{RES}/{name}_L2_touchno.csv")
        md += [f"### L2 by touch number (4 = 4+)", t.round(3).to_string(), ""]
        # 4. by slope quintile
        e2c = e2.dropna(subset=["slope15"]).copy()
        e2c["slope_q"] = pd.qcut(e2c["slope15"], 5, labels=["Q1_dn", "Q2", "Q3_flat", "Q4", "Q5_up"])
        t = cell_table(e2c, ["slope_q", "side"])
        t.to_csv(f"{RES}/{name}_L2_slope.csv")
        md += [f"### L2 by VWAP slope15 quintile", t.round(3).to_string(), ""]
        # 5. signed slope (slope in direction of the touch side)
        e2d = e2.dropna(subset=["slope15"]).copy()
        e2d["slope_signed"] = e2d["slope15"] * e2d["side"]
        e2d["sslope_q"] = pd.qcut(e2d["slope_signed"], 5,
                                  labels=["against", "q2", "q3", "q4", "with"])
        t = cell_table(e2d, ["sslope_q"])
        t.to_csv(f"{RES}/{name}_L2_signedslope.csv")
        md += [f"### L2 by SIGNED slope (touch in slope direction = 'with')",
               t.round(3).to_string(), ""]
        # 6. by n_cross
        e2e = e2.copy(); e2e["cross_b"] = pd.cut(e2e["n_cross"], [-1, 0, 2, 5, 10, 1e9],
                                                 labels=["0", "1-2", "3-5", "6-10", ">10"])
        t = cell_table(e2e, ["cross_b"])
        t.to_csv(f"{RES}/{name}_L2_ncross.csv")
        md += [f"### L2 by prior VWAP crosses", t.round(3).to_string(), ""]
        # 7. by arrival speed
        e2f = e2.dropna(subset=["speed5"]).copy()
        e2f["speed_q"] = pd.qcut(e2f["speed5"].abs(), 5,
                                 labels=["slow", "q2", "q3", "q4", "fast"])
        t = cell_table(e2f, ["speed_q"])
        t.to_csv(f"{RES}/{name}_L2_speed.csv")
        md += [f"### L2 by |arrival speed| quintile", t.round(3).to_string(), ""]
        # 8. weekly vwap distance
        e2g = e2.dropna(subset=["dw"]).copy()
        e2g["dw_signed"] = e2g["dw"] * e2g["side"]     # + = touch on far side of weekly
        e2g["dw_q"] = pd.qcut(e2g["dw_signed"], 5, labels=["opp", "q2", "q3", "q4", "same"])
        t = cell_table(e2g, ["dw_q"])
        t.to_csv(f"{RES}/{name}_L2_dw.csv")
        md += [f"### L2 by signed daily-weekly VWAP distance", t.round(3).to_string(), ""]
        # 9. sequences: days where +L2 and -L2 both touched
        piv = ev[ev["level"] == 2.0].groupby(["session_day", "side"]).size().unstack(fill_value=0)
        both = piv[(piv.get(1, 0) > 0) & (piv.get(-1, 0) > 0)]
        md += [f"### Days with both +L2 and -L2 touched: {len(both)} / {piv.shape[0]} L2-days", ""]
        e2h = e2.copy()
        prior_opp = []
        seen = {}
        for _, row in e2h.sort_values("time").iterrows():
            key = row["session_day"]
            s = seen.setdefault(key, set())
            prior_opp.append(-row["side"] in s)
            s.add(row["side"])
        e2h["prior_opp_touch"] = prior_opp
        t = cell_table(e2h, ["prior_opp_touch"])
        t.to_csv(f"{RES}/{name}_L2_prioropp.csv")
        md += [f"### L2 conditioned on opposite L2 already touched today",
               t.round(3).to_string(), ""]
        # 10. hour heatmap for all levels: P(vwap60)
        hm = ev.pivot_table(index="tod", columns="level", values="hit_vwap_60",
                            aggfunc="mean", observed=True)
        hn = ev.pivot_table(index="tod", columns="level", values="hit_vwap_60",
                            aggfunc="count", observed=True)
        hm.to_csv(f"{RES}/{name}_heat_tod_level_P60.csv")
        hn.to_csv(f"{RES}/{name}_heat_tod_level_N.csv")
        md += ["### Heatmap P(vwap within 60m) tod x level", hm.round(3).to_string(),
               "counts:", hn.to_string(), ""]
    open(os.path.join(RES, "phase1_summary.md"), "w").write("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
