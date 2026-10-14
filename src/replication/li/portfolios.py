"""Quintile portfolios of Li et al. (DM p.2, Appendix A): four procedures, five holding
periods.

- Breakpoints: quintiles of the Mainboard (SH + SZ mainboard) stocks with a signal
  ("Mainboard") or of all sample stocks ("All").
- Weights: circulating market cap at the end of the month before each return month ("VW"),
  or equal weights ("EW").
- Formation: annual signals are sorted at the end of June of year t and held July t to June
  t+1; monthly signals are sorted at the end of month t-1 (the "beginning of month t").
- Holding N months (monthly signals): in month t the quintile return is the average of the N
  portfolios formed at the ends of months t-1, ..., t-N (DM A.1.1).
- Penny stocks and abnormal trading status. The data manual says penny stocks (price < 5)
  are dropped "after forming quintiles but before calculating quintile returns" (DM p.2).
  Calibrated against the authors' own quintile series (g5_g1_2000_2019/pps_1_2: the price
  sort, whose lowest quintile is the most sensitive to this rule), the authors' procedure is:
  1. at formation (end of t-1): only stocks with normal trading status and price >= 5 enter
     the breakpoints and the quintiles;
  2. in the return month t: a stock is also dropped when its month-t record has a price
     below 5 or an abnormal trading status.
  With both rules our Pps1 quintiles match the authors' to within 0.05 percentage points
  in 210 (g3) to 228 (g1) of 228 months; without rule 2 the lowest quintile earns 1.1%
  instead of their 2.3% a month. Rule 2 uses month-t information (the month-end price and
  status are not known when the portfolio is formed): a look-ahead in the authors'
  procedure. HOLDING_MONTH_FILTER=True reproduces the paper (comparison with the printed
  numbers, lighthouse 3.1); False gives the look-ahead-free version, reported alongside
  (deviation_log LI-2).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from replication.li import data as D

PENNY_PRICE = 5.0
PENNY_AT_FORMATION = True  # rule 1: price >= 5 at formation, before the breakpoints
HOLDING_MONTH_FILTER = True  # rule 2: month-t price >= 5 and normal status (look-ahead)
WEIGHTS_AT_FORMATION = False  # calibration switch: hold cohorts at formation-date weights


@dataclass(frozen=True)
class Procedure:
    name: str
    breakpoints: str  # "mainboard" | "all"
    weights: str  # "vw" | "ew"


PROCEDURES = {
    "Mainboard-VW": Procedure("Mainboard-VW", "mainboard", "vw"),
    "Mainboard-EW": Procedure("Mainboard-EW", "mainboard", "ew"),
    "All-VW": Procedure("All-VW", "all", "vw"),
    "All-EW": Procedure("All-EW", "all", "ew"),
}


def _panel_with_weights() -> pd.DataFrame:
    p = D.stock_panel()
    prev = p.groupby("stkcd")["month"].shift(1)
    w = p.groupby("stkcd")["mv_float"].shift(1).where(prev == p["month"] - 1)
    return p.assign(w=w)


_PANEL: pd.DataFrame | None = None


def panel() -> pd.DataFrame:
    global _PANEL
    if _PANEL is None:
        _PANEL = _panel_with_weights()
    return _PANEL


def assign_quintiles(sig: pd.DataFrame, proc: Procedure) -> pd.DataFrame:
    """sig: columns stkcd, form (formation month, Period), value. Returns sig with quintile q
    (1..5) for eligible stocks at the formation month end; penny stocks removed after
    grouping."""
    p = panel()[["stkcd", "month", "eligible", "mainboard", "close"]].rename(columns={"month": "form"})
    x = sig.dropna(subset=["value"]).merge(p, on=["stkcd", "form"], how="inner")
    x = x[x["eligible"]]
    if PENNY_AT_FORMATION:
        x = x[x["close"] >= PENNY_PRICE]
    base = x[x["mainboard"]] if proc.breakpoints == "mainboard" else x
    br = base.groupby("form")["value"].quantile([0.2, 0.4, 0.6, 0.8]).unstack()
    br = br.reindex(x["form"]).to_numpy()
    v = x["value"].to_numpy()[:, None]
    # A value equal to a breakpoint goes to the lower group (as in SAS PROC UNIVARIATE-based
    # breakpoints compared with "<=").
    q = 1 + (v > br).sum(axis=1)
    x = x.assign(q=np.where(np.isnan(br).any(axis=1), np.nan, q))
    x = x[x["q"].notna()]
    x = x[x["close"] >= PENNY_PRICE]
    mv = panel()[["stkcd", "month", "mv_float"]].rename(columns={"month": "form", "mv_float": "w_form"})
    return x.merge(mv, on=["stkcd", "form"], how="left")[["stkcd", "form", "q", "w_form"]]


def holding_returns() -> pd.DataFrame:
    """Return-month rows usable in portfolio returns: (stkcd, month, ret, w), with the
    holding-month filter (rule 2) applied when HOLDING_MONTH_FILTER is set."""
    p = panel()
    keep = p["ret"].notna()
    if HOLDING_MONTH_FILTER:
        keep &= (p["close"] >= PENNY_PRICE) & p["normal_status"]
    return p.loc[keep, ["stkcd", "month", "ret", "w"]]


def quintile_returns(sig: pd.DataFrame, proc: Procedure, kind: str, hold: int = 1) -> pd.DataFrame:
    """Monthly returns of quintiles 1..5 and g5_g1 (columns g1..g5, g5_g1), indexed by month.

    kind="annual": formation at June-end, held 12 months (hold ignored).
    kind="monthly": formation at each month end, held `hold` months (overlapping cohorts,
    equally averaged)."""
    g = assign_quintiles(sig, proc)
    p = holding_returns()
    lags = range(1, 13) if kind == "annual" else range(1, hold + 1)
    parts = []
    for k in lags:
        h = g.assign(month=g["form"] + k)
        d = h.merge(p, on=["stkcd", "month"], how="inner")
        if WEIGHTS_AT_FORMATION:
            d["w"] = d["w_form"]
        if proc.weights == "vw":
            d = d[d["w"] > 0]
            num = (d["ret"] * d["w"]).groupby([d["month"], d["form"], d["q"]]).sum()
            r = num / d["w"].groupby([d["month"], d["form"], d["q"]]).sum()
        else:
            r = d.groupby(["month", "form", "q"])["ret"].mean()
        parts.append(r)
    r = pd.concat(parts)
    if kind == "annual":
        # Each month is held by exactly one June cohort.
        out = r.groupby(level=["month", "q"]).mean().unstack("q")
    else:
        # Average over the cohorts formed in t-1..t-N; months with fewer available cohorts at
        # the sample start use the ones that exist.
        out = r.groupby(level=["month", "q"]).mean().unstack("q")
    out.columns = [f"g{int(c)}" for c in out.columns]
    out["g5_g1"] = out["g5"] - out["g1"]
    return out
