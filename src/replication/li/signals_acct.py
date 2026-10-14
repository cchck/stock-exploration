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

@lru_cache(maxsize=1)
def annual() -> pd.DataFrame:
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


@lru_cache(maxsize=1)
def q_stock() -> pd.DataFrame:
    """Balance-sheet values at each fiscal period end with derived items."""
    q = D.quarterly_stocks([TA, BE, CASH, STI_OLD, STI_NEW, STD1, STD2, LTD, PREF, INV, CA, CL, TL, "A001111000",
                            "A001101000", "A001212000"])
    q["sti"] = _sti(q, q["period_end"].dt.year)
    q["debt"] = _debt(q)
    return q


@lru_cache(maxsize=1)
def q_flow() -> pd.DataFrame:
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
