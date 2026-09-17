"""Moteur de backtest hebdomadaire, sans look-ahead.

Convention temporelle stricte :
- les signaux sont calculés sur la clôture hebdomadaire de la semaine t ;
- les ordres correspondants sont exécutés au premier prix quotidien disponible
  APRES cette clôture (le lundi de la semaine t+1), colonne `exec_open` ;
- aucune décision n'utilise une information postérieure à la clôture qui la
  déclenche.
"""
from dataclasses import dataclass, field
import numpy as np
import pandas as pd


@dataclass
class Trade:
    date: pd.Timestamp
    side: str          # "buy" / "sell"
    reason: str
    price: float
    fraction: float    # fraction de la position (vente) ou du capital (achat)
    btc: float
    cash_after: float
    btc_after: float
    equity_after: float


@dataclass
class Result:
    equity: pd.Series
    exposure: pd.Series
    trades: list
    thresholds: pd.DataFrame | None = None

    def trades_df(self) -> pd.DataFrame:
        return pd.DataFrame([vars(t) for t in self.trades])


def run_strategy(
    w: pd.DataFrame,
    ma: pd.Series | None = None,          # ligne de tendance (close > ma = haussier)
    above: pd.Series | None = None,       # alternative : booléen "tendance haussière" déjà calculé
    exit_mode: str = "tranches",          # "tranches" | "sma" | "none"
    exit_levels=None,                      # liste de float OU pd.Series (drawdown depuis sommet)
    exit_fractions=(0.50, 1.00),           # fractions CUMULEES vendues
    peak_source: str = "close",            # "close" | "high"
    peak_updates_after_partial: bool = True,
    strict_initial_state: bool = True,
    confirm_weeks: int = 1,                # nb de clôtures consécutives > MA pour confirmer l'entrée
    cost_per_side: float = 0.002,
    cash_rate: pd.Series | None = None,    # taux hebdo du cash (None = 0)
    initial_capital: float = 1.0,
    freeze_levels_at_entry: bool = False,  # fige les seuils adaptatifs à l'entrée
) -> Result:
    idx = w.index
    close = w["close"].values
    high = w["high"].values
    exec_open = w["exec_open"].values
    if above is None:
        assert ma is not None, "fournir `ma` ou `above`"
        above_v = (w["close"] > ma.reindex(idx)).values
        valid_v = ma.reindex(idx).notna().values
    else:
        above_v = above.reindex(idx).fillna(False).astype(bool).values
        valid_v = above.reindex(idx).notna().values

    if exit_levels is None:
        exit_levels = [0.20, 0.40]
    # normalise les seuils en matrices (n_semaines x n_tranches)
    lv = np.column_stack([
        (l.reindex(idx).values if isinstance(l, pd.Series) else np.full(len(idx), l))
        for l in exit_levels
    ])
    fr = list(exit_fractions)
    assert len(fr) == lv.shape[1] and abs(fr[-1] - 1.0) < 1e-9

    cash_r = cash_rate.reindex(idx).fillna(0.0).values if cash_rate is not None else np.zeros(len(idx))

    cash, btc = initial_capital, 0.0
    state = "start"          # start -> waiting_below -> armed -> invested
    above_count = 0
    tranche_fired = np.zeros(lv.shape[1], dtype=bool)
    frozen_lv = lv[0].copy()
    peak = np.nan
    pending = None           # ordre décidé à la clôture précédente
    trades, eq_hist, expo_hist, thr_hist = [], [], [], []

    for i in range(len(idx)):
        px_exec = exec_open[i - 1] if i > 0 else np.nan  # lundi de la semaine i

        # 1) exécution des ordres en attente (décidés à la clôture i-1)
        if pending is not None and not np.isnan(px_exec):
            kind, frac = pending
            if kind == "buy":
                spend = cash
                units = spend / (px_exec * (1 + cost_per_side))
                btc += units
                cash = 0.0
                peak = px_exec
                tranche_fired[:] = False
                frozen_lv = lv[i].copy()  # seuils au moment de l'entrée
                state = "invested"
                trades.append(Trade(idx[i], "buy", "entry", px_exec, 1.0, units,
                                    cash, btc, cash + btc * close[i]))
            elif kind == "sell":
                units = btc * frac
                cash += units * px_exec * (1 - cost_per_side)
                btc -= units
                reason = "stop_full" if btc <= 1e-12 else "stop_partial"
                if btc <= 1e-12:
                    btc = 0.0
                    state = "waiting_below"
                    peak = np.nan
                trades.append(Trade(idx[i], "sell", reason, px_exec, frac, units,
                                    cash, btc, cash + btc * close[i]))
            pending = None

        # 2) rémunération du cash
        cash *= (1 + cash_r[i])

        # 3) mise à jour du sommet glissant
        if state == "invested" and btc > 0:
            ref = high[i] if peak_source == "high" else close[i]
            if peak_updates_after_partial or not tranche_fired.any():
                peak = max(peak, ref) if not np.isnan(peak) else ref

        equity = cash + btc * close[i]
        eq_hist.append(equity)
        expo_hist.append((btc * close[i]) / equity if equity > 0 else 0.0)
        thr_hist.append(lv[i].copy())

        # 4) génération des signaux à la clôture i (exécution semaine i+1)
        if not valid_v[i]:
            continue
        if state == "start":
            if strict_initial_state:
                state = "waiting_below" if above_v[i] else "armed"
            else:
                state = "armed"
                above_count = confirm_weeks  # autorise l'entrée immédiate si au-dessus
        if state == "waiting_below":
            if not above_v[i]:
                state = "armed"
                above_count = 0
        elif state == "armed":
            if above_v[i]:
                above_count += 1
                if above_count >= confirm_weeks:
                    pending = ("buy", 1.0)
            else:
                above_count = 0
        elif state == "invested":
            if exit_mode == "sma":
                if not above_v[i]:
                    pending = ("sell", 1.0)
            elif exit_mode == "tranches+sma" and not above_v[i]:
                # garde-fou : croisement sous la tendance => liquidation totale
                tranche_fired[:] = True
                pending = ("sell", 1.0)
            elif exit_mode in ("tranches", "tranches+sma") and not np.isnan(peak):
                dd = 1.0 - close[i] / peak
                lv_now = frozen_lv if freeze_levels_at_entry else lv[i]
                frac_now = 0.0
                sold_before = fr[int(np.argmax(~tranche_fired)) - 1] if tranche_fired.any() else 0.0
                for j in range(lv.shape[1]):
                    if not tranche_fired[j] and dd >= lv_now[j]:
                        tranche_fired[j] = True
                        frac_now = fr[j]
                if frac_now > 0:
                    # convertit la fraction cumulée en fraction de la position restante
                    remaining = 1.0 - sold_before
                    sell_frac = min(1.0, (frac_now - sold_before) / remaining)
                    pending = ("sell", sell_frac)

    equity = pd.Series(eq_hist, index=idx, name="equity")
    exposure = pd.Series(expo_hist, index=idx, name="exposure")
    thresholds = pd.DataFrame(thr_hist, index=idx,
                              columns=[f"D{k+1}" for k in range(lv.shape[1])])
    return Result(equity, exposure, trades, thresholds)


def buy_and_hold(w: pd.DataFrame, cost_per_side: float = 0.002,
                 start=None, initial_capital: float = 1.0) -> Result:
    idx = w.index if start is None else w.index[w.index >= start]
    px0 = w.loc[idx[0], "exec_open"]
    units = initial_capital / (px0 * (1 + cost_per_side))
    eq = units * w.loc[idx, "close"]
    trades = [Trade(idx[0], "buy", "bh_entry", px0, 1.0, units, 0.0, units, eq.iloc[0])]
    return Result(eq.rename("equity"), pd.Series(1.0, index=idx, name="exposure"), trades)
