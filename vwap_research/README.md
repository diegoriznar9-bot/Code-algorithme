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
