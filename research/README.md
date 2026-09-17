# Recherche quantitative — stratégie Bitcoin long terme

Étude complète : **[RAPPORT.md](RAPPORT.md)**.

## Reproduire

```bash
pip install -r requirements.txt
python run_01_baseline.py     # données, stratégie de référence, ambiguïtés, coûts
python run_02_ma_robustness.py# balayage SMA 104-208 + entrées alternatives
python run_03_amplitude.py    # tassement des amplitudes : mesures, modèles, OOS
python run_04_adaptive.py     # calibration + comparaison des sorties adaptatives
python run_05_robustness.py   # sensibilités + bootstrap par blocs (graine 42)
python run_06_charts.py       # les 10 graphiques du rapport
```

Tous les paramètres modifiables (frais, slippage, longueur de MA, fractions
vendues, seuils, fenêtres de volatilité, périodes d'apprentissage/test) sont
dans `src/config.py`. Les scripts n'utilisent que le snapshot commité
`data/btc_coinmetrics_community_20260917.csv` : les résultats sont
reproductibles à l'identique.

## Structure

- `src/` — moteur de backtest hebdomadaire sans look-ahead (`strategy.py`),
  filtres d'entrée (`entries.py`), seuils adaptatifs (`adaptive.py`),
  métriques (`metrics.py`), données (`data.py`), configuration (`config.py`)
- `data/` — snapshot Coin Metrics community (quotidien, 2010-2026)
- `output/` — figures (`fig01`–`fig10`), tables CSV, journaux, transactions
  (`trades_recapitulatif.csv`)
