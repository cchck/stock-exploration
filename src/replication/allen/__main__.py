"""Command line: rebuild every Allen et al. (2024) A-share result.

    python -m replication.allen                     # all segments, figures, comparison
    python -m replication.allen --period original   # one segment
    python -m replication.allen --rebuild           # rebuild the cached annual panel

Outputs (aggregates only): results/allen/<segment>_tables.csv, results/allen/figures/,
results/allen_comparison.csv (original segment vs the paper, lighthouse.md 7.3). A partial
run (--period other than all, or --tables) writes *_partial.csv and leaves the comparison
unchanged.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

import pandas as pd

from csmar.registry import PROJECT_ROOT
from replication.allen import tables as T
from replication.common.compare import compare

OUT = PROJECT_ROOT / "results" / "allen"
COMPARISON = PROJECT_ROOT / "results" / "allen_comparison.csv"

TABLE_FUNCS = {"TI": T.table1, "TVIII": T.table8, "TIX": T.table9, "TX": T.table10, "TXI": T.table11,
               "TXII": T.table12, "TXIII": T.table13, "F1-2": T.figures12, "F4": T.figure4, "F5": T.figure5, "S3A2": T.section3a2,
               "TXT": T.text_numbers}
DEVIATION_LINKS = {"TI": "ALN-1", "TVIII": "ALN-2", "TIX": "ALN-2", "TX": "ALN-4", "TXI": "ALN-4", "TXII": "ALN-9", "TXIII": "ALN-5",
                   "F1-2": "ALN-6", "F4": "ALN-7", "F5": "ALN-7", "S3A2": "ALN-7", "TXT": "ALN-8"}


def plot_figures(segment: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    seg = T.allen_segments()[segment]
    figdir = OUT / "figures"
    figdir.mkdir(parents=True, exist_ok=True)
    b = T.bhr(seg)
    b.to_csv(figdir / f"fig1_2_bhr_{segment}.csv")
    fig, ax = plt.subplots(figsize=(7, 4))
    ts = b.index.to_timestamp()
    ax.plot(ts, b["all"], color="black", label="A-share market (VW)")
    for g, style in (("small", "--"), ("medium", ":"), ("large", "-.")):
        ax.plot(ts, b[g], style, color="0.35", label=f"{g} (30/70 pct of lagged one-year cap)")
    ax.set_ylabel("Real value of RMB 1")
    ax.set_title(f"Figures 1-2 (A-share lines): buy-and-hold real returns, {seg.start}..{seg.end}", fontsize=9)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(figdir / f"fig1_2_bhr_{segment}.png", dpi=150)
    plt.close(fig)

    f4 = T.figure4(seg)
    f4 = f4[f4["col"] == "roa_weighted"].copy()
    f4["k"] = f4["row"].str.replace("year", "").astype(int)
    f4 = f4.sort_values("k")
    f4.to_csv(figdir / f"fig4_st_roa_{segment}.csv", index=False)
    fig, ax = plt.subplots(figsize=(5, 3.2))
    ax.plot(f4["k"], f4["value"], marker="o", color="black")
    ax.axhline(0, color="0.6", lw=0.8)
    ax.set_xlabel("Years relative to first ST designation")
    ax.set_ylabel("ROA (lagged-assets weighted)")
    ax.set_title("Figure 4 (A-share part): permanent ST firms", fontsize=9)
    fig.tight_layout()
    fig.savefig(figdir / f"fig4_st_roa_{segment}.png", dpi=150)
    plt.close(fig)

    f5 = T.figure5(seg)
    f5 = f5[f5["row"] != "average"].pivot(index="row", columns="col", values="value")
    f5.to_csv(figdir / f"fig5_investment_ncf_{segment}.csv")
    fig, axes = plt.subplots(2, 1, figsize=(6, 5), sharex=True)
    axes[0].plot(f5.index.astype(int), f5["investment_pct"], marker="o", color="black")
    axes[0].set_title("Panel A. Investment (capex / assets, %), assets-weighted", fontsize=9)
    axes[1].plot(f5.index.astype(int), f5["ncf_pct"], marker="o", color="black")
    axes[1].axhline(0, color="0.6", lw=0.8)
    axes[1].set_title("Panel B. Net cash flows (% of assets), assets-weighted", fontsize=9)
    fig.tight_layout()
    fig.savefig(figdir / f"fig5_investment_ncf_{segment}.png", dpi=150)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--period", choices=["original", "extended", "full", "all"], default="all")
    ap.add_argument("--tables", nargs="*", default=list(TABLE_FUNCS))
    ap.add_argument("--rebuild", action="store_true")
    args = ap.parse_args(argv)
    unknown = set(args.tables) - set(TABLE_FUNCS)
    if unknown:
        ap.error(f"unknown tables: {sorted(unknown)}")
    t0 = time.time()
    if args.rebuild:
        T.panel(rebuild=True)
    segs = T.allen_segments()
    names = list(segs) if args.period == "all" else [args.period]
    complete = args.period == "all" and set(args.tables) == set(TABLE_FUNCS)
    OUT.mkdir(parents=True, exist_ok=True)
    original = None
    for name in names:
        seg = segs[name]
        out = pd.concat([TABLE_FUNCS[t](seg) for t in args.tables], ignore_index=True)
        path = OUT / (f"{name}_tables.csv" if complete else f"{name}_tables_partial.csv")
        out.to_csv(path, index=False)
        print(f"{seg}: {len(out)} numbers -> {path}")
        if complete:
            plot_figures(name)
        if name == "original":
            original = out
    if complete and original is not None:
        c = compare("allen", original)
        c["deviation"] = [DEVIATION_LINKS.get(t, "") if (p is not None and not p) else ""
                          for t, p in zip(c["table"], c["pass"])]
        c.to_csv(COMPARISON, index=False)
        scored = c[c["pass"].notna()]
        print(f"comparison: {int((scored['pass'] == True).sum())}/{len(scored)} within tolerance -> {COMPARISON}")
    else:
        print(f"partial run: {COMPARISON} left unchanged")
    print(f"done in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
