"""Command line: rebuild every Li et al. (2024) result.

    python -m replication.li                    # all segments, comparison
    python -m replication.li --period original
    python -m replication.li --build            # (re)build the anomaly caches first
    LI_VARIANT=clean python -m replication.li   # look-ahead-free variant

Two procedure variants (deviation_log LI-2): "authors" (default) reproduces the paper and
writes results/li/<segment>_tables.csv and results/li_comparison.csv (original segment vs the
paper, lighthouse 7.3); "clean" (no holding-month look-ahead) writes
results/li/<segment>_tables_clean.csv and is the headline for the extended and full segments
(user decision 2026-10-11). Partial runs write *_partial.csv.
"""

from __future__ import annotations

import argparse
import sys
import time

import pandas as pd

from csmar.registry import PROJECT_ROOT
from replication.common.compare import compare
from replication.li import anomalies as AN
from replication.li import tables as T

OUT = PROJECT_ROOT / "results" / "li"
COMPARISON = PROJECT_ROOT / "results" / "li_comparison.csv"
TABLE_FUNCS = {"T1": T.table1, "T2": T.table2, "T3": T.table3, "T4": T.table4, "T5": T.table5,
               "T6": T.table6, "T7": T.table7, "TXT": T.text_numbers, "S4.2": T.hxz_us}
DEVIATION_LINKS = {"T1": "LI-1", "T2": "LI-5", "T3": "LI-6", "T4": "LI-6", "T5": "LI-7", "T6": "LI-7",
                   "T7": "LI-8", "TXT": "LI-6", "S4.2": "LI-9"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--period", choices=["original", "extended", "full", "all"], default="all")
    ap.add_argument("--tables", nargs="*", default=list(TABLE_FUNCS))
    ap.add_argument("--build", action="store_true")
    a = ap.parse_args(argv)
    t0 = time.time()
    if a.build:
        AN.build()
        AN.build_membership()
        AN.build_soe()
    segs = T.li_segments()
    names = list(segs) if a.period == "all" else [a.period]
    complete = a.period == "all" and set(a.tables) == set(TABLE_FUNCS)
    OUT.mkdir(parents=True, exist_ok=True)
    original = None
    for name in names:
        seg = segs[name]
        out = pd.concat([TABLE_FUNCS[t](seg) for t in a.tables], ignore_index=True)
        sfx = "" if AN.VARIANT == "authors" else "_clean"
        path = OUT / (f"{name}_tables{sfx}.csv" if complete else f"{name}_tables{sfx}_partial.csv")
        out.to_csv(path, index=False)
        print(f"{seg}: {len(out)} numbers -> {path}", flush=True)
        if name == "original":
            original = out
    if complete and original is not None and AN.VARIANT == "authors":
        c = compare("li", original)
        c["deviation"] = [DEVIATION_LINKS.get(t, "") if (p is not None and not p) else "" for t, p in zip(c["table"], c["pass"])]
        c.to_csv(COMPARISON, index=False)
        scored = c[c["pass"].notna()]
        print(f"comparison: {int((scored['pass'] == True).sum())}/{len(scored)} within tolerance -> {COMPARISON}")
        from replication.li import checks
        fc, gc = checks.run()
        built = gc[gc["status"] != "not built"]
        print(f"factor check: {int(fc['pass'].sum())}/{len(fc)} >= 0.95; g5-g1 check: "
              f"{int((built['status'] == 'pass').sum())}/{len(built)} >= 0.90 (results/li_*_check.csv)")
    else:
        print(f"partial run: {COMPARISON} left unchanged")
    print(f"done in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
