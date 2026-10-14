"""Accounting-based anomaly signals of Li et al. (DM Appendix A.1-A.5). Each public function
returns (stkcd, form, value) like signals_market.

Timing rules (DM, per variable):
- annual: values of the fiscal year ending in t-1, sorted at the end of June of year t
  (form = June t); "market equity at the end of calendar year t-1" for price ratios.
- quarterly, earnings-type ("most recent quarterly earnings announcement"): the latest report
  announced by the formation date, kept if its fiscal quarter end is no more than six months
  before formation and precedes the announcement (factors.latest_quarterly).
- quarterly, other items ("fiscal quarter end at least four months prior to forming
  portfolios"): the latest fiscal period ending at least four months before the formation
  month end.

Market equity in ratios: ME_BASE (named parameter, calibrated in deviation_log LI-3).
Short-term investments: net short-term investments (A001109000) before 2007, trading financial
assets (A001107000) from 2007 (DM A.2.15).
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from replication.li import data as D
from replication.li.factors import latest_quarterly

ME_BASE = "mv_float"  # market equity for price ratios: circulating (calibrated, deviation_log LI-3)

TA, BE, NI, REV, SALES = "A001000000", "A003000000", "B002000000", "B001100000", "B001101000"
CASH, STI_OLD, STI_NEW = "C006000000", "A001109000", "A001107000"
STD1, STD2, LTD, PREF = "A002101000", "A002125000", "A002206000", "A003112101"
DEP, AMORT, OCF, ICF, FCF = "D000103000", "D000104000", "C001000000", "C002000000", "C003000000"
CAPX, INV, PPE, INTANG, OLTA, OLTL = "C002007000", "A001123000", "A001212000", "A001218000", "A001223000", "A002209000"
CA, CL, TL = "A001100000", "A002100000", "A002000000"
LTI = ["A001203000", "A001202000", "A001205000", "A001211000", "A001204000", "A001206000"]
OPINC = "B001300000"

ITEMS = sorted({TA, BE, NI, REV, SALES, CASH, STI_OLD, STI_NEW, STD1, STD2, LTD, PREF, DEP, AMORT, OCF, ICF, FCF,
                CAPX, INV, PPE, INTANG, OLTA, OLTL, CA, CL, TL, OPINC, *LTI})


def _out(df: pd.DataFrame, value: str = "v") -> pd.DataFrame:
    o = df[["stkcd", "form", value]].rename(columns={value: "value"})
    o = o.replace([np.inf, -np.inf], np.nan).dropna(subset=["value"])
    return o.reset_index(drop=True)


def _sti(x: pd.DataFrame, year: pd.Series) -> pd.Series:
    return np.where(year < 2007, x[STI_OLD], x[STI_NEW])


def _debt(x: pd.DataFrame) -> pd.Series:
    return x[STD1].fillna(0) + x[STD2].fillna(0) + x[LTD].fillna(0)


def _lti(x: pd.DataFrame) -> pd.Series:
    return x[LTI].fillna(0).sum(axis=1).where(x[LTI].notna().any(axis=1))


# ---------------------------------------------------------------------------------------------
# Annual panel: fiscal year values with lags, formation at June of fy + 1
# ---------------------------------------------------------------------------------------------

def annual() -> pd.DataFrame:
    # Callers may add columns: hand out a copy so the memoized frame stays intact.
    return _annual_cached().copy()


@lru_cache(maxsize=1)
def _annual_cached() -> pd.DataFrame:
    a = D.annual(ITEMS).sort_values(["stkcd", "fy"]).reset_index(drop=True)
    a["sti"] = _sti(a, a["fy"])
    a["debt"] = _debt(a)
    a["lti"] = _lti(a)
    return a


def lagged(cols: list[str], k: int = 1) -> pd.DataFrame:
    """Annual panel with `cols` of fiscal year fy - k as <col>_l<k> (matched on fy, so a
    missing year gives NaN rather than an older year)."""
    a = annual()
    lag = a[["stkcd", "fy", *cols]].copy()
    lag["fy"] = lag["fy"] + k
    return a.merge(lag.rename(columns={c: f"{c}_l{k}" for c in cols}), on=["stkcd", "fy"], how="left")


def _june(x: pd.DataFrame) -> pd.DataFrame:
    x = x.copy()
    x["form"] = pd.PeriodIndex([pd.Period(f"{y + 1}-06", "M") for y in x["fy"]], freq="M")
    return x


@lru_cache(maxsize=2)
def _me_month(base: str) -> pd.DataFrame:
    p = D.stock_panel()
    return p[["stkcd", "month", base]].rename(columns={base: "me"})


def _with_me_dec(x: pd.DataFrame) -> pd.DataFrame:
    """Add market equity at the end of December of the fiscal year (calendar year t-1)."""
    me = _me_month(ME_BASE)
    dec = me[me["month"].dt.month == 12].copy()
    dec["fy"] = dec["month"].dt.year
    return x.merge(dec[["stkcd", "fy", "me"]], on=["stkcd", "fy"], how="left")


def _with_me_form(x: pd.DataFrame) -> pd.DataFrame:
    """Add market equity at the end of the formation month."""
    me = _me_month(ME_BASE).rename(columns={"month": "form"})
    return x.merge(me, on=["stkcd", "form"], how="left")


# ---------------------------------------------------------------------------------------------
# Quarterly data
# ---------------------------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _months() -> pd.PeriodIndex:
    p = D.stock_panel()
    return pd.period_range(p["month"].min(), p["month"].max(), freq="M")


def quarterly_lagged(values: pd.DataFrame, cols: list[str], lag_months: int = 4) -> pd.DataFrame:
    """For each stock and formation month f, the latest fiscal period whose end is at least
    `lag_months` months before the end of f (DM: "at least four months prior to forming
    portfolios"). values: stkcd, period_end, cols."""
    v = values.dropna(subset=["period_end"]).copy()
    v["avail"] = (v["period_end"].dt.to_period("M") + lag_months)
    v = v.sort_values("avail").rename(columns={"avail": "form"})
    months = _months()
    stocks = v["stkcd"].astype(str).unique()
    grid = pd.DataFrame({"stkcd": np.repeat(stocks, len(months)), "form": np.tile(months, len(stocks))})
    grid = grid.sort_values("form")
    v["stkcd"] = v["stkcd"].astype(str)
    v = v.sort_values(["form"])
    out = pd.merge_asof(grid, v[["stkcd", "form", "period_end", *cols]], on="form", by="stkcd", direction="backward")
    out["stkcd"] = out["stkcd"].astype("string")
    return out


def quarterly_announced(events: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Latest announced report at each formation month end, fiscal quarter end within six
    months and before the announcement (DM A.1.1). events: stkcd, period_end, announce_date,
    cols. Output column 'form' = formation month."""
    e = events[events["announce_date"].notna() & (events["period_end"] < events["announce_date"])]
    out = latest_quarterly(e, cols, _months())
    return out.rename(columns={"month": "form"})


def q_stock() -> pd.DataFrame:
    # Callers may add columns: hand out a copy so the memoized frame stays intact.
    return _q_stock_cached().copy()


@lru_cache(maxsize=1)
def _q_stock_cached() -> pd.DataFrame:
    """Balance-sheet values at each fiscal period end with derived items."""
    q = D.quarterly_stocks([TA, BE, CASH, STI_OLD, STI_NEW, STD1, STD2, LTD, PREF, INV, CA, CL, TL, "A001111000",
                            "A001101000", "A001212000"])
    q["sti"] = _sti(q, q["period_end"].dt.year)
    q["debt"] = _debt(q)
    return q


def q_flow() -> pd.DataFrame:
    # Callers may add columns: hand out a copy so the memoized frame stays intact.
    return _q_flow_cached().copy()


@lru_cache(maxsize=1)
def _q_flow_cached() -> pd.DataFrame:
    """Single-quarter flows (YTD differences) with announcement dates."""
    return D.quarterly_flows([NI, REV, SALES, OPINC, DEP, OCF, "B001201000", "B001209000", "B001210000",
                              "B001211000", "B002100000", "B001000000"])


# ---------------------------------------------------------------------------------------------
# A.2 Value versus growth
# ---------------------------------------------------------------------------------------------

def _annual_ratio(num: pd.Series, x: pd.DataFrame, positive: bool = False) -> pd.DataFrame:
    x = _with_me_dec(x.assign(num=num))
    x["v"] = x["num"] / x["me"].where(x["me"] > 0)
    if positive:
        x.loc[~(x["num"] > 0), "v"] = np.nan
    return _out(_june(x))


def bm() -> pd.DataFrame:
    """Bm (A.2.1): book equity fy t-1 / ME Dec t-1."""
    a = annual()
    return _annual_ratio(a[BE], a)


def dm() -> pd.DataFrame:
    """Dm (A.2.4): total debt / ME; zero-debt firms excluded."""
    a = annual()
    return _annual_ratio(a["debt"].where(a["debt"] != 0), a)


def am() -> pd.DataFrame:
    """Am (A.2.6): total assets / ME."""
    a = annual()
    return _annual_ratio(a[TA], a)


def ep() -> pd.DataFrame:
    """Ep (A.2.9): income before extraordinary items / ME (positive earnings, as HXZ)."""
    a = annual()
    return _annual_ratio(a[NI], a, positive=True)


def cp() -> pd.DataFrame:
    """Cp (A.2.11): (income + depreciation) / ME, positive cash flow only."""
    a = annual()
    return _annual_ratio(a[NI] + a[DEP], a, positive=True)


def sp() -> pd.DataFrame:
    """Sp (A.2.17): sales / ME, positive sales."""
    a = annual()
    return _annual_ratio(a[REV], a, positive=True)


def ocp() -> pd.DataFrame:
    """Ocp (A.2.19): operating cash flow (direct statement) / ME, positive only."""
    a = annual()
    return _annual_ratio(a[OCF], a, positive=True)


def _net_debt(x: pd.DataFrame) -> pd.Series:
    fin_liab = x[LTD].fillna(0) + x[STD1].fillna(0) + x[STD2].fillna(0) + x[PREF].fillna(0)
    fin_assets = x[CASH].fillna(0) + pd.Series(x["sti"], index=x.index).fillna(0)
    return fin_liab - fin_assets


def ebp() -> pd.DataFrame:
    """Ebp (A.2.21): (net debt + BE) / (net debt + ME); both positive."""
    a = _with_me_dec(annual())
    nd = _net_debt(a)
    book, mkt = nd + a[BE], nd + a["me"]
    a["v"] = (book / mkt).where((book > 0) & (mkt > 0))
    return _out(_june(a))


def ndp() -> pd.DataFrame:
    """Ndp (A.2.21): net debt / ME; positive net debt only."""
    a = _with_me_dec(annual())
    nd = _net_debt(a)
    a["v"] = (nd / a["me"]).where(nd > 0)
    return _out(_june(a))


def em() -> pd.DataFrame:
    """Em (A.2.15): EV / operating income before depreciation; both positive."""
    a = _with_me_dec(annual())
    ev = a["me"] + a["debt"] + a[PREF].fillna(0) - a[CASH].fillna(0) - pd.Series(a["sti"], index=a.index).fillna(0)
    oibd = a[OPINC] + a[DEP]
    a["v"] = (ev / oibd).where((ev > 0) & (oibd > 0))
    return _out(_june(a))


def sg() -> pd.DataFrame:
    """Sg (A.2.14): sales growth fy t-2 -> t-1."""
    a = lagged([REV], 1)
    a["v"] = a[REV] / a[f"{REV}_l1"].where(a[f"{REV}_l1"] > 0) - 1
    return _out(_june(a))


def sr() -> pd.DataFrame:
    """Sr (A.2.13): weighted average of the past five years' sales-growth quintile ranks,
    sum_{j=1..5} (6 - j) * Rank(t - j); positive sales and full five years required.
    Ranks are quintiles of all firms' growth each year."""
    a = lagged([REV], 1)
    a["g"] = (a[REV] / a[f"{REV}_l1"] - 1).where((a[REV] > 0) & (a[f"{REV}_l1"] > 0))
    a["rank"] = a.groupby("fy")["g"].transform(lambda s: pd.qcut(s, 5, labels=False, duplicates="drop") + 1)
    r = a[["stkcd", "fy", "rank"]]
    acc = r.copy()
    acc["v"] = 0.0
    acc["n"] = 0
    acc = acc[["stkcd", "fy"]].copy()
    tot = None
    for j in range(1, 6):
        lag = r.copy()
        lag["fy"] = lag["fy"] + (j - 1)  # rank of fy - (j-1) relative to the last fiscal year
        lag = lag.rename(columns={"rank": f"r{j}"})
        acc = acc.merge(lag, on=["stkcd", "fy"], how="left")
    acc["v"] = sum((6 - j) * acc[f"r{j}"] for j in range(1, 6))
    acc.loc[acc[[f"r{j}" for j in range(1, 6)]].isna().any(axis=1), "v"] = np.nan
    return _out(_june(acc))


def bmj() -> pd.DataFrame:
    """Bmj (A.2.2): book equity per share (fy t-1) / June-end price of t
    = BE / (ME at June t) with the same shares; we use BE / June ME."""
    a = annual()
    me = _me_month(ME_BASE)
    june = me[me["month"].dt.month == 6].copy()
    june["fy"] = june["month"].dt.year - 1
    x = a.merge(june[["stkcd", "fy", "me"]], on=["stkcd", "fy"], how="left")
    x["v"] = x[BE] / x["me"].where(x["me"] > 0)
    return _out(_june(x))


# Quarterly value ratios: numerator from quarterly data, ME at the end of t-1 (= form)

def _q_ratio(q: pd.DataFrame, positive: bool = False) -> pd.DataFrame:
    q = _with_me_form(q)
    q["v"] = q["num"] / q["me"].where(q["me"] > 0)
    if positive:
        q.loc[~(q["num"] > 0), "v"] = np.nan
    return _out(q)


def bmq() -> pd.DataFrame:
    """Bmq (A.2.3): book equity, latest quarter at least four months old / ME end t-1."""
    q = quarterly_lagged(q_stock().rename(columns={BE: "num"}), ["num"])
    return _q_ratio(q)


def dmq() -> pd.DataFrame:
    """Dmq (A.2.5): total debt (four-month rule) / ME; zero debt excluded."""
    s = q_stock()
    q = quarterly_lagged(s.assign(num=s["debt"].where(s["debt"] != 0)), ["num"])
    return _q_ratio(q)


def amq() -> pd.DataFrame:
    """Amq (A.2.7): total assets (four-month rule) / ME."""
    q = quarterly_lagged(q_stock().rename(columns={TA: "num"}), ["num"])
    return _q_ratio(q)


def epq() -> pd.DataFrame:
    """Epq (A.2.10): latest announced quarterly earnings / ME end t-1; positive earnings."""
    f = q_flow()
    q = quarterly_announced(f.rename(columns={NI: "num"}), ["num"])
    return _q_ratio(q, positive=True)


def spq() -> pd.DataFrame:
    """Spq (A.2.18): latest announced quarterly sales / ME; positive sales."""
    f = q_flow()
    q = quarterly_announced(f.rename(columns={REV: "num"}), ["num"])
    return _q_ratio(q, positive=True)


def cpq() -> pd.DataFrame:
    """Cpq (A.2.12): quarterly (earnings + depreciation), four-month rule / ME; positive."""
    f = q_flow()
    q = quarterly_lagged(f.assign(num=f[NI] + f[DEP]), ["num"])
    return _q_ratio(q, positive=True)


def ocpq() -> pd.DataFrame:
    """Ocpq (A.2.20): quarterly operating cash flow, four-month rule / ME; positive."""
    f = q_flow()
    q = quarterly_lagged(f.rename(columns={OCF: "num"}), ["num"])
    return _q_ratio(q, positive=True)


def emq() -> pd.DataFrame:
    """Emq (A.2.16): EV / quarterly operating income before depreciation (four-month rule)."""
    s, f = q_stock(), q_flow()
    x = s.merge(f[["stkcd", "period_end", OPINC, DEP]], on=["stkcd", "period_end"], how="left")
    x["oibd"] = x[OPINC] + x[DEP]
    x["adj"] = x["debt"] + x[PREF].fillna(0) - x[CASH].fillna(0) - pd.Series(x["sti"], index=x.index).fillna(0)
    q = _with_me_form(quarterly_lagged(x, ["oibd", "adj"]))
    ev = q["me"] + q["adj"]
    q["v"] = (ev / q["oibd"]).where((ev > 0) & (q["oibd"] > 0))
    return _out(q)


def _q_net_debt() -> pd.DataFrame:
    s = q_stock()
    return s.assign(nd=_net_debt(s))


def ebpq() -> pd.DataFrame:
    """Ebpq (A.2.22): (net debt + BE) / (net debt + ME), four-month rule."""
    q = _with_me_form(quarterly_lagged(_q_net_debt(), ["nd", BE]))
    book, mkt = q["nd"] + q[BE], q["nd"] + q["me"]
    q["v"] = (book / mkt).where((book > 0) & (mkt > 0))
    return _out(q)


def ndpq() -> pd.DataFrame:
    """Ndpq (A.2.22): net debt / ME, four-month rule; positive net debt."""
    q = _with_me_form(quarterly_lagged(_q_net_debt(), ["nd"]))
    q["v"] = (q["nd"] / q["me"]).where(q["nd"] > 0)
    return _out(q)


# ---------------------------------------------------------------------------------------------
# A.3 Investment
# ---------------------------------------------------------------------------------------------

def _ratio_lag_ta(num_col: str, x: pd.DataFrame) -> pd.DataFrame:
    x = x.copy()
    x["v"] = x[num_col] / x[f"{TA}_l1"].where(x[f"{TA}_l1"] > 0)
    return _out(_june(x))


def ia() -> pd.DataFrame:
    """I/A (A.3.2): total assets fy t-1 / fy t-2 - 1."""
    a = lagged([TA], 1)
    a["v"] = a[TA] / a[f"{TA}_l1"].where(a[f"{TA}_l1"] > 0) - 1
    return _out(_june(a))


def dpia() -> pd.DataFrame:
    """dPia (A.3.4): (change in gross PPE + change in inventory) / lagged total assets."""
    a = lagged([PPE, INV, TA], 1)
    a["num"] = (a[PPE] - a[f"{PPE}_l1"]).fillna(0) + (a[INV] - a[f"{INV}_l1"]).fillna(0)
    a.loc[(a[PPE] - a[f"{PPE}_l1"]).isna() & (a[INV] - a[f"{INV}_l1"]).isna(), "num"] = np.nan
    return _ratio_lag_ta("num", a)


def noa() -> pd.DataFrame:
    """Noa (A.3.5): (operating assets - operating liabilities) / lagged total assets."""
    a = lagged([TA], 1)
    op_assets = a[TA] - a[CASH].fillna(0) - pd.Series(a["sti"], index=a.index).fillna(0)
    op_liab = a[TA] - a[STD1].fillna(0) - a[STD2].fillna(0) - a[LTD].fillna(0) - a[PREF].fillna(0) - a[BE]
    a["num"] = op_assets - op_liab
    return _ratio_lag_ta("num", a)


def dlno() -> pd.DataFrame:
    """dLno (A.3.6): change in (net PPE + intangibles + other LT assets - other LT
    liabilities) + depreciation + amortization, over average total assets."""
    a = lagged([PPE, INTANG, OLTA, OLTL, TA], 1)
    chg = sum((a[c] - a[f"{c}_l1"]).fillna(0) * s for c, s in ((PPE, 1), (INTANG, 1), (OLTA, 1), (OLTL, -1)))
    a["v"] = (chg + a[DEP].fillna(0) + a[AMORT].fillna(0)) / ((a[TA] + a[f"{TA}_l1"]) / 2)
    return _out(_june(a))


def _capx_growth(k: int) -> pd.DataFrame:
    a = lagged([CAPX], k)
    a["v"] = a[CAPX] / a[f"{CAPX}_l{k}"].where(a[f"{CAPX}_l{k}"] > 0) - 1
    return _out(_june(a))


def ig() -> pd.DataFrame:
    """Ig (A.3.7): capex growth fy t-2 -> t-1."""
    return _capx_growth(1)


def ig2() -> pd.DataFrame:
    """2Ig (A.3.8): capex growth fy t-3 -> t-1."""
    return _capx_growth(2)


def ig3() -> pd.DataFrame:
    """3Ig (A.3.9): capex growth fy t-4 -> t-1."""
    return _capx_growth(3)


def aci() -> pd.DataFrame:
    """Aci (A.3.1): Ce(t-1) / mean(Ce(t-2..t-4)) - 1, Ce = capex / sales."""
    a = annual().copy()
    a["ce"] = a[CAPX] / a[REV].where(a[REV] > 0)
    base = a[["stkcd", "fy"]].copy()
    for k in (1, 2, 3):
        l = a[["stkcd", "fy", "ce"]].copy()
        l["fy"] += k
        base = base.merge(l.rename(columns={"ce": f"ce{k}"}), on=["stkcd", "fy"], how="left")
    x = a.merge(base, on=["stkcd", "fy"])
    bench = (x["ce1"] + x["ce2"] + x["ce3"]) / 3
    x["v"] = x["ce"] / bench.where(bench > 0) - 1
    return _out(_june(x))


def cdi() -> pd.DataFrame:
    """Cdi (A.3.13): log growth of total debt fy t-6 -> t-1."""
    a = lagged(["debt"], 5)
    a["v"] = np.log(a["debt"].where(a["debt"] > 0) / a["debt_l5"].where(a["debt_l5"] > 0))
    return _out(_june(a))


def ivg() -> pd.DataFrame:
    """Ivg (A.3.14): inventory growth fy t-2 -> t-1."""
    a = lagged([INV], 1)
    a["v"] = a[INV] / a[f"{INV}_l1"].where(a[f"{INV}_l1"] > 0) - 1
    return _out(_june(a))


def ivchg() -> pd.DataFrame:
    """Ivc (A.3.15): change in inventory / average total assets; firms with no inventory in
    both years excluded."""
    a = lagged([INV, TA], 1)
    no_inv = (a[INV].fillna(0) == 0) & (a[f"{INV}_l1"].fillna(0) == 0)
    a["v"] = ((a[INV] - a[f"{INV}_l1"]) / ((a[TA] + a[f"{TA}_l1"]) / 2)).where(~no_inv)
    return _out(_june(a))


def oa() -> pd.DataFrame:
    """Oa (A.3.16): (net income - operating cash flow) / lagged total assets."""
    a = lagged([TA], 1)
    a["num"] = a[NI] - a[OCF]
    return _ratio_lag_ta("num", a)


def ta_accr() -> pd.DataFrame:
    """Ta (A.3.17): (net income - operating, investing and financing cash flows) / lagged TA."""
    a = lagged([TA], 1)
    a["num"] = a[NI] - (a[OCF] + a[ICF] + a[FCF])
    return _ratio_lag_ta("num", a)


def _wc_parts(a: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    coa = a[CA] - a[CASH].fillna(0) - pd.Series(a["sti"], index=a.index).fillna(0)
    col = a[CL] - (a[STD1].fillna(0) + a[STD2].fillna(0))
    return coa, col


def _changes(builder) -> pd.DataFrame:
    a = annual().copy()
    parts = builder(a)
    base = a[["stkcd", "fy", TA]].copy()
    for name, s in parts.items():
        base[name] = s
    lag = base.copy()
    lag["fy"] += 1
    x = base.merge(lag.rename(columns={c: f"{c}_l1" for c in base.columns if c not in ("stkcd", "fy")}),
                   on=["stkcd", "fy"], how="left")
    return x


def _chg_out(x: pd.DataFrame, num: pd.Series) -> pd.DataFrame:
    x = x.assign(v=num / x[f"{TA}_l1"].where(x[f"{TA}_l1"] > 0))
    return _out(_june(x))


def _wc() -> pd.DataFrame:
    def parts(a):
        coa, col = _wc_parts(a)
        return {"coa": coa, "col": col, "wc": coa - col}
    return _changes(parts)


def dwc() -> pd.DataFrame:
    """dWc (A.3.18): change in (current operating assets - current operating liabilities)
    / lagged total assets."""
    x = _wc()
    return _chg_out(x, x["wc"] - x["wc_l1"])


def dcoa() -> pd.DataFrame:
    """dCoa (A.3.18)."""
    x = _wc()
    return _chg_out(x, x["coa"] - x["coa_l1"])


def dcol() -> pd.DataFrame:
    """dCol (A.3.18)."""
    x = _wc()
    return _chg_out(x, x["col"] - x["col_l1"])


def _nco() -> pd.DataFrame:
    def parts(a):
        nca = a[TA] - (a[CA] + a["lti"].fillna(0))
        ncl = a[TL] - a[CL] - a[LTD].fillna(0)
        return {"nca": nca, "ncl": ncl, "nco": nca - ncl}
    return _changes(parts)


def dnco() -> pd.DataFrame:
    """dNco (A.3.19): change in (non-current operating assets - liabilities) / lagged TA."""
    x = _nco()
    return _chg_out(x, x["nco"] - x["nco_l1"])


def dnca() -> pd.DataFrame:
    """dNca (A.3.19)."""
    x = _nco()
    return _chg_out(x, x["nca"] - x["nca_l1"])


def dncl() -> pd.DataFrame:
    """dNcl (A.3.19)."""
    x = _nco()
    return _chg_out(x, x["ncl"] - x["ncl_l1"])


def _fin() -> pd.DataFrame:
    def parts(a):
        fna = pd.Series(a["sti"], index=a.index).fillna(0) + a["lti"].fillna(0)
        fnl = a[LTD].fillna(0) + a[STD1].fillna(0) + a[STD2].fillna(0) + a[PREF].fillna(0)
        return {"fna": fna, "fnl": fnl, "fin": fna - fnl, "lti_": a["lti"], "be": a[BE]}
    return _changes(parts)


def dfin() -> pd.DataFrame:
    """dFin (A.3.20): change in net financial assets / lagged TA."""
    x = _fin()
    return _chg_out(x, x["fin"] - x["fin_l1"])


def dlti() -> pd.DataFrame:
    """dLti (A.3.20): change in long-term investments / lagged TA; firms without long-term
    investments in both years excluded."""
    x = _fin()
    none = (x["lti_"].fillna(0) == 0) & (x["lti__l1"].fillna(0) == 0)
    return _chg_out(x, (x["lti_"].fillna(0) - x["lti__l1"].fillna(0)).where(~none))


def dfnl() -> pd.DataFrame:
    """dFnl (A.3.20): change in financial liabilities / lagged TA."""
    x = _fin()
    return _chg_out(x, x["fnl"] - x["fnl_l1"])


def dbe() -> pd.DataFrame:
    """dBe (A.3.20): change in book equity / lagged TA."""
    x = _fin()
    return _chg_out(x, x["be"] - x["be_l1"])


def iaq() -> pd.DataFrame:
    """Iaq (A.3.3): quarterly total assets / four-quarter-lagged - 1, four-month rule."""
    s = q_stock()[["stkcd", "period_end", TA]].copy()
    lag = s.copy()
    lag["period_end"] = (lag["period_end"].dt.to_period("Q") + 4).dt.to_timestamp(how="end").dt.normalize()
    s = s.merge(lag.rename(columns={TA: "ta4"}), on=["stkcd", "period_end"], how="left")
    s["num"] = s[TA] / s["ta4"].where(s["ta4"] > 0) - 1
    q = quarterly_lagged(s, ["num"])
    return _out(q.rename(columns={"num": "v"}))


def nsi() -> pd.DataFrame:
    """Nsi (A.3.10): log(shares outstanding fy t-1 / fy t-2); shares from the share-capital
    history (TRD_Capchg) at each fiscal year end."""
    from replication.lsy.data import total_shares_month_end
    months = pd.period_range("1998-12", "2026-12", freq="M")
    sh = total_shares_month_end(months)
    sh = sh[sh["month"].dt.month == 12].copy()
    sh["fy"] = sh["month"].dt.year
    a = annual()[["stkcd", "fy"]].merge(sh[["stkcd", "fy", "total_shares"]], on=["stkcd", "fy"], how="left")
    l = a.copy()
    l["fy"] += 1
    a = a.merge(l.rename(columns={"total_shares": "sh_l1"}), on=["stkcd", "fy"], how="left")
    a["v"] = np.log(a["total_shares"].where(a["total_shares"] > 0) / a["sh_l1"].where(a["sh_l1"] > 0))
    return _out(_june(a))


CEI_ME, CEI_MIN_MONTHS, CEI_RET = "mv_float", 60, "ret"  # calibration switches (deviation_log LI-3)


def cei() -> pd.DataFrame:
    """Cei (A.3.12): log(ME June t / ME June t-5) - cumulative log return July t-5..June t."""
    p = D.stock_panel()
    me = p.pivot(index="month", columns="stkcd", values=CEI_ME)
    from csmar.panels import load
    rr = load("stock_month")[["stkcd", "month", CEI_RET]]
    lr = np.log1p(rr.pivot(index="month", columns="stkcd", values=CEI_RET)).reindex(columns=me.columns)
    full = pd.period_range(me.index.min(), me.index.max(), freq="M")
    me, lr = me.reindex(full), lr.reindex(full)
    cum = lr.rolling(60, min_periods=CEI_MIN_MONTHS).sum()
    v = np.log(me / me.shift(60)) - cum
    v = v[v.index.month == 6].stack().rename("value").reset_index().rename(columns={"level_0": "form"})
    return v.replace([np.inf, -np.inf], np.nan).dropna()


def dii() -> pd.DataFrame:
    """dIi (A.3.11): %d(firm capex) - %d(industry capex), each relative to the prior
    two-year average; industry = CSRC code (Nnindcd ~ csrc2012), at least two firms."""
    a = annual()[["stkcd", "fy", CAPX]].copy()
    ind = D.stock_panel().drop_duplicates("stkcd").set_index("stkcd")["csrc2012"]
    a["ind"] = a["stkcd"].map(ind)
    for k in (1, 2):
        l = a[["stkcd", "fy", CAPX]].copy()
        l["fy"] += k
        a = a.merge(l.rename(columns={CAPX: f"c{k}"}), on=["stkcd", "fy"], how="left")
    a["e"] = (a["c1"] + a["c2"]) / 2
    ok = a["e"] > 0
    a["pd_f"] = ((a[CAPX] - a["e"]) / a["e"]).where(ok)
    g = a[ok].groupby(["ind", "fy"])
    agg = g[[CAPX, "e"]].sum().assign(n=g.size())
    agg["pd_i"] = ((agg[CAPX] - agg["e"]) / agg["e"]).where(agg["n"] >= 2)
    a = a.merge(agg["pd_i"].reset_index(), on=["ind", "fy"], how="left")
    a["v"] = a["pd_f"] - a["pd_i"]
    return _out(_june(a))


def poa() -> pd.DataFrame:
    """Poa (A.3.22): operating accruals / |net income|."""
    a = annual().copy()
    a["v"] = (a[NI] - a[OCF]) / a[NI].abs().where(a[NI] != 0)
    return _out(_june(a))


def pta() -> pd.DataFrame:
    """Pta (A.3.23): total accruals / |net income|."""
    a = annual().copy()
    a["v"] = (a[NI] - (a[OCF] + a[ICF] + a[FCF])) / a[NI].abs().where(a[NI] != 0)
    return _out(_june(a))


def _dac_panel() -> pd.DataFrame:
    # Callers may add columns: hand out a copy so the memoized frame stays intact.
    return _dac_panel_cached().copy()


@lru_cache(maxsize=1)
def _dac_panel_cached() -> pd.DataFrame:
    """Discretionary accruals, modified Jones model (Dechow, Sloan and Sweeney 1995), the
    method CSMAR's DisAcc follows (DM A.3.21; CSMAR's own DisAcc table is not in our
    subscription, so it is rebuilt): total accruals / lagged TA regressed by CSRC industry
    and fiscal year on 1/lagged TA, (change in revenue - change in receivables) / lagged TA
    and gross PPE / lagged TA; at least 10 firms per industry-year."""
    a = lagged([TA, REV, PPE], 1)
    rec = "A001111000"  # accounts receivable
    if rec not in a.columns:
        s = D.annual([rec])
        a = a.merge(s, on=["stkcd", "fy"], how="left")
        l = s.copy()
        l["fy"] += 1
        a = a.merge(l.rename(columns={rec: f"{rec}_l1"}), on=["stkcd", "fy"], how="left")
    ind = D.stock_panel().drop_duplicates("stkcd").set_index("stkcd")["csrc2012"].astype(str).str[:1]
    a["ind"] = a["stkcd"].map(ind)
    lta = a[f"{TA}_l1"].where(a[f"{TA}_l1"] > 0)
    a["y"] = (a[NI] - a[OCF]) / lta
    a["x0"] = 1 / lta
    a["x1"] = ((a[REV] - a[f"{REV}_l1"]) - (a[rec].fillna(0) - a[f"{rec}_l1"].fillna(0))) / lta
    a["x2"] = a[PPE] / lta
    a = a.dropna(subset=["y", "x0", "x1", "x2", "ind"])
    out = []
    for _, g in a.groupby(["ind", "fy"]):
        if len(g) < 10:
            continue
        X = g[["x0", "x1", "x2"]].to_numpy()
        b, *_ = np.linalg.lstsq(X, g["y"].to_numpy(), rcond=None)
        out.append(pd.DataFrame({"stkcd": g["stkcd"], "fy": g["fy"], "dac": g["y"] - X @ b, "ta_l1": g[f"{TA}_l1"],
                                 "ni": g[NI]}))
    return pd.concat(out, ignore_index=True)


def dac() -> pd.DataFrame:
    """Dac (A.3.21): discretionary accruals (see _dac_panel)."""
    d = _dac_panel().rename(columns={"dac": "v"})
    return _out(_june(d))


def pda() -> pd.DataFrame:
    """Pda (A.3.24): Dac x lagged TA / |net income|."""
    d = _dac_panel()
    d["v"] = d["dac"] * d["ta_l1"] / d["ni"].abs().where(d["ni"] != 0)
    return _out(_june(d))


def nxf() -> pd.DataFrame:
    """Nxf (A.3.25): net equity financing (change in common stock + capital surplus) + net
    debt financing (change in long-term debt + long-term notes - change in short-term debt),
    over average total assets."""
    cs, sur, ltn = "A003101000", "A003102000", "A002203000"
    s = D.annual([cs, sur, ltn])
    a = annual().merge(s, on=["stkcd", "fy"], how="left")
    a["st"] = a[STD1].fillna(0) + a[STD2].fillna(0)
    cols = [cs, sur, LTD, ltn, "st", TA]
    l = a[["stkcd", "fy", *cols]].copy()
    l["fy"] += 1
    a = a.merge(l.rename(columns={c: f"{c}_l1" for c in cols}), on=["stkcd", "fy"], how="left")
    d = lambda c: (a[c] - a[f"{c}_l1"])
    nef = d(cs).fillna(0) + d(sur).fillna(0)
    ndf = d(LTD).fillna(0) + d(ltn).fillna(0) - d("st").fillna(0)
    a["v"] = (nef + ndf) / ((a[TA] + a[f"{TA}_l1"]) / 2)
    return _out(_june(a))


# ---------------------------------------------------------------------------------------------
# A.4 Profitability
# ---------------------------------------------------------------------------------------------

def _june_ratio(num: pd.Series, den: pd.Series, x: pd.DataFrame, den_positive: bool = True) -> pd.DataFrame:
    x = x.assign(v=num / (den.where(den > 0) if den_positive else den.where(den != 0)))
    return _out(_june(x))


def roe() -> pd.DataFrame:
    """Roe (A.4.1): income / book equity, fy t-1."""
    a = annual()
    return _june_ratio(a[NI], a[BE], a)


def roa() -> pd.DataFrame:
    """Roa (A.4.3): income / total assets."""
    a = annual()
    return _june_ratio(a[NI], a[TA], a)


def _noa_level(a: pd.DataFrame) -> pd.Series:
    op_assets = a[TA] - a[CASH].fillna(0) - pd.Series(a["sti"], index=a.index).fillna(0)
    op_liab = a[TA] - a[STD1].fillna(0) - a[STD2].fillna(0) - a[LTD].fillna(0) - a[PREF].fillna(0) - a[BE]
    return op_assets - op_liab


def _with_noa_lag() -> pd.DataFrame:
    a = annual().copy()
    a["noa_lvl"] = _noa_level(a)
    l = a[["stkcd", "fy", "noa_lvl"]].copy()
    l["fy"] += 1
    return a.merge(l.rename(columns={"noa_lvl": "noa_l1"}), on=["stkcd", "fy"], how="left")


def rna() -> pd.DataFrame:
    """Rna (A.4.5): operating income / lagged Noa (positive)."""
    a = _with_noa_lag()
    return _june_ratio(a[OPINC], a["noa_l1"], a)


def pm() -> pd.DataFrame:
    """Pm (A.4.5): operating income / sales."""
    a = annual()
    return _june_ratio(a[OPINC], a[REV], a)


def ato() -> pd.DataFrame:
    """Ato (A.4.5): sales / lagged Noa (positive)."""
    a = _with_noa_lag()
    return _june_ratio(a[REV], a["noa_l1"], a)


def cto() -> pd.DataFrame:
    """Cto (A.4.6): sales / lagged total assets."""
    a = lagged([TA], 1)
    return _june_ratio(a[REV], a[f"{TA}_l1"], a)


def gpa() -> pd.DataFrame:
    """Gpa (A.4.9): (total revenue - COGS) / total assets (current)."""
    a = annual().merge(D.annual(["B001201000"]), on=["stkcd", "fy"], how="left")
    return _june_ratio(a[SALES] - a["B001201000"], a[TA], a)


def gla() -> pd.DataFrame:
    """Gla (A.4.10): (total revenue - COGS) / lagged total assets."""
    a = lagged([TA], 1).merge(D.annual(["B001201000"]), on=["stkcd", "fy"], how="left")
    return _june_ratio(a[SALES] - a["B001201000"], a[f"{TA}_l1"], a)


def ope() -> pd.DataFrame:
    """Ope (A.4.12): operating income / book equity (current)."""
    a = annual()
    return _june_ratio(a[OPINC], a[BE], a)


def ole() -> pd.DataFrame:
    """Ole (A.4.13): operating income / lagged book equity."""
    a = lagged([BE], 1)
    return _june_ratio(a[OPINC], a[f"{BE}_l1"], a)


def opa() -> pd.DataFrame:
    """Opa (A.4.15): operating income / total assets (current)."""
    a = annual()
    return _june_ratio(a[OPINC], a[TA], a)


def ola() -> pd.DataFrame:
    """Ola (A.4.16): operating income / lagged total assets."""
    a = lagged([TA], 1)
    return _june_ratio(a[OPINC], a[f"{TA}_l1"], a)


def _cash_op(a: pd.DataFrame) -> pd.Series:
    return a[OPINC] - (a[NI] - a[OCF])


def cop() -> pd.DataFrame:
    """Cop (A.4.18): (operating income - operating accruals) / total assets."""
    a = annual()
    return _june_ratio(_cash_op(a), a[TA], a)


def cla() -> pd.DataFrame:
    """Cla (A.4.19): (operating income - operating accruals) / lagged total assets."""
    a = lagged([TA], 1)
    return _june_ratio(_cash_op(a), a[f"{TA}_l1"], a)


def cbe() -> pd.DataFrame:
    """Cbe (A.4.21): (operating income - operating accruals) / book equity."""
    a = annual()
    return _june_ratio(_cash_op(a), a[BE], a)


def tbi() -> pd.DataFrame:
    """Tbi (A.4.24): pretax income / net income; both positive."""
    a = annual().merge(D.annual(["B002100000"]), on=["stkcd", "fy"], how="left")
    pre = a[NI] + a["B002100000"]
    a["v"] = (pre / a[NI]).where((pre > 0) & (a[NI] > 0))
    return _out(_june(a))


def bl() -> pd.DataFrame:
    """Bl (A.4.26): total assets / book equity."""
    a = annual()
    return _june_ratio(a[TA], a[BE], a)


def oscore() -> pd.DataFrame:
    """O (A.4.22): Ohlson (1980) model one."""
    a = lagged([NI], 1).merge(D.annual(["B002100000"]), on=["stkcd", "fy"], how="left")
    ta = a[TA].where(a[TA] > 0)
    tlta = a["debt"] / ta
    wcta = (a[CA] - a[CL]) / ta
    clca = a[CL] / a[CA].where(a[CA] > 0)
    oeneg = (a[TL] > a[TA]).astype(float)
    nita = a[NI] / ta
    futl = (a[NI] + a["B002100000"].fillna(0) + a[DEP].fillna(0)) / a[TL].where(a[TL] > 0)
    intwo = ((a[NI] < 0) & (a[f"{NI}_l1"] < 0)).astype(float)
    chin = (a[NI] - a[f"{NI}_l1"]) / (a[NI].abs() + a[f"{NI}_l1"].abs()).where(lambda s: s > 0)
    a["v"] = (-1.32 - 0.407 * np.log(ta) + 6.03 * tlta - 1.43 * wcta + 0.076 * clca - 1.72 * oeneg - 2.37 * nita
              - 1.83 * futl + 0.285 * intwo - 0.521 * chin)
    return _out(_june(a))


def zscore() -> pd.DataFrame:
    """Z (A.4.23): Altman (1968); components winsorized at 1%/99% each year; ME at the
    fiscal year end."""
    a = _with_me_dec(annual().merge(D.annual(["A003103000", "A003105000"]), on=["stkcd", "fy"], how="left"))
    ta = a[TA].where(a[TA] > 0)
    comps = {"wcta": (a[CA] - a[CL]) / ta, "reta": (a["A003103000"].fillna(0) + a["A003105000"].fillna(0)) / ta,
             "ebitta": a[OPINC] / ta, "metl": a["me"] / a[TL].where(a[TL] > 0), "saleta": a[REV] / ta}
    for k, s in comps.items():
        lo = s.groupby(a["fy"]).transform(lambda v: v.quantile(0.01))
        hi = s.groupby(a["fy"]).transform(lambda v: v.quantile(0.99))
        a[k] = s.clip(lo, hi)
    a["v"] = 1.2 * a["wcta"] + 1.4 * a["reta"] + 3.3 * a["ebitta"] + 0.6 * a["metl"] + a["saleta"]
    return _out(_june(a))


# Quarterly profitability

def _q_lag_stock(cols: list[str], quarters: int = 1) -> pd.DataFrame:
    """Balance-sheet values lagged by `quarters` fiscal quarters, keyed on the current
    period_end; before 2002 (semi-annual reports only) the previous available report is used."""
    s = q_stock()[["stkcd", "period_end", *cols]].sort_values(["stkcd", "period_end"])
    lag = s.copy()
    lag["period_end"] = (lag["period_end"].dt.to_period("Q") + quarters).dt.to_timestamp(how="end").dt.normalize()
    out = s[["stkcd", "period_end"]].merge(lag, on=["stkcd", "period_end"], how="left")
    prev = s.groupby("stkcd")[cols].shift(1)
    early = s["period_end"].dt.year < 2002
    for c in cols:
        out[c] = out[c].where(~(early.to_numpy() & out[c].isna().to_numpy()), prev[c].to_numpy())
    return out.rename(columns={c: f"{c}_lq" for c in cols})


def q_all() -> pd.DataFrame:
    # Callers may add columns: hand out a copy so the memoized frame stays intact.
    return _q_all_cached().copy()


@lru_cache(maxsize=1)
def _q_all_cached() -> pd.DataFrame:
    """Quarterly flows + stocks + one-quarter-lagged stocks + four-quarter-lagged flows."""
    f = q_flow()
    s = q_stock()
    x = f.merge(s.drop(columns=["announce_date"]), on=["stkcd", "period_end"], how="left")
    x = x.merge(_q_lag_stock([TA, BE]), on=["stkcd", "period_end"], how="left")
    s2 = s.assign(noa_lvl=_noa_level(s))
    x = x.merge(s2[["stkcd", "period_end", "noa_lvl"]], on=["stkcd", "period_end"], how="left")
    nl = s2[["stkcd", "period_end", "noa_lvl"]].copy()
    nl["period_end"] = (nl["period_end"].dt.to_period("Q") + 1).dt.to_timestamp(how="end").dt.normalize()
    x = x.merge(nl.rename(columns={"noa_lvl": "noa_lq"}), on=["stkcd", "period_end"], how="left")
    f4 = f[["stkcd", "period_end", NI, REV]].copy()
    f4["period_end"] = (f4["period_end"].dt.to_period("Q") + 4).dt.to_timestamp(how="end").dt.normalize()
    x = x.merge(f4.rename(columns={NI: "ni_l4", REV: "rev_l4"}), on=["stkcd", "period_end"], how="left")
    return x


def _ann(col: str, x: pd.DataFrame) -> pd.DataFrame:
    return _out(quarterly_announced(x, [col]).rename(columns={col: "v"}))


def _lag4(col: str, x: pd.DataFrame) -> pd.DataFrame:
    return _out(quarterly_lagged(x, [col]).rename(columns={col: "v"}))


def _div(a: pd.Series, b: pd.Series) -> pd.Series:
    return a / b.where(b > 0)


def roeq() -> pd.DataFrame:
    """Roeq (A.4.1): quarterly income / one-quarter-lagged book equity (announced)."""
    x = q_all()
    return _ann("v", x.assign(v=_div(x[NI], x[f"{BE}_lq"])))


def droe() -> pd.DataFrame:
    """dRoe (A.4.2): Roeq minus its value four quarters prior (announced)."""
    x = q_all().assign(r=lambda d: _div(d[NI], d[f"{BE}_lq"]))
    l = x[["stkcd", "period_end", "r"]].copy()
    l["period_end"] = (l["period_end"].dt.to_period("Q") + 4).dt.to_timestamp(how="end").dt.normalize()
    x = x.merge(l.rename(columns={"r": "r4"}), on=["stkcd", "period_end"], how="left")
    return _ann("v", x.assign(v=x["r"] - x["r4"]))


def roaq() -> pd.DataFrame:
    """Roaq (A.4.3): quarterly income / one-quarter-lagged total assets (announced)."""
    x = q_all()
    return _ann("v", x.assign(v=_div(x[NI], x[f"{TA}_lq"])))


def droa() -> pd.DataFrame:
    """dRoa (A.4.4): Roaq minus its value four quarters prior (announced)."""
    x = q_all().assign(r=lambda d: _div(d[NI], d[f"{TA}_lq"]))
    l = x[["stkcd", "period_end", "r"]].copy()
    l["period_end"] = (l["period_end"].dt.to_period("Q") + 4).dt.to_timestamp(how="end").dt.normalize()
    x = x.merge(l.rename(columns={"r": "r4"}), on=["stkcd", "period_end"], how="left")
    return _ann("v", x.assign(v=x["r"] - x["r4"]))


def rnaq() -> pd.DataFrame:
    """Rnaq (A.4.7): quarterly operating income / one-quarter-lagged Noa (four-month rule)."""
    x = q_all()
    return _lag4("v", x.assign(v=_div(x[OPINC], x["noa_lq"])))


def pmq() -> pd.DataFrame:
    """Pmq (A.4.7): quarterly operating income / quarterly sales (four-month rule)."""
    x = q_all()
    return _lag4("v", x.assign(v=_div(x[OPINC], x[REV])))


def atoq() -> pd.DataFrame:
    """Atoq (A.4.7): quarterly sales / one-quarter-lagged Noa (announced)."""
    x = q_all()
    return _ann("v", x.assign(v=_div(x[REV], x["noa_lq"])))


def ctoq() -> pd.DataFrame:
    """Ctoq (A.4.8): quarterly sales / one-quarter-lagged total assets (announced)."""
    x = q_all()
    return _ann("v", x.assign(v=_div(x[REV], x[f"{TA}_lq"])))


def glaq() -> pd.DataFrame:
    """Glaq (A.4.11): (quarterly revenue - COGS) / lagged total assets (four-month rule)."""
    x = q_all()
    return _lag4("v", x.assign(v=_div(x[SALES] - x["B001201000"], x[f"{TA}_lq"])))


def oleq() -> pd.DataFrame:
    """Oleq (A.4.14): quarterly operating income / lagged book equity (four-month rule)."""
    x = q_all()
    return _lag4("v", x.assign(v=_div(x[OPINC], x[f"{BE}_lq"])))


def olaq() -> pd.DataFrame:
    """Olaq (A.4.17): quarterly operating income / lagged total assets (four-month rule)."""
    x = q_all()
    return _lag4("v", x.assign(v=_div(x[OPINC], x[f"{TA}_lq"])))


def claq() -> pd.DataFrame:
    """Claq (A.4.20): (quarterly operating income - (income - operating cash flow)) / lagged
    total assets (four-month rule)."""
    x = q_all()
    return _lag4("v", x.assign(v=_div(x[OPINC] - (x[NI] - x[OCF]), x[f"{TA}_lq"])))


def tbiq() -> pd.DataFrame:
    """Tbiq (A.4.25): quarterly pretax income / net income; both positive (four-month rule)."""
    x = q_all()
    pre = x[NI] + x["B002100000"]
    return _lag4("v", x.assign(v=(pre / x[NI]).where((pre > 0) & (x[NI] > 0))))


def blq() -> pd.DataFrame:
    """Blq (A.4.27): total assets / book equity (four-month rule)."""
    x = q_stock()
    return _lag4("v", x.assign(v=_div(x[TA], x[BE])))


def sgq() -> pd.DataFrame:
    """Sgq (A.4.28): quarterly sales / sales four quarters ago (announced)."""
    x = q_all()
    return _ann("v", x.assign(v=_div(x[REV], x["rev_l4"])))


# ---------------------------------------------------------------------------------------------
# A.5 Intangibles
# ---------------------------------------------------------------------------------------------

SELL, ADMIN, COGS, TAX, GOODWILL, RECV = "B001209000", "B001210000", "B001201000", "B002100000", "A001220000", "A001111000"
# R&D proxy (deviation_log LI-4): the paper's annual R&D (CSMAR RDSpendSum, 研发投入情况表) is not
# in NYU's subscription. The paper itself proxies R&D with management fees (B001210000,
# Chen, Kim, Yao and Yu 2010) for Rdmq, Rdsq and Rca; we use the same proxy for Rdm and Rds.
RD_PROXY = ADMIN


def annual_x() -> pd.DataFrame:
    # Callers may add columns: hand out a copy so the memoized frame stays intact.
    return _annual_x_cached().copy()


@lru_cache(maxsize=1)
def _annual_x_cached() -> pd.DataFrame:
    """Annual panel with the extra intangibles items and one-year lags."""
    extra = [SELL, ADMIN, COGS, TAX, GOODWILL, RECV, "A001212000"]
    a = annual().merge(D.annual([c for c in extra if c not in annual().columns]), on=["stkcd", "fy"], how="left")
    cols = [SELL, ADMIN, REV, SALES, COGS, INV, RECV, TA, BE, NI, TAX, AMORT]
    for k in (1, 2, 3):
        l = a[["stkcd", "fy", *cols]].copy()
        l["fy"] += k
        a = a.merge(l.rename(columns={c: f"{c}_l{k}" for c in cols}), on=["stkcd", "fy"], how="left")
    return a


def adm() -> pd.DataFrame:
    """Adm (A.5.1): selling expenses (advertising proxy, as the paper) / ME Dec t-1; positive."""
    a = annual_x()
    return _annual_ratio(a[SELL].where(a[SELL] > 0), a)


def gad() -> pd.DataFrame:
    """gAd (A.5.2): growth of selling expenses fy t-2 -> t-1."""
    a = annual_x()
    a = a.assign(v=a[SELL] / a[f"{SELL}_l1"].where(a[f"{SELL}_l1"] > 0) - 1)
    return _out(_june(a))


def rdm() -> pd.DataFrame:
    """Rdm (A.5.3): R&D (proxy) / ME Dec t-1; positive."""
    a = annual_x()
    return _annual_ratio(a[RD_PROXY].where(a[RD_PROXY] > 0), a)


def rds() -> pd.DataFrame:
    """Rds (A.5.5): R&D (proxy) / sales; positive."""
    a = annual_x()
    a = a.assign(v=(a[RD_PROXY] / a[REV].where(a[REV] > 0)).where(a[RD_PROXY] > 0))
    return _out(_june(a))


def rdmq() -> pd.DataFrame:
    """Rdmq (A.5.4): quarterly management fees / ME at the end of last calendar year;
    four-month rule; positive."""
    q = quarterly_lagged(q_flow().rename(columns={ADMIN: "num"}), ["num"])
    me = _me_month(ME_BASE)
    dec = me[me["month"].dt.month == 12].copy()
    dec["y"] = dec["month"].dt.year + 1
    q["y"] = q["form"].dt.year
    q = q.merge(dec[["stkcd", "y", "me"]], on=["stkcd", "y"], how="left")
    q["v"] = (q["num"] / q["me"].where(q["me"] > 0)).where(q["num"] > 0)
    return _out(q)


def rdsq() -> pd.DataFrame:
    """Rdsq (A.5.6): quarterly management fees / quarterly sales; four-month rule; positive."""
    f = q_flow()
    x = f.assign(v=(f[ADMIN] / f[REV].where(f[REV] > 0)).where(f[ADMIN] > 0))
    return _lag4("v", x)


def ol() -> pd.DataFrame:
    """Ol (A.5.7): (COGS + selling + admin) / total assets."""
    a = annual_x()
    return _june_ratio(a[COGS] + a[SELL].fillna(0) + a[ADMIN].fillna(0), a[TA], a)


def olq() -> pd.DataFrame:
    """Olq (A.5.8): quarterly operating costs / total assets; four-month rule."""
    x = q_all()
    return _lag4("v", x.assign(v=_div(x[COGS] + x[SELL].fillna(0) + x[ADMIN].fillna(0), x[TA])))


@lru_cache(maxsize=1)
def _employees() -> pd.DataFrame:
    from csmar.readers import read_raw
    y = read_raw("CG_Ybasic", columns=["Stkcd", "Reptdt", "Y0601b"])
    e = pd.DataFrame({"stkcd": y["Stkcd"], "fy": pd.to_datetime(y["Reptdt"]).dt.year,
                      "emp": pd.to_numeric(y["Y0601b"], errors="coerce")})
    e = e[pd.to_datetime(y["Reptdt"]).dt.month.eq(12).to_numpy()]
    return e.drop_duplicates(["stkcd", "fy"], keep="last")


def hn() -> pd.DataFrame:
    """Hn (A.5.9): (N(t-1) - N(t-2)) / average; zero excluded."""
    e = _employees()
    l = e.copy()
    l["fy"] += 1
    x = e.merge(l.rename(columns={"emp": "emp_l1"}), on=["stkcd", "fy"], how="left")
    x["v"] = (x["emp"] - x["emp_l1"]) / ((x["emp"] + x["emp_l1"]) / 2).where(lambda s: s > 0)
    x.loc[x["v"] == 0, "v"] = np.nan
    return _out(_june(x))


def lfe() -> pd.DataFrame:
    """Lfe (A.5.20): change in sales per employee over last year's sales per employee."""
    e = _employees()
    a = annual_x().merge(e, on=["stkcd", "fy"], how="left")
    l = e.copy()
    l["fy"] += 1
    a = a.merge(l.rename(columns={"emp": "emp_l1"}), on=["stkcd", "fy"], how="left")
    spe = a[SALES] / a["emp"].where(a["emp"] > 0)
    spe1 = a[f"{SALES}_l1"] / a["emp_l1"].where(a["emp_l1"] > 0)
    a["v"] = (spe - spe1) / spe1.where(spe1 > 0)
    return _out(_june(a))


def rca() -> pd.DataFrame:
    """Rca (A.5.10): R&D capital (management fees, five years at 1, .8, .6, .4, .2) / TA;
    latest year required, earlier years missing -> 0."""
    a = annual()[["stkcd", "fy", ADMIN if ADMIN in annual().columns else TA, TA]].copy() if False else None
    s = D.annual([ADMIN]).merge(annual()[["stkcd", "fy", TA]], on=["stkcd", "fy"], how="outer")
    rc = s[["stkcd", "fy", ADMIN]].copy()
    tot = s[["stkcd", "fy", TA, ADMIN]].copy()
    tot["rc"] = tot[ADMIN]
    for k, w in ((1, 0.8), (2, 0.6), (3, 0.4), (4, 0.2)):
        l = rc.copy()
        l["fy"] += k
        tot = tot.merge(l.rename(columns={ADMIN: f"x{k}"}), on=["stkcd", "fy"], how="left")
        tot["rc"] = tot["rc"] + w * tot[f"x{k}"].fillna(0)
    tot["v"] = (tot["rc"] / tot[TA].where(tot[TA] > 0)).where(tot[ADMIN].notna())
    return _out(_june(tot))


def _analyst_profile() -> pd.DataFrame:
    from csmar.readers import read_raw
    a = read_raw("AF_CFEATUREPROFILE", columns=["Stkcd", "Accper", "AnaAttention", "ReportAttention"])
    return pd.DataFrame({"stkcd": a["Stkcd"], "fy": pd.to_datetime(a["Accper"]).dt.year,
                         "ana": pd.to_numeric(a["AnaAttention"], errors="coerce").fillna(0),
                         "rep": pd.to_numeric(a["ReportAttention"], errors="coerce").fillna(0)})


def _analyst_base() -> pd.DataFrame:
    """Firms in the annual panel from fiscal 2001 (zero if missing, DM A.5.21)."""
    a = annual()[["stkcd", "fy"]]
    a = a[a["fy"] >= 2001]
    return a.merge(_analyst_profile(), on=["stkcd", "fy"], how="left").fillna({"ana": 0, "rep": 0})


def ana() -> pd.DataFrame:
    """Ana (A.5.21): analyst coverage attention, fiscal year t-1, zero if missing."""
    return _out(_june(_analyst_base().rename(columns={"ana": "v"})))


def rep() -> pd.DataFrame:
    """Rep (A.5.22): analyst report attention, fiscal year t-1, zero if missing."""
    return _out(_june(_analyst_base().rename(columns={"rep": "v"})))


def fop() -> pd.DataFrame:
    """Fop (A.5.11): forecast optimism. CSMAR's RelativeOptimism per analyst report,
    averaged over the reports dated in calendar year t-1 for each firm (the data manual gives
    no aggregation rule; deviation_log LI-4)."""
    from csmar.readers import read_raw
    f = read_raw("AF_ANAFOREFEATURE", columns=["Stkcd", "Rptdt", "RelativeOptimism"])
    x = pd.DataFrame({"stkcd": f["Stkcd"], "fy": pd.to_datetime(f["Rptdt"], errors="coerce").dt.year,
                      "o": pd.to_numeric(f["RelativeOptimism"], errors="coerce")}).dropna()
    x = x[x["stkcd"].astype(str).str.len() > 0]
    g = x.groupby(["stkcd", "fy"])["o"].mean().rename("v").reset_index()
    return _out(_june(g))


def _pct_change_vs_avg(cur, l1, l2):
    e = (l1 + l2) / 2
    return (cur - e) / e.where(e > 0), e


def dsi() -> pd.DataFrame:
    """dSi (A.5.15): %d(sales) - %d(inventory), each vs the prior two-year average."""
    a = annual_x()
    s, es = _pct_change_vs_avg(a[SALES], a[f"{SALES}_l1"], a[f"{SALES}_l2"])
    i, ei = _pct_change_vs_avg(a[INV], a[f"{INV}_l1"], a[f"{INV}_l2"])
    a["v"] = (s - i).where((es > 0) & (ei > 0))
    return _out(_june(a))


def dsa() -> pd.DataFrame:
    """dSa (A.5.16): %d(sales) - %d(receivables)."""
    a = annual_x()
    s, es = _pct_change_vs_avg(a[SALES], a[f"{SALES}_l1"], a[f"{SALES}_l2"])
    r, er = _pct_change_vs_avg(a[RECV], a[f"{RECV}_l1"], a[f"{RECV}_l2"])
    a["v"] = s - r
    return _out(_june(a))


def dgs() -> pd.DataFrame:
    """dGs (A.5.17): %d(gross margin) - %d(sales)."""
    a = annual_x()
    gm = a[SALES] - a[COGS]
    gm1 = a[f"{SALES}_l1"] - a[f"{COGS}_l1"]
    gm2 = a[f"{SALES}_l2"] - a[f"{COGS}_l2"]
    g, _ = _pct_change_vs_avg(gm, gm1, gm2)
    s, _ = _pct_change_vs_avg(a[SALES], a[f"{SALES}_l1"], a[f"{SALES}_l2"])
    a["v"] = g - s
    return _out(_june(a))


def dss() -> pd.DataFrame:
    """dSs (A.5.18): %d(sales) - %d(SG&A)."""
    a = annual_x()
    sga = a[SELL].fillna(0) + a[ADMIN].fillna(0)
    sga1 = a[f"{SELL}_l1"].fillna(0) + a[f"{ADMIN}_l1"].fillna(0)
    sga2 = a[f"{SELL}_l2"].fillna(0) + a[f"{ADMIN}_l2"].fillna(0)
    s, _ = _pct_change_vs_avg(a[SALES], a[f"{SALES}_l1"], a[f"{SALES}_l2"])
    g, _ = _pct_change_vs_avg(sga, sga1, sga2)
    a["v"] = s - g
    return _out(_june(a))


def etr() -> pd.DataFrame:
    """Etr (A.5.19): [Tax/EBT - mean(Tax/EBT over t-1..t-3)] x dEPS; EBT = pretax income +
    amortization; dEPS = change in EPS (income / total shares) over the price at the end of
    the previous fiscal year."""
    from replication.lsy.data import total_shares_month_end
    a = annual_x()
    ebt = lambda k: (a[NI if k == 0 else f"{NI}_l{k}"] + a[TAX if k == 0 else f"{TAX}_l{k}"]
                     + a[AMORT if k == 0 else f"{AMORT}_l{k}"].fillna(0))
    rate = lambda k: a[TAX if k == 0 else f"{TAX}_l{k}"] / ebt(k).where(ebt(k) > 0)
    sh = total_shares_month_end(pd.period_range("1998-12", "2026-12", freq="M"))
    sh = sh[sh["month"].dt.month == 12].assign(fy=lambda d: d["month"].dt.year)[["stkcd", "fy", "total_shares"]]
    a = a.merge(sh, on=["stkcd", "fy"], how="left")
    l = sh.copy()
    l["fy"] += 1
    a = a.merge(l.rename(columns={"total_shares": "sh_l1"}), on=["stkcd", "fy"], how="left")
    p = D.stock_panel()
    px = p[p["month"].dt.month == 12].assign(fy=lambda d: d["month"].dt.year + 1)[["stkcd", "fy", "close"]]
    a = a.merge(px, on=["stkcd", "fy"], how="left")
    deps = (a[NI] / a["total_shares"] - a[f"{NI}_l1"] / a["sh_l1"]) / a["close"]
    a["v"] = (rate(0) - (rate(1) + rate(2) + rate(3)) / 3) * deps
    return _out(_june(a))


def _cash_hold(x: pd.DataFrame) -> pd.Series:
    return x[CASH].fillna(0) + pd.Series(x["sti"], index=x.index).fillna(0)


def tan() -> pd.DataFrame:
    """Tan (A.5.23): (cash + .715 receivables + .547 inventory + .535 PPE) / TA."""
    a = annual_x()
    num = _cash_hold(a) + 0.715 * a[RECV].fillna(0) + 0.547 * a[INV].fillna(0) + 0.535 * a[PPE].fillna(0)
    return _june_ratio(num, a[TA], a)


def tanq() -> pd.DataFrame:
    """Tanq (A.5.24): quarterly tangibility; four-month rule."""
    s = q_stock()
    num = _cash_hold(s) + 0.715 * s[RECV].fillna(0) + 0.547 * s[INV].fillna(0) + 0.535 * s[PPE].fillna(0)
    return _lag4("v", s.assign(v=_div(num, s[TA])))


def cta() -> pd.DataFrame:
    """Cta (A.5.28): cash holdings / total assets; four-month rule."""
    s = q_stock()
    return _lag4("v", s.assign(v=_div(_cash_hold(s), s[TA])))


@lru_cache(maxsize=1)
def _dividends() -> pd.DataFrame:
    """Total cash dividends per fiscal year: cash dividend per share with ex-dates in the
    calendar year (TRD_Cptl, type CA) x total shares at year end."""
    from csmar.readers import read_raw
    from replication.lsy.data import total_shares_month_end
    c = read_raw("TRD_Cptl", columns=["Stkcd", "Disttyp", "Exdistdt", "Amount"])
    c = c[c["Disttyp"] == "CA"]
    d = pd.DataFrame({"stkcd": c["Stkcd"], "fy": pd.to_datetime(c["Exdistdt"], errors="coerce").dt.year,
                      "dps": pd.to_numeric(c["Amount"], errors="coerce")}).dropna()
    d = d.groupby(["stkcd", "fy"])["dps"].sum().reset_index()
    sh = total_shares_month_end(pd.period_range("1998-12", "2026-12", freq="M"))
    sh = sh[sh["month"].dt.month == 12].assign(fy=lambda x: x["month"].dt.year)[["stkcd", "fy", "total_shares"]]
    d = d.merge(sh, on=["stkcd", "fy"], how="left")
    d["div"] = d["dps"] * d["total_shares"]
    return d[["stkcd", "fy", "div"]]


def kz() -> pd.DataFrame:
    """Kz (A.5.25): Lamont, Polk and Saa-Requejo (2001) index."""
    a = _with_me_dec(annual_x())
    l = a[["stkcd", "fy", PPE]].copy()
    l["fy"] += 1
    a = a.merge(l.rename(columns={PPE: "k_l1"}), on=["stkcd", "fy"], how="left").merge(_dividends(), on=["stkcd", "fy"], how="left")
    k = a["k_l1"].where(a["k_l1"] > 0)
    cf = a[NI] + a[DEP].fillna(0) + a[AMORT].fillna(0)
    q = (a[TA] + a["me"] - a[BE]) / a[TA].where(a[TA] > 0)
    tc = a[BE] + a["debt"]
    a["v"] = (-1.002 * cf / k + 0.283 * q - 1.315 * a[CASH].fillna(0) / k + 3.139 * a["debt"] / tc.where(tc != 0)
              - 39.368 * a["div"].fillna(0) / k)
    return _out(_june(a))


def sa() -> pd.DataFrame:
    """Sa (A.5.26): -0.737 Size + 0.043 Size^2 - 0.040 Age; Size = log total assets, Age =
    years since the first trading record."""
    a = annual().copy()
    first = D.stock_panel().groupby("stkcd")["month"].min().dt.year
    a["age"] = a["fy"] - a["stkcd"].map(first)
    size = np.log(a[TA].where(a[TA] > 0))
    a["v"] = -0.737 * size + 0.043 * size ** 2 - 0.040 * a["age"]
    return _out(_june(a))


def vcf() -> pd.DataFrame:
    """Vcf (A.5.27): standard deviation over the past 16 quarters (>= 8) of quarterly
    operating cash flow (income + depreciation + amortization + change in working capital)
    over sales; four-month rule."""
    x = q_all().sort_values(["stkcd", "period_end"]).copy()
    f = D.quarterly_flows([AMORT])[["stkcd", "period_end", AMORT]]
    x = x.merge(f, on=["stkcd", "period_end"], how="left")
    wc = x[CA] - x[CL]
    dwc = wc - wc.groupby(x["stkcd"]).shift(1)
    ocf = x[NI] + x[DEP].fillna(0) + x[AMORT].fillna(0) + dwc
    x["r"] = ocf / x[REV].where(x[REV] > 0)
    x["v"] = x.groupby("stkcd")["r"].transform(lambda s: s.rolling(16, min_periods=8).std())
    return _lag4("v", x)


def _al(x: pd.DataFrame) -> pd.Series:
    cash = _cash_hold(x)
    tang = x[TA] - x[CA] - x[GOODWILL].fillna(0) - x[INTANG].fillna(0)
    return cash + 0.75 * (x[CA] - cash) + 0.5 * tang


def ala() -> pd.DataFrame:
    """Ala (A.5.34): asset liquidity / lagged total assets."""
    a = _with_me_dec(annual_x().merge(D.annual([INTANG]) if INTANG not in annual_x().columns else annual_x()[["stkcd", "fy"]],
                                      on=["stkcd", "fy"], how="left"))
    return _june_ratio(_al(a), a[f"{TA}_l1"], a)


def alm() -> pd.DataFrame:
    """Alm (A.5.34): asset liquidity / lagged market value of assets (TA + ME - BE)."""
    a = _with_me_dec(annual_x())
    a["mva"] = a[TA] + a["me"] - a[BE]
    l = a[["stkcd", "fy", "mva"]].copy()
    l["fy"] += 1
    a = a.merge(l.rename(columns={"mva": "mva_l1"}), on=["stkcd", "fy"], how="left")
    return _june_ratio(_al(a), a["mva_l1"], a)


def _q_al() -> pd.DataFrame:
    # Callers may add columns: hand out a copy so the memoized frame stays intact.
    return _q_al_cached().copy()


@lru_cache(maxsize=1)
def _q_al_cached() -> pd.DataFrame:
    s = q_stock().merge(D.quarterly_stocks([GOODWILL, INTANG])[["stkcd", "period_end", GOODWILL, INTANG]],
                        on=["stkcd", "period_end"], how="left")
    s["al"] = _al(s)
    return s.merge(_q_lag_stock([TA, BE]), on=["stkcd", "period_end"], how="left")


def alaq() -> pd.DataFrame:
    """Alaq (A.5.35): quarterly asset liquidity / one-quarter-lagged TA; four-month rule."""
    s = _q_al()
    return _lag4("v", s.assign(v=_div(s["al"], s[f"{TA}_lq"])))


def almq() -> pd.DataFrame:
    """Almq (A.5.35): quarterly asset liquidity / one-quarter-lagged market value of assets
    (ME at the lagged quarter end); four-month rule."""
    s = _q_al()
    me = _me_month(ME_BASE).copy()
    me["period_end"] = (me["month"] + 3).dt.to_timestamp(how="end").dt.normalize()  # ME of the previous quarter end
    s = s.merge(me[["stkcd", "period_end", "me"]], on=["stkcd", "period_end"], how="left")
    mva = s[f"{TA}_lq"] + s["me"] - s[f"{BE}_lq"]
    return _lag4("v", s.assign(v=_div(s["al"], mva)))


# ---------------------------------------------------------------------------------------------
# A.1 Momentum (accounting surprises)
# ---------------------------------------------------------------------------------------------

def _per_share() -> pd.DataFrame:
    # Callers may add columns: hand out a copy so the memoized frame stays intact.
    return _per_share_cached().copy()


@lru_cache(maxsize=1)
def _per_share_cached() -> pd.DataFrame:
    """Quarterly flows per share (total shares at the fiscal period end) and assets per share."""
    from replication.lsy.data import total_shares_month_end
    x = q_all()[["stkcd", "period_end", "announce_date", NI, REV, "B002100000", TA]].copy()
    sh = total_shares_month_end(pd.period_range("1990-12", "2026-12", freq="M"))
    sh["period_end"] = sh["month"].dt.to_timestamp(how="end").dt.normalize()
    x = x.merge(sh[["stkcd", "period_end", "total_shares"]], on=["stkcd", "period_end"], how="left")
    s = x["total_shares"].where(x["total_shares"] > 0)
    x["eps"], x["rps"], x["tps"], x["aps"] = x[NI] / s, x[REV] / s, x["B002100000"] / s, x[TA] / s
    return x


def _lag_q(x: pd.DataFrame, cols: list[str], k: int) -> pd.DataFrame:
    l = x[["stkcd", "period_end", *cols]].copy()
    l["period_end"] = (l["period_end"].dt.to_period("Q") + k).dt.to_timestamp(how="end").dt.normalize()
    return x.merge(l.rename(columns={c: f"{c}_q{k}" for c in cols}), on=["stkcd", "period_end"], how="left")


def _surprise(col: str) -> pd.DataFrame:
    """(X_q - X_{q-4}) / sd of that change over the past eight quarters (>= 6), announced."""
    x = _lag_q(_per_share(), [col], 4).sort_values(["stkcd", "period_end"])
    x["chg"] = x[col] - x[f"{col}_q4"]
    sd = x.groupby("stkcd")["chg"].transform(lambda s: s.rolling(8, min_periods=6).std())
    x["v"] = x["chg"] / sd.where(sd > 0)
    return _ann("v", x)


def sue() -> pd.DataFrame:
    """Sue (A.1.1): standardized unexpected quarterly earnings per share."""
    return _surprise("eps")


def rs() -> pd.DataFrame:
    """Rs (A.1.5): standardized unexpected quarterly revenue per share."""
    return _surprise("rps")


def tes() -> pd.DataFrame:
    """Tes (A.1.6): change in quarterly tax expense per share vs four quarters ago, over
    assets per share four quarters ago; zero Tes excluded."""
    x = _lag_q(_per_share(), ["tps", "aps"], 4)
    x["v"] = (x["tps"] - x["tps_q4"]) / x["aps_q4"].where(x["aps_q4"] > 0)
    x.loc[x["v"] == 0, "v"] = np.nan
    return _ann("v", x)


def abr() -> pd.DataFrame:
    """Abr (A.1.2): sum of daily (stock - value-weighted market) returns over trading days
    -2..+1 around the latest quarterly earnings announcement (announced)."""
    from csmar.panels import daily
    d = daily(["Dretwd", "Dsmvosd"])
    d = d[d["board"].isin(["SH_MAIN", "SZ_MAIN", "SZ_SME", "CHINEXT", "STAR"])].copy()
    d["r"] = pd.to_numeric(d["Dretwd"], errors="coerce")
    d = d.sort_values(["stkcd", "date"])
    d["w"] = d.groupby("stkcd")["Dsmvosd"].shift(1)
    ok = d["r"].notna() & (d["w"] > 0)
    mkt = (d.loc[ok, "r"] * d.loc[ok, "w"]).groupby(d.loc[ok, "date"]).sum() / d.loc[ok, "w"].groupby(d.loc[ok, "date"]).sum()
    days = mkt.index.sort_values()
    pos = pd.Series(np.arange(len(days)), index=days)
    d["ar"] = d["r"] - d["date"].map(mkt)
    d["pos"] = d["date"].map(pos)
    ev = q_all()[["stkcd", "period_end", "announce_date"]].dropna().copy()
    # Day 0 = the announcement date, or the next trading day when it is not one.
    idx = np.searchsorted(days.values, ev["announce_date"].values)
    ev = ev[idx < len(days)]
    ev["p0"] = idx[idx < len(days)]
    car = []
    ar = d.set_index(["stkcd", "pos"])["ar"]
    for k in (-2, -1, 0, 1):
        key = pd.MultiIndex.from_arrays([ev["stkcd"], ev["p0"] + k])
        car.append(ar.reindex(key).to_numpy())
    ev["v"] = np.nansum(np.vstack(car), axis=0)
    ev.loc[np.isnan(np.vstack(car)).all(axis=0), "v"] = np.nan
    return _ann("v", ev)


# ---------------------------------------------------------------------------------------------
# A.5.29-A.5.33 Governance and earnings attributes
# ---------------------------------------------------------------------------------------------

def gov() -> pd.DataFrame:
    """Gov (A.5.29): first principal component (standardized inputs, by year) of total
    management pay, executive share ownership, share of independent directors, board size,
    CEO duality and shares balance (sum of the 2nd-5th largest holdings over the largest).
    The paper's seventh input, institutional ownership (机构投资者), is not in NYU's
    subscription; the index uses the other six (deviation_log LI-4)."""
    from csmar.readers import read_raw
    from replication.lsy.data import total_shares_month_end
    m = read_raw("CG_ManagerShareSalary", columns=["Symbol", "Enddate", "StatisticalCaliber", "TotalSalary",
                                                   "Holdshares", "DirectorNumber", "IndependentDirectorNumber"])
    m = m[pd.to_numeric(m["StatisticalCaliber"], errors="coerce") == 1]
    g = pd.DataFrame({"stkcd": m["Symbol"].astype(str).str.zfill(6).astype("string"), "date": pd.to_datetime(m["Enddate"]),
                      "pay": pd.to_numeric(m["TotalSalary"], errors="coerce"),
                      "hold": pd.to_numeric(m["Holdshares"], errors="coerce"),
                      "board": pd.to_numeric(m["DirectorNumber"], errors="coerce"),
                      "indep": pd.to_numeric(m["IndependentDirectorNumber"], errors="coerce")})
    g = g[g["date"].dt.month == 12].assign(fy=lambda x: x["date"].dt.year).drop_duplicates(["stkcd", "fy"], keep="last")
    y = read_raw("CG_Ybasic", columns=["Stkcd", "Reptdt", "Y1001b"])
    y = pd.DataFrame({"stkcd": y["Stkcd"], "date": pd.to_datetime(y["Reptdt"]),
                      "dual": (pd.to_numeric(y["Y1001b"], errors="coerce") == 1).astype(float)})
    y = y[y["date"].dt.month == 12].assign(fy=lambda x: x["date"].dt.year).drop_duplicates(["stkcd", "fy"], keep="last")
    h = read_raw("HLD_CR", columns=["Stkcd", "Reptdt", "Shrcr1", "Shrcr2"])
    h = pd.DataFrame({"stkcd": h["Stkcd"], "date": pd.to_datetime(h["Reptdt"]),
                      "bal": (pd.to_numeric(h["Shrcr2"], errors="coerce") - pd.to_numeric(h["Shrcr1"], errors="coerce"))
                      / pd.to_numeric(h["Shrcr1"], errors="coerce")})
    h = h[h["date"].dt.month == 12].assign(fy=lambda x: x["date"].dt.year).drop_duplicates(["stkcd", "fy"], keep="last")
    sh = total_shares_month_end(pd.period_range("1998-12", "2026-12", freq="M"))
    sh = sh[sh["month"].dt.month == 12].assign(fy=lambda x: x["month"].dt.year)[["stkcd", "fy", "total_shares"]]
    x = g.merge(y[["stkcd", "fy", "dual"]], on=["stkcd", "fy"], how="inner").merge(
        h[["stkcd", "fy", "bal"]], on=["stkcd", "fy"], how="inner").merge(sh, on=["stkcd", "fy"], how="left")
    x["exec"] = x["hold"] / x["total_shares"]
    x["indep_ratio"] = x["indep"] / x["board"].where(x["board"] > 0)
    x["lpay"] = np.log1p(x["pay"])
    cols = ["lpay", "exec", "indep_ratio", "board", "dual", "bal"]
    x = x.dropna(subset=cols)
    out = []
    for fy, gx in x.groupby("fy"):
        if len(gx) < 30:
            continue
        z = (gx[cols] - gx[cols].mean()) / gx[cols].std(ddof=0).replace(0, np.nan)
        z = z.fillna(0)
        w, v = np.linalg.eigh(np.cov(z.to_numpy(), rowvar=False))
        pc = v[:, -1]
        pc = pc if pc[0] >= 0 else -pc  # sign: higher pay loads positively
        out.append(gx[["stkcd", "fy"]].assign(v=z.to_numpy() @ pc))
    return _out(_june(pd.concat(out, ignore_index=True)))


def _earn_panel() -> pd.DataFrame:
    # Callers may add columns: hand out a copy so the memoized frame stays intact.
    return _earn_panel_cached().copy()


@lru_cache(maxsize=1)
def _earn_panel_cached() -> pd.DataFrame:
    """Annual earnings attributes inputs: EPS, earnings / ME, change in earnings / ME, the
    15-month return ending three months after the fiscal year end, OCF and income over
    lagged assets."""
    from replication.lsy.data import total_shares_month_end
    a = lagged([TA, NI], 1)
    sh = total_shares_month_end(pd.period_range("1990-12", "2026-12", freq="M"))
    sh = sh[sh["month"].dt.month == 12].assign(fy=lambda x: x["month"].dt.year)[["stkcd", "fy", "total_shares"]]
    a = _with_me_dec(a.merge(sh, on=["stkcd", "fy"], how="left"))
    a["eps"] = a[NI] / a["total_shares"].where(a["total_shares"] > 0)
    me = a["me"].where(a["me"] > 0)
    a["earn"] = a[NI] / me
    a["dearn"] = (a[NI] - a[f"{NI}_l1"]) / me
    a["ni_ta"] = a[NI] / a[f"{TA}_l1"].where(a[f"{TA}_l1"] > 0)
    a["ocf_ta"] = a[OCF] / a[f"{TA}_l1"].where(a[f"{TA}_l1"] > 0)
    p = D.stock_panel()
    lr = np.log1p(p.pivot(index="month", columns="stkcd", values="ret"))
    lr = lr.reindex(pd.period_range(lr.index.min(), lr.index.max(), freq="M"))
    r15 = np.expm1(lr.rolling(15, min_periods=12).sum())
    r15 = r15[r15.index.month == 3].stack().rename("r15").reset_index().rename(columns={"level_0": "month"})
    r15["fy"] = r15["month"].dt.year - 1
    return a.merge(r15[["stkcd", "fy", "r15"]], on=["stkcd", "fy"], how="left")


def _rolling_firm(fn, cols: list[str], window: int = 8) -> pd.DataFrame:
    """Apply fn(window_frame) -> dict over each firm's rolling `window`-year history ending at
    fiscal year fy (full history required)."""
    a = _earn_panel()
    rows = []
    for s, g in a.sort_values("fy").groupby("stkcd"):
        g = g.set_index("fy")
        years = g.index.to_numpy()
        for fy in years:
            win = g.loc[fy - window + 1: fy, cols]
            if len(win) < window or win.isna().any().any():
                continue
            rows.append({"stkcd": s, "fy": fy, **fn(win)})
    return pd.DataFrame(rows)


@lru_cache(maxsize=1)
def _ar1() -> pd.DataFrame:
    def f(w):
        y, x = w["eps"].to_numpy()[1:], w["eps"].to_numpy()[:-1]
        X = np.column_stack([np.ones_like(x), x])
        b, *_ = np.linalg.lstsq(X, y, rcond=None)
        e = y - X @ b
        return {"eper": b[1], "eprd": e.std(ddof=2) if len(e) > 2 else np.nan}
    return _rolling_firm(f, ["eps"], 9)  # 8 AR(1) observations need nine annual values


def eper() -> pd.DataFrame:
    """Eper (A.5.30): AR(1) slope of EPS over the eight-year window ending t-1."""
    return _out(_june(_ar1().rename(columns={"eper": "v"})))


def eprd() -> pd.DataFrame:
    """Eprd (A.5.30): residual volatility of the AR(1) of EPS."""
    return _out(_june(_ar1().rename(columns={"eprd": "v"})))


def esm() -> pd.DataFrame:
    """Esm (A.5.31): sd(income / lagged TA) / sd(OCF / lagged TA) over eight years."""
    def f(w):
        s = w["ocf_ta"].std()
        return {"v": w["ni_ta"].std() / s if s > 0 else np.nan}
    return _out(_june(_rolling_firm(f, ["ni_ta", "ocf_ta"])))


@lru_cache(maxsize=1)
def _evr_etl() -> pd.DataFrame:
    def f(w):
        out = {}
        y = w["r15"].to_numpy()
        X = np.column_stack([np.ones(len(w)), w["earn"], w["dearn"]])
        b, *_ = np.linalg.lstsq(X, y, rcond=None)
        e = y - X @ b
        out["evr"] = 1 - (e @ e) / ((y - y.mean()) @ (y - y.mean())) if y.std() > 0 else np.nan
        r = w["r15"].to_numpy()
        neg = (r < 0).astype(float)
        X2 = np.column_stack([np.ones(len(w)), neg, r, neg * r])
        y2 = w["earn"].to_numpy()
        b2, *_ = np.linalg.lstsq(X2, y2, rcond=None)
        e2 = y2 - X2 @ b2
        out["etl"] = 1 - (e2 @ e2) / ((y2 - y2.mean()) @ (y2 - y2.mean())) if y2.std() > 0 else np.nan
        out["ecs"] = (b2[2] + b2[3]) / b2[2] if b2[2] != 0 else np.nan
        return out
    return _rolling_firm(f, ["r15", "earn", "dearn"])


def evr() -> pd.DataFrame:
    """Evr (A.5.32): R2 of the 15-month return on earnings and earnings changes (8 years)."""
    return _out(_june(_evr_etl().rename(columns={"evr": "v"})))


def etl() -> pd.DataFrame:
    """Etl (A.5.33): R2 of earnings on returns with the negative-return interaction."""
    return _out(_june(_evr_etl().rename(columns={"etl": "v"})))


def ecs() -> pd.DataFrame:
    """Ecs (A.5.33): (beta1 + beta2) / beta1 of the same regression."""
    return _out(_june(_evr_etl().rename(columns={"ecs": "v"})))
