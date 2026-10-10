"""CH-3 and CH-4 factors (LSY section 5.1 and 7.1).

CH-3: within the universe (top 70% after filters), split at the median size into S/B and by
EP into the top 30% (V), middle 40% (M) and bottom 30% (G); value-weight the six
intersections by total A-share market value;
    SMB = (S/V + S/M + S/G)/3 - (B/V + B/M + B/G)/3,   VMG = (S/V + B/V)/2 - (S/G + B/G)/2,
    MKT = value-weighted universe return minus the one-year deposit rate.
Negative-EP stocks are kept and classified as growth (section 7, p. 61).
CH-4 adds PMO from the same 2x3 construction on abnormal turnover (long low turnover =
pessimistic, short high = optimistic); CH-4's SMB averages the EP-neutral and the
turnover-neutral SMB. MKT and VMG are the same as in CH-3.

Choices the paper leaves open are parameters (`ep_breakpoints`), documented where used.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from csmar.readers import read_raw
from replication.common.portfolios import assign_groups, weighted_returns


def risk_free_monthly() -> pd.Series:
    """One-year deposit rate (CSMAR NRI01) converted to a monthly return, in decimal.

    The rate in force on each calendar day of month t is compounded daily,
    (1 + r_annual)^(1/365) per day, which is CSMAR's own daily conversion. This reproduces
    Stambaugh's rf_mon (e.g. 2000-02: 2.25% x 29/365 = 0.18%, 2000-03: 0.19%).
    """
    r = read_raw("TRD_Nrrate", columns=["Nrr1", "Clsdt", "Nrrdata"])
    r = r[r["Nrr1"] == "NRI01"]
    rate = pd.Series(r["Nrrdata"].astype(float).to_numpy() / 100, index=pd.to_datetime(r["Clsdt"])).sort_index()
    rate = rate[~rate.index.duplicated(keep="last")]
    days = pd.date_range(rate.index.min(), pd.Timestamp("2026-12-31"), freq="D")
    daily = rate.reindex(days, method="ffill")
    log_daily = np.log1p(daily) / 365
    monthly = np.expm1(log_daily.groupby(days.to_period("M")).sum())
    monthly.index.name = "month"
    return monthly.rename("rf")


def _two_by_three(panel: pd.DataFrame, var: str, *, negative_as_low: bool,
                  breakpoints: str) -> pd.DataFrame:
    """Six value-weighted portfolios from a median size split and a 30/40/30 split on var.

    Returns wide returns with columns like ('S', 'H'), where H = top 30% of var.
    breakpoints="all": 30/70 percentiles over all universe stocks with var;
    breakpoints="positive": over stocks with var > 0 only (negative values then go to L).
    """
    u = panel[panel["in_universe"]].copy()
    u["size_g"] = assign_groups(u, "me", [0.5], labels=["S", "B"])
    mask = u[var].notna() if breakpoints == "all" else u[var] > 0
    u["var_g"] = assign_groups(u, var, [0.3, 0.7], breakpoint_mask=mask, labels=["L", "M", "H"])
    if negative_as_low:
        u.loc[u[var] <= 0, "var_g"] = "L"
    return weighted_returns(u, ["size_g", "var_g"], ret="ret", weight="me")


def ch3(panel: pd.DataFrame, *, ep_breakpoints: str = "all") -> pd.DataFrame:
    """Monthly CH-3 factors (decimal returns): mkt (excess), smb, vmg, plus rf and mkt_raw."""
    p = _two_by_three(panel, "ep", negative_as_low=True, breakpoints=ep_breakpoints)
    smb = p[[("S", g) for g in "LMH"]].mean(axis=1) - p[[("B", g) for g in "LMH"]].mean(axis=1)
    vmg = p[[("S", "H"), ("B", "H")]].mean(axis=1) - p[[("S", "L"), ("B", "L")]].mean(axis=1)
    u = panel[panel["in_universe"]].assign(g=1)
    mkt_raw = weighted_returns(u, ["g"], ret="ret", weight="me")[1]
    rf = risk_free_monthly().reindex(mkt_raw.index)
    return pd.DataFrame({"mkt": mkt_raw - rf, "smb": smb, "vmg": vmg, "rf": rf, "mkt_raw": mkt_raw})


def ch4(panel: pd.DataFrame, *, ep_breakpoints: str = "all") -> pd.DataFrame:
    """Monthly CH-4 factors: mkt, smb (average of EP- and turnover-neutral SMB), vmg, pmo."""
    f3 = ch3(panel, ep_breakpoints=ep_breakpoints)
    p = _two_by_three(panel, "abn_turn", negative_as_low=False, breakpoints="all")
    smb_turn = p[[("S", g) for g in "LMH"]].mean(axis=1) - p[[("B", g) for g in "LMH"]].mean(axis=1)
    pmo = p[[("S", "L"), ("B", "L")]].mean(axis=1) - p[[("S", "H"), ("B", "H")]].mean(axis=1)
    return pd.DataFrame({"mkt": f3["mkt"], "smb": (f3["smb"] + smb_turn) / 2, "vmg": f3["vmg"],
                         "pmo": pmo, "rf": f3["rf"]})


def stambaugh_monthly() -> pd.DataFrame:
    """Stambaugh's published monthly CH-4 series (2000-01..2021-12), decimal."""
    from csmar.registry import RAW_EXTERNAL
    f = pd.read_csv(RAW_EXTERNAL / "stambaugh" / "CH_4_fac_update_20211231.csv", skiprows=9)
    f["month"] = pd.PeriodIndex(f["mnthdt"].astype(str).str.slice(0, 6), freq="M")
    out = f.set_index("month")[["rf_mon", "mktrf", "SMB", "VMG", "PMO"]] / 100
    return out.rename(columns={"rf_mon": "rf", "mktrf": "mkt", "SMB": "smb", "VMG": "vmg", "PMO": "pmo"})


def stambaugh_ch3_monthly() -> pd.DataFrame:
    """Stambaugh's CH-3 is published daily only; monthly = compounded daily returns.
    Excess market: compound (mktrf + rf) and subtract compounded rf."""
    from csmar.registry import RAW_EXTERNAL
    f = pd.read_csv(RAW_EXTERNAL / "stambaugh" / "CH_3_fac_daily_update_20211231.csv", skiprows=8)
    f.columns = [c.strip() for c in f.columns]
    f["month"] = pd.PeriodIndex(pd.to_datetime(f["date"].astype(str)).dt.to_period("M"), freq="M")
    x = f.set_index("month").drop(columns="date") / 100
    comp = lambda s: np.expm1(np.log1p(s).groupby(level=0).sum())
    rf = comp(x["rf_dly"])
    mkt = comp(x["mktrf"] + x["rf_dly"]) - rf
    out = pd.DataFrame({"rf": rf, "mkt": mkt, "smb": comp(x["SMB"]), "vmg": comp(x["VMG"])})
    return out


def ff3(panel: pd.DataFrame) -> pd.DataFrame:
    """FF-3 built on the same universe (section 5.3): 2x3 on size (median) and BM (30/40/30),
    FFSMB = mean(S/H, S/M, S/L) - mean(B/H, B/M, B/L), FFHML = mean(S/H, B/H) - mean(S/L, B/L).
    Following Fama and French (1993), firms with non-positive book equity are left out of the
    BM sort (and so of the six portfolios). MKT is CH-3's."""
    q = panel.assign(bm_pos=panel["bm"].where(panel["bm"] > 0))
    p = _two_by_three(q, "bm_pos", negative_as_low=False, breakpoints="all")
    smb = p[[("S", g) for g in "LMH"]].mean(axis=1) - p[[("B", g) for g in "LMH"]].mean(axis=1)
    hml = p[[("S", "H"), ("B", "H")]].mean(axis=1) - p[[("S", "L"), ("B", "L")]].mean(axis=1)
    f3 = ch3(panel)
    return pd.DataFrame({"mkt": f3["mkt"], "smb": smb, "hml": hml, "rf": f3["rf"]})


def with_shells(panel: pd.DataFrame) -> pd.DataFrame:
    """The panel with the shell cut switched off: every eligible stock is in the universe
    (section 5.2, 'Including shell stocks')."""
    return panel.assign(in_universe=panel["eligible"])


def ff5(panel: pd.DataFrame) -> pd.DataFrame:
    """FF-5 on the same universe, for the section 5.3 text comparison (details in LSY's
    Appendix A.7, following Guo et al. 2017): 2x3 sorts of size with BM, operating
    profitability and investment. Profitability = annual operating profitability
    (Fama and French 2015); investment = annual asset growth. SMB averages the three size
    spreads; RMW = robust - weak; CMA = conservative (low growth) - aggressive. Firms with
    non-positive book equity are left out of the BM and profitability sorts.
    An ROE-based RMW (built from the same single-quarter earnings as VMG) was tried first and
    reversed the paper's FF-5 conclusion (deviation_log LSY-9); operating profitability
    reproduces both printed conclusions."""
    q = panel.assign(bm_pos=panel["bm"].where(panel["bm"] > 0))
    out, smbs = {}, []
    for name, var in (("hml", "bm_pos"), ("rmw", "op"), ("cma", "asset_growth")):
        p = _two_by_three(q, var, negative_as_low=False, breakpoints="all")
        smbs.append(p[[("S", g) for g in "LMH"]].mean(axis=1) - p[[("B", g) for g in "LMH"]].mean(axis=1))
        hi = p[[("S", "H"), ("B", "H")]].mean(axis=1)
        lo = p[[("S", "L"), ("B", "L")]].mean(axis=1)
        out[name] = (lo - hi) if name == "cma" else (hi - lo)
    f3 = ch3(panel)
    return pd.DataFrame({"mkt": f3["mkt"], "smb": sum(smbs) / 3, **out, "rf": f3["rf"]})
