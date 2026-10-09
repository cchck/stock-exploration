"""The ten LSY anomalies (section 6.1, Appendix A.2): long-short decile spreads.

Universe: the LSY universe (top 70% after filters). Deciles from the universe's own
breakpoints; value-weighted by the most recent month-end total A-share market value.

| key     | measure (end of t-1)                           | long leg        |
|---------|------------------------------------------------|-----------------|
| size    | total A-share market value                     | small (D1)      |
| ep      | EP (positive values only)                      | high EP (D10)   |
| bm      | book-to-market                                 | high BM         |
| cp      | cash-flow-to-price (positive values only)      | high CP         |
| roe     | single-quarter earnings / book equity          | high ROE        |
| vol     | std of daily returns, past 20 records          | low vol         |
| max     | max daily return, past 20 records              | low MAX         |
| rev     | 20-day cumulative return, daily-rebalanced     | losers          |
| turn12  | average daily turnover, past 250 records       | low turnover    |
| abnturn | 20-day / 250-day average daily turnover        | low             |

Size-neutral version: size deciles first, anomaly deciles within each size decile, then
anomaly decile d pools decile d of every size group (value-weighted). Size is omitted there.

Reversal is not a month-end sort (A.2): each trading day stocks are ranked on the latest
20-day cumulative return, a one-fifth slice is formed and held for five trading days, the
daily spread return averages the five live slices, and daily returns are compounded into
the month.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from csmar.panels import daily
from replication.common.portfolios import assign_groups, weighted_returns

ANOMALIES = ["size", "ep", "bm", "cp", "roe", "vol", "max", "rev", "turn12", "abnturn"]
MEASURE = {"size": "me", "ep": "ep", "bm": "bm", "cp": "cp", "roe": "roe", "vol": "vol20", "max": "max20",
           "turn12": "turn250", "abnturn": "abn_turn"}
LONG_HIGH = {"ep", "bm", "cp", "roe"}  # long the top decile; all others long the bottom
POSITIVE_ONLY = {"ep", "cp"}  # A.2 / section 6.1: "For EP and CP, we sort only the positive values"
DECILES = [i / 10 for i in range(1, 10)]


def _with_roe(panel: pd.DataFrame) -> pd.DataFrame:
    p = panel
    if "roe" not in p:
        p = p.assign(roe=p["earnings"] / p["book_equity"].where(p["book_equity"] > 0))
    return p


def _spread_from_deciles(dec_returns: pd.DataFrame, key: str) -> pd.Series:
    long_d, short_d = (10, 1) if key in LONG_HIGH else (1, 10)
    return (dec_returns[long_d] - dec_returns[short_d]).rename(key)


def monthly_sort_spread(panel: pd.DataFrame, key: str, *, size_neutral: bool) -> pd.Series:
    """Long-short decile spread (decimal monthly) for a month-end-sorted anomaly."""
    var = MEASURE[key]
    u = _with_roe(panel)
    u = u[u["in_universe"] & u["ret"].notna()].copy()
    if key in POSITIVE_ONLY:
        u = u[u[var] > 0]
    u = u[u[var].notna()]
    labels = list(range(1, 11))
    if size_neutral:
        if key == "size":
            raise ValueError("the size anomaly has no size-neutral version")
        u["size_d"] = assign_groups(u, "me", DECILES, labels=labels)
        u["key"] = u["month"].astype(str) + "_" + u["size_d"].astype(str)
        u["dec"] = assign_groups(u, var, DECILES, by="key", labels=labels)
    else:
        u["dec"] = assign_groups(u, var, DECILES, labels=labels)
    dr = weighted_returns(u, ["dec"], ret="ret", weight="me")
    return _spread_from_deciles(dr, key)


def reversal_spread(panel: pd.DataFrame, *, size_neutral: bool, hold_days: int = 5, window: int = 20,
                    min_obs: int = 15) -> pd.Series:
    """One-month reversal with daily one-fifth slices (A.2). Decimal monthly returns."""
    d = daily(["Dretwd"])
    d = d[d["stkcd"].str.slice(0, 2).isin(["60", "30", "00"])].sort_values(["stkcd", "date"]).reset_index(drop=True)
    r = d["Dretwd"].astype(float)
    lr = np.log1p(r)
    g = lr.groupby(d["stkcd"])
    roll = g.rolling(window, min_periods=min_obs).sum().reset_index(level=0, drop=True).sort_index()
    d["rev20"] = np.expm1(roll)
    d["r"] = r
    d["month"] = d["date"].dt.to_period("M")

    # Universe and weights of the month the formation day falls in (end-of-previous-month info)
    uni = panel.loc[panel["in_universe"], ["stkcd", "month", "me"]]
    f = d.merge(uni, on=["stkcd", "month"], how="inner").dropna(subset=["rev20"])
    labels = list(range(1, 11))
    if size_neutral:
        f["size_d"] = assign_groups(f, "me", DECILES, by="date", labels=labels)
        f["key"] = f["date"].dt.strftime("%Y%m%d") + "_" + f["size_d"].astype(str)
        f["dec"] = assign_groups(f, "rev20", DECILES, by="key", labels=labels)
    else:
        f["dec"] = assign_groups(f, "rev20", DECILES, by="date", labels=labels)
    legs = f[f["dec"].isin([1, 10])][["stkcd", "date", "dec", "me"]].rename(columns={"date": "form_date"})

    # Map each formation day to the next hold_days market trading days
    cal = pd.Index(np.sort(d["date"].unique()))
    pos = cal.get_indexer(legs["form_date"])
    parts = []
    for k in range(1, hold_days + 1):
        ok = pos + k < len(cal)
        part = legs[ok].copy()
        part["date"] = cal[pos[ok] + k]
        parts.append(part)
    held = pd.concat(parts, ignore_index=True).merge(d[["stkcd", "date", "r"]], on=["stkcd", "date"], how="inner")
    held = held.dropna(subset=["r"])
    held["wr"] = held["r"] * held["me"]
    sl = held.groupby(["date", "form_date", "dec"])[["wr", "me"]].sum()
    slice_ret = (sl["wr"] / sl["me"]).rename("r").reset_index()
    daily_leg = slice_ret.groupby(["date", "dec"])["r"].mean().unstack("dec")
    spread_daily = daily_leg[1] - daily_leg[10]  # losers minus winners
    monthly = np.expm1(np.log1p(spread_daily).groupby(spread_daily.index.to_period("M")).sum())
    monthly.index.name = "month"
    return monthly.rename("rev")


def all_spreads(panel: pd.DataFrame, *, size_neutral: bool) -> pd.DataFrame:
    keys = [k for k in ANOMALIES if not (size_neutral and k == "size")]
    out = {}
    for k in keys:
        out[k] = reversal_spread(panel, size_neutral=size_neutral) if k == "rev" else \
            monthly_sort_spread(panel, k, size_neutral=size_neutral)
    return pd.DataFrame(out)
