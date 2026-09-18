"""Mission 2 — figures du rapport (results/m2/figs)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from vwapresearch.ingest import OUT_ROOT
from vwapresearch import stats
from vwapresearch.config import split_of

R = os.path.join(os.path.dirname(__file__), "..", "results", "m2")
FIG = os.path.join(R, "figs")
os.makedirs(FIG, exist_ok=True)
plt.rcParams.update({"figure.dpi": 120, "font.size": 9, "axes.grid": True,
                     "grid.alpha": 0.3, "figure.autolayout": True})
C = {"NAS100": "#1f6feb", "SPX500": "#fb8500"}

EVS = {}
for name in ["NAS100", "SPX500"]:
    ev = pd.read_parquet(os.path.join(OUT_ROOT, f"{name}_impulse_TRAIN.parquet"))
    EVS[name] = ev[ev["imp_dur"].notna()].copy()


def fig_drift_by(var, xlabel, fname, q=5, deep_only=True, absx=False):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
    for ax, (name, ev) in zip(axes, EVS.items()):
        e = ev[ev["level"] >= 2.5] if deep_only else ev
        x = e[var].abs() if absx else e[var]
        qq = pd.qcut(x, q, duplicates="drop")
        g = e.groupby(qq, observed=True)[["fret_60", "fret_120", "fret_240"]].mean()
        n = e.groupby(qq, observed=True).size()
        idx = np.arange(len(g))
        for off, (col, lab, cc) in enumerate([("fret_60", "60 min", "#9ec1f7"),
                                              ("fret_120", "120 min", "#1f6feb"),
                                              ("fret_240", "240 min", "#0d3d8c")]):
            ax.bar(idx + (off - 1) * 0.27, g[col], width=0.27, label=lab, color=cc)
        ax.axhline(0, color="k", lw=0.8)
        ax.set_xticks(idx, [f"Q{i+1}\nn={v}" for i, v in enumerate(n)], fontsize=7)
        ax.set_title(f"{name} — dérive de fade (σ) par quintile de {xlabel}")
        ax.legend(fontsize=7)
    axes[0].set_ylabel("dérive moyenne vers VWAP (σ)")
    fig.savefig(f"{FIG}/{fname}"); plt.close(fig)


fig_drift_by("imp_retr_frac", "retracement/mouvement (Q1=direct)", "drift_by_retr.png")
fig_drift_by("imp_eff", "efficiency (Q5=direct)", "drift_by_eff.png")
fig_drift_by("imp_speed", "vitesse σ/min (Q5=rapide)", "drift_by_speed.png")
fig_drift_by("eq120_slope", "|pente VWAP| 2h avant (Q1=plate)", "drift_by_eqslope.png")

# P(vwap) selon la distance initiale (niveau) + temps de retour
fig, axes = plt.subplots(1, 2, figsize=(11, 4))
for name, ev in EVS.items():
    g = ev.groupby("level")["hit_vwap_120"].mean()
    axes[0].plot(g.index, g.values, "o-", color=C[name], label=name)
    e25 = ev[ev["level"] == 2.5]["t_vwap"].dropna()
    axes[1].hist(e25, bins=48, range=(0, 240), alpha=0.55, color=C[name],
                 label=f"{name} (méd {e25.median():.0f}m)", density=True)
axes[0].set_title("P(retour VWAP < 120 min) selon le niveau touché")
axes[0].set_xlabel("niveau (σ)"); axes[0].legend()
axes[1].set_title("Temps de retour à la VWAP après touch 2.5σ")
axes[1].set_xlabel("minutes"); axes[1].legend(fontsize=7)
fig.savefig(f"{FIG}/pvwap_level_time.png"); plt.close(fig)

# equity curves TRAIN+VAL (σ-units) CTX vs BASE
fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=False)
for ax, name in zip(axes, ["NAS100", "SPX500"]):
    for cn, col in [("M2-CTX", "#2da44e"), ("M2-BASE", "#8250df")]:
        parts = []
        for sp in ["TRAIN", "VAL"]:
            f = f"{R}/{cn}_{name}_{sp}_trades.parquet"
            if os.path.exists(f):
                parts.append(pd.read_parquet(f))
        tr = pd.concat(parts).sort_values("t_entry")
        tr["pnl_sg"] = tr["pnl_pts"] / tr["sigma_entry"]
        d = tr.groupby("session_day")["pnl_sg"].sum()
        d.index = pd.to_datetime(d.index)
        d = d.sort_index()
        ax.plot(d.index, d.cumsum().values, lw=1.0, color=col, label=cn)
    ax.axvline(pd.Timestamp("2015-01-01"), color="k", ls="--", lw=0.8)
    ax.text(pd.Timestamp("2015-03-01"), ax.get_ylim()[1] * 0.9, "VAL", fontsize=8)
    ax.set_title(f"{name} — PnL cumulé brut (σ), contexte vs baseline")
    ax.legend(fontsize=8)
fig.savefig(f"{FIG}/equity_ctx_base.png"); plt.close(fig)

# yearly exp_sg bars
fig, axes = plt.subplots(1, 2, figsize=(11, 4))
for ax, name in zip(axes, ["NAS100", "SPX500"]):
    for k, (cn, col) in enumerate([("M2-CTX", "#2da44e"), ("M2-BASE", "#8250df")]):
        parts = [pd.read_parquet(f"{R}/{cn}_{name}_{sp}_trades.parquet") for sp in ["TRAIN", "VAL"]]
        tr = pd.concat(parts)
        tr["year"] = pd.to_datetime(tr["session_day"]).dt.year
        tr["pnl_sg"] = tr["pnl_pts"] / tr["sigma_entry"]
        g = tr.groupby("year")["pnl_sg"].mean()
        ax.bar(g.index + (k - 0.5) * 0.4, g.values, width=0.4, color=col, label=cn)
    ax.axhline(0, color="k", lw=0.8)
    ax.axvspan(2014.5, 2018.5, color="grey", alpha=0.12)
    ax.set_title(f"{name} — espérance/trade (σ) par année (VAL grisée)")
    ax.legend(fontsize=8)
fig.savefig(f"{FIG}/yearly_exp.png"); plt.close(fig)

# MAE/MFE
tr = pd.read_parquet(f"{R}/M2-CTX_SPX500_TRAIN_trades.parquet")
fig, ax = plt.subplots(figsize=(6, 5.5))
win = tr["pnl_pts"] > 0
ax.scatter(tr.loc[win, "mae"], tr.loc[win, "mfe"], s=6, alpha=0.4, color="#2da44e", label="gagnants")
ax.scatter(tr.loc[~win, "mae"], tr.loc[~win, "mfe"], s=6, alpha=0.4, color="#d1242f", label="perdants")
ax.set_xlabel("MAE (pts)"); ax.set_ylabel("MFE (pts)")
ax.set_title("M2-CTX SPX500 TRAIN — MAE vs MFE"); ax.legend()
fig.savefig(f"{FIG}/mae_mfe.png"); plt.close(fig)

# ------------------- trade visuals with equilibrium/impulse annotations
def day_chart(name, trade, ev_row, label, fname):
    fr = pd.read_parquet(os.path.join(OUT_ROOT, f"{name}_feat.parquet"),
                         columns=["close", "vwap_sess", "sigma_sess", "session_day", "ny_minute"])
    d = fr[fr["session_day"] == trade["session_day"]]
    ny = d.index.tz_convert("America/New_York")
    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    ax.plot(ny, d["close"], lw=0.8, color="k", label="close")
    ax.plot(ny, d["vwap_sess"], lw=1.1, color="#1f6feb", label="VWAP session")
    for L, a in [(1.0, 0.3), (2.5, 0.65)]:
        ax.plot(ny, d["vwap_sess"] + L * d["sigma_sess"], lw=0.7, color="#fb8500", alpha=a)
        ax.plot(ny, d["vwap_sess"] - L * d["sigma_sess"], lw=0.7, color="#fb8500", alpha=a)
    t_ent = pd.Timestamp(trade["t_entry"]).tz_convert("America/New_York")
    t_ex = pd.Timestamp(trade["t_exit"]).tz_convert("America/New_York")
    if ev_row is not None and np.isfinite(ev_row.get("imp_dur", np.nan)):
        t_sig = pd.Timestamp(ev_row["time"]).tz_convert("America/New_York")
        t_start = t_sig - pd.Timedelta(minutes=int(ev_row["imp_dur"]))
        t_eq0 = t_start - pd.Timedelta(minutes=120)
        ax.axvspan(t_eq0, t_start, color="#2da44e", alpha=0.10, label="équilibre (2h)")
        ax.axvspan(t_start, t_sig, color="#d1242f", alpha=0.10, label="impulsion")
    side = trade["side"]
    stop = trade["entry"] - side * 2.5 * trade["sigma_entry"]
    ax.axhline(stop, color="#d1242f", lw=0.9, ls=":", label="stop 2.5σ")
    ax.plot(t_ent, trade["entry"], "^" if side == 1 else "v", color="#2da44e", ms=10, label="entrée")
    ax.plot(t_ex, trade["exit"], "x", color="#d1242f", ms=10, label="sortie")
    ax.set_title(f"{name} {label} — {trade['session_day']}  pnl {trade['pnl_pts']:+.1f} pts ({trade['reason']})")
    ax.legend(fontsize=7, ncol=3)
    fig.savefig(f"{FIG}/{fname}"); plt.close(fig)


name = "SPX500"
tr = pd.read_parquet(f"{R}/M2-CTX_{name}_TRAIN_trades.parquet").sort_values("pnl_pts")
ev = EVS[name]
ev_by_time = ev.set_index(pd.DatetimeIndex(ev["time"]))


def ev_of(trade):
    t = pd.Timestamp(trade["t_signal"])
    try:
        return ev_by_time.loc[t].iloc[0] if isinstance(ev_by_time.loc[t], pd.DataFrame) else ev_by_time.loc[t]
    except KeyError:
        return None


picks = {
    "pire trade": tr.iloc[0],
    "trade perdant type": tr.iloc[int(0.25 * len(tr))],
    "trade médian": tr.iloc[len(tr) // 2],
    "gagnant type": tr.iloc[int(0.8 * len(tr))],
    "meilleur trade": tr.iloc[-1],
}
tr_mae = tr[tr["pnl_pts"] > 0].sort_values("mae")
picks["gagnant avec fort MAE"] = tr_mae.iloc[-1]
for i, (lab, t) in enumerate(picks.items()):
    day_chart(name, t, ev_of(t), lab, f"trade_{i}_{lab.replace(' ', '_')}.png")

# rejected example: very direct impulse (retr<0.08) out of equilibrium that continued
rej = ev[(ev["level"] == 2.5) & (ev["ny_minute"].between(570, 810))
         & (ev["imp_retr_frac"] < 0.08) & (ev["eq120_inside"] > 0.5)
         & (ev["fret_120"] < -0.8)]
if len(rej):
    rr = rej.iloc[0]
    fake_trade = {"session_day": rr["session_day"], "t_entry": rr["time"], "t_exit": rr["time"],
                  "entry": rr["entry"], "exit": rr["entry"], "side": -int(rr["side"]),
                  "sigma_entry": rr["sg"], "pnl_pts": 0.0, "reason": "REJETÉ (exemple)"}
    day_chart(name, fake_trade, rr, "exemple rejeté: impulsion directe -> continuation", "trade_6_rejete.png")

print("figs:", sorted(os.listdir(FIG)))
