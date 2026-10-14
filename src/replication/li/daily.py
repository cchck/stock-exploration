"""Stock-month aggregates of daily data for Li et al.'s trading-friction and momentum
variables (DM A.1.7, A.6.x). Each moment is stored as sums, sums of squares and counts per
stock-month, so multi-month windows (e.g. "six-month average daily turnover, at least 50
daily observations", DM A.6.13) are exact pooled statistics over the daily observations,
not averages of monthly averages.

Daily inputs (TRD_Dalyr): Dretwd (return with dividends), Clsprc (close), Dnshrtrd (shares
traded), Dnvaltrd (RMB traded), Dsmvosd (circulating market cap, RMB thousand -> yuan in
csmar.panels.daily). Daily share turnover = shares traded / circulating shares (Dsmvosd /
Clsprc), DM A.6.13: "shares traded within a day / shares outstanding that day"; the
tradable A shares are the shares that can trade (LSY use the same convention).
A day enters the return moments when Dretwd is present; trading moments when the stock
traded (Dnshrtrd > 0).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from csmar.panels import daily
from csmar.registry import INTERIM

CACHE = INTERIM / "li_daily_month.parquet"


def build(rebuild: bool = False) -> pd.DataFrame:
    if CACHE.exists() and not rebuild:
        return pd.read_parquet(CACHE)
    d = daily(["Dretwd", "Clsprc", "Dnshrtrd", "Dnvaltrd", "Dsmvosd"])
    d = d[d["board"].isin(["SH_MAIN", "SZ_MAIN", "SZ_SME", "CHINEXT", "STAR"])]
    d["month"] = d["date"].dt.to_period("M")
    r = pd.to_numeric(d["Dretwd"], errors="coerce")
    px = pd.to_numeric(d["Clsprc"], errors="coerce")
    vol = pd.to_numeric(d["Dnshrtrd"], errors="coerce")
    amt = pd.to_numeric(d["Dnvaltrd"], errors="coerce")
    shares = d["Dsmvosd"] / px
    traded = vol > 0
    tur = (vol / shares).where(traded & (shares > 0))
    amt_t = amt.where(traded & (amt > 0))
    ami = (r.abs() / amt_t).where(r.notna())
    x = pd.DataFrame({
        "stkcd": d["stkcd"], "month": d["month"],
        "r_n": r.notna().astype(int), "r_s1": r, "r_s2": r ** 2, "r_s3": r ** 3, "r_max": r,
        "tur_n": tur.notna().astype(int), "tur_s1": tur, "tur_s2": tur ** 2,
        "amt_n": amt_t.notna().astype(int), "amt_s1": amt_t, "amt_s2": amt_t ** 2,
        "ami_n": ami.notna().astype(int), "ami_s1": ami,
        "px_max": px, "px_last": px,
    })
    g = x.groupby(["stkcd", "month"], sort=True)
    sums = g[["r_n", "r_s1", "r_s2", "r_s3", "tur_n", "tur_s1", "tur_s2", "amt_n", "amt_s1", "amt_s2",
              "ami_n", "ami_s1"]].sum(min_count=1)
    out = sums.join(g[["r_max", "px_max"]].max()).join(g["px_last"].last()).reset_index()
    for c in ("r_n", "tur_n", "amt_n", "ami_n"):
        out[c] = out[c].fillna(0).astype(int)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(CACHE, index=False)
    return out


def rolling_window(m: pd.DataFrame, cols: list[str], months: int) -> pd.DataFrame:
    """Sum of `cols` over the `months` calendar months ending at each row's month (missing
    months contribute nothing). Rows: every (stkcd, month) in m."""
    wide = {c: m.pivot(index="month", columns="stkcd", values=c) for c in cols}
    full = pd.period_range(m["month"].min(), m["month"].max(), freq="M")
    out = []
    for c, w in wide.items():
        w = w.reindex(full)
        s = w.rolling(months, min_periods=1).sum()
        out.append(s.stack().rename(c))
    res = pd.concat(out, axis=1).reset_index()
    return res.rename(columns={"level_0": "month"})
