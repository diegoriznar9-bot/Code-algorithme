# VWAP Systematic Research — NQ/ES (proxies) 

Recherche quantitative systématique des comportements de marché autour de la VWAP
(bandes de déviation, mean reversion, continuation), avec discipline stricte
anti-overfitting : splits temporels verrouillés a priori, registre d'expériences,
Vault holdout ouvert une seule fois sur règles gelées.

## Données
- **Primaire** : Oanda CFD M1 `NAS100_USD` (proxy NQ) et `SPX500_USD` (proxy ES),
  2005-01 → 2020-05, timestamps UTC (vérifié empiriquement), volume = tick count.
  Source : snapshot public `FutureSharks/financial-data` (commit dans
  `rawdata/financial-data.commit`).
- **Tranche moderne (Vault)** : échantillons getdata.finance `NAS100`/`SPX500` 1m,
  2026-03 → 2026-09, UTC.
- **Limite majeure documentée** : pas de volume CME réel ni de carnet futures ;
  la VWAP est pondérée par tick-volume CFD. Voir rapport, section Data.

## Splits (verrouillés avant toute exploration — voir `src/vwapresearch/config.py`)
- TRAIN 2005–2014 · VALIDATION 2015–2018 · VAULT 2019–2020-05 + 2026.

## Reproduction
```
pip install pandas numpy scipy matplotlib pyarrow statsmodels scikit-learn
git clone https://github.com/FutureSharks/financial-data  # commit épinglé
# + clones getdata-finance (commits épinglés), copier vers rawdata/ (cf. ingest.py)
python3 scripts/audit_timezone.py
python3 -m vwapresearch.ingest        # ou PYTHONPATH=src python3 src/vwapresearch/ingest.py
python3 scripts/build_features_events.py
python3 scripts/phase1_descriptive.py # TRAIN uniquement
```

## Pipeline complet (ordre d'exécution)
1. `scripts/audit_timezone.py` — preuve empirique que les timestamps Oanda sont UTC
2. `PYTHONPATH=src python3 src/vwapresearch/ingest.py` — parquet propres
3. `scripts/audit_quality.py` — audit qualité (results/data_audit.md)
4. `scripts/build_features_events.py` — features + événements, splits TRAIN/VAL/VAULT
5. `scripts/phase1_descriptive.py` — cartographie (TRAIN)
6. `scripts/phase2_interactions.py` — interactions à heure fixée (TRAIN)
7. `scripts/phase3_candidates.py`, `phase3_preopen.py`, `phase3b_preopen_grid.py` — candidats & plateaux (TRAIN)
8. `scripts/phase5_validation.py` — validation 2015-2018, règles gelées
9. `scripts/phase6_stress.py` — coûts, perturbations, walk-forward, Monte Carlo, DSR
10. `scripts/phase7_vault.py` — OUVERTURE UNIQUE du Vault (2019-20 + 2026)
11. `scripts/phase8_figures.py`, `phase9_deliverables.py`, `phase10_report.py` — figures, CSV, PDF

## Conclusion (résumé)
Une anomalie de mean reversion pré-open (07:30–09:30 ET) autour des bandes VWAP de session
était réelle sur 2005–2014 (plateau complet de paramètres, deux instruments, DSR 0,95),
mais a décru hors échantillon : validation 2015–2018 en échec sur critères pré-enregistrés,
Vault 2019–2020 négatif, tranche 2026 indistinguable de zéro (n≈70–90).
**Aucune stratégie n'est recommandée pour le trading réel.**
Rapport complet : `results/VWAP_Research_Report.pdf` · Registre : `experiments/registry.csv`.

## Mission 2 (2026-09-18) : Équilibre → Expansion directe → Extension extrême → Fade
Recherche ciblée (scripts `scripts/m2_*.py`, résultats `results/m2/`).
**Verdict : hypothèse forte falsifiée et INVERSÉE** — les impulsions directes/rapides sortant
d'un équilibre continuent (−0,2..−0,9σ) ; seules les extensions laborieuses réversent.
La variante récupérable (VWAP plate + impulsion soutenue, fade 2,5σ, 09h30–13h30 ET) est
marginale in-sample, incohérente NQ/ES, et son edge tombe à ≈0 en validation 2015–2018
(4/4 candidats en échec sur critères pré-enregistrés). Vault non ouvert (rien à confirmer).
Rapport : `results/m2/M2_Expansion_MeanReversion_Report.pdf`.
