"""PHASE 8 — report figures.  Generated from saved results; safe to re-run."""
import os, sys, glob
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from vwapresearch.ingest import OUT_ROOT
from vwapresearch import plots, stats
from vwapresearch.config import split_of

R = os.path.join(os.path.dirname(__file__), "..", "results")
FIG = os.path.join(R, "figures")
os.makedirs(FIG, exist_ok=True)
P5 = os.path.join(R, "phase5")
P6 = os.path.join(R, "phase6")
P7 = os.path.join(R, "phase7_vault")

plt.rcParams.update({"figure.dpi": 120, "font.size": 9, "axes.grid": True,
                     "grid.alpha": 0.3, "figure.autolayout": True})


def equity_all():
    for name in ["NAS100", "SPX500"]:
        fig, ax = plt.subplots(figsize=(9, 5))
        for cn, color in [("PREFADE-S", "#1f6feb"), ("PREFADE-F", "#2da44e")]:
            parts = []
            for sp in ["TRAIN", "VAL"]:
                f = f"{P5}/{cn}_{name}_{sp}_trades.parquet"
                if os.path.exists(f):
                    parts.append(pd.read_parquet(f))
            for suffix in [f"{cn}_{name}_vault_2019_20_trades.parquet",
                           f"{cn}_{name.split('_')[0]}_2026_trades.parquet"]:
                f = os.path.join(P7, suffix)
                if os.path.exists(f):
                    parts.append(pd.read_parquet(f))
            tr = pd.concat(parts).sort_values("t_entry")
            d = stats.daily_series(tr)
            # sigma-normalized cumulative PnL for era comparability
            trn = tr.copy()
            trn["pnl_sg"] = trn["pnl_pts"] / trn["sigma_entry"]
            dn = trn.groupby("session_day")["pnl_sg"].sum()
            dn.index = pd.to_datetime(dn.index)
            ax.plot(dn.sort_index().index, dn.sort_index().cumsum().values,
                    lw=1.0, label=f"{cn} (gross, σ units)", color=color)
        for x, lab in [(pd.Timestamp("2015-01-01"), "VAL"),
                       (pd.Timestamp("2019-01-01"), "VAULT"),
                       (pd.Timestamp("2026-03-12"), "2026")]:
            ax.axvline(x, color="k", ls="--", lw=0.8)
            ax.text(x, ax.get_ylim()[1] * 0.95, " " + lab, fontsize=8)
        ax.set_title(f"{name} — pre-open fade, cumulative gross PnL in sigma units (all periods)")
        ax.set_ylabel("cumulative PnL (σ)")
        ax.legend()
        fig.savefig(f"{FIG}/{name}_equity_sigma.png"); plt.close(fig)


def decay_curve():
    fig, ax = plt.subplots(figsize=(9, 4.5))
    width = 0.4
    for k, (name, color) in enumerate([("NAS100", "#1f6feb"), ("SPX500", "#fb8500")]):
        parts = []
        for sp in ["TRAIN", "VAL"]:
            parts.append(pd.read_parquet(f"{P5}/PREFADE-S_{name}_{sp}_trades.parquet"))
        f = os.path.join(P7, f"PREFADE-S_{name}_vault_2019_20_trades.parquet")
        if os.path.exists(f):
            parts.append(pd.read_parquet(f))
        f = os.path.join(P7, f"PREFADE-S_{name}_2026_trades.parquet")
        if os.path.exists(f):
            parts.append(pd.read_parquet(f))
        tr = pd.concat(parts)
        tr["year"] = pd.to_datetime(tr["session_day"]).dt.year
        tr["pnl_sg"] = tr["pnl_pts"] / tr["sigma_entry"]
        g = tr.groupby("year")["pnl_sg"].mean()
        ax.bar(g.index + (k - 0.5) * width, g.values, width=width, color=color,
               alpha=0.85, label=name)
    ax.axhline(0, color="k", lw=0.8)
    ax.axvspan(2014.5, 2018.5, color="grey", alpha=0.10)
    ax.axvspan(2018.5, 2026.5, color="red", alpha=0.06)
    ax.set_title("PREFADE-S: gross expectancy per trade (σ units) by year — TRAIN | VAL (grey) | VAULT (red)")
    ax.set_ylabel("mean PnL per trade (σ)")
    ax.legend()
    fig.savefig(f"{FIG}/decay_curve.png"); plt.close(fig)


def plateau_maps():
    for name in ["NAS100", "SPX500"]:
        sw = pd.read_csv(f"{R}/phase3/PREB_{name}_grid.csv")
        sub = sw[(sw["window"] == "(450, 570)") & (sw["target"] == "vwap") & (sw["time_stop"] == 180)]
        plots.param_heatmap(sub, "gross_sharpe", "level", "stop_sigma",
                            f"{name} TRAIN gross Sharpe — level x stop (window 07:30-09:30, VWAP target, ts180)",
                            f"{FIG}/{name}_plateau_level_stop.png")
        sub2 = sw[(sw["level"] == 2.0) & (sw["target"] == "vwap")]
        plots.param_heatmap(sub2, "gross_sharpe", "window", "time_stop",
                            f"{name} TRAIN gross Sharpe — window x time-stop (L2, VWAP target)",
                            f"{FIG}/{name}_plateau_window_ts.png")


def heat_tod():
    for name in ["NAS100", "SPX500"]:
        hm = pd.read_csv(f"{R}/phase1/{name}_heat_tod_level_P60.csv", index_col=0)
        fig, ax = plt.subplots(figsize=(6.5, 4.5))
        im = ax.imshow(hm.values, cmap="RdYlGn", aspect="auto", vmin=0, vmax=1)
        ax.set_xticks(range(len(hm.columns)), hm.columns)
        ax.set_yticks(range(len(hm.index)), hm.index)
        for i in range(hm.shape[0]):
            for j in range(hm.shape[1]):
                ax.text(j, i, f"{hm.values[i,j]:.2f}", ha="center", va="center", fontsize=7)
        ax.set_title(f"{name} TRAIN — P(VWAP touch within 60 min) by time-of-day x band level")
        ax.set_xlabel("band level (σ)")
        fig.colorbar(im, ax=ax, shrink=0.8)
        fig.savefig(f"{FIG}/{name}_heat_tod_level.png"); plt.close(fig)


def cost_sensitivity():
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, name in zip(axes, ["NAS100", "SPX500"]):
        c = pd.read_csv(f"{P6}/{name}_costs.csv")
        labels = c["scenario"] + " (" + c["instr"] + ")"
        x = np.arange(len(c))
        ax.bar(x - 0.2, c["net_exp_TRAIN"], width=0.4, label="TRAIN era", color="#1f6feb")
        ax.bar(x + 0.2, c["net_exp_VAL"], width=0.4, label="VAL era", color="#d1242f")
        ax.set_xticks(x, labels, rotation=45, ha="right", fontsize=7)
        ax.axhline(0, color="k", lw=0.8)
        ax.set_title(f"{name} PREFADE-F net expectancy by cost scenario")
        ax.set_ylabel("net pts/trade")
        ax.legend(fontsize=7)
    fig.savefig(f"{FIG}/cost_sensitivity.png"); plt.close(fig)


def mae_mfe():
    for name in ["NAS100"]:
        tr = pd.read_parquet(f"{P5}/PREFADE-S_{name}_TRAIN_trades.parquet")
        plots.mae_mfe(tr, f"{name} PREFADE-S TRAIN — MAE vs MFE (pts)",
                      f"{FIG}/{name}_mae_mfe.png")
        plots.hist(tr["pnl_pts"], f"{name} PREFADE-S TRAIN — trade PnL (gross pts)",
                   f"{FIG}/{name}_pnl_hist.png", xlabel="pts")


def walkforward_fig():
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, name in zip(axes, ["NAS100", "SPX500"]):
        wf = pd.read_csv(f"{P6}/{name}_walkforward.csv")
        x = wf["test_year"]
        ax.bar(x - 0.2, wf["oos_sharpe"], width=0.4, label="reselected", color="#1f6feb")
        ax.bar(x + 0.2, wf["fixed_sharpe"], width=0.4, label="fixed centre", color="#8250df")
        ax.axhline(0, color="k", lw=0.8)
        ax.set_title(f"{name} walk-forward OOS Sharpe by test year (gross)")
        ax.legend(fontsize=7)
    fig.savefig(f"{FIG}/walkforward.png"); plt.close(fig)


def trade_examples():
    """Best / median / worst PREFADE-S trades on NAS100 TRAIN, day charts."""
    name = "NAS100"
    tr = pd.read_parquet(f"{P5}/PREFADE-S_{name}_TRAIN_trades.parquet")
    fr = pd.read_parquet(os.path.join(OUT_ROOT, f"{name}_feat.parquet"),
                         columns=["close", "vwap_sess", "sigma_sess", "session_day", "ny_minute"])
    tr = tr.sort_values("pnl_pts")
    picks = {"worst": tr.iloc[0], "median": tr.iloc[len(tr) // 2], "best": tr.iloc[-1]}
    for lab, t in picks.items():
        day = t["session_day"]
        d = fr[fr["session_day"] == day]
        ny = d.index.tz_convert("America/New_York")
        fig, ax = plt.subplots(figsize=(10, 4.5))
        ax.plot(ny, d["close"], lw=0.8, color="k", label="close")
        ax.plot(ny, d["vwap_sess"], lw=1.0, color="#1f6feb", label="session VWAP")
        for L, alpha in [(1.0, 0.25), (2.0, 0.5)]:
            ax.plot(ny, d["vwap_sess"] + L * d["sigma_sess"], lw=0.7, color="#fb8500", alpha=alpha)
            ax.plot(ny, d["vwap_sess"] - L * d["sigma_sess"], lw=0.7, color="#fb8500", alpha=alpha)
        for ts, px, mk, col in [(t["t_entry"], t["entry"], "^" if t["side"] == 1 else "v", "#2da44e"),
                                (t["t_exit"], t["exit"], "x", "#d1242f")]:
            ax.plot(pd.Timestamp(ts).tz_convert("America/New_York"), px, mk,
                    color=col, markersize=9)
        ax.set_title(f"{name} PREFADE-S {lab} trade — {day}  pnl {t['pnl_pts']:+.1f} pts ({t['reason']})")
        ax.legend(fontsize=7)
        fig.savefig(f"{FIG}/trade_{lab}.png"); plt.close(fig)


if __name__ == "__main__":
    equity_all()
    decay_curve()
    plateau_maps()
    heat_tod()
    cost_sensitivity()
    mae_mfe()
    walkforward_fig()
    trade_examples()
    print("figures written to", FIG)
