"""Plot helpers (matplotlib, headless)."""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams.update({"figure.dpi": 110, "font.size": 9, "axes.grid": True,
                     "grid.alpha": 0.3, "figure.autolayout": True})


def equity_curve(daily: pd.Series, title: str, path: str):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6), sharex=True,
                                   gridspec_kw={"height_ratios": [3, 1]})
    eq = daily.cumsum()
    ax1.plot(eq.index, eq.values, lw=1.0, color="#1f6feb")
    ax1.set_title(title)
    ax1.set_ylabel("cumulative PnL (pts)")
    dd = eq - eq.cummax()
    ax2.fill_between(dd.index, dd.values, 0, color="#d1242f", alpha=0.6)
    ax2.set_ylabel("drawdown (pts)")
    fig.savefig(path); plt.close(fig)


def param_heatmap(df: pd.DataFrame, value: str, idx: str, col: str, title: str,
                  path: str, fmt: str = "{:.2f}", center0: bool = True):
    piv = df.pivot_table(index=idx, columns=col, values=value)
    fig, ax = plt.subplots(figsize=(1.1 * len(piv.columns) + 2, 0.55 * len(piv) + 1.5))
    vmax = np.nanmax(np.abs(piv.values)) if center0 else None
    im = ax.imshow(piv.values, cmap="RdYlGn", aspect="auto",
                   vmin=-vmax if center0 else None, vmax=vmax)
    ax.set_xticks(range(len(piv.columns)), [str(c) for c in piv.columns])
    ax.set_yticks(range(len(piv.index)), [str(i) for i in piv.index])
    ax.set_xlabel(col); ax.set_ylabel(idx); ax.set_title(title)
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            v = piv.values[i, j]
            if not np.isnan(v):
                ax.text(j, i, fmt.format(v), ha="center", va="center", fontsize=7)
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.savefig(path); plt.close(fig)


def hist(series: pd.Series, title: str, path: str, bins=60, xlabel=""):
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(series.dropna().values, bins=bins, color="#1f6feb", alpha=0.85)
    ax.axvline(0, color="k", lw=0.8)
    ax.set_title(title); ax.set_xlabel(xlabel); ax.set_ylabel("count")
    fig.savefig(path); plt.close(fig)


def mae_mfe(trades: pd.DataFrame, title: str, path: str):
    fig, ax = plt.subplots(figsize=(6.5, 6))
    win = trades["pnl_pts"] > 0
    ax.scatter(trades.loc[win, "mae"], trades.loc[win, "mfe"], s=6, alpha=0.4,
               color="#2da44e", label="winners")
    ax.scatter(trades.loc[~win, "mae"], trades.loc[~win, "mfe"], s=6, alpha=0.4,
               color="#d1242f", label="losers")
    ax.set_xlabel("MAE (pts)"); ax.set_ylabel("MFE (pts)")
    ax.set_title(title); ax.legend()
    fig.savefig(path); plt.close(fig)


def bar_by(df: pd.DataFrame, x: str, y: str, n: str, title: str, path: str):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(df[x].astype(str), df[y], color="#1f6feb", alpha=0.85)
    for i, (v, cnt) in enumerate(zip(df[y], df[n])):
        ax.text(i, v, f"n={cnt}", ha="center",
                va="bottom" if v >= 0 else "top", fontsize=7)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_title(title); ax.set_xlabel(x); ax.set_ylabel(y)
    plt.xticks(rotation=45, ha="right")
    fig.savefig(path); plt.close(fig)
