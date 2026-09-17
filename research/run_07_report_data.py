"""Étape 7 : prépare le JSON compact consommé par le rapport visuel (HTML/PDF)."""
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT.parent))
from research.src import config, data, strategy, metrics, entries, adaptive

OUT = ROOT / "output"
daily = data.load_daily(ROOT)
w = data.weekly_frame(daily)
ma156 = entries.sma(w, 156)
cost = sum(config.COST_SCENARIOS["central"].values())
COMMON_START = w.index[207]

BOUNDED = dict(d1_bounds=(0.12, 0.20), d2_bounds=(0.24, 0.40), min_ratio=2.0)
d1b, d2b = adaptive.thresholds(w, 0.5, 1.0, params=BOUNDED)
res_act = strategy.run_strategy(w, ma=ma156, exit_levels=[0.20, 0.40], cost_per_side=cost)
res_born = strategy.run_strategy(w, ma=ma156, exit_levels=[d1b, d2b], cost_per_side=cost)
res_bh = strategy.buy_and_hold(w, cost_per_side=cost, start=COMMON_START)

def ser(s, nd=4, start=None):
    s = s.loc[start:] if start else s
    return [None if pd.isna(v) else round(float(v), nd) for v in s.values]

def dates(ix, start=None):
    ix = ix[ix >= start] if start else ix
    return [d.strftime("%Y-%m-%d") for d in ix]

J = {}
J["meta"] = {
    "data_start": str(w.index[0].date()), "data_end": str(w.index[-1].date()),
    "last_close": round(float(w["close"].iloc[-1]), 0),
    "common_start": str(COMMON_START.date()),
    "halvings": config.HALVINGS,
}

# --- série principale ---
J["px"] = {"d": dates(w.index), "close": ser(w["close"], 2), "sma": ser(ma156, 2)}

# --- segments de position (actuelle) : pleine / demi ---
segs, cur = [], None
for t in res_act.trades:
    if t.side == "buy":
        cur = {"start": str(t.date.date()), "kind": "full"}
    elif cur:
        if t.reason == "stop_partial":
            segs.append({**cur, "end": str(t.date.date())})
            cur = {"start": str(t.date.date()), "kind": "half"}
        else:
            segs.append({**cur, "end": str(t.date.date())}); cur = None
if cur:
    segs.append({**cur, "end": J["meta"]["data_end"]})
J["segments"] = segs
J["trades"] = [{"d": str(t.date.date()), "side": t.side, "p": round(t.price, 2),
                "r": t.reason} for t in res_act.trades]

# --- courbes de capital & drawdowns (base 1 au départ commun) ---
def norm(res):
    eq = res.equity.loc[COMMON_START:]
    return eq / eq.iloc[0]
eq = {k: norm(r) for k, r in [("bh", res_bh), ("act", res_act), ("born", res_born)]}
J["equity"] = {"d": dates(w.index, COMMON_START),
               **{k: ser(v, 3) for k, v in eq.items()},
               "dd": {k: ser(metrics.drawdown(v) * 100, 1) for k, v in eq.items()}}

# --- volatilité / régimes ---
amp = pd.read_csv(OUT / "amplitude_measures.csv", index_col=0, parse_dates=True)
ssl = pd.read_csv(OUT / "statespace_level.csv", index_col=0, parse_dates=True)
prob = pd.read_csv(OUT / "markov_prob_high_vol.csv", index_col=0, parse_dates=True).iloc[:, 0]
J["vol"] = {"d": dates(amp.index), "rv52": ser(amp["rv52"] * 100, 1),
            "level_d": dates(ssl.index), "level": ser(np.exp(ssl["niveau_lisse"]) * 100, 1),
            "prob_d": dates(prob.index), "prob": ser(prob * 100, 1)}

halv = pd.to_datetime(config.HALVINGS)
amp["cyc"] = np.searchsorted(halv, amp.index)
J["cycles_vol"] = {
    "labels": ["pré-2012", "2012-16", "2016-20", "2020-24", "2024-"],
    "rv52_med": [round(float(x) * 100, 1) for x in amp.groupby("cyc")["rv52"].median()],
    "semivol_med": [round(float(x) * 100, 1) for x in amp.groupby("cyc")["semivol_down52"].median()],
}
cyc = pd.read_csv(OUT / "cycles_episodes.csv")
J["episodes"] = [{"peak_y": str(r.sommet)[:7], "dd": round(-r.drawdown * 100, 1),
                  "mult": round(r.multiple_creux_prec, 1)} for r in cyc.itertuples()]

# --- OOS vol ---
preds = pd.read_csv(OUT / "amplitude_oos_preds.csv", index_col=0, parse_dates=True)
targ = pd.read_csv(OUT / "amplitude_oos_target.csv", index_col=0, parse_dates=True)["target_fwd26"]
sel = preds["M2_exp_temps"].dropna().index
J["oos"] = {"d": dates(sel),
            "obs": ser(np.exp(targ.reindex(sel)) * 100, 1),
            "m2": ser(np.exp(preds.loc[sel, "M2_exp_temps"]) * 100, 1),
            "m5": ser(np.exp(preds.loc[sel, "M5_cycle"]) * 100, 1),
            "m1": ser(np.exp(preds.loc[sel, "M1_marche_aleatoire"]) * 100, 1)}
J["rmse"] = json.loads(pd.read_csv(OUT / "amplitude_oos_rmse.csv", index_col=0).round(3).to_json())

# --- seuils adaptatifs ---
J["thr"] = {"d": dates(d1b.dropna().index), "d1": ser(d1b.dropna() * 100, 1),
            "d2": ser(d2b.dropna() * 100, 1)}

# --- heatmap ---
heat = pd.read_csv(OUT / "heatmap_ma_d1_calmar.csv", index_col=0)
J["heat"] = {"ma": [int(i) for i in heat.index],
             "d1": [round(float(c) * 100, 1) for c in heat.columns],
             "z": [[None if pd.isna(v) else round(float(v), 2) for v in row] for row in heat.values]}

# --- walk-forward 2018+ ---
wf = pd.read_csv(OUT / "equity_walkforward_adaptive.csv", index_col=0, parse_dates=True).iloc[:, 0]
def norm18(s):
    s = s.loc["2018-01-01":]
    return s / s.iloc[0]
J["wf"] = {"d": dates(w.index[w.index >= "2018-01-01"]),
           "bh": ser(norm18(eq["bh"]), 3), "act": ser(norm18(eq["act"]), 3),
           "born": ser(norm18(eq["born"]), 3),
           "wf_d": dates(wf.index), "wf": ser(wf, 3),
           "k1": json.load(open(OUT / "adaptive_params.json"))["chosen_walkforward"]}

# --- bootstrap (préparé en histogrammes) ---
boot = pd.read_csv(OUT / "bootstrap_results.csv")
def hist(col, lo=-0.5, hi=3.5, n=40):
    h, edges = np.histogram(boot[col].clip(lo, hi), bins=n, range=(lo, hi))
    return {"x": [round(float(e), 3) for e in (edges[:-1] + edges[1:]) / 2],
            "y": [int(v) for v in h]}
J["boot"] = {"bh": hist("bh_cagr"), "act": hist("actuelle_cagr"), "born": hist("bornee_cagr"),
             "p_act": round(float((boot.actuelle_cagr > boot.bh_cagr).mean()), 3),
             "p_born": round(float((boot.bornee_cagr > boot.bh_cagr).mean()), 3),
             "mdd_med": {k: round(float(boot[c].median()) * 100, 1)
                         for k, c in [("bh", "bh_mdd"), ("act", "actuelle_mdd"), ("born", "bornee_mdd")]}}

# --- tables ---
J["final"] = json.loads(pd.read_csv(OUT / "final_comparison.csv", index_col=0)
                        [["Buy&Hold", "Actuelle_SMA156_20_40", "Adaptative_bornee_0.5"]]
                        .round(3).to_json())
J["per_cycle"] = json.loads(pd.read_csv(OUT / "per_cycle_performance.csv", index_col=0).round(3).to_json())

# --- statut courant ---
st = res_act.trades[-1]
peak_since = w.loc[st.date:, "close"].max()
J["status"] = {
    "entry_date": str(st.date.date()) if st.side == "buy" else None,
    "entry_price": round(st.price, 0),
    "peak": round(float(peak_since), 0),
    "sma_now": round(float(ma156.iloc[-1]), 0),
    "d1_now": round(float(d1b.iloc[-1]) * 100, 1), "d2_now": round(float(d2b.iloc[-1]) * 100, 1),
    "sell1_fixed": round(float(peak_since) * 0.80, 0), "sell2_fixed": round(float(peak_since) * 0.60, 0),
    "sell1_born": round(float(peak_since) * (1 - float(d1b.iloc[-1])), 0),
    "sell2_born": round(float(peak_since) * (1 - float(d2b.iloc[-1])), 0),
    "dd_now": round(float(w["close"].iloc[-1] / peak_since - 1) * 100, 1),
    "sigma_mix": round(float(adaptive.sigma_mix(w).iloc[-1]) * 100, 1),
}

out_file = OUT / "report_data.json"
json.dump(J, open(out_file, "w"), separators=(",", ":"))
print("écrit :", out_file, f"({out_file.stat().st_size/1024:.0f} Ko)")
print(json.dumps(J["status"], indent=1))
