"""Allen, Qian, Shan & Zhu (2024, JF): A-share annual firm panel (lighthouse.md 5.2).

The paper's A-share data are WIND/CSMAR (governance, RPT, ownership) and the Chinese Capital
Market Research Group (returns); ours are CSMAR throughout. Definitions follow the paper's
Appendix A and, where the text is silent, the authors' SAS replication code
(data/raw/external/allen_jf_code): the code fixes the regression controls, weights and
clustering, but its input datasets are not public, so variable construction from raw CSMAR
items is ours and is documented field by field below.

One row per (stock, fiscal year) for A shares (markettypes 1, 4, 16, 32, 64) listed at any
time in the year. All flows are annual-report (Typrep A, period-end rows, original values).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from csmar.panels import A_SHARE_MARKETTYPES, company_info, load, parse_csmar_date
from csmar.readers import read_raw
from csmar.registry import RAW_EXTERNAL

# Actual-controller nature codes (HLD_Contrshr.S0702b) counted as state ownership: state-
# owned enterprises (1100), government agencies (2000), central SASAC / Ministry of Finance
# (2100) and local SASACs (2120). Allen et al.: firms "ultimately controlled by the central
# SASAC, Ministry of Finance, local SASACs, or other government agents".
SOE_CODES = {"1100", "2000", "2100", "2120"}

# Shareholder-nature strings (HLD_Shareholders.S0305a) treated as state holdings.
STATE_SHARE_PATTERN = r"国家股|国有法人股|国有股"


def fx_cny_per_usd() -> pd.Series:
    """Annual average CNY per USD (FRED AEXCHUS), by year; 2026 from the monthly series."""
    a = pd.read_csv(RAW_EXTERNAL / "fred" / "AEXCHUS.csv")
    s = pd.Series(a["AEXCHUS"].astype(float).to_numpy(), index=pd.to_datetime(a["observation_date"]).dt.year)
    m = pd.read_csv(RAW_EXTERNAL / "fred" / "EXCHUS.csv")
    m["y"] = pd.to_datetime(m["observation_date"]).dt.year
    monthly = m.groupby("y")["EXCHUS"].mean()
    return s.combine_first(monthly).rename("cny_per_usd")


def soe_flags() -> pd.DataFrame:
    """SOE indicator per (stock, fiscal year) from the actual-controller nature at year end.
    The controller file starts in 2003; earlier years are left missing (deviation_log ALN-1)."""
    h = read_raw("HLD_Contrshr", columns=["Stkcd", "Reptdt", "S0702b"])
    out = pd.DataFrame({"stkcd": h["Stkcd"], "fy": pd.to_datetime(h["Reptdt"]).dt.year,
                        "nature": h["S0702b"].astype("string")})
    out = out.drop_duplicates(["stkcd", "fy"], keep="last")
    out["soe"] = out["nature"].isin(SOE_CODES).astype(float).where(out["nature"].notna())
    return out[["stkcd", "fy", "soe"]]


def listed_years() -> pd.DataFrame:
    """(stock, year) pairs for A shares listed at any time in the year: first traded month <=
    year <= last traded month (same definition as the data-layer Table I check, D-006)."""
    m = load("stock_month")
    a = m[m["markettype"].isin(A_SHARE_MARKETTYPES)]
    span = a.groupby("stkcd")["month"].agg(["min", "max"])
    rows = [(s, y) for s, (lo, hi) in span.iterrows() for y in range(lo.year, hi.year + 1)]
    return pd.DataFrame(rows, columns=["stkcd", "fy"])


def accounting() -> pd.DataFrame:
    """Annual accounting variables (CSMAR codes in brackets), all in RMB:
    - at: total assets [A001000000]; be: parent equity [A003100000]; debt: total liabilities
      [A002000000]; revenue [B001101000]; net income [B002000000];
    - ebit: total profit [B001000000] + interest expense [B001211101], falling back to
      financial expenses [B001211000] where interest expense is not reported (before 2018);
    - da: depreciation [D000103000] + amortization of intangibles [D000104000] + of long-term
      deferred expenses [D000105000];
    - capex: cash paid for fixed, intangible and other long-term assets [C002006000];
    - taxes: income tax expense [B002100000];
    - working capital: current assets [A001100000] - current liabilities [A002100000];
    - roa = ebit / at; roe = net income / be;
    - ocf = (ebitda - change in working capital - taxes) / at; ncf = ocf - capex / at
      (Allen Appendix A; Figure 5 note);
    - leverage = debt / at; sales growth; ROIC = (net income + interest x (1 - 25%)) /
      (long-term borrowing [A002201000] + minority interest [A003200000] + be).
    Statements are annual reports (period end 12-31), as originally reported."""
    st = load("statements")
    st = st[st["report_type"] == 4].copy()
    st["fy"] = st["period_end"].dt.year
    g = lambda c: st[c].astype(float)
    z = lambda c: st[c].astype(float).fillna(0.0)
    interest = st["B001211101"].astype(float).fillna(st["B001211000"].astype(float))
    out = pd.DataFrame({
        "stkcd": st["stkcd"], "fy": st["fy"], "announce_date": st["announce_date"],
        "at": g("A001000000"), "be": g("A003100000"), "debt": g("A002000000"),
        "revenue": g("B001101000"), "ni": g("B002000000"),
        "ebit": g("B001000000") + interest.fillna(0.0),
        "da": z("D000103000") + z("D000104000") + z("D000105000"),
        "capex": z("C002006000"), "taxes": z("B002100000"),
        "wc": g("A001100000") - g("A002100000"),
        "lt_borrow": z("A002201000"), "minority": z("A003200000"), "interest": interest.fillna(0.0),
    }).sort_values(["stkcd", "fy"])
    prev = out.groupby("stkcd").shift(1)
    consecutive = (out["fy"] - prev["fy"]).eq(1)
    at = out["at"].where(out["at"] > 0)
    out["roa"] = out["ebit"] / at
    out["roe"] = out["ni"] / out["be"].where(out["be"] > 0)
    out["d_wc"] = (out["wc"] - prev["wc"]).where(consecutive)
    out["ocf"] = (out["ebit"] + out["da"] - out["d_wc"] - out["taxes"]) / at
    out["capx"] = out["capex"] / at
    out["ncf"] = out["ocf"] - out["capx"]
    out["leverage"] = out["debt"] / at
    out["sales_growth"] = ((out["revenue"] - prev["revenue"]) / prev["revenue"].where(prev["revenue"] > 0)).where(consecutive)
    out["ni_growth"] = ((out["ni"] - prev["ni"]) / prev["ni"].abs().where(prev["ni"].abs() > 0)).where(consecutive)
    out["roic"] = (out["ni"] + out["interest"] * 0.75) / (out["lt_borrow"] + out["minority"] + out["be"]).where(
        lambda x: x > 0)
    return out.drop(columns=["wc", "lt_borrow", "minority", "interest"])


RPT_GOODS_LIKE = [1, 2, 3, 7, 13, 15]  # goods, assets, services, leases, equity, debt (Repat codes)


def rpt_flows(definition: str = "cash_by_category") -> pd.DataFrame:
    """Related-party cash flows per (stock, fiscal year) from RPT_Operation (annual reports,
    transactions between the listed firm and a related party), RMB.

    definition="funds": only funds transactions (Repat 05 资金交易); providing funds
      (Direction 1) is an outflow, receiving (Direction 2) an inflow. This is the literal
      "loan-based RPT" reading.
    definition="cash_by_category" (default): every cash-settled category. Buying goods,
      assets, services, leases, equity or debt (Direction 2) and lending funds (Repat 05,
      Direction 1) are outflows; the opposite positions are inflows.
    The choice is an empirical one (deviation_log ALN-3): the funds-only measure has a
    standard deviation of 0.05 of assets against Table VIII's 0.117; the cash-by-category
    measure gives 0.127 and a range close to the printed -0.475..0.524."""
    rp = read_raw("RPT_Operation", columns=["Stkcd", "Reptdt", "Repttype", "Trasub", "Direction", "Repat", "Isam"])
    rp = pd.DataFrame({"stkcd": rp["Stkcd"], "fy": pd.to_datetime(rp["Reptdt"]).dt.year,
                       "rt": pd.to_numeric(rp["Repttype"], errors="coerce"), "sub": pd.to_numeric(rp["Trasub"], errors="coerce"),
                       "dir": pd.to_numeric(rp["Direction"], errors="coerce"), "cat": pd.to_numeric(rp["Repat"], errors="coerce"),
                       "amt": pd.to_numeric(rp["Isam"], errors="coerce").fillna(0.0)})
    rp = rp[(rp["rt"] == 1) & (rp["sub"] == 1)]
    funds = rp["cat"] == 5
    if definition == "funds":
        out = np.where(funds & (rp["dir"] == 1), rp["amt"], 0.0)
        inn = np.where(funds & (rp["dir"] == 2), rp["amt"], 0.0)
    elif definition == "cash_by_category":
        goods = rp["cat"].isin(RPT_GOODS_LIKE)
        out = np.where((goods & (rp["dir"] == 2)) | (funds & (rp["dir"] == 1)), rp["amt"], 0.0)
        inn = np.where((goods & (rp["dir"] == 1)) | (funds & (rp["dir"] == 2)), rp["amt"], 0.0)
    else:
        raise ValueError(definition)
    rp = rp.assign(rpt_out=out, rpt_in=inn)
    return rp.groupby(["stkcd", "fy"])[["rpt_out", "rpt_in"]].sum().reset_index()


def governance(rpt_definition: str = "cash_by_category") -> pd.DataFrame:
    """G-Index components per (stock, fiscal year), year-end values:
    - ceo_duality: chairman and general manager are the same person [CG_Ybasic.Y1001b = 1];
    - board_size: directors, supervisors and senior managers in office at year end
      [CG_ManagerShareSalary.TotalNumber, caliber 1]. Directors alone (DirectorNumber,
      median 9) cannot produce Table VIII's mean 16.8 / max 54; the full governance team
      does (deviation_log ALN-2);
    - exec_holdings: shares held by directors, supervisors and senior managers
      [CG_ManagerShareSalary.Holdshares] / total shares [TRD_Capchg.Nshrttl];
    - top5: holdings of the five largest shareholders [HLD_CR.Shrcr3] / 100;
    - state_holdings: sum of top-10 holdings whose share nature is state (国家股/国有法人股)
      [HLD_Shareholders] / 100;
    - rpt_out, rpt_in: related-party cash outflows / inflows in the year (rpt_flows())."""
    cg = read_raw("CG_Ybasic", columns=["Stkcd", "Reptdt", "Y1001b"])
    cg = pd.DataFrame({"stkcd": cg["Stkcd"], "fy": parse_csmar_date(cg["Reptdt"]).dt.year,
                       "ceo_duality": (pd.to_numeric(cg["Y1001b"], errors="coerce") == 1).astype(float)
                       .where(pd.to_numeric(cg["Y1001b"], errors="coerce").notna())}).dropna(subset=["fy"])
    cg = cg.drop_duplicates(["stkcd", "fy"], keep="last")
    ms = read_raw("CG_ManagerShareSalary", columns=["Symbol", "Enddate", "StatisticalCaliber", "TotalNumber", "Holdshares"])
    ms = ms[pd.to_numeric(ms["StatisticalCaliber"], errors="coerce") == 1]
    ms = pd.DataFrame({"stkcd": ms["Symbol"].astype("string").str.zfill(6), "fy": pd.to_datetime(ms["Enddate"]).dt.year,
                       "board_size": pd.to_numeric(ms["TotalNumber"], errors="coerce"),
                       "exec_shares": pd.to_numeric(ms["Holdshares"], errors="coerce")}).drop_duplicates(["stkcd", "fy"])
    cap = read_raw("TRD_Capchg", columns=["Stkcd", "Shrchgdt", "Nshrttl"])
    cap = pd.DataFrame({"stkcd": cap["Stkcd"], "date": parse_csmar_date(cap["Shrchgdt"]),
                        "total_shares": pd.to_numeric(cap["Nshrttl"], errors="coerce")}).dropna().sort_values("date")
    ye = ms[["stkcd", "fy"]].assign(date=pd.to_datetime(ms["fy"].astype(str) + "-12-31")).sort_values("date")
    ye = pd.merge_asof(ye, cap, on="date", by="stkcd", direction="backward")
    ms = ms.merge(ye[["stkcd", "fy", "total_shares"]], on=["stkcd", "fy"], how="left")
    ms["exec_holdings"] = (ms["exec_shares"].fillna(0) / ms["total_shares"]).clip(upper=1)
    cr = read_raw("HLD_CR", columns=["Stkcd", "Reptdt", "Shrcr3"])
    cr = pd.DataFrame({"stkcd": cr["Stkcd"], "fy": pd.to_datetime(cr["Reptdt"]).dt.year,
                       "top5": pd.to_numeric(cr["Shrcr3"], errors="coerce") / 100}).drop_duplicates(["stkcd", "fy"], keep="last")
    sh = read_raw("HLD_Shareholders", columns=["Stkcd", "Reptdt", "S0304a", "S0305a"])
    sh = pd.DataFrame({"stkcd": sh["Stkcd"], "date": pd.to_datetime(sh["Reptdt"]),
                       "pct": pd.to_numeric(sh["S0304a"], errors="coerce"),
                       "state": sh["S0305a"].astype("string").str.contains(STATE_SHARE_PATTERN, regex=True).fillna(False)})
    sh = sh[sh["date"].dt.strftime("%m-%d") == "12-31"]
    sh["fy"] = sh["date"].dt.year
    st_h = (sh["pct"].where(sh["state"], 0.0).groupby([sh["stkcd"], sh["fy"]]).sum() / 100).rename("state_holdings").reset_index()
    flows = rpt_flows(rpt_definition)
    g = cg.merge(ms[["stkcd", "fy", "board_size", "exec_holdings", "total_shares"]], on=["stkcd", "fy"], how="outer")
    g = g.merge(cr, on=["stkcd", "fy"], how="outer").merge(st_h, on=["stkcd", "fy"], how="outer")
    g = g.merge(flows[["stkcd", "fy", "rpt_out", "rpt_in"]], on=["stkcd", "fy"], how="left")
    # A firm-year with no loan-type RPT record has zero RPT flows (Allen's code: "we define zero
    # to this variable if the firm does not conduct an RPT according to CSMAR").
    g[["rpt_out", "rpt_in"]] = g[["rpt_out", "rpt_in"]].fillna(0.0)
    # Loan-type outflow alone (Repat 05, providing funds), for Table XIII's "RPT Amt Out":
    # the text describes it as "cash outflows from loan-based transactions".
    loans = rpt_flows("funds").rename(columns={"rpt_out": "rpt_loan_flow_out"})[["stkcd", "fy", "rpt_loan_flow_out"]]
    g = g.merge(loans, on=["stkcd", "fy"], how="left")
    g["rpt_loan_flow_out"] = g["rpt_loan_flow_out"].fillna(0.0)
    # State holdings: zero when the top-10 shareholder list for the year has no state holder;
    # missing when there is no shareholder list at all (CSMAR's list starts in 2003).
    covered = pd.MultiIndex.from_frame(sh[["stkcd", "fy"]].drop_duplicates())
    has_list = pd.MultiIndex.from_frame(g[["stkcd", "fy"]]).isin(covered)
    g["state_holdings"] = np.where(has_list, g["state_holdings"].fillna(0.0), np.nan)
    return g


def g_indices(panel: pd.DataFrame) -> pd.DataFrame:
    """G-Index-A (0-6) and G-Index-I (0-7) with year-specific percentiles (Table VIII):
    G-Index-A adds one for each of: CEO duality; state holdings < 40%; executive holdings
    above the year's 70th percentile; board size below the 30th; top-5 holdings above the
    70th; no net RPT cash outflow (rpt_net_out <= 0).
    G-Index-I: CEO duality (0/1) plus 0-2 scores for board size (2 below p30, 1 between, 0
    above p70), ownership concentration and executive holdings (2 above p70, 1 between, 0
    below p30)."""
    p = panel.copy()
    q = lambda c, x: p.groupby("fy")[c].transform(lambda s: s.quantile(x))
    # CEO duality, board size and executive holdings are required. Ownership concentration and
    # state holdings come from shareholder lists that start in 2003; where they are missing
    # the index is the sum of the remaining components (lighthouse 5.2: "该成分缺失时用其余
    # 成分计算并记录"; deviation_log ALN-2).
    ok = p[["ceo_duality", "board_size", "exec_holdings"]].notna().all(axis=1)
    comp = lambda cond, col: np.where(p[col].notna(), cond.astype(float), 0.0)
    p["g_index_a"] = pd.Series(p["ceo_duality"] + comp(p["state_holdings"] < 0.4, "state_holdings")
                               + (p["exec_holdings"] > q("exec_holdings", 0.7)) + (p["board_size"] < q("board_size", 0.3))
                               + comp(p["top5"] > q("top5", 0.7), "top5") + (p["rpt_net_out"] <= 0), index=p.index).where(ok)

    def three(c, high_is_good):
        # "larger than the 70th percentile" = 2, "between" = 1, "smaller than the 30th" = 0
        # (reversed for board size). A value equal to a percentile is not "larger" or
        # "smaller" than it, so ties fall in the middle band; but a variable with a mass
        # point at zero (executive holdings) has p30 = 0, and zero holdings then count as
        # "between" unless "between" is read strictly. Strict reading used: lo < x <= hi.
        lo, hi = q(c, 0.3), q(c, 0.7)
        if high_is_good:
            return np.where(p[c] > hi, 2, np.where(p[c] > lo, 1, 0))
        return np.where(p[c] < lo, 2, np.where(p[c] < hi, 1, 0))

    p["g_index_i"] = (p["ceo_duality"] + three("board_size", False) + np.where(p["top5"].notna(), three("top5", True), 0)
                      + three("exec_holdings", True)).where(ok)
    return p


def annual_returns() -> pd.DataFrame:
    """Annual returns per (stock, year): compounded monthly dividend-reinvested returns
    (CSMAR leaves the IPO month blank, so an IPO year starts after the listing month, which is
    close to Allen's "closing price on the first trading day" base), the real return deflated
    by the December-to-December CPI change, return volatility (std of monthly returns), and
    year-end market values and turnover (annual shares traded / year-end total A shares;
    Appendix A: "trading volume divided by the number of shares", Table IX)."""
    m = load("stock_month")
    m = m[m["markettype"].isin(A_SHARE_MARKETTYPES)].copy()
    m["fy"] = m["month"].dt.year
    m["lr"] = np.log1p(m["ret"])
    g = m.groupby(["stkcd", "fy"])
    cpi = load("cpi").set_index("month")["cpi"]
    dec = cpi[cpi.index.month == 12]
    infl = (dec / dec.shift(1) - 1)
    infl.index = infl.index.year
    last = g.tail(1).set_index(["stkcd", "fy"])
    out = pd.DataFrame({
        "ret": np.expm1(g["lr"].sum(min_count=1)),
        "n_months": g["ret"].count(),
        "std_ret": g["ret"].std() * np.sqrt(12),
        "volume": g["volume"].sum(),
        "mv_total_ye": last["mv_total"], "mv_float_ye": last["mv_float"], "close_ye": last["close"],
    }).reset_index()
    out["infl"] = out["fy"].map(infl)
    out["ret_real"] = (1 + out["ret"]) / (1 + out["infl"]) - 1
    out["turnover_year"] = out["volume"] / (out["mv_total_ye"] / out["close_ye"])
    return out


def st_events() -> pd.DataFrame:
    """ST history per stock (SPT_Trdchg): first date the stock entered ST or *ST (change
    type ending in B or D), and whether it is still ST, *ST or PT at a given cut-off."""
    s = read_raw("SPT_Trdchg", columns=["Stkcd", "Chgtype", "Execudt"])
    s = pd.DataFrame({"stkcd": s["Stkcd"], "type": s["Chgtype"].astype("string"),
                      "date": parse_csmar_date(s["Execudt"])}).dropna(subset=["date"]).sort_values("date")
    return s


def delistings() -> pd.DataFrame:
    """Terminations of listing (SPT_LTDSTACHG, status after = 终止上市) with reason codes."""
    l = read_raw("SPT_LTDSTACHG", columns=["Stkcd", "Execudt", "Stkstatac", "Chgreas", "Chgrsdis"])
    l = l[l["Stkstatac"] == "终止上市"]
    return pd.DataFrame({"stkcd": l["Stkcd"], "date": parse_csmar_date(l["Execudt"]),
                         "reason": l["Chgreas"].astype("string"), "reason_text": l["Chgrsdis"]})


# Board size is a count with natural bounds and is not winsorized (Table VIII prints min 1, max 54).
WINSORIZED = ["at", "at_usd_bn", "roa", "roe", "ocf", "ncf", "capx", "leverage", "sales_growth", "ni_growth", "roic",
              "exec_holdings", "top5", "state_holdings", "rpt_net_out", "rpt_amt_out", "rpt_loan_out", "turnover_year",
              "ret", "ret_real", "std_ret", "mb"]


def winsorize(p: pd.DataFrame, cols: list[str], lower: float = 0.01, upper: float = 0.99) -> pd.DataFrame:
    """Pooled 1%/99% winsorization, as in Allen et al. ("All the datasets have been winsorized",
    code readme; Table I note on total assets). Applied after the G-indices are formed, so the
    percentile scores use raw values."""
    p = p.copy()
    for c in cols:
        lo, hi = p[c].quantile([lower, upper])
        p[c] = p[c].clip(lo, hi)
    return p


def build_panel(rpt_definition: str = "cash_by_category") -> pd.DataFrame:
    """The Allen annual A-share panel: listing years x accounting x governance x returns."""
    base = listed_years()
    acc = accounting()
    p = base.merge(acc, on=["stkcd", "fy"], how="left")
    p = p.merge(governance(rpt_definition), on=["stkcd", "fy"], how="left")
    p["rpt_net_out"] = (p["rpt_out"] - p["rpt_in"]) / p["at"].where(p["at"] > 0)
    p["rpt_amt_out"] = p["rpt_out"] / p["at"].where(p["at"] > 0)
    p["rpt_loan_out"] = p["rpt_loan_flow_out"] / p["at"].where(p["at"] > 0)
    p = g_indices(p)
    p = p.merge(soe_flags(), on=["stkcd", "fy"], how="left")
    p = p.merge(annual_returns(), on=["stkcd", "fy"], how="left")
    ci = company_info().set_index("stkcd")
    co = read_raw("TRD_Co", columns=["Stkcd", "Estbdt", "PROVINCE", "Commnt"]).set_index("Stkcd")
    p["list_date"] = p["stkcd"].map(ci["list_date"])
    p["industry"] = p["stkcd"].map(ci["csrc2012"]).str.slice(0, 3)
    p["province"] = p["stkcd"].map(co["PROVINCE"])
    p["cross_listed_h"] = p["stkcd"].map(co["Commnt"].notna()).astype(float)
    est = parse_csmar_date(co["Estbdt"])
    p["firm_age"] = p["fy"] - p["stkcd"].map(est).dt.year
    fx = fx_cny_per_usd()
    p["at_usd_bn"] = p["at"] / p["fy"].map(fx) / 1e9
    p["mb"] = p["mv_total_ye"] / p["be"].where(p["be"] > 0)
    p = winsorize(p, WINSORIZED)
    p = p.sort_values(["stkcd", "fy"])
    lag = p.groupby("stkcd").shift(1)
    consecutive = (p["fy"] - lag["fy"]).eq(1)
    p["mcap_lag"] = lag["mv_total_ye"].where(consecutive)
    p["mcap_lag_usd"] = p["mcap_lag"] / p["fy"].sub(1).map(fx)
    for c in ("g_index_a", "turnover_year", "at", "leverage", "roa", "sales_growth", "firm_age", "std_ret", "mb",
              "soe", "mv_total_ye"):
        p[f"{c}_lag"] = lag[c].where(consecutive)
    p["size_lag"] = np.log(p["at_lag"].where(p["at_lag"] > 0))
    p["log_firm_age_lag"] = np.log1p(p["firm_age_lag"].clip(lower=0))
    p["log_mcap_lag_usd"] = np.log(p["mcap_lag_usd"].where(p["mcap_lag_usd"] > 0))
    return p.reset_index(drop=True)
