"""Étape 6 : les 10 graphiques du rapport (PNG, style homogène)."""
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT.parent))
from research.src import config, data, strategy, metrics, entries, adaptive

OUT = ROOT / "output"

# ---- style ----------------------------------------------------------------
C1, C2, C3, C4, C5 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e5e5e2", "#fcfcfb"
plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "axes.edgecolor": GRID, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.labelcolor": INK2, "text.color": INK, "xtick.color": INK2, "ytick.color": INK2,
    "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold",
    "legend.frameon": False, "figure.dpi": 130,
})
def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / name, bbox_inches="tight")
    plt.close(fig)
    print("écrit :", name)

halvings = pd.to_datetime(config.HALVINGS)
daily = data.load_daily(ROOT)
w = data.weekly_frame(daily)
ma156 = entries.sma(w, 156)
cost = sum(config.COST_SCENARIOS["central"].values())
COMMON_START = w.index[207]
VALID_START, TEST_START = pd.Timestamp("2018-01-01"), pd.Timestamp("2022-01-01")

BOUNDED = dict(d1_bounds=(0.12, 0.20), d2_bounds=(0.24, 0.40), min_ratio=2.0)
d1b, d2b = adaptive.thresholds(w, 0.5, 1.0, params=BOUNDED)
res_base = strategy.run_strategy(w, ma=ma156, exit_levels=[0.20, 0.40], cost_per_side=cost)
res_adap = strategy.run_strategy(w, ma=ma156, exit_levels=[d1b, d2b], cost_per_side=cost)
res_bh = strategy.buy_and_hold(w, cost_per_side=cost, start=COMMON_START)

def shade(ax):
    ax.axvspan(VALID_START, TEST_START, color="#eda100", alpha=0.06, lw=0)
    ax.axvspan(TEST_START, w.index[-1], color="#e34948", alpha=0.05, lw=0)

# ---- fig 1 : prix + SMA + halvings + transactions -------------------------
fig, ax = plt.subplots(figsize=(11, 5.5))
ax.plot(w.index, w["close"], color=C1, lw=1.4, label="Bitcoin (clôture hebdo, USD)")
ax.plot(w.index, ma156, color=C2, lw=1.6, label="SMA 156 semaines")
for h in halvings:
    ax.axvline(h, color=INK2, ls=":", lw=1)
    ax.annotate("halving", (h, ax.get_ylim()[0]), xytext=(4, 4), textcoords="offset points",
                rotation=90, fontsize=8, color=INK2)
t = res_base.trades_df()
buys, sells = t[t.side == "buy"], t[t.side == "sell"]
ax.scatter(buys.date, buys.price, marker="^", s=70, color=C3, zorder=5, label="entrée")
ax.scatter(sells.date, sells.price, marker="v", s=70, color="#e34948", zorder=5, label="sortie")
ax.set_yscale("log")
ax.set_ylabel("Prix (USD, échelle log)")
ax.set_title("Bitcoin, SMA 156 semaines, halvings et transactions de la stratégie de référence")
ax.legend(loc="upper left")
save(fig, "fig01_prix_sma.png")

# ---- fig 2 : courbes de capital -------------------------------------------
fig, ax = plt.subplots(figsize=(11, 5.5))
for res, c, lab in [(res_bh, C1, "Buy & Hold"), (res_base, C2, "Stratégie actuelle (-20 %/-40 %)"),
                    (res_adap, C3, "Adaptative bornée")]:
    eq = res.equity.loc[COMMON_START:]
    ax.plot(eq.index, eq / eq.iloc[0], color=c, lw=1.6, label=lab)
shade(ax)
ax.set_yscale("log")
ax.set_ylabel("Capital (base 1 en juil. 2014, échelle log)")
ax.set_title("Courbes de capital normalisées — zones : validation (jaune), test (rouge)")
ax.legend(loc="upper left")
save(fig, "fig02_courbes_capital.png")

# ---- fig 3 : drawdowns -----------------------------------------------------
fig, ax = plt.subplots(figsize=(11, 4.5))
for res, c, lab in [(res_bh, C1, "Buy & Hold"), (res_base, C2, "Actuelle"),
                    (res_adap, C3, "Adaptative bornée")]:
    eq = res.equity.loc[COMMON_START:]
    ax.plot(eq.index, metrics.drawdown(eq) * 100, color=c, lw=1.3, label=lab)
shade(ax)
ax.set_ylabel("Drawdown (%)")
ax.set_title("Drawdowns comparés depuis juillet 2014")
ax.legend(loc="lower left")
save(fig, "fig03_drawdowns.png")

# ---- fig 4 : volatilité réalisée + régimes --------------------------------
amp = pd.read_csv(OUT / "amplitude_measures.csv", index_col=0, parse_dates=True)
ssl = pd.read_csv(OUT / "statespace_level.csv", index_col=0, parse_dates=True)
prob = pd.read_csv(OUT / "markov_prob_high_vol.csv", index_col=0, parse_dates=True).iloc[:, 0]
fig, (ax, ax2) = plt.subplots(2, 1, figsize=(11, 6.5), sharex=True,
                              gridspec_kw={"height_ratios": [2.2, 1]})
ax.plot(amp.index, amp["rv52"] * 100, color=C2, lw=1.4, label="Vol réalisée 52 sem.")
ax.plot(ssl.index, np.exp(ssl["niveau_lisse"]) * 100, color=C1, lw=1.6, alpha=0.85,
        label="Niveau lissé de la vol 26 sem. (espace-état)")
for h in halvings:
    ax.axvline(h, color=INK2, ls=":", lw=0.8)
ax.set_ylabel("Volatilité annualisée (%)")
ax.set_title("Volatilité réalisée : le tassement structurel")
ax.legend(loc="upper right")
ax2.fill_between(prob.index, prob * 100, color=C4, alpha=0.6, lw=0)
ax2.set_ylabel("P(régime agité) %")
ax2.set_xlabel("")
save(fig, "fig04_volatilite.png")

# ---- fig 5 : amplitudes par cycle -----------------------------------------
cyc = pd.read_csv(OUT / "cycles_episodes.csv")
amp["cycle_num"] = np.searchsorted(halvings, amp.index)
fig, axes = plt.subplots(2, 2, figsize=(11, 7))
labels_cyc = ["pré-2012", "2012-16", "2016-20", "2020-24", "2024-"]
g = amp.groupby("cycle_num")["rv52"].median() * 100
axes[0, 0].bar([labels_cyc[i] for i in g.index], g.values, color=C1, width=0.62)
axes[0, 0].set_title("Vol réalisée 52 sem. médiane (%)")
g = amp.groupby("cycle_num")["semivol_down52"].median() * 100
axes[0, 1].bar([labels_cyc[i] for i in g.index], g.values, color=C2, width=0.62)
axes[0, 1].set_title("Semi-vol baissière médiane (%)")
axes[1, 0].bar(cyc["sommet"].str[:4], -cyc["drawdown"] * 100, color=C3, width=0.62)
axes[1, 0].set_title("Profondeur du drawdown par épisode (%)")
axes[1, 1].bar(cyc["sommet"].str[:4], cyc["multiple_creux_prec"], color=C4, width=0.62)
axes[1, 1].set_yscale("log")
axes[1, 1].set_title("Multiple creux -> sommet (échelle log)")
for a in axes.flat:
    a.tick_params(axis="x", rotation=45)
save(fig, "fig05_amplitude_cycles.png")

# ---- fig 6 : ajustements des modèles --------------------------------------
import statsmodels.api as sm
d = amp.dropna(subset=["rv52", "log_cap"]).copy()
y = np.log(d["rv52"])
fig, ax = plt.subplots(figsize=(11, 5))
ax.plot(d.index, d["rv52"] * 100, color=INK2, lw=1.0, alpha=0.7, label="Vol réalisée 52 sem.")
X = sm.add_constant(d["t_years"]); m = sm.OLS(y, X).fit()
ax.plot(d.index, np.exp(m.fittedvalues) * 100, color=C1, lw=2, label=f"Exponentiel temps (R²={m.rsquared:.2f})")
X = sm.add_constant(d["log_cap"]); m2 = sm.OLS(y, X).fit()
ax.plot(d.index, np.exp(m2.fittedvalues) * 100, color=C2, lw=2, label=f"Log-capitalisation (R²={m2.rsquared:.2f})")
X = sm.add_constant(d["cycle_num"].astype(float)); m3 = sm.OLS(y, X).fit()
ax.plot(d.index, np.exp(m3.fittedvalues) * 100, color=C3, lw=2, label=f"Numéro de cycle (R²={m3.rsquared:.2f})")
ax.set_ylabel("Volatilité annualisée (%)")
ax.set_title("Modèles de décroissance de l'amplitude (ajustements in-sample)")
ax.legend()
save(fig, "fig06_modeles_fits.png")

# ---- fig 7 : prévisions hors échantillon vs observé ------------------------
preds = pd.read_csv(OUT / "amplitude_oos_preds.csv", index_col=0, parse_dates=True)
targ = pd.read_csv(OUT / "amplitude_oos_target.csv", index_col=0, parse_dates=True)["target_fwd26"]
fig, ax = plt.subplots(figsize=(11, 5))
ax.plot(targ.loc["2018":].index, np.exp(targ.loc["2018":]) * 100, color=INK, lw=1.8,
        label="Vol future 26 sem. observée")
for mname, c in [("M2_exp_temps", C1), ("M5_cycle", C3), ("M1_marche_aleatoire", C2)]:
    pr = preds[mname].dropna()
    ax.plot(pr.index, np.exp(pr) * 100, color=c, lw=1.2, alpha=0.9, label=mname)
ax.axvline(TEST_START, color=INK2, ls="--", lw=1)
ax.annotate("validation | test", (TEST_START, ax.get_ylim()[1]), xytext=(6, -14),
            textcoords="offset points", color=INK2, fontsize=9)
ax.set_ylabel("Volatilité annualisée (%)")
ax.set_title("Prévisions hors échantillon de la volatilité future (refit expanding hebdomadaire)")
ax.legend()
save(fig, "fig07_oos_pred.png")

# ---- fig 8 : seuils adaptatifs dans le temps -------------------------------
fig, ax = plt.subplots(figsize=(11, 4.5))
ax.plot(d1b.index, d1b * 100, color=C3, lw=1.6, label="D1 adaptatif borné")
ax.plot(d2b.index, d2b * 100, color=C5, lw=1.6, label="D2 adaptatif borné")
ax.axhline(20, color=C2, ls="--", lw=1.2)
ax.axhline(40, color=C2, ls="--", lw=1.2)
ax.annotate("règle fixe -20 %", (w.index[30], 20.5), color=C2, fontsize=9)
ax.annotate("règle fixe -40 %", (w.index[30], 40.5), color=C2, fontsize=9)
ax.set_ylabel("Seuil de vente (% sous le sommet)")
ax.set_ylim(0, 55)
ax.set_title("Évolution des seuils de sortie adaptatifs (bornés par la règle fixe)")
ax.legend(loc="center right")
save(fig, "fig08_seuils_adaptatifs.png")

# ---- fig 9 : heatmap MA x D1 ----------------------------------------------
heat = pd.read_csv(OUT / "heatmap_ma_d1_calmar.csv", index_col=0)
fig, ax = plt.subplots(figsize=(9, 6.5))
im = ax.imshow(heat.values, cmap="Blues", aspect="auto", origin="lower", vmin=0)
ax.set_xticks(range(len(heat.columns)), [f"{float(c):.0%}" for c in heat.columns])
ax.set_yticks(range(len(heat.index)), heat.index)
ax.set_xlabel("Seuil D1 (D2 = 2 x D1)")
ax.set_ylabel("Longueur de la SMA (semaines)")
ax.set_title("Calmar (2014-2026) selon la longueur de MA et le seuil de sortie")
i156 = list(heat.index).index(152)
j20 = list(heat.columns).index("0.2")
ax.add_patch(plt.Rectangle((j20 - 0.5, i156 - 0.5), 1, 2, fill=False, edgecolor=C2, lw=2.5))
ax.annotate("règle actuelle (≈156, 20 %)", (j20, i156 + 1.6), color=C2, fontsize=9, ha="center")
for i in range(heat.shape[0]):
    for j in range(heat.shape[1]):
        v = heat.values[i, j]
        ax.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=7,
                color="white" if v > heat.values.max() * 0.6 else INK2)
fig.colorbar(im, ax=ax, label="Ratio de Calmar")
ax.grid(False)
save(fig, "fig09_heatmap.png")

# ---- fig 10 : walk-forward -------------------------------------------------
wf = pd.read_csv(OUT / "equity_walkforward_adaptive.csv", index_col=0, parse_dates=True).iloc[:, 0]
params = json.load(open(OUT / "adaptive_params.json"))
fig, (ax, ax2) = plt.subplots(2, 1, figsize=(11, 6.5), sharex=True,
                              gridspec_kw={"height_ratios": [2.4, 1]})
eqb = res_base.equity.loc["2018-01-01":]; eqb = eqb / eqb.iloc[0]
eqa = res_adap.equity.loc["2018-01-01":]; eqa = eqa / eqa.iloc[0]
bhe = res_bh.equity.loc["2018-01-01":]; bhe = bhe / bhe.iloc[0]
ax.plot(bhe.index, bhe, color=C1, lw=1.4, label="Buy & Hold")
ax.plot(eqb.index, eqb, color=C2, lw=1.6, label="Actuelle (-20 %/-40 %)")
ax.plot(eqa.index, eqa, color=C3, lw=1.6, label="Adaptative bornée")
ax.plot(wf.index, wf, color=C5, lw=1.4, label="Adaptative walk-forward (k recalibré/an)")
ax.axvline(TEST_START, color=INK2, ls="--", lw=1)
ax.set_yscale("log")
ax.set_ylabel("Capital (base 1 début 2018, log)")
ax.set_title("Hors échantillon 2018-2026 : validation puis test (droite de la ligne pointillée)")
ax.legend(loc="upper left", fontsize=9)
ks = params["chosen_walkforward"]
ax2.step(pd.to_datetime([f"{y}-01-01" for y in ks]), list(ks.values()), where="post", color=C5, lw=1.8)
ax2.set_ylabel("k1 retenu")
ax2.set_ylim(0.4, 1.1)
save(fig, "fig10_walkforward.png")
print("OK figures")
