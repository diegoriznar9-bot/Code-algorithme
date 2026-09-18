"""Mission 2, passe 2 — variantes raisonnables de définition du phénomène.

But: éviter de rejeter l'hypothèse sur UNE paramétrisation.  On croise:
  EQ:   a) eq120_inside>=0.5   b) eq120_ncross>=8 & slope<med
        c) eq180_absm<0.8      d) eq60_inside>=0.5
  DIR:  a) retr_frac<=0.15     b) imp_eff>=0.6
        c) imp_maxrun>=4       d) imp_speed tercile sup
  EXT:  niveaux 2.5/3.0 (le touch 2.0 sert de comparaison)
et on mesure la dérive pure de fade (σ) à 60/120/240 min, par instrument,
sur trois fenêtres: ALL, RTH (09:30-16 ET), PREOPEN->MORNING Paris 07-14.
Plus: effet de la réintégration (clôture du bar de signal revenue sous la
bande) au sein des événements EQ&DIR.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np
import pandas as pd
from vwapresearch.ingest import OUT_ROOT

RES = os.path.join(os.path.dirname(__file__), "..", "results", "m2")
pd.set_option("display.width", 250)

WINS = {
    "ALL": lambda e: pd.Series(True, index=e.index),
    "RTH": lambda e: (e["ny_minute"] >= 570) & (e["ny_minute"] < 960),
    "PAR0714": lambda e: (e["paris_h"] >= 7) & (e["paris_h"] < 14),
}


def defs(e):
    eq = {
        "eqA_inside120": e["eq120_inside"] >= 0.5,
        "eqB_cross&flat": (e["eq120_ncross"] >= 8) & (e["eq120_slope"] < e["eq120_slope"].median()),
        "eqC_absm180": e["eq180_absm"] < 0.8,
        "eqD_inside60": e["eq60_inside"] >= 0.5,
    }
    di = {
        "dirA_retr15": e["imp_retr_frac"] <= 0.15,
        "dirB_eff60": e["imp_eff"] >= 0.6,
        "dirC_run4": e["imp_maxrun"] >= 4,
        "dirD_fast": e["imp_speed"] >= e["imp_speed"].quantile(2 / 3),
    }
    return eq, di


def main():
    md = ["# Mission 2 passe 2 — matrice de définitions (TRAIN)", ""]
    loaded = {}
    for name in ["NAS100", "SPX500"]:
        ev = pd.read_parquet(os.path.join(OUT_ROOT, f"{name}_impulse_TRAIN.parquet"))
        ev = ev[ev["imp_dur"].notna()].copy()
        t = pd.DatetimeIndex(ev["time"])
        ev["paris_h"] = t.tz_convert("Europe/Paris").hour + t.tz_convert("Europe/Paris").minute / 60
        loaded[name] = ev

    for wlab, wfun in WINS.items():
        md.append(f"## Fenêtre {wlab}")
        rows = []
        for name, ev in loaded.items():
            w = ev[wfun(ev)]
            deep = w[w["level"] >= 2.5]
            eq, di = defs(w)
            for eqk, eqm in eq.items():
                for dik, dim in di.items():
                    sub = deep[eqm.reindex(deep.index, fill_value=False)
                               & dim.reindex(deep.index, fill_value=False)]
                    if len(sub) < 60:
                        rows.append({"instr": name, "EQ": eqk, "DIR": dik, "n": len(sub)})
                        continue
                    rows.append({
                        "instr": name, "EQ": eqk, "DIR": dik, "n": len(sub),
                        "f60": sub["fret_60"].mean(), "f120": sub["fret_120"].mean(),
                        "f240": sub["fret_240"].mean(),
                        "P120": sub["hit_vwap_120"].mean(),
                    })
        t = pd.DataFrame(rows)
        piv = t.pivot_table(index=["EQ", "DIR"], columns="instr",
                            values=["n", "f60", "f120", "f240"], aggfunc="first")
        md.append(piv.round(3).to_string())
        md.append("")

    md.append("## Réintégration au sein de EQ(A) & DIR(A), niveaux >=2.5, ALL")
    for name, ev in loaded.items():
        deep = ev[ev["level"] >= 2.5]
        eq, di = defs(ev)
        sub = deep[eq["eqA_inside120"].reindex(deep.index, fill_value=False)
                   & di["dirA_retr15"].reindex(deep.index, fill_value=False)].copy()
        sub["reint"] = sub["close_m"] * sub["side"] < sub["level"]
        g = sub.groupby("reint")[["fret_60", "fret_120", "fret_240"]].mean().round(3)
        g["n"] = sub.groupby("reint").size()
        md.append(f"### {name}")
        md.append(g.to_string())
        md.append("")

    md.append("## Contrôle: mêmes matrices au niveau 2.0 (non-extrême), fenêtre ALL")
    rows = []
    for name, ev in loaded.items():
        w = ev[ev["level"] == 2.0]
        eq, di = defs(ev)
        sub = w[eq["eqA_inside120"].reindex(w.index, fill_value=False)
                & di["dirA_retr15"].reindex(w.index, fill_value=False)]
        rows.append({"instr": name, "n": len(sub),
                     "f60": sub["fret_60"].mean(), "f120": sub["fret_120"].mean(),
                     "f240": sub["fret_240"].mean()})
    md.append(pd.DataFrame(rows).round(3).to_string(index=False))

    out = "\n".join(md)
    open(os.path.join(RES, "m2_analysis2.md"), "w").write(out)
    print(out)


if __name__ == "__main__":
    main()
