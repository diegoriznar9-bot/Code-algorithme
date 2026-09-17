"""Étape 3 : le tassement des amplitudes est-il réel, significatif, modélisable ?

3.1  mesures d'amplitude (cycles + mesures glissantes)
3.2  modèles concurrents estimés et comparés in/out-of-sample
3.3  changement de régime (Markov), espace-état, régression quantile
"""
import sys, json, warnings
from pathlib import Path
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT.parent))
from research.src import config, data, entries

import statsmodels.api as sm
from statsmodels.regression.quantile_regression import QuantReg
from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression
from statsmodels.tsa.statespace.structural import UnobservedComponents

pd.set_option("display.width", 250)
OUT = ROOT / "output"
daily = data.load_daily(ROOT)
w = data.weekly_frame(daily)
r = w["log_ret"].dropna()

# ---------------------------------------------------------------------------
# 3.1a — cycles : sommets/creux détectés par épisodes de drawdown > 50 %
# ---------------------------------------------------------------------------
p = daily["PriceUSD"]
ath = p.cummax()
dd = p / ath - 1
episodes = []
in_ep, ep_peak_date = False, None
for t, v in dd.items():
    if not in_ep and v <= -0.50:
        in_ep = True
        ep_peak_date = p.loc[:t][p.loc[:t] == ath.loc[t]].index[-1]
    elif in_ep and v >= -1e-9:
        in_ep = False
        episodes.append((ep_peak_date, t))
if in_ep:
    episodes.append((ep_peak_date, None))

rows = []
prev_trough = p.index[0]
for k, (pk, rec) in enumerate(episodes):
    end = rec if rec is not None else p.index[-1]
    seg = p.loc[pk:end]
    tr_date = seg.idxmin()
    rows.append(dict(
        episode=k + 1,
        sommet=pk.date(), prix_sommet=p.loc[pk],
        creux=tr_date.date(), prix_creux=p.loc[tr_date],
        drawdown=p.loc[tr_date] / p.loc[pk] - 1,
        multiple_creux_prec=p.loc[pk] / p.loc[prev_trough],
        log_ret_creux_sommet=np.log(p.loc[pk] / p.loc[prev_trough]),
        duree_hausse_sem=(pk - prev_trough).days / 7,
        duree_baisse_sem=(tr_date - pk).days / 7,
        vitesse_hausse=np.log(p.loc[pk] / p.loc[prev_trough]) / max((pk - prev_trough).days / 7, 1),
        vitesse_baisse=np.log(p.loc[tr_date] / p.loc[pk]) / max((tr_date - pk).days / 7, 1),
        recuperation=rec.date() if rec is not None else "en cours",
    ))
    prev_trough = tr_date
cyc = pd.DataFrame(rows)
print("=== Épisodes de drawdown > 50 % (détection automatique) ===")
print(cyc.round(3).to_string(index=False))
cyc.to_csv(OUT / "cycles_episodes.csv", index=False)

# drawdown actuel (épisode éventuel < 50 %)
last_ath_date = p[p == ath.iloc[-1]].index[-1]
print(f"\nDernier ATH : {last_ath_date.date()} à {ath.iloc[-1]:.0f} $ ; "
      f"drawdown courant : {dd.iloc[-1]:.1%} (min depuis ATH : {dd.loc[last_ath_date:].min():.1%})")

# ---------------------------------------------------------------------------
# 3.1b — mesures glissantes
# ---------------------------------------------------------------------------
amp = pd.DataFrame(index=w.index)
amp["rv26"] = data.realized_vol(w["log_ret"], 26)
amp["rv52"] = data.realized_vol(w["log_ret"], 52)
amp["rv104"] = data.realized_vol(w["log_ret"], 104)
amp["semivol_down52"] = w["log_ret"].rolling(52).apply(
    lambda x: x[x < 0].std() * np.sqrt(52) if (x < 0).sum() > 5 else np.nan)
amp["range_hebdo_norm"] = ((w["high"] - w["low"]) / w["close"]).rolling(26).mean()
amp["iqr52"] = w["log_ret"].rolling(52).apply(lambda x: np.subtract(*np.percentile(x, [90, 10])))
amp["dd_from_ath"] = w["close"] / w["close"].cummax() - 1
amp["log_cap"] = np.log(w["CapMrktCurUSD"])
amp["log_price"] = np.log(w["close"])
amp["t_years"] = (w.index - w.index[0]).days / 365.25
amp.to_csv(OUT / "amplitude_measures.csv")

halvings = pd.to_datetime(config.HALVINGS)
amp["cycle_num"] = np.searchsorted(halvings, w.index)  # 0 = pré-2012,... 4 = post-2024

print("\n=== Volatilité réalisée 52 s (annualisée) par cycle de halving ===")
print(amp.groupby("cycle_num")["rv52"].agg(["mean", "median", "max"]).round(3).to_string())
print("\n=== Semi-volatilité baissière 52 s par cycle ===")
print(amp.groupby("cycle_num")["semivol_down52"].agg(["mean", "median"]).round(3).to_string())

# ---------------------------------------------------------------------------
# 3.2 — tendance déterministe sur log(RV52) : significativité (HAC)
# ---------------------------------------------------------------------------
d = amp.dropna(subset=["rv52", "log_cap"]).copy()
y = np.log(d["rv52"])
print("\n=== Régressions sur log(vol réalisée 52 s), erreurs Newey-West (52 lags) ===")
fits = {}
for name, X in {
    "temps (exp decay)": sm.add_constant(d["t_years"]),
    "log(temps)": sm.add_constant(np.log(d["t_years"] + 4.0)),  # +4 ans ~ genèse 2009->2010 + offset
    "log(prix)": sm.add_constant(d["log_price"]),
    "log(capitalisation)": sm.add_constant(d["log_cap"]),
    "numero de cycle": sm.add_constant(d["cycle_num"].astype(float)),
}.items():
    m = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 52})
    b = m.params.iloc[1]; ci = m.conf_int().iloc[1]
    fits[name] = m
    print(f"  {name:22s} pente={b:+.4f}  IC95%=[{ci[0]:+.4f},{ci[1]:+.4f}]  R2={m.rsquared:.3f}  p={m.pvalues.iloc[1]:.2e}")
hl = -np.log(2) / fits["temps (exp decay)"].params.iloc[1]
print(f"  demi-vie de la volatilité (modèle exponentiel) : {hl:.1f} ans")

# ---------------------------------------------------------------------------
# 3.2b — prévision hors échantillon de la vol future 26 s (cible réalisable)
# ---------------------------------------------------------------------------
d_all = amp.copy()
d_all["target_fwd26"] = np.log(data.realized_vol(w["log_ret"], 26).shift(-26))
d_all["log_rv26"] = np.log(d_all["rv26"])
d_all = d_all.dropna(subset=["target_fwd26", "log_rv26", "log_cap"])

def design(name, dd_):
    ones = np.ones(len(dd_))
    if name == "M0_constante": return ones[:, None]
    if name == "M1_marche_aleatoire": return None  # pred = log_rv26
    if name == "M2_exp_temps": return np.column_stack([ones, dd_["t_years"]])
    if name == "M3_loi_puissance": return np.column_stack([ones, np.log(dd_["t_years"] + 4.0)])
    if name == "M4_log_cap": return np.column_stack([ones, dd_["log_cap"]])
    if name == "M5_cycle": return np.column_stack([ones, dd_["cycle_num"].astype(float)])
    if name == "M6_AR_vol": return np.column_stack([ones, dd_["log_rv26"]])
    if name == "M7_cap+ARvol": return np.column_stack([ones, dd_["log_cap"], dd_["log_rv26"]])

MODELS = ["M0_constante", "M1_marche_aleatoire", "M2_exp_temps", "M3_loi_puissance",
          "M4_log_cap", "M5_cycle", "M6_AR_vol", "M7_cap+ARvol"]
splits = {"valid_2018_21": ("2018-01-01", "2021-12-31"), "test_2022+": ("2022-01-01", None)}
oos = {m: {} for m in MODELS}
preds_store = {m: pd.Series(index=d_all.index, dtype=float) for m in MODELS}
dates = d_all.index
for i, t in enumerate(dates):
    train = d_all.iloc[:max(i - 26, 0)]  # exclut les cibles chevauchantes (pas d'info future)
    if len(train) < 156 or t < pd.Timestamp("2018-01-01"):
        continue
    for mname in MODELS:
        if mname == "M1_marche_aleatoire":
            preds_store[mname].loc[t] = d_all["log_rv26"].loc[t]
            continue
        Xtr = design(mname, train)
        beta, *_ = np.linalg.lstsq(Xtr, train["target_fwd26"].values, rcond=None)
        Xte = design(mname, d_all.loc[[t]])
        preds_store[mname].loc[t] = float((Xte @ beta)[0])

print("\n=== RMSE hors échantillon (log vol 26 s à horizon 26 s), refit hebdo expanding ===")
tab = {}
for mname in MODELS:
    pr = preds_store[mname].dropna()
    err = pr - d_all["target_fwd26"].reindex(pr.index)
    row = {}
    for sp, (s, e) in splits.items():
        seg = err.loc[s:e] if e else err.loc[s:]
        row[sp] = float(np.sqrt((seg ** 2).mean()))
    tab[mname] = row
oos_df = pd.DataFrame(tab).T
print(oos_df.round(4).to_string())
oos_df.to_csv(OUT / "amplitude_oos_rmse.csv")
pd.DataFrame(preds_store).to_csv(OUT / "amplitude_oos_preds.csv")
d_all[["target_fwd26"]].to_csv(OUT / "amplitude_oos_target.csv")

# AIC/BIC in-sample (à titre indicatif seulement)
print("\n=== AIC/BIC in-sample (indicatif ; ne mesure PAS la capacité prédictive) ===")
for name, m in fits.items():
    print(f"  {name:22s} AIC={m.aic:8.1f}  BIC={m.bic:8.1f}")

# ---------------------------------------------------------------------------
# 3.3a — Markov switching (2 régimes de variance) sur les rendements hebdo
# ---------------------------------------------------------------------------
print("\n=== Markov switching : 2 régimes de variance (rendements hebdo) ===")
try:
    ms = MarkovRegression(r.values, k_regimes=2, trend="c", switching_variance=True)
    msf = ms.fit(search_reps=20)
    sig = np.sqrt(msf.params[-2:]) * np.sqrt(52)
    lo, hi = np.argsort(sig)
    prob_hi = pd.Series(msf.smoothed_marginal_probabilities[:, hi], index=r.index)
    print(f"  vol régime calme : {sig[lo]:.1%} ann. ; régime agité : {sig[hi]:.1%} ann.")
    yearly = prob_hi.resample("YE").mean()
    print("  part de temps en régime agité par année :")
    print("  " + "  ".join(f"{d.year}:{v:.0%}" for d, v in yearly.items()))
    prob_hi.to_csv(OUT / "markov_prob_high_vol.csv")
except Exception as e:
    print("  échec Markov:", e)

# ---------------------------------------------------------------------------
# 3.3b — espace-état : niveau local sur log RV26 (tendance stochastique)
# ---------------------------------------------------------------------------
print("\n=== Espace-état (niveau local + pente stochastique) sur log RV26 ===")
lv = np.log(amp["rv26"].dropna())
uc = UnobservedComponents(lv.values, level="local linear trend")
ucf = uc.fit(disp=False)
level = pd.Series(ucf.smoothed_state[0], index=lv.index)
pd.DataFrame({"log_rv26": lv, "niveau_lisse": level}).to_csv(OUT / "statespace_level.csv")
print(f"  niveau lissé (vol ann.) : 2012:{np.exp(level.loc['2012'].mean()):.0%}  "
      f"2015:{np.exp(level.loc['2015'].mean()):.0%}  2018:{np.exp(level.loc['2018'].mean()):.0%}  "
      f"2021:{np.exp(level.loc['2021'].mean()):.0%}  2024:{np.exp(level.loc['2024'].mean()):.0%}  "
      f"2026:{np.exp(level.loc['2026'].mean()):.0%}")

# ---------------------------------------------------------------------------
# 3.3c — régression quantile : queues des rendements hebdo vs log(cap)
# ---------------------------------------------------------------------------
print("\n=== Régression quantile des rendements hebdo sur log(capitalisation) ===")
dq = pd.DataFrame({"r": w["log_ret"], "log_cap": np.log(w["CapMrktCurUSD"])}).dropna()
for q in [0.05, 0.25, 0.75, 0.95]:
    qr = QuantReg(dq["r"], sm.add_constant(dq["log_cap"])).fit(q=q)
    b = qr.params.iloc[1]; ci = qr.conf_int().iloc[1]
    print(f"  q={q:.2f} : pente={b:+.5f}  IC95%=[{ci[0]:+.5f},{ci[1]:+.5f}]")

# ---------------------------------------------------------------------------
# 3.1c — MFE/MAE après chaque entrée SMA156 (pour calibrer les sorties)
# ---------------------------------------------------------------------------
print("\n=== Excursions favorables (MFE) / défavorables (MAE) après entrée SMA156 ===")
from research.src import strategy as strat
_res = strat.run_strategy(w, ma=entries.sma(w, 156), exit_mode="none", cost_per_side=0.0)
entries_dates = [t.date for t in _res.trades if t.side == "buy"]
# NB : exit_mode="none" => une seule entrée puis conservation ; pour obtenir toutes
# les entrées de la machine à états, on réutilise celles de la stratégie de référence
_res2 = strat.run_strategy(w, ma=entries.sma(w, 156), exit_levels=[0.20, 0.40], cost_per_side=0.0)
entries_dates = sorted({t.date for t in _res2.trades if t.side == "buy"} | set(entries_dates))
rows = []
for t0 in entries_dates:
    seg = w.loc[t0:, "close"]
    seg = seg.iloc[:520]  # 10 ans max
    e0 = seg.iloc[0]
    run_max = seg.cummax()
    mae_vs_peak = (seg / run_max - 1).min()
    rows.append(dict(entree=t0.date(), prix=e0, mfe=seg.max() / e0 - 1,
                     mae_abs=seg.min() / e0 - 1, max_dd_apres=mae_vs_peak))
mfe = pd.DataFrame(rows)
print(mfe.round(3).to_string(index=False))
mfe.to_csv(OUT / "mfe_mae_entries.csv", index=False)
print("\nOK")
