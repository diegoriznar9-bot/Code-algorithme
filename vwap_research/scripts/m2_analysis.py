"""Mission 2 — event-level analysis (TRAIN only).

Answers, in order:
1. BASELINE: pure fade drift after L2/L2.5/L3 touches (no context).
2. Single-variable conditioning: retracement, efficiency, speed, duration,
   equilibrium quality, prior crosses, VWAP slope, touch number, hour.
3. KEY INTERACTION: equilibrium x directness x level.
All values are pure price drift toward VWAP in touch sigmas (fret_H) —
no stops/targets, so no execution or VWAP-catchup artifacts.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np
import pandas as pd
from vwapresearch.ingest import OUT_ROOT

RES = os.path.join(os.path.dirname(__file__), "..", "results", "m2")
os.makedirs(RES, exist_ok=True)
pd.set_option("display.width", 250)

OUTC = ["fret_30", "fret_60", "fret_120"]


def tab(ev, by, min_n=150):
    g = ev.groupby(by, observed=True)
    t = g[OUTC].mean().round(3)
    t.insert(0, "n", g.size())
    t["P_vwap60"] = g["hit_vwap_60"].mean().round(3)
    t["P_vwap120"] = g["hit_vwap_120"].mean().round(3)
    t["t_vwap_med"] = g["t_vwap"].median()
    return t


def main():
    md = ["# Mission 2 — analyse événementielle (TRAIN 2005-2014)", ""]
    evs = {}
    for name in ["NAS100", "SPX500"]:
        ev = pd.read_parquet(os.path.join(OUT_ROOT, f"{name}_impulse_TRAIN.parquet"))
        ev = ev[ev["imp_dur"].notna()].copy()
        # Paris hour from actual timestamps
        t = pd.DatetimeIndex(ev["time"])
        ev["paris_h"] = t.tz_convert("Europe/Paris").hour + t.tz_convert("Europe/Paris").minute / 60
        ev["paris_b"] = pd.cut(ev["paris_h"], [0, 7, 9, 12, 14, 15.5, 16, 17, 24],
                               labels=["nuit", "07-09", "09-12", "12-14", "14-1530",
                                       "1530-16", "16-17", "17-24"], right=False)
        evs[name] = ev
        md.append(f"## {name} — {len(ev):,} événements (impulsion définie)")

        md.append("### 1. BASELINE : dérive de fade par niveau (σ)")
        md.append(tab(ev, ["level"]).to_string()); md.append("")
        md.append("### … par niveau x heure Paris")
        md.append(tab(ev, ["paris_b", "level"]).to_string()); md.append("")

        e = ev.copy()
        md.append("### 2. Conditionnement une variable (tous niveaux >=2 confondus)")
        for var, nice in [("imp_retr_frac", "retracement max / mouvement (bas=direct)"),
                          ("imp_eff", "efficiency ratio (haut=direct)"),
                          ("imp_speed", "vitesse (σ/min)"),
                          ("imp_dur", "durée impulsion (min)"),
                          ("imp_amp_sg", "amplitude impulsion (σ)"),
                          ("imp_maxrun", "plus longue série directionnelle"),
                          ("eq120_inside", "équilibre: % du temps |m|<0.5σ (120min)"),
                          ("eq120_ncross", "équilibre: n cross VWAP (120min)"),
                          ("eq120_absm", "équilibre: |m| moyen (120min)"),
                          ("eq120_slope", "équilibre: |pente VWAP| (120min)"),
                          ("slope15", "pente VWAP au touch (signée x side)")]:
            x = e[var] if var != "slope15" else e["slope15"] * e["side"]
            try:
                q = pd.qcut(x, 5, duplicates="drop")
            except (ValueError, IndexError):
                continue
            e["_q"] = q
            t = tab(e, ["_q"])
            md.append(f"-- {nice} [{var}]")
            md.append(t.to_string()); md.append("")

        md.append("### 3. INTERACTION CLÉ : équilibre x directness")
        e["EQ"] = e["eq120_inside"] >= e["eq120_inside"].quantile(2 / 3)
        e["DIRECT"] = e["imp_retr_frac"] <= e["imp_retr_frac"].quantile(1 / 3)
        t = tab(e, ["EQ", "DIRECT", "level"])
        md.append(t.to_string()); md.append("")
        md.append("### 3b. même chose, premier touch uniquement (première vraie expansion)")
        t = tab(e[e["touch_no"] == 1], ["EQ", "DIRECT", "level"], min_n=50)
        md.append(t.to_string()); md.append("")
        md.append("### 3c. équilibre x vitesse (terciles)")
        e["FAST"] = e["imp_speed"] >= e["imp_speed"].quantile(2 / 3)
        t = tab(e, ["EQ", "FAST", "level"])
        md.append(t.to_string()); md.append("")

    open(os.path.join(RES, "m2_analysis.md"), "w").write("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
