"""PHASE 6 — robustness battery on the locked candidates.

All computed on TRAIN+VAL (2005-2018); the Vault stays sealed.
Battery: cost scenarios, degraded execution, parameter perturbations,
walk-forward with per-fold reselection, trade removal, Monte Carlo,
best/worst-trade concentration, DSR.

Outputs results/phase6/*.csv and a summary markdown.
"""
import os, sys, itertools, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np
import pandas as pd

from vwapresearch.ingest import OUT_ROOT
from vwapresearch import backtest, candidates, stats, registry
from vwapresearch.config import split_of, COSTS, DATASET_COSTBOOK

RES = os.path.join(os.path.dirname(__file__), "..", "results", "phase6")
os.makedirs(RES, exist_ok=True)

N_TRIALS = 400          # experiment count from registry (order of magnitude)


def load(name):
    fr = pd.read_parquet(os.path.join(OUT_ROOT, f"{name}_feat.parquet"))
    lab = split_of(fr.index)
    fr = fr[((lab == "TRAIN") | (lab == "VAL")).values]
    ev = pd.concat([
        pd.read_parquet(os.path.join(OUT_ROOT, f"{name}_events_TRAIN.parquet")),
        pd.read_parquet(os.path.join(OUT_ROOT, f"{name}_events_VAL.parquet")),
    ]).sort_values("time")
    return fr, ev


def base_filter(level=2.0, a=450, b=570, slow=None):
    def flt(e):
        m = (e["level"] == level) & (e["ny_minute"] >= a) & (e["ny_minute"] < b)
        if slow is not None:
            m &= e["speed5"].abs() < slow
        return m
    return flt


def spec_of(stop=2.5, ts=180, cost=0.0, slip=0.0):
    return backtest.ExecSpec(stop_sigma=stop, target="vwap", time_stop=ts,
                             cost_per_side_pts=cost, slip_entry_pts=slip,
                             slip_exit_pts=slip, max_trades_day=6)


def main():
    md = ["# Phase 6 — robustness battery (2005-2018, Vault sealed)", ""]
    for name in ["NAS100", "SPX500"]:
        big, micro = DATASET_COSTBOOK[name]
        fr, ev = load(name)
        md.append(f"## {name}")
        tick = 0.25

        # ---------- 1. cost scenarios + degraded execution (PREFADE-F)
        flt = base_filter(slow=0.9)
        rows = []
        for scen in ["base", "stress1", "stress15", "stress2"]:
            for instr in [big, micro]:
                c = COSTS[instr][scen]["per_side_pts"]
                tr = candidates.run_candidate(fr, ev, flt, spec_of(cost=c), fade=True)
                t_tr = tr[pd.to_datetime(tr["session_day"]).dt.year <= 2014]
                v_tr = tr[pd.to_datetime(tr["session_day"]).dt.year >= 2015]
                rows.append({"scenario": scen, "instr": instr,
                             "net_exp_TRAIN": t_tr["pnl_pts"].mean(),
                             "net_exp_VAL": v_tr["pnl_pts"].mean(),
                             "n": len(tr)})
        for slip_t in [1, 2]:
            c = COSTS[big]["base"]["per_side_pts"]
            tr = candidates.run_candidate(fr, ev, flt,
                                          spec_of(cost=c, slip=slip_t * tick), fade=True)
            t_tr = tr[pd.to_datetime(tr["session_day"]).dt.year <= 2014]
            rows.append({"scenario": f"slip+{slip_t}t", "instr": big,
                         "net_exp_TRAIN": t_tr["pnl_pts"].mean(),
                         "net_exp_VAL": tr[pd.to_datetime(tr['session_day']).dt.year >= 2015]["pnl_pts"].mean(),
                         "n": len(tr)})
        cost_df = pd.DataFrame(rows)
        cost_df.to_csv(f"{RES}/{name}_costs.csv", index=False)
        md += ["### Cost & slippage scenarios (PREFADE-F, net exp pts/trade)",
               cost_df.round(3).to_string(index=False), ""]

        # ---------- 2. parameter perturbations ±5/10/20% (PREFADE-S, gross)
        base_p = {"level": 2.0, "stop": 2.5, "ts": 180}
        rows = []
        for f in [0.8, 0.9, 0.95, 1.0, 1.05, 1.1, 1.2]:
            for which in ["level", "stop", "ts"]:
                p = dict(base_p)
                p[which] = p[which] * f
                lv = round(p["level"] * 2) / 2 if which == "level" else p["level"]
                # level must exist in event table (0.5 grid): snap and note
                tr = candidates.run_candidate(
                    fr, ev, base_filter(level=lv),
                    spec_of(stop=p["stop"], ts=int(p["ts"])), fade=True)
                t_tr = tr[pd.to_datetime(tr["session_day"]).dt.year <= 2014]
                d = stats.daily_series(t_tr)
                rows.append({"param": which, "factor": f, "snapped_level": lv,
                             "gross_exp_TRAIN": t_tr["pnl_pts"].mean(),
                             "sharpe_TRAIN": stats.sharpe_daily(d), "n": len(t_tr)})
        pert = pd.DataFrame(rows).drop_duplicates(subset=["param", "snapped_level", "factor"])
        pert.to_csv(f"{RES}/{name}_perturb.csv", index=False)
        md += ["### Parameter perturbations (PREFADE-S, TRAIN gross)",
               pert.round(3).to_string(index=False), ""]

        # ---------- 3. walk-forward with per-fold reselection (27-combo grid)
        grid = list(itertools.product([1.5, 2.0, 2.5], [2.0, 2.5, 3.0], [120, 180, 240]))
        all_trades = {}
        for (lv, st, ts) in grid:
            tr = candidates.run_candidate(fr, ev, base_filter(level=lv),
                                          spec_of(stop=st, ts=ts), fade=True)
            tr["year"] = pd.to_datetime(tr["session_day"]).dt.year
            all_trades[(lv, st, ts)] = tr
        wf_rows = []
        for test_year in range(2009, 2019):
            best, best_sh = None, -1e9
            for k, tr in all_trades.items():
                tt = tr[(tr["year"] >= 2005) & (tr["year"] < test_year)]
                if len(tt) < 200:
                    continue
                sh = stats.sharpe_daily(stats.daily_series(tt))
                if sh > best_sh:
                    best, best_sh = k, sh
            te = all_trades[best]
            te = te[te["year"] == test_year]
            fixed = all_trades[(2.0, 2.5, 180)]
            fx = fixed[fixed["year"] == test_year]
            wf_rows.append({"test_year": test_year, "chosen": str(best),
                            "train_sharpe": best_sh,
                            "oos_exp": te["pnl_pts"].mean(), "oos_n": len(te),
                            "oos_sharpe": stats.sharpe_daily(stats.daily_series(te)),
                            "fixed_exp": fx["pnl_pts"].mean(),
                            "fixed_sharpe": stats.sharpe_daily(stats.daily_series(fx))})
        wf = pd.DataFrame(wf_rows)
        wf.to_csv(f"{RES}/{name}_walkforward.csv", index=False)
        md += ["### Walk-forward (expanding train, reselect argmax Sharpe on 27-combo grid; gross)",
               wf.round(3).to_string(index=False), ""]

        # ---------- 4. concentration, removal, Monte Carlo, DSR (PREFADE-S TRAIN)
        tr = all_trades[(2.0, 2.5, 180)]
        t_tr = tr[tr["year"] <= 2014].reset_index(drop=True)
        pnl = t_tr["pnl_pts"]
        d = stats.daily_series(t_tr)
        m = stats.trade_metrics(pnl)
        conc = {
            "total": pnl.sum(), "wo_best1": pnl.sum() - pnl.max(),
            "wo_best5": pnl.sum() - pnl.nlargest(5).sum(),
            "wo_best10": pnl.sum() - pnl.nlargest(10).sum(),
            "wo_best1pct": pnl.sum() - pnl.nlargest(max(1, len(pnl) // 100)).sum(),
            "wo_worst5": pnl.sum() - pnl.nsmallest(5).sum(),
            "wo_worst1pct": pnl.sum() - pnl.nsmallest(max(1, len(pnl) // 100)).sum(),
        }
        rng = np.random.default_rng(7)
        rem_rows = []
        for frac in [0.05, 0.10, 0.20]:
            sims = []
            for _ in range(500):
                keep = rng.random(len(pnl)) > frac
                sims.append(pnl[keep].sum())
            rem_rows.append({"removed": frac, "mean_total": np.mean(sims),
                             "p5_total": np.percentile(sims, 5),
                             "p_neg": float(np.mean(np.array(sims) <= 0))})
        mc = []
        x = d.to_numpy()
        for _ in range(2000):
            idx = rng.integers(0, len(x), len(x))
            eq = np.cumsum(x[idx])
            peak = np.maximum.accumulate(eq)
            mc.append({"total": eq[-1], "maxdd": float(np.min(eq - peak))})
        mc = pd.DataFrame(mc)
        dsr = stats.deflated_sharpe(stats.sharpe_daily(d), len(d), pnl.skew(),
                                    pnl.kurtosis(), N_TRIALS)
        summ = {
            "n_trades": len(pnl), "gross_sharpe_TRAIN": stats.sharpe_daily(d),
            "DSR(400 trials)": dsr, **conc,
            "removal": rem_rows,
            "MC_maxDD_p95": float(mc["maxdd"].quantile(0.05)),
            "MC_total_p5": float(mc["total"].quantile(0.05)),
            "losing_streak": stats.losing_streak(pnl),
        }
        json.dump(summ, open(f"{RES}/{name}_battery.json", "w"), indent=1, default=str)
        md += ["### Concentration / removal / Monte Carlo / DSR (PREFADE-S TRAIN gross)",
               "```", json.dumps(summ, indent=1, default=str), "```", ""]
    open(f"{RES}/phase6_summary.md", "w").write("\n".join(md))
    print("\n".join(md[-80:]))


if __name__ == "__main__":
    main()
