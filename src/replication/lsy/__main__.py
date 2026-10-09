"""Command line: rebuild every LSY result.

    python -m replication.lsy                      # all three segments, figures, comparison
    python -m replication.lsy --period original    # one segment
    python -m replication.lsy --tables T3 T5       # a subset of tables
    python -m replication.lsy --rebuild            # rebuild the cached panel and anomaly spreads

Outputs (aggregate numbers only, safe to commit):
- results/lsy/<segment>_tables.csv: every reported number, tidy (table, row, col, value).
- results/lsy/figures/: Figure 1 and 2 (PNG) and their data (CSV).
- results/lsy_comparison.csv: paper vs ours for the original segment, with tolerance verdicts
  and links to docs/deviation_log.md (lighthouse.md 7.3).
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

import pandas as pd

from csmar.registry import PROJECT_ROOT
from replication.common.compare import compare
from replication.lsy import tables as T

OUT = PROJECT_ROOT / "results" / "lsy"
COMPARISON = PROJECT_ROOT / "results" / "lsy_comparison.csv"

TABLE_FUNCS = {
    "T1": T.table1, "T2": T.table2, "T3": T.table3, "T4": T.table4, "S5.2": T.section52, "T5": T.table5,
    "T6": T.table6, "T7": T.table7, "T8": T.table8, "T9": T.table9, "T10": T.table10,
}

# Deviation-log entry for each target that misses its tolerance (docs/deviation_log.md).
DEVIATION_LINKS = {
    "T1": "LSY-5", "T2": "LSY-3", "T3": "LSY-1", "T4": "LSY-4", "S5.2": "LSY-1", "T5": "LSY-1",
    "T6": "LSY-7", "T7": "LSY-7", "T8": "LSY-7", "T9": "LSY-7", "T10": "LSY-7", "factor_check": "LSY-1",
    "F1": "LSY-6", "F2": "LSY-6",
}


def figures(seg_end: str) -> pd.DataFrame:
    """Figures 1-2 for deals announced 2007-01..seg_end; returns the scored summary numbers."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from replication.lsy import shells

    figdir = OUT / "figures"
    figdir.mkdir(parents=True, exist_ok=True)
    tag = "original" if seg_end == "2016-12-31" else "full"
    deals = shells.reverse_mergers(end=seg_end)
    f1 = shells.figure1(deals)
    f1.to_csv(figdir / f"fig1_shell_size_deciles_{tag}.csv")
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.bar(f1.index, f1.values, color="0.3")
    ax.set_xlabel("Size decile (month-end market value three months before the deal)")
    ax.set_ylabel("Fraction")
    ax.set_xticks(range(1, 11))
    ax.set_title(f"Fig. 1. Size distribution of reverse-merger shells, 2007-{seg_end[:4]} (n = {len(deals)})")
    fig.tight_layout()
    fig.savefig(figdir / f"fig1_shell_size_deciles_{tag}.png", dpi=150)
    plt.close(fig)

    f2 = shells.figure2(deals, end=seg_end)
    f2.to_csv(figdir / f"fig2_shell_value_{tag}.csv")
    fig, axes = plt.subplots(2, 1, figsize=(7, 5.5), sharex=True)
    axes[0].plot(f2.index, f2["S_over_V"], color="0.2")
    axes[0].set_ylabel("S / V")
    axes[0].set_title("Panel A. Ratio of estimated shell value to market cap")
    axes[1].plot(f2.index, f2["S"] / 1e6, color="0.2")
    axes[1].set_ylabel("RMB million")
    axes[1].set_title("Panel B. Estimated shell value")
    fig.tight_layout()
    fig.savefig(figdir / f"fig2_shell_value_{tag}.png", dpi=150)
    plt.close(fig)

    seg = T.Segment(tag, pd.Period("2007-01", "M"), pd.Period(seg_end[:7], "M"))
    items = [("deals", "n", float(len(deals))),
             ("shells", "share_bottom30_pct", float(f1.loc[1:3].sum() * 100)),
             ("shells", "share_bottom10_pct", float(f1.loc[1] * 100))]
    f2_items = [("S_over_V", "mean_pct", float(f2["S_over_V"].mean() * 100))]
    return pd.concat([T._rows("F1", seg, items), T._rows("F2", seg, f2_items)])


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--period", choices=["original", "extended", "full", "all"], default="all")
    ap.add_argument("--tables", nargs="*", default=list(TABLE_FUNCS), help="subset of " + " ".join(TABLE_FUNCS))
    ap.add_argument("--rebuild", action="store_true", help="rebuild cached panel and anomaly spreads")
    ap.add_argument("--no-figures", action="store_true")
    args = ap.parse_args(argv)
    unknown = set(args.tables) - set(TABLE_FUNCS)
    if unknown:
        ap.error(f"unknown tables: {sorted(unknown)}")

    t0 = time.time()
    if args.rebuild:
        T.panel(rebuild=True)
        T.anomaly_spreads(rebuild=True)
    segs = T.lsy_segments()
    names = list(segs) if args.period == "all" else [args.period]
    OUT.mkdir(parents=True, exist_ok=True)
    original_rows = []
    for name in names:
        seg = segs[name]
        parts = [TABLE_FUNCS[t](seg) for t in args.tables]
        if name == "original":
            parts.append(T.factor_series_check())
        out = pd.concat(parts, ignore_index=True)
        out.to_csv(OUT / f"{name}_tables.csv", index=False)
        print(f"{seg}: {len(out)} numbers -> {OUT / f'{name}_tables.csv'}")
        if name == "original":
            original_rows.append(out)
    if not args.no_figures and args.period in ("all", "original"):
        fig_orig = figures("2016-12-31")
        original_rows.append(fig_orig)
        if args.period == "all":
            figures(str(T.lsy_segments()["full"].end.to_timestamp(how="end").date()))
    if original_rows and set(args.tables) == set(TABLE_FUNCS):
        ours = pd.concat(original_rows, ignore_index=True)
        c = compare("lsy", ours)
        # pass holds True, False (numpy bool) or None; compare by value, not identity
        c["deviation"] = [DEVIATION_LINKS.get(t, "") if (p is not None and not p) else "" for t, p in zip(c["table"], c["pass"])]
        c.to_csv(COMPARISON, index=False)
        scored = c[c["pass"].notna()]
        print(f"comparison: {int((scored['pass'] == True).sum())}/{len(scored)} within tolerance -> {COMPARISON}")
    print(f"done in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
