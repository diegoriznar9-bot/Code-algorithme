# Phase 6 — robustness battery (2005-2018, Vault sealed)

## NAS100
### Cost & slippage scenarios (PREFADE-F, net exp pts/trade)
scenario instr  net_exp_TRAIN  net_exp_VAL    n
    base    NQ          0.334        0.153 1000
    base   MNQ         -0.056       -0.237 1000
 stress1    NQ          0.084       -0.097 1000
 stress1   MNQ         -0.306       -0.487 1000
stress15    NQ          0.019       -0.162 1000
stress15   MNQ         -0.566       -0.747 1000
 stress2    NQ         -0.296       -0.477 1000
 stress2   MNQ         -1.076       -1.257 1000
 slip+1t    NQ         -0.142       -0.367 1004
 slip+2t    NQ         -0.688       -0.854 1012

### Parameter perturbations (PREFADE-S, TRAIN gross)
param  factor  snapped_level  gross_exp_TRAIN  sharpe_TRAIN    n
level    0.80            1.5            0.590         1.899 2610
 stop    0.80            2.0            0.628         2.016 1836
   ts    0.80            2.0            0.649         1.910 1789
level    0.90            2.0            0.673         1.966 1789
 stop    0.90            2.0            0.661         2.011 1802
   ts    0.90            2.0            0.667         1.952 1789
level    0.95            2.0            0.673         1.966 1789
 stop    0.95            2.0            0.645         1.921 1795
   ts    0.95            2.0            0.670         1.955 1789
level    1.00            2.0            0.673         1.966 1789
 stop    1.00            2.0            0.673         1.966 1789
   ts    1.00            2.0            0.673         1.966 1789
level    1.05            2.0            0.673         1.966 1789
 stop    1.05            2.0            0.658         1.869 1781
   ts    1.05            2.0            0.664         1.934 1789
level    1.10            2.0            0.673         1.966 1789
 stop    1.10            2.0            0.661         1.854 1770
   ts    1.10            2.0            0.659         1.917 1789
level    1.20            2.5            0.727         1.915 1014
 stop    1.20            2.0            0.698         1.907 1758
   ts    1.20            2.0            0.661         1.926 1789

### Walk-forward (expanding train, reselect argmax Sharpe on 27-combo grid; gross)
 test_year          chosen  train_sharpe  oos_exp  oos_n  oos_sharpe  fixed_exp  fixed_sharpe
      2009 (2.5, 3.0, 240)         3.336    0.477     66       1.059      1.059         2.941
      2010 (2.0, 2.0, 180)         3.025   -0.040    168      -0.119      0.259         0.708
      2011 (2.5, 3.0, 120)         2.695    0.967     57       1.708      1.146         2.373
      2012 (2.5, 3.0, 120)         2.536    0.559    109       1.182      0.192         0.426
      2013 (2.5, 3.0, 120)         2.283    0.109    113       0.316      0.375         1.214
      2014 (2.5, 2.5, 240)         2.073    0.633    117       1.277      1.188         2.643
      2015 (1.5, 3.0, 120)         2.185    1.858    210       2.836      1.877         2.821
      2016 (1.5, 3.0, 120)         2.223    0.870    173       1.377      0.928         1.170
      2017 (1.5, 3.0, 120)         2.115   -1.332    186      -2.403     -1.753        -3.042
      2018 (1.5, 3.0, 120)         1.716    0.693    167       0.515     -2.643        -1.699

### Concentration / removal / Monte Carlo / DSR (PREFADE-S TRAIN gross)
```
{
 "n_trades": 1789,
 "gross_sharpe_TRAIN": 1.9656062140268933,
 "DSR(400 trials)": 0.9479931950633491,
 "total": 1204.7291492299273,
 "wo_best1": 1180.9421277770975,
 "wo_best5": 1092.95954364369,
 "wo_best10": 1007.1916394982368,
 "wo_best1pct": 906.1674894000298,
 "wo_worst5": 1347.5041222289901,
 "wo_worst1pct": 1586.7753181973496,
 "removal": [
  {
   "removed": 0.05,
   "mean_total": 1141.6145632175123,
   "p5_total": 1057.7047310664605,
   "p_neg": 0.0
  },
  {
   "removed": 0.1,
   "mean_total": 1082.7577641805567,
   "p5_total": 964.6001815009433,
   "p_neg": 0.0
  },
  {
   "removed": 0.2,
   "mean_total": 971.0295364739072,
   "p5_total": 802.7019830344823,
   "p_neg": 0.0
  }
 ],
 "MC_maxDD_p95": -180.67014942836505,
 "MC_total_p5": 784.2018339712838,
 "losing_streak": 5
}
```

## SPX500
### Cost & slippage scenarios (PREFADE-F, net exp pts/trade)
scenario instr  net_exp_TRAIN  net_exp_VAL    n
    base    ES         -0.027       -0.265 1068
    base   MES         -0.183       -0.421 1068
 stress1    ES         -0.277       -0.515 1068
 stress1   MES         -0.433       -0.671 1068
stress15    ES         -0.303       -0.541 1068
stress15   MES         -0.537       -0.775 1068
 stress2    ES         -0.579       -0.817 1068
 stress2   MES         -0.891       -1.129 1068
 slip+1t    ES         -0.519       -0.821 1070
 slip+2t    ES         -1.073       -1.252 1089

### Parameter perturbations (PREFADE-S, TRAIN gross)
param  factor  snapped_level  gross_exp_TRAIN  sharpe_TRAIN    n
level    0.80            1.5            0.253         1.298 2573
 stop    0.80            2.0            0.174         0.821 1786
   ts    0.80            2.0            0.272         1.246 1737
level    0.90            2.0            0.242         1.064 1737
 stop    0.90            2.0            0.244         1.112 1757
   ts    0.90            2.0            0.249         1.110 1737
level    0.95            2.0            0.242         1.064 1737
 stop    0.95            2.0            0.224         0.995 1748
   ts    0.95            2.0            0.245         1.080 1737
level    1.00            2.0            0.242         1.064 1737
 stop    1.00            2.0            0.242         1.064 1737
   ts    1.00            2.0            0.242         1.064 1737
level    1.05            2.0            0.242         1.064 1737
 stop    1.05            2.0            0.274         1.204 1731
   ts    1.05            2.0            0.238         1.048 1737
level    1.10            2.0            0.242         1.064 1737
 stop    1.10            2.0            0.286         1.241 1725
   ts    1.10            2.0            0.222         0.965 1737
level    1.20            2.5            0.483         2.001 1032
 stop    1.20            2.0            0.324         1.373 1715
   ts    1.20            2.0            0.218         0.942 1737

### Walk-forward (expanding train, reselect argmax Sharpe on 27-combo grid; gross)
 test_year          chosen  train_sharpe  oos_exp  oos_n  oos_sharpe  fixed_exp  fixed_sharpe
      2009 (2.5, 2.5, 120)         3.374    0.343     78       1.236      0.483         1.880
      2010 (2.5, 2.0, 180)         3.060    0.096     88       0.455     -0.123        -0.564
      2011 (2.5, 2.0, 120)         2.807    0.031     76       0.113     -0.333        -1.079
      2012 (2.5, 3.0, 120)         2.477    0.559    101       2.579      0.400         1.769
      2013 (2.5, 3.0, 120)         2.485   -0.001    115      -0.003      0.208         1.228
      2014 (2.5, 2.0, 180)         2.229    0.195    125       1.059      0.264         1.357
      2015 (2.5, 3.0, 120)         2.192    1.670     96       4.556      0.586         1.656
      2016 (2.5, 3.0, 120)         2.457    0.845     95       2.905     -0.016        -0.049
      2017 (2.5, 3.0, 120)         2.497   -0.110    105      -0.537      0.054         0.299
      2018 (2.5, 3.0, 120)         2.291    0.258     84       0.548      0.305         0.645

### Concentration / removal / Monte Carlo / DSR (PREFADE-S TRAIN gross)
```
{
 "n_trades": 1737,
 "gross_sharpe_TRAIN": 1.0636936967271462,
 "DSR(400 trials)": 0.3230939116402535,
 "total": 420.2486919479677,
 "wo_best1": 388.6143887022572,
 "wo_best5": 305.5153781691106,
 "wo_best10": 243.7872345809194,
 "wo_best1pct": 178.2803537810354,
 "wo_worst5": 521.6959225569478,
 "wo_worst1pct": 670.2760544174905,
 "removal": [
  {
   "removed": 0.05,
   "mean_total": 400.5216042776305,
   "p5_total": 345.35383117744647,
   "p_neg": 0.0
  },
  {
   "removed": 0.1,
   "mean_total": 380.8335618579831,
   "p5_total": 299.63733937382267,
   "p_neg": 0.0
  },
  {
   "removed": 0.2,
   "mean_total": 337.0813049474653,
   "p5_total": 226.12901283875274,
   "p_neg": 0.0
  }
 ],
 "MC_maxDD_p95": -172.76976113842548,
 "MC_total_p5": 140.30982743664254,
 "losing_streak": 7
}
```
