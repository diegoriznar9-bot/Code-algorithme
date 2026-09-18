"""Mission 2 — rapport PDF final (concis, structure §25)."""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import pandas as pd
import numpy as np
from fpdf import FPDF

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from vwapresearch import stats as st

ROOT = os.path.join(os.path.dirname(__file__), "..")
R = os.path.join(ROOT, "results", "m2")
FIG = os.path.join(R, "figs")
OUT = os.path.join(R, "M2_Expansion_MeanReversion_Report.pdf")

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONTB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONTM = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"


class PDF(FPDF):
    def header(self):
        if self.page_no() > 1:
            self.set_font("dejavu", "", 7); self.set_text_color(130)
            self.cell(0, 5, "Mission 2 — Équilibre → Expansion → Extension extrême → Mean reversion VWAP — 2026-09-18", align="R")
            self.ln(6); self.set_text_color(0)

    def footer(self):
        self.set_y(-12); self.set_font("dejavu", "", 7); self.set_text_color(130)
        self.cell(0, 5, f"page {self.page_no()}", align="C"); self.set_text_color(0)


pdf = PDF(format="A4")
pdf.add_font("dejavu", "", FONT); pdf.add_font("dejavu", "B", FONTB)
pdf.add_font("mono", "", FONTM)
pdf.set_auto_page_break(True, margin=14); pdf.set_margins(16, 12, 16)


def H1(t):
    pdf.add_page(); pdf.set_font("dejavu", "B", 14); pdf.set_text_color(20, 60, 130)
    pdf.multi_cell(0, 7, t); pdf.set_text_color(0); pdf.ln(2)


def H2(t):
    pdf.ln(2); pdf.set_font("dejavu", "B", 11); pdf.set_text_color(20, 60, 130)
    pdf.multi_cell(0, 6, t); pdf.set_text_color(0); pdf.ln(1)


def P(t, size=9):
    pdf.set_font("dejavu", "", size); pdf.multi_cell(0, 4.6, t); pdf.ln(1)


def MONO(t, size=7):
    pdf.set_font("mono", "", size); pdf.multi_cell(0, 3.7, t); pdf.ln(1)


def IMG(p, w=168, cap=None):
    if not os.path.exists(p):
        return
    if pdf.get_y() > 185:
        pdf.add_page()
    pdf.image(p, w=w)
    if cap:
        pdf.set_font("dejavu", "", 7.5); pdf.set_text_color(90)
        pdf.multi_cell(0, 4, cap); pdf.set_text_color(0)
    pdf.ln(2)


# ---------- page de titre
pdf.add_page(); pdf.ln(28)
pdf.set_font("dejavu", "B", 19)
pdf.multi_cell(0, 9, "Équilibre → Expansion directe →\nExtension extrême → Mean reversion VWAP", align="C")
pdf.ln(3); pdf.set_font("dejavu", "", 11)
pdf.multi_cell(0, 6, "Recherche ciblée — NQ/MNQ (NAS100) & ES/MES (SPX500), M1, 2005-2018\n"
               "Rapport final — 18 septembre 2026", align="C")
pdf.ln(14); pdf.set_font("dejavu", "B", 11); pdf.set_text_color(150, 30, 30)
pdf.multi_cell(0, 6,
    "Conclusion principale : l'hypothèse est FALSIFIÉE dans sa forme forte — et INVERSÉE.\n"
    "Une expansion directe et rapide sortant d'un équilibre CONTINUE (jusqu'à -0,9σ de dérive\n"
    "de fade) ; seules les extensions laborieuses, avec retracements, réversent modestement.\n"
    "La variante récupérable (contexte VWAP plate) est marginale in-sample, incohérente entre\n"
    "instruments, et son edge tombe à ~0 en validation 2015-2018.\n"
    "Aucune stratégie n'est proposée pour le trading réel ni le forward test.", align="C")
pdf.set_text_color(0)

# ---------- 1 exec summary
H1("1. Executive Summary")
P("Mission : rechercher en profondeur UN setup — marché en équilibre autour de sa VWAP, puis "
  "expansion rapide et directe (sans retracement) jusqu'à une déviation extrême (L2.5/L3), que "
  "l'on fade vers la VWAP. Priorité NQ, validation croisée ES.")
P("Méthode : ~61 000 (NQ) et ~75 000 (ES) événements de touch >= 2σ sur TRAIN 2005-2014, chacun "
  "enrichi de la structure complète équilibre (3 fenêtres × 5 mesures) + impulsion (durée, "
  "amplitude, vitesse, retracement max, efficiency, séries directionnelles) + dérive de prix "
  "forward PURE à 15-240 min (sans stop ni cible, en σ — immune à l'artefact de convergence "
  "VWAP). Puis 16 définitions croisées ÉQUILIBRE × DIRECTNESS × 3 fenêtres horaires, ablations, "
  "324 combinaisons de backtest réel, baseline comparée, validation gelée 2015-2018.")
P("Résultats clés :\n"
  "1. INVERSION : la directness NUIT à la réversion. Quintile le plus direct (retracement "
  "< 13 %) : dérive -0,03 à -0,26σ ; quintiles retracés : +0,10 à +0,37σ (NQ, 240 min). Idem "
  "en vitesse : équilibre + impulsion rapide = -0,2 à -0,75σ sur ES. Une expansion directe "
  "sortant d'une balance est une initiative de breakout qui continue — cohérent avec la "
  "théorie des enchères, contraire à l'intuition du « ressort comprimé ».\n"
  "2. Ce qui aide réellement : VWAP PLATE sur les 2 h précédant l'impulsion (les deux "
  "instruments), et extension laborieuse plutôt que directe. Le nombre de croisements VWAP "
  "n'apporte rien (non monotone).\n"
  "3. La meilleure variante honnête (M2-CTX : touch 2,5σ + VWAP plate + impulsion soutenue, "
  "09:30-13:30 ET) : TRAIN brut +0,17σ/trade sur ES (PF 1,18, 8/10 années) mais NUIT à NQ "
  "(+0,09σ contre +0,14σ pour le fade nu) — apport du contexte incohérent entre instruments.\n"
  "4. VALIDATION 2015-2018 (une lecture, règles gelées) : effondrement général — exp_sg "
  "+0,01..+0,05σ, PF 0,97-1,05, critères pré-enregistrés échoués sur les 4 combinaisons.\n"
  "5. Vault NON ouvert : rien à tester, holdout préservé.")

# ---------- 2 hypothèse & données
H1("2. Hypothèse et données")
P("Hypothèse de marché (mission) : après une phase d'équilibre autour de la VWAP, une expansion "
  "unidirectionnelle violente sans retracement atteignant une déviation extrême crée une "
  "opportunité de mean reversion supérieure au simple touch de bande.")
P("Données : identiques à la recherche précédente (rapport VWAP_Research_Report.pdf, section 2) "
  "— M1 CFD Oanda NAS100/SPX500 2005-2020 (UTC vérifié, tick-volume), splits verrouillés "
  "TRAIN 2005-2014 / VAL 2015-2018 / VAULT 2019-20 + 2026. Limites héritées : pas de volume "
  "CME réel, proxy CFD. VWAP de session (ancrage 18:00 ET), σ pondéré cumulatif, prix (H+L+C)/3.")

# ---------- 3 définitions
H1("3. Définitions quantitatives")
MONO(
"IMPULSION (du dernier passage side*m <= 0.25σ jusqu'au touch):\n"
"  imp_dur        durée (min)\n"
"  imp_amp_sg     amplitude nette (σ)\n"
"  imp_speed      amplitude/durée (σ/min)\n"
"  imp_retr_frac  retracement adverse max / plus haut favorable atteint\n"
"  imp_eff        |net| / chemin parcouru (efficiency ratio)\n"
"  imp_maxrun     plus longue série de bougies dans le sens de l'impulsion\n"
"ÉQUILIBRE (fenêtres 60/120/180 min AVANT le départ de l'impulsion):\n"
"  eqW_inside     % du temps |close-VWAP| < 0.5σ\n"
"  eqW_absm       distance moyenne à la VWAP (σ)\n"
"  eqW_ncross     nb de croisements VWAP\n"
"  eqW_slope      |ΔVWAP| sur la fenêtre / σ\n"
"  eqW_eff        efficiency du prix (bas = marché en deux sens)\n"
"EXTENSION: niveaux 2.0 / 2.5 / 3.0 σ (bandes de déviation pondérée)\n"
"RÉSULTAT:  fret_H = dérive du PRIX vers la VWAP à H min (σ), sans stop/cible")
P("Seize croisements testés : équilibre ∈ {inside120>=50 %, ncross>=8 & pente<méd, "
  "absm180<0,8, inside60>=50 %} × directness ∈ {retr<=15 %, efficiency>=0,6, run>=4, "
  "vitesse tercile sup}, sur 3 fenêtres (toutes heures, RTH, matin Paris 07-14).")

# ---------- 4 exploration
H1("4. Exploration : ce que montrent les données")
H2("4.1 Baseline sans contexte")
P("Dérive de fade après touch, TRAIN : NQ L2 +0,01σ/60 min, L2.5 +0,05σ, L3 -0,03σ ; ES "
  "≈ 0 partout. Confirmation : le fade nu d'une bande extrême n'a AUCUN edge de prix — la "
  "probabilité élevée de « retour VWAP » (36-47 % à 60 min) vient de la convergence de la VWAP "
  "vers le prix.")
IMG(f"{FIG}/pvwap_level_time.png", cap="Fig. 4.1 — P(retour VWAP<120 min) par niveau ; distribution du temps de retour (touch 2,5σ).")
H2("4.2 L'inversion : directness et vitesse")
IMG(f"{FIG}/drift_by_retr.png", cap="Fig. 4.2 — Dérive de fade par quintile de retracement d'impulsion (Q1 = le plus direct). "
    "Q1 négatif sur les deux instruments : les impulsions directes continuent.")
IMG(f"{FIG}/drift_by_speed.png", cap="Fig. 4.3 — Idem par vitesse (Q5 = le plus rapide) : monotone décroissant.")
H2("4.3 Ce qui aide : VWAP plate avant l'impulsion")
IMG(f"{FIG}/drift_by_eqslope.png", cap="Fig. 4.4 — Dérive par |pente VWAP| des 2 h précédentes (Q1 = plate) : "
    "le calme préalable de la VWAP améliore la réversion sur les deux instruments.")
H2("4.4 Matrice équilibre × directness (extraits, dérive 120 min, σ)")
MONO(
"définition                        NAS100   SPX500   lecture\n"
"eqA(inside>=50%) x dirA(retr<=15%)  +0.33   -0.36   contradiction inter-instruments\n"
"eqA x dirD(rapide)                  +0.35   -0.31   idem\n"
"eqC(absm<0.8) x dirB(eff>=0.6)      -0.27   -0.55   négatif partout\n"
"matin Paris 07-14, eqA x dirD       -0.90   -0.52   fortement négatif\n"
"eqB(cross&flat) x dirC(run>=4)      +0.22   +0.21   SEULE cellule cohérente positive\n"
"ablation: retr<=15% (direct)        +0.00   +0.04   la directness tue l'edge\n"
"ablation: retr>15% (non-direct)     +0.28   +0.16   c'est la non-directness qui aide")
P("Conclusion d'exploration : le phénomène recherché existe à l'ENVERS. La composante "
  "« absence de retracement » est un prédicteur de continuation, pas de réversion. Le nombre "
  "de croisements VWAP (rotation préalable) n'est pas monotone et n'ajoute rien ; la platitude "
  "de la VWAP est le seul marqueur d'équilibre robuste.")

# ---------- 5 baseline vs contexte
H1("5. Baseline vs contexte (§24) et stratégies candidates")
P("Candidats verrouillés (exécution héritée des leçons de la mission 1 : stop LARGE, cible "
  "VWAP dynamique, time-stop long — un stop serré détruit une dérive lente) :")
MONO(
"M2-CTX : touch bande 2.5σ, 09:30-13:30 ET, contexte requis:\n"
"         eq120_slope < 0.75 (VWAP plate)  ET  imp_maxrun >= 4 (impulsion soutenue)\n"
"         fade au marché à l'open de la minute suivante\n"
"         stop 2.5σ | cible VWAP dynamique | time-stop 240 min | max 6/jour | 2 sens\n"
"M2-BASE: identique SANS le contexte (baseline §24)")
MONO(
"TRAIN 2005-2014 (brut)      n     exp_sg    PF    Sharpe   années+\n"
"NQ  M2-CTX                1625    +0.085   1.11   +0.74     7/10\n"
"NQ  M2-BASE               2837    +0.136   1.13   +0.98     8/10   <- contexte NUIT\n"
"ES  M2-CTX                1181    +0.165   1.18   +1.09     8/10   <- contexte aide\n"
"ES  M2-BASE               2248    +0.092   1.12   +0.80     6/10")
P("Réponse à la question §24 : le contexte équilibre+impulsion n'apporte PAS d'amélioration "
  "robuste inter-instruments. Il double presque l'espérance sur ES mais la dégrade sur NQ. "
  "Un apport qui change de signe entre deux indices corrélés n'est pas une découverte "
  "exploitable.")
H2("Plateau de paramètres (TRAIN)")
P("Sweep 324 combinaisons (pente {0,5/0,75/1,0} × run {3/4/5} × stop {2/2,5/3} × time-stop "
  "{180/240/300} × 4 fenêtres) : 100 % (NQ) et 99 % (ES) de Sharpe brut positif — le "
  "phénomène in-sample est un plateau, pas un pic. Mais seulement ~55 % des combos ont "
  ">= 8/10 années positives (contre 87-100 % pour le candidat pré-open de la mission 1) : "
  "stabilité temporelle médiocre dès l'in-sample.")
IMG(f"{FIG}/equity_ctx_base.png", cap="Fig. 5.1 — PnL cumulé brut (σ) contexte vs baseline, TRAIN puis VAL (après la ligne).")

# ---------- 6 validation
H1("6. Validation out-of-sample (2015-2018) — lecture unique")
P("Critères pré-enregistrés avant lecture : A1 exp_sg >= +0,08 ; A2 >= 3/4 années positives ; "
  "A3 PF >= 1,10. Attente notée : décroissance probable.")
MONO(
"VAL 2015-2018 (brut)        n     exp_sg    PF    Sharpe   années+   verdict\n"
"NQ  M2-CTX                 794    +0.019   1.01   +0.07     1/4      FAIL\n"
"NQ  M2-BASE               1023    +0.012   0.97   -0.20     1/4      FAIL\n"
"ES  M2-CTX                 657    +0.009   1.00   +0.04     2/4      FAIL\n"
"ES  M2-BASE                929    +0.051   1.05   +0.34     3/4      FAIL (A1,A3)")
P("L'edge TRAIN s'effondre à ~0 hors échantillon, sur les quatre combinaisons, sans qu'aucune "
  "retouche n'ait été faite après lecture. Même signature de décroissance que le candidat "
  "pré-open de la recherche précédente : les anomalies de mean reversion intraday VWAP de "
  "l'ère 2005-2014 ne survivent pas à 2015+ sur ces données.")
IMG(f"{FIG}/yearly_exp.png", cap="Fig. 6.1 — Espérance/trade (σ) par année, TRAIN puis VAL (grisé).")
P("Vault (2019-20 + 2026) : NON ouvert pour cette mission — aucun candidat n'ayant passé la "
  "validation, une lecture n'aurait aucune valeur de confirmation et consommerait le holdout. "
  "(Divulgation : le Vault a été lu une fois lors de la mission précédente, pour la famille "
  "pré-open uniquement.)")

# ---------- 7 coûts & risque
H1("7. Coûts, risque, multiple testing")
P("Coûts : même au mieux de l'in-sample (ES M2-CTX, +0,62 pt brut/trade, σ médian ~2,2 pts), "
  "l'aller-retour ES base (~0,55 pt) absorbe l'essentiel de l'edge à l'échelle de prix "
  "2005-2014 ; NQ (+0,62 pt brut vs 0,63 pt de coûts) est à zéro net. Le ratio coût/σ "
  "s'améliore mécaniquement aux niveaux d'indice modernes (~×8-10), mais cela ne sauve pas un "
  "edge qui disparaît en OOS.")
tr = pd.read_parquet(f"{R}/M2-CTX_SPX500_TRAIN_trades.parquet")
d = st.daily_series(tr)
dsr = st.deflated_sharpe(st.sharpe_daily(d), len(d), tr["pnl_pts"].skew(),
                         tr["pnl_pts"].kurtosis(), 800)
P(f"Multiple testing : ~800 configurations/définitions effectives explorées en mission 2 "
  f"(registre : experiments/registry.csv, entrées m2-*). DSR du meilleur candidat TRAIN "
  f"(ES M2-CTX, Sharpe {st.sharpe_daily(d):.2f}) après déflation pour 800 essais : "
  f"{dsr:.2f} — l'edge in-sample lui-même n'est pas significatif une fois la recherche "
  "déflatée (contrairement au candidat pré-open m1, DSR 0,95). Le verdict OOS le confirme.")
P("Risque (TRAIN, ES M2-CTX, à titre documentaire) : WR 59 %, pire trade -9,5σ (gap "
  "au-delà du stop), MAE médian des gagnants ~0,6σ.")
IMG(f"{FIG}/mae_mfe.png", w=110, cap="Fig. 7.1 — MAE/MFE (ES M2-CTX TRAIN).")

# ---------- 8 visuels
H1("8. Visuels de trades (ES, M2-CTX, TRAIN)")
P("Zone verte = fenêtre d'équilibre (2 h), zone rouge = impulsion, pointillé rouge = stop 2,5σ.")
for i, (f, cap) in enumerate([
    ("trade_3_gagnant_type.png", "Gagnant type : équilibre nocturne, extension matinale laborieuse, retour VWAP (target)."),
    ("trade_2_trade_médian.png", "Trade médian."),
    ("trade_5_gagnant_avec_fort_MAE.png", "Gagnant après fort MAE — le stop large est structurel."),
    ("trade_1_trade_perdant_type.png", "Perdant type (time-stop/stop)."),
    ("trade_0_pire_trade.png", "Pire trade : continuation violente à travers le stop."),
    ("trade_6_rejete.png", "Exemple REJETÉ par la logique inversée : impulsion très directe depuis l'équilibre — elle continue (le filtre 'direct' aurait pris ce trade, à tort)."),
]):
    IMG(f"{FIG}/{f}", w=165, cap=f"Fig. 8.{i+1} — {cap}")

# ---------- 9 conclusion
H1("9. Conclusion")
P("Pourquoi cet edge semblait exister : sur 2005-2014, les extensions >= 2,5σ survenant après "
  "une VWAP plate réversaient de +0,2..+0,4σ en 2-4 h, sur les deux indices, avec un plateau "
  "de paramètres complet. Mécanisme plausible : épuisement d'extensions laborieuses dans des "
  "journées sans conviction directionnelle, à une époque de liquidité intraday plus mince.")
P("À quel point il est robuste : insuffisamment. (1) L'apport du contexte change de signe "
  "entre NQ et ES ; (2) la stabilité annuelle in-sample est médiocre (2011-2013 négatives) ; "
  "(3) le DSR déflaté est faible (~{:.2f}) ; (4) la validation 2015-2018 le réduit à néant "
  "sur les quatre combinaisons.".format(dsr))
P("Dans quelles conditions il fonctionne / échoue : il a fonctionné dans le régime 2005-2010 "
  "(forte volatilité, liquidité mince) ; il échoue après 2014 dans tous les régimes testés — "
  "ce n'est pas un problème de filtre mais une disparition du phénomène.")
P("Découverte structurelle réelle (et réutilisable) : la SÉQUENCE recherchée existe mais dans "
  "le sens OPPOSÉ — équilibre + expansion directe/rapide sans retracement = continuation "
  "(-0,2..-0,9σ selon les définitions), de façon cohérente sur les deux instruments et "
  "particulièrement le matin Paris. Si une piste mérite une future recherche dédiée, c'est "
  "celle du BREAKOUT de balance (trade dans le sens de l'impulsion), pas son fade — avec les "
  "mêmes exigences de validation, et en gardant à l'esprit que sa profitabilité après coûts "
  "reste à démontrer.")
P("Verdict final : les résultats ne justifient PAS un forward test du setup de mean reversion "
  "étudié. Aucune stratégie n'est livrée pour exécution réelle ; les règles exactes des "
  "candidats testés (M2-CTX / M2-BASE) restent documentées ci-dessus et dans le code pour "
  "reproductibilité.")

pdf.output(OUT)
print("report:", OUT, os.path.getsize(OUT))
