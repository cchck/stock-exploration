"""Portfolio sorts: breakpoints, group assignment, weighted portfolio returns.

Conventions are arguments, because the papers differ in exactly these places:
- which stocks set the breakpoints (all stocks, a size-filtered universe, mainboard only);
- which weights (total A-share value, circulating value, equal);
- how ties at a breakpoint are treated (here: a value equal to a breakpoint goes to the
  lower group, i.e. groups are (-inf, b1], (b1, b2], ..., like Fama-French's NYSE sorts).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def assign_groups(df: pd.DataFrame, var: str, quantiles: list[float], *, by: str = "month",
                  breakpoint_mask: pd.Series | None = None, labels: list | None = None) -> pd.Series:
    """Assign each row to a group by per-period quantile breakpoints of `var`.

    quantiles: interior cut points, e.g. [0.3, 0.7] for 30/40/30, [0.5] for a median split.
    breakpoint_mask: rows used to compute breakpoints (default: all rows with `var`).
    Returns group labels (default 1..len(quantiles)+1); NaN where `var` is missing.
    """
    labels = labels or list(range(1, len(quantiles) + 2))
    if len(labels) != len(quantiles) + 1:
        raise ValueError("need one more label than cut points")
    mask = pd.Series(True, index=df.index) if breakpoint_mask is None else breakpoint_mask.reindex(df.index).fillna(False)
    base = df.loc[mask & df[var].notna(), [by, var]]
    bps = base.groupby(by)[var].quantile(quantiles).unstack()
    out = pd.Series(np.nan, index=df.index, dtype=object)
    for t, g in df[[by, var]].groupby(by):
        if t not in bps.index:
            continue
        cuts = bps.loc[t].to_numpy(float)
        v = g[var].to_numpy(float)
        idx = np.searchsorted(cuts, v, side="left")  # equal to a cut point -> lower group
        lab = np.array(labels, dtype=object)[idx]
        lab[np.isnan(v)] = np.nan
        out.loc[g.index] = lab
    return out


def weighted_returns(df: pd.DataFrame, groups: list[str], *, ret: str = "ret", weight: str | None = "weight",
                     by: str = "month", min_stocks: int = 1) -> pd.DataFrame:
    """Portfolio returns per period and group: value-weighted by `weight`, or equal-weighted
    if weight is None. Rows with a missing return or weight are dropped (a stock with no
    return in the holding month does not enter that month's portfolio). Groups with fewer
    than min_stocks stocks in a period get NaN. Returns a wide frame: index = period,
    columns = group tuples (or the single group value)."""
    cols = [by, *groups, ret] + ([weight] if weight else [])
    d = df[cols].dropna()
    if weight:
        d = d[d[weight] > 0]
        d = d.assign(__wr=d[ret] * d[weight])
        g = d.groupby([by, *groups])
        out = g["__wr"].sum() / g[weight].sum()
    else:
        g = d.groupby([by, *groups])
        out = g[ret].mean()
    n = g.size()
    out[n < min_stocks] = np.nan
    wide = out.unstack(groups)
    return wide.sort_index()
