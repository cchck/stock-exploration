"""The eleven self-built factors of Li et al. (DM Appendix B.1): MKT, SMB-FF3, HML-FF3,
SMB-FF5, HML-FF5, RMW, CMA, MOM, ME, I/A, ROE. All use Mainboard breakpoints and
circulating-market-cap value weights. CH3 / CH4 come from Stambaugh's website (lighthouse
4.3); after 2021-12 the LSY module's own CH factors extend them.

Checked month by month against the authors' allfactors.sas7bdat (2000-07 to 2019-06,
lighthouse 3.3: correlation >= 0.95), tests/test_li.py.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from csmar.panels import load
from replication.li import data as D
from replication.li import portfolios as PF
from replication.li.rates import rf_monthly


def _with_prev_weight(m: pd.DataFrame, col: str = "mv_float") -> pd.DataFrame:
    """Add w = the stock's circulating market cap at the end of the previous month (missing
    when that month is not in the panel)."""
    m = m.sort_values(["stkcd", "month"]).copy()
    prev = m.groupby("stkcd")["month"].shift(1)
    m["w"] = m.groupby("stkcd")[col].shift(1).where(prev == m["month"] - 1)
    return m


def vw_return(d: pd.DataFrame, by: list[str]) -> pd.Series:
    d = d[(d["w"] > 0) & d["ret"].notna()]
    num = (d["ret"] * d["w"]).groupby([d[b] for b in by]).sum()
    return num / d["w"].groupby([d[b] for b in by]).sum()


@lru_cache(maxsize=1)
def mkt() -> pd.Series:
    """MKT: value-weighted return of all A shares (every board, CSMAR's market return is a
    circulating-cap weighted return over all A shares, DM p.1) minus the three-month deposit
    rate. Weights: previous month-end circulating market cap."""
    m = load("stock_month")
    m = _with_prev_weight(m[m["is_a_share"]])
    r = vw_return(m, ["month"])
    return (r - rf_monthly().reindex(r.index)).rename("mkt")


def _june_characteristics(be_me_base: str = "mv_float") -> pd.DataFrame:
    """Annual sort variables at the end of June of year t (DM B.1):
    size = circulating ME at end of June t; B/M = book equity of fiscal t-1 / December t-1
    ME; OP = operating profit t-1 / book equity t-1; INV = total assets t-1 / t-2 - 1."""
    p = D.stock_panel()
    june = p[p["month"].dt.month == 6][["stkcd", "month", "mv_float", "eligible", "mainboard", "close"]].copy()
    june["year"] = june["month"].dt.year
    dec = p[p["month"].dt.month == 12][["stkcd", "month", be_me_base]].copy()
    dec["year"] = dec["month"].dt.year + 1
    dec = dec.rename(columns={be_me_base: "me_dec"}).drop(columns="month")
    a = D.annual([D.BE, D.TA, D.OP, "B001101000", "B001201000", "B001209000", "B001210000", "B001211000", "B001207000"])
    a["year"] = a["fy"] + 1
    a2 = a[["stkcd", "fy", D.TA]].rename(columns={D.TA: "ta_lag"})
    a2["year"] = a2["fy"] + 2
    x = june.merge(dec, on=["stkcd", "year"], how="left").merge(a.drop(columns="fy"), on=["stkcd", "year"], how="left")
    x = x.merge(a2.drop(columns="fy"), on=["stkcd", "year"], how="left")
    x["size"] = x["mv_float"]
    x["bm"] = x[D.BE] / x["me_dec"]
    x["op"] = x[D.OP] / x[D.BE]
    # Fama-French (2015) operating profitability: revenue - cost of goods sold - selling,
    # general and administrative expenses - interest expense, over book equity.
    ff_op = x["B001101000"] - x["B001201000"].fillna(0) - x["B001209000"].fillna(0) - x["B001210000"].fillna(0) - x["B001211000"].fillna(0)
    x["op_ff"] = ff_op / x[D.BE]
    x["inv"] = x[D.TA] / x["ta_lag"] - 1
    return x


def _breaks(x: pd.DataFrame, var: str, qs: list[float], by: str) -> pd.DataFrame:
    """Mainboard percentiles of `var` per group `by`."""
    mb = x[x["mainboard"] & x[var].notna()]
    return mb.groupby(by)[var].quantile(qs).unstack()


def _bucket(x: pd.DataFrame, var: str, qs: list[float], by: str) -> pd.Series:
    br = _breaks(x, var, qs, by).reindex(x[by])
    v = x[var].to_numpy()
    out = np.zeros(len(x), dtype=float)
    for j in range(br.shape[1]):
        out += (v > br.iloc[:, j].to_numpy())
    return pd.Series(np.where(np.isnan(v) | br.isna().any(axis=1).to_numpy(), np.nan, out + 1), index=x.index)


# Calibration switches (set by the rounds in deviation_log LI-1; defaults are the kept choice).
PENNY_FILTER = False  # factors: no formation price filter (calibration, deviation_log LI-1)
WEIGHTS = "prev"  # "prev": previous month-end circulating ME; "june": fixed at formation


def _annual_sort_returns(x: pd.DataFrame, groups: dict[str, pd.Series]) -> pd.DataFrame:
    """Monthly value-weighted returns (July t to June t+1) of the portfolios defined at the end
    of June t by the group labels in `groups` (Series aligned with x)."""
    lab = x[["stkcd", "year"]].copy()
    for k, g in groups.items():
        lab[k] = g
    if PENNY_FILTER:
        lab = lab[(x["close"] >= 5).to_numpy()]
    if WEIGHTS == "june":
        lab["w_june"] = x["mv_float"]
    lab = lab.dropna()
    p = PF.holding_returns()
    if WEIGHTS == "june":
        p = p.drop(columns="w")
    p["year"] = np.where(p["month"].dt.month >= 7, p["month"].dt.year, p["month"].dt.year - 1)
    d = p.merge(lab, on=["stkcd", "year"], how="inner")
    if WEIGHTS == "june":
        d = d.rename(columns={"w_june": "w"})
    return vw_return(d, ["month", *groups]).unstack(list(groups))


def _eligible_june(x: pd.DataFrame, require_positive_be: bool = True) -> pd.DataFrame:
    ok = x["eligible"] & (x["size"] > 0)
    if require_positive_be:
        ok &= x[D.BE] > 0
    return x[ok].copy()


@lru_cache(maxsize=4)
def ff_factors(be_me_base: str = "mv_float", op_var: str = "op", common_ff5: bool = True) -> pd.DataFrame:
    """SMB-FF3 / HML-FF3 (2x3 size-B/M) and SMB-FF5 / HML-FF5 / RMW / CMA (three 2x3 sorts),
    Fama and French (1993, 2015) as described in DM B.1."""
    x0 = _eligible_june(_june_characteristics(be_me_base))
    x0["op"] = x0[op_var]
    out = {}
    smbs = []
    # FF3 uses every stock with B/M; the FF5 sorts use the stocks with B/M, OP and INV
    # (the authors' HML-FF5 differs from their HML-FF3, so the samples differ).
    x5 = x0.dropna(subset=["bm", "op", "inv"]) if common_ff5 else x0
    r3 = _annual_sort_returns(x0, {"s": _bucket(x0, "size", [0.5], "year"), "g": _bucket(x0, "bm", [0.3, 0.7], "year")})
    out["smbff3"] = r3.xs(1.0, axis=1, level="s").mean(axis=1) - r3.xs(2.0, axis=1, level="s").mean(axis=1)
    out["hmlff3"] = (r3[(1.0, 3.0)] + r3[(2.0, 3.0)]) / 2 - (r3[(1.0, 1.0)] + r3[(2.0, 1.0)]) / 2
    x = x5
    size = _bucket(x, "size", [0.5], "year")
    for var, name in (("bm", "bm"), ("op", "op"), ("inv", "inv")):
        g = _bucket(x, var, [0.3, 0.7], "year")
        r = _annual_sort_returns(x, {"s": size, "g": g})
        small = r.xs(1.0, axis=1, level="s")
        big = r.xs(2.0, axis=1, level="s")
        smbs.append(small.mean(axis=1) - big.mean(axis=1))
        hi = (small[3.0] + big[3.0]) / 2
        lo = (small[1.0] + big[1.0]) / 2
        if var == "bm":
            out["hml"] = hi - lo
        elif var == "op":
            out["rmw"] = hi - lo
        else:
            out["cma"] = lo - hi
    out["smbff5"] = sum(smbs) / 3
    return pd.DataFrame(out)


@lru_cache(maxsize=1)
def mom() -> pd.DataFrame:
    """MOM (Carhart 1997, DM B.1): 2x3 sort at the end of month t-1 on size (circulating ME,
    t-1) and prior 2-12 returns (t-12..t-2), Mainboard breakpoints (median; 30/70), held one
    month; (small winner + big winner)/2 - (small loser + big loser)/2."""
    p = _with_prev_weight(D.stock_panel())
    p = p.sort_values(["stkcd", "month"])
    lr = np.log1p(p["ret"])
    g = p.groupby("stkcd")
    # Prior 2-12: returns from t-12 to t-2, i.e. at the end of month t-1 the 11 months ending
    # at t-2. Require all 11 months.
    s = lr.groupby(p["stkcd"]).transform(lambda v: v.shift(1).rolling(11, min_periods=11).sum())
    p["prior"] = np.expm1(s)
    form = p[["stkcd", "month", "mv_float", "prior", "eligible", "mainboard"]].copy()
    form = form[form["eligible"] & (form["mv_float"] > 0)]
    if PENNY_FILTER:
        form = form[p.loc[form.index, "close"] >= PF.PENNY_PRICE]
    form["size"] = form["mv_float"]
    form["sg"] = _bucket(form, "size", [0.5], "month")
    form["mg"] = _bucket(form, "prior", [0.3, 0.7], "month")
    form["month"] = form["month"] + 1  # held in month t
    d = PF.holding_returns().merge(form[["stkcd", "month", "sg", "mg"]].dropna(), on=["stkcd", "month"])
    r = vw_return(d, ["month", "sg", "mg"]).unstack(["sg", "mg"])
    return pd.DataFrame({"mom": (r[(1.0, 3.0)] + r[(2.0, 3.0)]) / 2 - (r[(1.0, 1.0)] + r[(2.0, 1.0)]) / 2})


def roe_events() -> pd.DataFrame:
    """Quarterly ROE events (HXZ 2015; DM B.1): single-quarter net income over book equity
    at the previous fiscal quarter end, dated by the report's announcement. Rows: stkcd,
    period_end, announce_date, roe."""
    ni = D.quarterly_flows([D.NI])
    be = D.quarterly_stocks([D.BE])[["stkcd", "period_end", D.BE]].copy()
    be["period_end"] = (be["period_end"].dt.to_period("Q") + 1).dt.to_timestamp(how="end").dt.normalize()
    e = ni.merge(be.rename(columns={D.BE: "be_lag"}), on=["stkcd", "period_end"], how="left")
    # Before 2002 there are no Q1/Q3 reports: the lagged book equity is the previous
    # semi-annual or annual report's (two quarters back).
    miss = e["be_lag"].isna()
    be2 = be.copy()
    be2["period_end"] = (be2["period_end"].dt.to_period("Q") + 1).dt.to_timestamp(how="end").dt.normalize()
    e = e.merge(be2.rename(columns={D.BE: "be_lag2"}), on=["stkcd", "period_end"], how="left")
    e["be_lag"] = e["be_lag"].where(~miss, e["be_lag2"])
    e["roe"] = e[D.NI] / e["be_lag"].where(e["be_lag"] > 0)
    e = e[e["announce_date"].notna() & (e["period_end"] < e["announce_date"])]
    return e[["stkcd", "period_end", "announce_date", "roe"]]


def latest_quarterly(events: pd.DataFrame, cols: list[str], months: pd.PeriodIndex, max_age_months: int = 6) -> pd.DataFrame:
    """For each stock and month end t-1 (formation for month t), the most recently announced
    value, kept only if its fiscal quarter end lies within `max_age_months` before the
    formation (DM: "no more than six months before forming portfolios"). Output month = the
    month whose end is the formation date."""
    from replication.lsy.data import latest_by_month_end
    out = latest_by_month_end(events, months, cols)
    age = (out["month"].dt.to_timestamp(how="end").dt.normalize() - out["period_end"]).dt.days
    ok = out["period_end"].notna() & (age <= max_age_months * 31)
    out.loc[~ok, cols] = np.nan
    return out.drop(columns="period_end")


@lru_cache(maxsize=1)
def q_factors() -> pd.DataFrame:
    """ME, I/A, ROE (HXZ 2015 as in DM B.1): 2x3x3 sort on size (June, Mainboard median),
    I/A (June, fiscal t-1 asset growth, Mainboard 30/70) and ROE (monthly, latest announced,
    Mainboard 30/70); 18 value-weighted portfolios held one month."""
    x = _eligible_june(_june_characteristics())
    x["sg"] = _bucket(x, "size", [0.5], "year")
    x["ig"] = _bucket(x, "inv", [0.3, 0.7], "year")
    annual = x[["stkcd", "year", "sg", "ig"]].dropna()
    p = _with_prev_weight(D.stock_panel())
    months = pd.PeriodIndex(sorted(p["month"].unique()), freq="M")
    roe = latest_quarterly(roe_events(), ["roe"], months)
    f = p[["stkcd", "month", "eligible", "mainboard", "close"]].merge(roe, on=["stkcd", "month"], how="left")
    f = f[f["eligible"]].copy()
    if PENNY_FILTER:
        f = f[f["close"] >= PF.PENNY_PRICE]
    # Annual groups in force for holding month t = formation month + 1.
    f["hold"] = f["month"] + 1
    f["year"] = np.where(f["hold"].dt.month >= 7, f["hold"].dt.year, f["hold"].dt.year - 1)
    f = f.merge(annual, on=["stkcd", "year"], how="inner")
    f["rg"] = _bucket(f, "roe", [0.3, 0.7], "month")
    d = PF.holding_returns().merge(
        f[["stkcd", "hold", "sg", "ig", "rg"]].dropna().rename(columns={"hold": "month"}), on=["stkcd", "month"])
    r = vw_return(d, ["month", "sg", "ig", "rg"]).unstack(["sg", "ig", "rg"])
    lvl = r.columns
    def avg(mask):
        return r.loc[:, mask].mean(axis=1)
    sg, ig, rg = (lvl.get_level_values(i) for i in range(3))
    return pd.DataFrame({"me": avg(sg == 1.0) - avg(sg == 2.0), "ia": avg(ig == 1.0) - avg(ig == 3.0),
                         "roe": avg(rg == 3.0) - avg(rg == 1.0)})
