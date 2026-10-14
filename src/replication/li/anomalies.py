"""Run every anomaly of the catalog through the four portfolio procedures and cache the
quintile returns (aggregates only, no firm-level data): data/interim/li_quintiles.parquet,
one row per (anomaly, procedure, month) with g1..g5 and g5_g1.

    python -m replication.li.anomalies            # build what is missing
    python -m replication.li.anomalies --rebuild  # recompute everything
"""

from __future__ import annotations

import argparse
import importlib
import logging
import sys
import time

import pandas as pd

from csmar.registry import INTERIM
from replication.li import catalog as C
from replication.li import portfolios as PF

# Two procedure variants (deviation_log LI-2; user decision 2026-10-11):
#   "authors": the authors' holding-month filter (reproduces the paper; original segment),
#   "clean":   look-ahead free (headline for the extended and full segments).
# The variant is fixed per process (factors and caches are memoized): set LI_VARIANT before
# importing, or call set_variant() first.
import os

VARIANT = os.environ.get("LI_VARIANT", "authors")
if VARIANT not in ("authors", "clean"):
    raise ValueError(f"LI_VARIANT must be 'authors' or 'clean', not {VARIANT!r}")
PF.HOLDING_MONTH_FILTER = VARIANT == "authors"
_SUFFIX = "" if VARIANT == "authors" else "_clean"
CACHE = INTERIM / f"li_quintiles{_SUFFIX}.parquet"
MODULES = {"market": "replication.li.signals_market", "acct": "replication.li.signals_acct",
           "resid": "replication.li.signals_resid"}
log = logging.getLogger(__name__)


def signal(var: C.Var) -> pd.DataFrame:
    mod, fn = var.builder.split(".")
    return getattr(importlib.import_module(MODULES[mod]), fn)()


def run_var(var: C.Var, procs=tuple(PF.PROCEDURES)) -> pd.DataFrame:
    sig = signal(var)
    kind = "monthly" if var.kind.startswith("monthly") else "annual"
    holds = C.HOLDS if var.kind == "monthly" else (1,)
    rows = []
    for pname in procs:
        res = PF.quintile_returns_multi(sig, PF.PROCEDURES[pname], kind, holds)
        for n, r in res.items():
            name = f"{var.name}{n}" if var.kind == "monthly" else var.name
            rows.append(r.assign(anomaly=name, var=var.name, category=var.category, proc=pname).reset_index())
    return pd.concat(rows, ignore_index=True)


def build(rebuild: bool = False, names: list[str] | None = None) -> pd.DataFrame:
    old = pd.read_parquet(CACHE) if CACHE.exists() and not rebuild else pd.DataFrame()
    done = set(old["var"]) if len(old) else set()
    parts = [old] if len(old) else []
    for v in C.VARS:
        if v.builder is None or (names and v.name not in names) or (v.name in done and not names):
            continue
        t = time.time()
        try:
            r = run_var(v)
        except Exception:
            log.exception("anomaly %s failed", v.name)
            raise
        parts = [p[p["var"] != v.name] for p in parts] + [r]
        out = pd.concat(parts, ignore_index=True)
        out.to_parquet(CACHE, index=False)
        print(f"{v.name:10s} {time.time() - t:6.1f}s", flush=True)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def load() -> pd.DataFrame:
    return pd.read_parquet(CACHE)


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--vars", nargs="*")
    a = ap.parse_args(argv)
    build(a.rebuild, a.vars)
    return 0


if __name__ == "__main__":
    sys.exit(main())


MEMBER_CACHE = INTERIM / f"li_membership{_SUFFIX}.parquet"


def membership_stats(var: C.Var, procs=tuple(PF.PROCEDURES)) -> pd.DataFrame:
    """Table 2 Panels B-D inputs per formation month for the lowest and highest quintiles:
    share of the portfolio weight in microcaps (below the 20th percentile of the Mainboard
    circulating ME at formation; VW weight for VW procedures, count share for EW), and the
    investment capacity (HXZ 2020, 2.3.2): VW = aggregate circulating ME of the quintile; EW =
    number of stocks x the smallest circulating ME; as a fraction of the aggregate A-share
    circulating ME and in yuan."""
    sig = signal(var)
    p = PF.panel()
    elig = p[p["eligible"]]
    micro_cut = elig[elig["mainboard"]].groupby("month")["mv_float"].quantile(0.2)
    total = p.groupby("month")["mv_float"].sum()
    rows = []
    for pname in procs:
        proc = PF.PROCEDURES[pname]
        g = PF.assign_quintiles(sig, proc)
        g = g[g["q"].isin([1, 5]) & (g["w_form"] > 0)].copy()
        g["micro"] = g["w_form"] < g["form"].map(micro_cut)
        agg = g.groupby(["form", "q"]).agg(n=("w_form", "size"), w=("w_form", "sum"), wmin=("w_form", "min"),
                                           nmicro=("micro", "sum"),
                                           wmicro=("w_form", lambda s: s[g.loc[s.index, "micro"]].sum()))
        agg = agg.reset_index()
        if proc.weights == "vw":
            agg["micro_share"] = agg["wmicro"] / agg["w"]
            agg["capacity"] = agg["w"]
        else:
            agg["micro_share"] = agg["nmicro"] / agg["n"]
            agg["capacity"] = agg["n"] * agg["wmin"]
        agg["capacity_frac"] = agg["capacity"] / agg["form"].map(total)
        rows.append(agg.assign(var=var.name, category=var.category, proc=pname,
                               n_anomalies=len(var.anomalies)))
    return pd.concat(rows, ignore_index=True)


def build_membership(rebuild: bool = False, names: list[str] | None = None) -> pd.DataFrame:
    old = pd.read_parquet(MEMBER_CACHE) if MEMBER_CACHE.exists() and not rebuild else pd.DataFrame()
    if names and len(old):
        old = old[~old["var"].isin(names)]
    done = set(old["var"]) if len(old) else set()
    parts = [old] if len(old) else []
    for v in C.VARS:
        if v.builder is None or v.name in done or (names and v.name not in names):
            continue
        parts.append(membership_stats(v))
        pd.concat(parts, ignore_index=True).to_parquet(MEMBER_CACHE, index=False)
    return pd.concat(parts, ignore_index=True)


SOE_CACHE = INTERIM / f"li_quintiles_soe{_SUFFIX}.parquet"


def _soe_by_form() -> pd.DataFrame:
    """SOE status in force at each formation month: the latest year-end status (actual
    controller, allen.data.soe_flags; Li et al. use CSMAR's equity-nature file, not in our
    subscription, from 2003-12-31)."""
    from replication.allen.data import soe_flags
    s = soe_flags()
    months = pd.period_range("2003-12", "2026-12", freq="M")
    grid = pd.DataFrame({"form": months})
    grid["fy"] = [m.year if m.month == 12 else m.year - 1 for m in months]
    return grid.merge(s, on="fy").drop(columns="fy")


def run_subsample(var: C.Var, soe: int) -> pd.DataFrame:
    """Mainboard-VW quintile returns within the SOE (soe=1) or non-SOE (soe=0) subsample
    (Table 7): breakpoints and portfolios use only the subsample's stocks."""
    sig = signal(var)
    flags = _soe_by_form()
    sig = sig.merge(flags[flags["soe"] == soe][["stkcd", "form"]], on=["stkcd", "form"], how="inner")
    kind = "monthly" if var.kind.startswith("monthly") else "annual"
    holds = C.HOLDS if var.kind == "monthly" else (1,)
    res = PF.quintile_returns_multi(sig, PF.PROCEDURES["Mainboard-VW"], kind, holds)
    rows = []
    for n, r in res.items():
        name = f"{var.name}{n}" if var.kind == "monthly" else var.name
        rows.append(r.assign(anomaly=name, var=var.name, category=var.category, proc="Mainboard-VW",
                             soe=soe).reset_index())
    return pd.concat(rows, ignore_index=True)


def build_soe(rebuild: bool = False, names: list[str] | None = None) -> pd.DataFrame:
    old = pd.read_parquet(SOE_CACHE) if SOE_CACHE.exists() and not rebuild else pd.DataFrame()
    if names and len(old):
        old = old[~old["var"].isin(names)]
    done = set(old["var"]) if len(old) else set()
    parts = [old] if len(old) else []
    for v in C.VARS:
        if v.builder is None or v.name in done or (names and v.name not in names):
            continue
        parts.append(pd.concat([run_subsample(v, 1), run_subsample(v, 0)], ignore_index=True))
        pd.concat(parts, ignore_index=True).to_parquet(SOE_CACHE, index=False)
    return pd.concat(parts, ignore_index=True)
