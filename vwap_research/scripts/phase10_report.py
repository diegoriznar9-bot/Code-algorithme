"""PHASE 10 — final PDF report (mission §89)."""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import pandas as pd
from fpdf import FPDF

ROOT = os.path.join(os.path.dirname(__file__), "..")
R = os.path.join(ROOT, "results")
FIG = os.path.join(R, "figures")
OUT = os.path.join(R, "VWAP_Research_Report.pdf")

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONTB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONTM = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"


class PDF(FPDF):
    def header(self):
        if self.page_no() > 1:
            self.set_font("dejavu", "", 7)
            self.set_text_color(130)
            self.cell(0, 5, "Recherche systématique VWAP — NQ/ES (proxies CFD) — 2026-09-17", align="R")
            self.ln(6)
            self.set_text_color(0)

    def footer(self):
        self.set_y(-12)
        self.set_font("dejavu", "", 7)
        self.set_text_color(130)
        self.cell(0, 5, f"page {self.page_no()}", align="C")
        self.set_text_color(0)


pdf = PDF(format="A4")
pdf.add_font("dejavu", "", FONT)
pdf.add_font("dejavu", "B", FONTB)
pdf.add_font("mono", "", FONTM)
pdf.set_auto_page_break(True, margin=14)
pdf.set_margins(16, 12, 16)


def H1(t):
    pdf.add_page()
    pdf.set_font("dejavu", "B", 14)
    pdf.set_text_color(20, 60, 130)
    pdf.multi_cell(0, 7, t)
    pdf.set_text_color(0)
    pdf.ln(2)


def H2(t):
    pdf.ln(2)
    pdf.set_font("dejavu", "B", 11)
    pdf.set_text_color(20, 60, 130)
    pdf.multi_cell(0, 6, t)
    pdf.set_text_color(0)
    pdf.ln(1)


def P(t, size=9):
    pdf.set_font("dejavu", "", size)
    pdf.multi_cell(0, 4.6, t)
    pdf.ln(1)


def MONO(t, size=6.8):
    pdf.set_font("mono", "", size)
    pdf.multi_cell(0, 3.6, t)
    pdf.ln(1)


def IMG(path, w=170, caption=None):
    if not os.path.exists(path):
        return
    if pdf.get_y() > 190:
        pdf.add_page()
    pdf.image(path, w=w)
    if caption:
        pdf.set_font("dejavu", "", 7.5)
        pdf.set_text_color(90)
        pdf.multi_cell(0, 4, caption)
        pdf.set_text_color(0)
    pdf.ln(2)


def csv_block(path, max_rows=40, round_=3, cols=None):
    df = pd.read_csv(path)
    if cols:
        df = df[cols]
    MONO(df.head(max_rows).round(round_).to_string(index=False))


# ================================================================ title page
pdf.add_page()
pdf.ln(30)
pdf.set_font("dejavu", "B", 20)
pdf.multi_cell(0, 10, "Recherche quantitative systématique\nautour de la VWAP", align="C")
pdf.ln(4)
pdf.set_font("dejavu", "", 12)
pdf.multi_cell(0, 7, "NQ / MNQ / ES / MES (proxies indice Nasdaq-100 & S&P 500)\n"
               "Scalping et intraday — 2005-2026", align="C")
pdf.ln(10)
pdf.set_font("dejavu", "", 10)
pdf.multi_cell(0, 6,
    "Rapport final — 17 septembre 2026\n"
    "Méthodologie : splits temporels verrouillés a priori, registre d'expériences,\n"
    "Vault holdout ouvert une seule fois sur règles gelées.", align="C")
pdf.ln(20)
pdf.set_font("dejavu", "B", 11)
pdf.set_text_color(150, 30, 30)
pdf.multi_cell(0, 6,
    "Conclusion principale : un comportement de mean reversion pré-open réel et robuste\n"
    "a été identifié sur 2005-2014 (DSR 0,95), mais il a décru hors échantillon (2015-2018)\n"
    "et le Vault (2019-2020, 2026) ne démontre pas d'edge exploitable actuellement.\n"
    "Aucune stratégie n'est recommandée pour le passage en réel.", align="C")
pdf.set_text_color(0)

# ================================================================ 1 exec summary
H1("1. Executive Summary")
P("Question étudiée : existe-t-il sur NQ/ES (ou leurs micros) un comportement suffisamment stable "
  "autour de la VWAP pour construire une stratégie scalping/intraday rentable après coûts, dont "
  "l'avantage persiste hors échantillon et ne soit pas un artefact de data-mining ?")
P("Démarche : cartographie descriptive large (Phase 1), déconfusion des interactions (Phase 2), "
  "mesure de la dérive PURE du prix après contact de bande (l'innovation méthodologique clé de "
  "cette étude : une probabilité de « retour à la VWAP » élevée peut être un artefact de la VWAP "
  "qui rattrape le prix), construction de candidats déterministes (Phase 3), sweeps orientés "
  "plateaux, validation sur période gelée, batterie de stress, walk-forward, ouverture unique du Vault.")
P("Résultat principal : un seul phénomène a survécu au filtrage économique en découverte : la "
  "réversion des extensions au-delà des bandes VWAP de session pendant la fenêtre pré-open "
  "(07:30-09:30 ET). Sur 2005-2014 (TRAIN) : dérive de retour de +0,2 à +0,5σ en 1-2h, monotone "
  "en profondeur d'extension, présente sur les DEUX instruments ; stratégie PREFADE-S "
  "(fade L2, stop 2,5σ, cible VWAP, time-stop 180 min) : PF brut 1,31 (NAS100) / 1,18 (SPX500), "
  "Sharpe brut 1,94 / 1,08, 10/10 et 8/10 années positives, plateau de paramètres massif "
  "(162/162 combinaisons positives), Deflated Sharpe Ratio 0,95 après prise en compte de "
  "~400 essais.")
P("MAIS : la validation 2015-2018 (règles gelées avant lecture) a échoué aux critères "
  "pré-enregistrés (NAS100 : -0,12σ ; SPX500 : +0,01σ), et le Vault 2019-2020 a confirmé la "
  "décroissance (-0,17σ / -0,11σ). La tranche moderne 2026 (source disjointe) est légèrement "
  "positive (+0,09σ / +0,12σ) mais sur 67-87 trades, statistiquement indistinguable de zéro.")
P("Limites majeures : données CFD (Oanda) et non futures CME ; volume = tick count (VWAP "
  "approchée) ; pas de carnet d'ordres ; trou de données 2020-2026. Détail en section 2.")

# ================================================================ 2 data
H1("2. Données")
P("Source primaire : bars M1 CFD Oanda NAS100_USD (proxy NQ) et SPX500_USD (proxy ES), "
  "snapshot public FutureSharks/financial-data (commit 7ba1d404, 2020-05-28). Couverture "
  "2005-01-02 → 2020-05-14 ; 4 283 343 bars NAS100, 4 011 719 bars SPX500. Timestamps naïfs "
  "vérifiés empiriquement comme UTC : le pic d'activité de l'open cash US tombe à 14:30 UTC en "
  "hiver et 13:30 UTC en été (= 09:30 America/New_York sous EST/EDT). Toutes les analyses "
  "utilisent une conversion timezone explicite vers America/New_York (jamais d'offset codé en dur).")
P("Tranche moderne : échantillons publics getdata.finance NAS100/SPX500 1m, 2026-03-12 → "
  "2026-09-11 (~180 000 bars chacun), timestamps UTC explicites, source de flux distincte. "
  "Utilisée EXCLUSIVEMENT comme composante du Vault.")
P("Qualité : 0 volume négatif ; trous non-weekend = jours fériés US attendus (Good Friday, "
  "Noël, Nouvel An) ; ~600-1100 bars par jour de cotation (les minutes sans tick n'existent pas, "
  "ce qui est correctement géré par les cumuls VWAP) ; 15-17 bars avec |rendement 1-min| > 2%, "
  "tous en mars 2020 (COVID) ou événements macro plausibles.")
P("LIMITES DOCUMENTÉES : (1) le « volume » Oanda est un nombre de ticks, pas le volume CME : "
  "la VWAP est donc une approximation tick-pondérée de la vraie VWAP futures ; (2) l'échelle du "
  "tick-volume n'est pas comparable entre années (croissance du courtier) — seule la pondération "
  "intra-journalière est utilisée ; (3) prix CFD : pas de basis futures, pas de rolls (avantage : "
  "aucun artefact de contrat continu ; inconvénient : microstructure d'exécution non identique) ; "
  "(4) fenêtre 17:00-18:00 ET absente (maintenance) ; (5) aucune donnée 2020-06 → 2026-02. "
  "Les coûts sont modélisés en points d'indice avec les valeurs réelles NQ/MNQ/ES/MES.")
MONO(open(os.path.join(R, "data_audit.md")).read()[:2600])

# ================================================================ 3 vwap defs
H1("3. Définitions VWAP")
P("VWAP étudiées (toutes calculées en flux causal, prix (H+L+C)/3, pondération tick-volume) :\n"
  "• Session (ancrage 18:00 ET, jour futures CME) — ancre PRINCIPALE retenue ;\n"
  "• Minuit New York ; • Minuit Europe/Paris ; • Open RTH 09:30 ET ; • Weekly (dimanche 18:00 ET).\n"
  "Bandes : VWAP ± L·σ, σ = √( Σw·p²/Σw − VWAP² ) (dispersion pondérée cumulative du prix "
  "autour de la VWAP courante), L ∈ {0.5, 1, 1.5, 2, 2.5, 3}.")
P("La comparaison des ancres quotidiennes (minuit Paris vs minuit NY vs 18:00 ET vs RTH) n'a pas "
  "été poussée jusqu'au backtest pour chaque variante : l'ancre session 18:00 ET a été retenue "
  "comme référence économique standard des futures CME ; les bandes weekly ont fait l'objet d'une "
  "famille dédiée (section 6). Ceci est une limitation de couverture assumée, documentée pour "
  "éviter un espace de recherche non maîtrisé.")

# ================================================================ 4 exploration
H1("4. Recherche exploratoire (TRAIN 2005-2014 uniquement)")
P("179 505 événements de contact de bande sur NAS100, 216 876 sur SPX500 (niveaux 1→3, deux "
  "côtés, hystérésis 0,3σ). Principaux faits descriptifs (tous per-TRAIN, cf. results/phase1) :")
P("• L'heure domine tout : P(toucher la VWAP en 60 min | contact L2) varie de ~65% (09:30-10:00 "
  "ET) à ~13-19% (13:00-16:00 ET).\n"
  "• Numéro de contact : décroissance MONOTONE de la réversion (1er contact : P60 ≈ 0,65-0,70 ; "
  "4e+ : ≈ 0,38-0,42) — relation progressive, pas un seuil.\n"
  "• Vitesse d'arrivée : monotone — arrivée lente → meilleure réversion.\n"
  "• Pente signée : un contact DANS le sens de la pente VWAP réverse mieux qu'un contact "
  "contre-pente (contre-intuitif vs l'hypothèse « VWAP plate = réversion »).\n"
  "• Séquences : 2 290 des 2 581 journées avec contact L2 touchent LES DEUX côtés ; un contact "
  "L2 précédé d'un contact opposé le même jour a une meilleure espérance de fade (+0,18σ vs "
  "+0,06σ en proxy).")
IMG(f"{FIG}/NAS100_heat_tod_level.png", w=150,
    caption="Fig. 4.1 — NAS100 TRAIN : P(retour VWAP en 60 min) par heure × niveau.")
IMG(f"{FIG}/SPX500_heat_tod_level.png", w=150,
    caption="Fig. 4.2 — SPX500 TRAIN : même carte.")
H2("4.b La mesure décisive : dérive pure du prix")
P("Une P(retour VWAP) élevée peut refléter la convergence de la VWAP vers le prix (aucun edge "
  "de prix). Nous avons donc mesuré la dérive PURE : rendement forward du prix signé vers la "
  "VWAP, sans stop ni cible, en unités de σ. Résultat : une seule zone où le PRIX revient "
  "réellement : le pré-open 08:00-09:30 ET (+0,21 à +0,44σ à 60 min selon le niveau, NAS100 ; "
  "+0,22 à +0,37σ SPX500), effet croissant avec le niveau et l'horizon. Le soir (18:00-24:00), "
  "les extensions CONTINUENT (dérive de fade négative), et l'après-midi 13:00-15:30 est en "
  "continuation modérée. C'est cette carte qui a orienté toute la suite.")

# ================================================================ 5 hypotheses
H1("5. Hypothèses testées")
P("Familles explorées (registre complet : experiments/registry.csv, 27 entrées, ~400 "
  "backtests/configurations effectifs) :\n"
  "H1 Fade L1.5-L3 → VWAP (fenêtres : matin, pré-open, soir, après-midi, nuit) ;\n"
  "H2 Entrée limite à la bande vs marché à l'open suivant ;\n"
  "H3 Réintégration (false-breakout) après overshoot ;\n"
  "H4 Continuation après-midi (anti-fade, avec pente) ;\n"
  "H5 Pullback de continuation après tenue de la VWAP (dominance 80% sur 45 min) ;\n"
  "H6 Fade des bandes WEEKLY (semaine mature) ;\n"
  "H7 Filtres : touch_no, pente signée, vitesse d'arrivée, distance daily/weekly, overshoot ;\n"
  "H8 Stops serrés vs larges, cibles VWAP dynamique vs L1 vs horizon fixe.")

# ================================================================ 6 failed
H1("6. Hypothèses rejetées (résultats négatifs importants)")
P("• Fade L2 naïf du matin (09:30-11:30), entrée marché : espérance BRUTE ≈ +0,05 pt "
  "(≈ +0,015σ) — la P(retour) élevée est essentiellement de la convergence VWAP ; les coûts "
  "rendent le trade négatif (-0,58 pt net NQ, era TRAIN). L'edge « évident » n'existe pas.\n"
  "• Entrée limite à la bande : PIRE que l'entrée marché (-0,22 pt brut) — sélection adverse "
  "(le limite n'est rempli que quand le prix traverse) + stop même bougie.\n"
  "• Stops serrés (1-1,5σ) sur le pré-open : détruisent un edge de dérive lente (la réversion "
  "vient souvent après une extension supplémentaire).\n"
  "• Réversion du SOIR (18:00-24:00 ET) : statistiquement réelle (P60 ≈ 0,60-0,73) mais "
  "σ ≈ 0,4-0,9 pt → récompense L2 ≈ 0,9-1,7 pt vs ~0,6-0,9 pt de coûts A/R : MORTE en coûts.\n"
  "• Continuation après-midi : l'excursion médiane de continuation (~0,9σ) n'excède pas la "
  "réversion (~0,85σ) ; divergence NQ/ES ; aucun design testé n'a d'edge net.\n"
  "• Pullback après tenue de VWAP (trend continuation) : dérive ≤ 0,06σ — rien.\n"
  "• Bandes weekly : +0,08-0,14 ATRj côté bas sur NQ mais ~0/négatif sur ES → incohérent, "
  "suspect de biais haussier séculaire : rejeté.\n"
  "• Filtres touch_no et overshoot : effets de sens OPPOSÉ entre NQ et ES → rejetés.\n"
  "• Asymétrie long/short : s'inverse entre instruments (NQ : long > short ; ES : short > long) "
  "→ règle symétrique conservée.")

# ================================================================ 7 candidates
H1("7. Stratégies candidates")
P("PREFADE-S (simple, verrouillée) :\n"
  "  Instruments cibles : NQ/MNQ (via NAS100), ES/MES (via SPX500)\n"
  "  Session : jour futures 18:00→17:00 ET ; Timezone : America/New_York ; TF : 1 minute\n"
  "  VWAP : ancrage session 18:00 ET, prix (H+L+C)/3, pondération volume\n"
  "  Bandes : VWAP ± L·σ (σ pondéré cumulatif)\n"
  "  Setup : contact de la bande 2,0σ entre 07:30:00 et 09:29:59 ET (tout contact, hystérésis 0,3σ)\n"
  "  Entrée : marché à l'open de la minute suivante, direction vers la VWAP\n"
  "  Stop : 2,5σ (σ au signal) depuis l'entrée, fixe ; priorité au stop en cas d'ambiguïté intra-bougie\n"
  "  Cible : VWAP de session dynamique ; Time-stop : 180 min ; Max 6 trades/jour ; deux sens\n"
  "  Sizing recherche : 1 contrat, pas de scale-in ; sortie forcée 16:55 ET (jamais atteinte)\n"
  "PREFADE-F : PREFADE-S + filtre d'arrivée lente |speed5| < 0,9 (vitesse 5 min normalisée vol).")
P("Justification des paramètres : centre du plateau (niveau {1.5,2,2.5} → 2 ; stop {2,2.5,3} → "
  "2,5 ; time-stop {120,180,240} → 180 ; fenêtre {07:00,07:30,08:00}→09:30 → 07:30). Le maximum "
  "historique n'a PAS été retenu.")

# ================================================================ 8 plateaus
H1("8. Robustesse des paramètres (plateaux)")
P("Sweep 162 combinaisons (niveau × stop × time-stop × fenêtre × cible) sur TRAIN : "
  "100% des combinaisons ont un Sharpe brut positif sur les deux instruments (médiane 1,60 "
  "NAS100 / 1,72 SPX500) ; 87% (NAS100) et 100% (SPX500) ont ≥ 8/10 années positives. "
  "Perturbations ±5/10/20% du niveau, du stop et du time-stop : Sharpe TRAIN stable "
  "(1,85-2,02 NAS100 ; 0,82-1,30 SPX500) — dégradation progressive, aucun effondrement.")
IMG(f"{FIG}/NAS100_plateau_level_stop.png", w=120,
    caption="Fig. 8.1 — NAS100 : Sharpe brut TRAIN, niveau × stop (fenêtre 07:30-09:30, cible VWAP, ts 180).")
IMG(f"{FIG}/SPX500_plateau_level_stop.png", w=120,
    caption="Fig. 8.2 — SPX500 : même surface.")
IMG(f"{FIG}/NAS100_plateau_window_ts.png", w=120,
    caption="Fig. 8.3 — NAS100 : fenêtre × time-stop (L2, cible VWAP).")

# ================================================================ 9 multiple testing
H1("9. Multiple testing & Deflated Sharpe Ratio")
P("Registre : 27 entrées consolidées couvrant ~400 backtests/configurations et ~40 tables "
  "descriptives (experiments/registry.csv, append-only, horodaté). Les hypothèses rejetées y "
  "figurent explicitement.")
P("DSR : Sharpe quotidien brut TRAIN de PREFADE-S NAS100 = 1,97 annualisé ; avec correction de "
  "sélection pour 400 essais, skew et kurtosis des trades : DSR = 0,948 (probabilité ~95% que le "
  "Sharpe TRAIN excède le maximum attendu de 400 essais sans skill). Le phénomène EN ÉCHANTILLON "
  "n'était donc pas un artefact de sélection. NB : le DSR ne protège pas contre un changement de "
  "régime — c'est précisément ce que la suite démontre. Approche PBO complète non réalisée "
  "(une seule famille finale) ; le walk-forward (sec. 12) en tient lieu partiellement.")

# ================================================================ 10-11 IS/VAL
H1("10. In-Sample (TRAIN 2005-2014)")
MONO(pd.read_csv(f"{R}/phase5/validation_summary.csv").query("split=='TRAIN'").round(3).to_string(index=False))
P("Détail annuel : cf. results/phase5/*_TRAIN_yearly.csv. 10/10 années brutes positives "
  "(PREFADE-S NAS100), 8/10 (SPX500).")
IMG(f"{FIG}/NAS100_mae_mfe.png", w=110, caption="Fig. 10.1 — MAE/MFE des trades PREFADE-S NAS100 TRAIN.")
IMG(f"{FIG}/NAS100_pnl_hist.png", w=110, caption="Fig. 10.2 — Distribution des PnL de trade (bruts).")

H1("11. Validation (2015-2018, règles gelées)")
P("Critères d'acceptation écrits AVANT lecture : A1 espérance brute ≥ +0,08σ ; A2 ≥ 3/4 années "
  "positives ; A3 PF brut ≥ 1,10 ; A4 net NQ > 0 (coûts era-vrais).")
MONO(pd.read_csv(f"{R}/phase5/validation_summary.csv").query("split=='VAL'").round(3).to_string(index=False))
P("VERDICT : PREFADE-S échoue A1-A3 (NAS100) et A1 (SPX500). PREFADE-F : NAS100 passe A1/A3 "
  "mais échoue A2 (2/4 années) ; SPX500 échoue A1 (≈ 0σ). Les années 2017 (dérive nocturne à "
  "très basse volatilité) et 2018 (continuation en haute volatilité) sont toutes deux négatives : "
  "l'affaiblissement n'est PAS réductible à un simple régime de volatilité. Aucune itération "
  "n'a été effectuée sur VAL après lecture de ces chiffres.")

# ================================================================ 12 walkforward
H1("12. Walk-forward")
P("Protocole : fenêtre d'entraînement expansive (2005→N-1), re-sélection annuelle du meilleur "
  "combo (grille 27) par Sharpe, application à l'année N. Comparé à la règle fixe centre-plateau.")
MONO(pd.read_csv(f"{R}/phase6/NAS100_walkforward.csv").round(3).to_string(index=False))
MONO(pd.read_csv(f"{R}/phase6/SPX500_walkforward.csv").round(3).to_string(index=False))
P("Lecture : OOS positif la plupart des années jusqu'en 2016, effondrement en 2017 (-2,4 de "
  "Sharpe OOS NAS100) ; la re-sélection adaptative n'aurait PAS détecté la décroissance à temps.")
IMG(f"{FIG}/walkforward.png", w=165, caption="Fig. 12.1 — Sharpe OOS par année de test.")

# ================================================================ 13 vault
H1("13. Vault final (ouvert une seule fois)")
P("Composition : Oanda 2019-01-01→2020-05-14 + getdata.finance 2026-03-12→2026-09-11. "
  "Attente pré-enregistrée avant ouverture : ≈ 0 ou négatif (hypothèse de décroissance issue de "
  "la validation). Résultats (bruts ; net = coûts base era-vrais) :")
MONO(pd.read_csv(f"{R}/phase7_vault/vault_results.csv").round(3).to_string(index=False))
P("Lecture : 2019-2020 confirme la décroissance (σ-espérance négative sur les deux instruments). "
  "2026 est légèrement positif (+0,09σ NAS100, +0,12σ SPX500, PREFADE-S) mais n = 67/87 trades "
  "sur 6 mois → IC95% ≈ ±0,2σ : indistinguable de zéro. En points modernes le net est positif "
  "(+14,1 pts/trade NQ) — conséquence mécanique du niveau d'indice, PAS une preuve d'edge. "
  "Aucune modification post-Vault n'a été faite ni ne sera présentée comme out-of-sample.")
IMG(f"{FIG}/decay_curve.png", w=170,
    caption="Fig. 13.1 — Espérance brute par trade (σ) par année : TRAIN | VAL (gris) | VAULT (rouge).")
IMG(f"{FIG}/NAS100_equity_sigma.png", w=165,
    caption="Fig. 13.2 — NAS100 : PnL cumulé brut (unités σ), toutes périodes.")
IMG(f"{FIG}/SPX500_equity_sigma.png", w=165,
    caption="Fig. 13.3 — SPX500 : idem.")

# ================================================================ 14 costs
H1("14. Coûts & slippage")
P("Modèle par side (points d'indice) : demi-spread (1 tick) + slippage + commission. "
  "Base/Stress1 (slippage 1 tick)/Stress ×1,5/Stress ×2 ; plus slip +1/+2 ticks à l'exécution. "
  "PREFADE-F, espérance nette par trade :")
MONO(pd.read_csv(f"{R}/phase6/NAS100_costs.csv").round(3).to_string(index=False))
MONO(pd.read_csv(f"{R}/phase6/SPX500_costs.csv").round(3).to_string(index=False))
P("Points clés : (1) aux niveaux d'indice 2005-2018, seul NQ (gros contrat) survit au scénario "
  "base, et +1 tick de slippage le tue ; MNQ/ES/MES négatifs partout → l'edge par trade était "
  "trop mince pour les micros (§75 de la mission : marge insuffisante). (2) Les coûts étant "
  "fixes en points alors que σ suit le niveau de l'indice, le ratio coût/σ à 24 000 points "
  "(2026) est ~8-10× plus favorable qu'à 2 500 points — mais l'edge σ-normalisé du Vault "
  "moderne reste indistinguable de zéro, donc cela ne sauve pas la stratégie.")
IMG(f"{FIG}/cost_sensitivity.png", w=165, caption="Fig. 14.1 — Sensibilité aux scénarios de coûts.")

# ================================================================ 15-18 stress
H1("15. Stress tests, MAE/MFE, tail risk, Monte Carlo")
bat = json.load(open(f"{R}/phase6/NAS100_battery.json"))
P("PREFADE-S NAS100 TRAIN (bruts) :\n"
  f"• Concentration : total +{bat['total']:.0f} pts ; sans les 10 meilleurs trades : "
  f"+{bat['wo_best10']:.0f} ; sans le meilleur 1% : +{bat['wo_best1pct']:.0f} → pas de "
  "dépendance à une poignée de trades.\n"
  f"• Suppression aléatoire de 5/10/20% des trades (500 tirages) : P(total ≤ 0) = 0 dans tous "
  "les cas.\n"
  f"• Monte Carlo (2000 rééchantillonnages par blocs de jours) : max drawdown p95 = "
  f"{bat['MC_maxDD_p95']:.0f} pts pour +{bat['total']:.0f} pts de PnL total TRAIN ; "
  f"total p5 = +{bat['MC_total_p5']:.0f} pts.\n"
  f"• Plus longue série perdante : {bat['losing_streak']} trades.\n"
  "• Tail risk : stop 2,5σ + time-stop bornent la perte par trade ; les 5 pires trades TRAIN "
  f"coûtent ensemble {bat['total']-bat['wo_worst5']:+.0f} pts (détail dans "
  "deliverables/all_trades.csv) ; en journée de crise (mars 2020, Vault), la stratégie a produit "
  "son max DD (-473 pts NAS100 2019-20) : les journées à gap+continuation restent le mode de "
  "perte principal.\n"
  "• MAE/MFE : cf. Fig. 10.1 ; la médiane des MAE des gagnants ~0,6σ justifie le stop large.")

# ================================================================ 19 regimes
H1("16. Régimes de marché")
P("Le phénomène pré-open était plus fort en volatilité élevée (2008-2011) mais l'explication "
  "« régime de volatilité » ne tient pas : 2017 (basse vol) ET 2018 (haute vol) sont négatives ; "
  "2020 (COVID, Vault) est positive en points mais négative en σ. La décroissance est mieux "
  "expliquée par l'approfondissement de la liquidité overnight/pré-open après 2015 "
  "(arbitrage de l'anomalie) que par un régime cyclique. Hypothèse économique initiale du "
  "phénomène : les extensions nocturnes sur liquidité mince, loin de la VWAP accumulée depuis "
  "18:00, étaient corrigées à l'approche de l'open par le positionnement pré-RTH.")

# ================================================================ 20 final strategy
H1("17. Stratégie finale : règles exactes (non recommandée en réel)")
P("La spécification complète et exécutable de PREFADE-S/F figure en section 7 et dans "
  "results/deliverables/final_config.json. Elle est fournie pour reproductibilité et pour un "
  "éventuel suivi en paper trading, PAS comme recommandation de trading réel (le niveau de "
  "preuve hors échantillon est insuffisant).")
H2("Pseudocode")
MONO(
"chaque minute t (bar clôturée), heure NY :\n"
"  si 07:30 <= t < 09:30 et sigma_warmup >= 25 bars :\n"
"    upper = vwap_sess(t) + 2.0*sigma_sess(t) ; lower = vwap_sess(t) - 2.0*sigma_sess(t)\n"
"    si high(t) >= upper et etat_upper == armé :  signal SHORT ; etat_upper = déclenché\n"
"    si low(t)  <= lower et etat_lower == armé :  signal LONG  ; etat_lower = déclenché\n"
"    (ré-armement quand close repasse 0.3*sigma à l'intérieur de la bande)\n"
"    [PREFADE-F : ignorer le signal si |speed5(t)| >= 0.9]\n"
"  à signal (si flat, < 6 trades ce jour) :\n"
"    entrer au marché à l'open de t+1 ; stop = entry -/+ 2.5*sigma(t) ;\n"
"    cible = vwap_sess (recotée chaque minute) ; time-stop 180 min (sortie au close) ;\n"
"    ambiguïté intra-bougie résolue stop d'abord (pessimiste).")

# ================================================================ 21 failure modes
H1("18. Failure modes & considérations opérationnelles")
P("Modes de défaillance observés : (1) journées de continuation pré-open→open (gap qui ne "
  "réintègre pas) : pertes séquentielles jusqu'à 6 stops de 2,5σ ; (2) régimes de dérive "
  "nocturne persistante (2017) : espérance négative pendant des mois ; (3) slippage : +1 tick "
  "par side suffit à annuler l'edge historique sur NQ ; (4) le signal exige un flux 1-min "
  "fiable dès 07:30 ET et une exécution < 1 min.")
P("Opérationnel (si paper trading) : suivre l'espérance σ-normalisée par trade et le PF sur "
  "fenêtres de 100 trades ; arrêt si PF < 1 sur 200 trades ; ne pas trader les jours fériés "
  "écourtés ; vérifier la VWAP du courtier contre la définition exacte (ancrage 18:00 ET, "
  "pondération volume, (H+L+C)/3).")

# ================================================================ 23 conclusion
H1("19. Conclusion")
P("Ce que nous avons découvert : une anomalie de mean reversion pré-open (07:30-09:30 ET) "
  "autour des bandes VWAP de session, réelle sur 2005-2014 : ~1 800 trades par instrument, "
  "espérance brute +0,21σ (NAS100) / +0,16σ (SPX500), plateau de paramètres complet, présence "
  "sur deux instruments corrélés mais distincts, DSR 0,95 après déflation pour ~400 essais, "
  "concentration et Monte Carlo sains.")
P("Ce que nous avons ensuite démontré en essayant de la casser : l'anomalie a décru — "
  "validation 2015-2018 en échec sur critères pré-enregistrés, Vault 2019-2020 négatif, "
  "tranche 2026 indistinguable de zéro (n trop faible). La décroissance n'est pas un artefact "
  "de nos choix : elle apparaît avec règles gelées, sur les deux instruments, en walk-forward "
  "adaptatif comme en règle fixe.")
P("Réponse à la question de la mission (§100) : sur les données étudiées, NON — nous ne "
  "pouvons pas démontrer aujourd'hui un comportement VWAP suffisamment stable pour une "
  "stratégie scalping/intraday rentable après coûts dont l'avantage persiste hors échantillon. "
  "Le seul candidat sérieux a existé puis s'est éteint ; le présenter comme exploitable serait "
  "précisément le data-mining que la mission interdit.")
P("Recommandations : (1) ne pas passer en réel ; (2) si souhaité, paper trading de PREFADE-S "
  "sur données futures CME réelles (volume vrai) pour lever la limite majeure de cette étude — "
  "la tranche 2026 positive justifie ce suivi, pas plus ; (3) toute reprise de recherche "
  "devrait d'abord acquérir des données CME 1-min avec volume réel 2020-2026, re-tester la "
  "carte de dérive pure sur 2021-2026, et explorer les familles restées ouvertes "
  "(ancres alternatives comparées, confluence daily/weekly conditionnelle, order flow).")
P("Toute personne disposant du dépôt peut reproduire l'intégralité des résultats : "
  "cf. vwap_research/README.md (sources publiques épinglées par commit, scripts numérotés, "
  "seeds fixes).")

pdf.output(OUT)
print("report written:", OUT, os.path.getsize(OUT), "bytes")
