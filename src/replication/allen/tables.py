"""Allen et al. (2024) A-share tables and figures (lighthouse.md 5.2). Each function takes a
Segment and returns tidy rows (table, segment, row, col, value), like replication.lsy.tables.

Segments: the paper's firm-level sample is 2000-2018 (annual). Extended = 2019-2025 and full =
2000-2025: annual statements are complete through fiscal 2025 (2026 only has a half year).
Monthly figures use the same calendar span.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from csmar.panels import load
from csmar.registry import INTERIM
from replication.allen import data as D
from replication.common.periods import Segment, segments
from replication.common.stats import panel_regression

PAPER_START, PAPER_END = "2000-01", "2018-12"
LAST_FULL_YEAR = pd.Period("2025-12", "M")
PANEL_CACHE = INTERIM / "allen_panel.parquet"
SOE_FIRST_YEAR = 2003  # first year of CSMAR's actual-controller file (HLD_Contrshr)


def allen_segments() -> dict[str, Segment]:
    return segments(PAPER_START, PAPER_END, data_end=LAST_FULL_YEAR)


@lru_cache(maxsize=1)
def panel(rebuild: bool = False) -> pd.DataFrame:
    if PANEL_CACHE.exists() and not rebuild:
        return pd.read_parquet(PANEL_CACHE)
    p = D.build_panel()
    PANEL_CACHE.parent.mkdir(parents=True, exist_ok=True)
    p.to_parquet(PANEL_CACHE, index=False)
    return p


def _years(seg: Segment) -> range:
    return range(seg.start.year, seg.end.year + 1)


def _rows(table: str, seg: Segment, items) -> pd.DataFrame:
    return pd.DataFrame([{"table": table, "segment": seg.name, "start": str(seg.start), "end": str(seg.end),
                          "row": r, "col": c, "value": v} for r, c, v in items])


def _in(seg: Segment) -> pd.DataFrame:
    """The segment's firm-years, winsorized at 1%/99% with the segment's own percentiles (levels
    and their one-year lags), so no number depends on years outside the segment."""
    p = panel()
    x = p[p["fy"].isin(_years(seg))].copy()
    cols = [c for c in D.WINSORIZED if c in x] + [f"{c}_lag" for c in D.WINSORIZED if f"{c}_lag" in x]
    x = D.winsorize(x, cols)
    return D.winsorize(x, [c for c in D.WINSORIZED_5_95 if c in x], 0.05, 0.95)


# ---------------------------------------------------------------------------------------------
# Table I (A-share columns)
# ---------------------------------------------------------------------------------------------

def table1(seg: Segment) -> pd.DataFrame:
    """Table I Panel A, A-share columns: listed firms, SOEs, average total assets ($ billion,
    winsorized), by year, plus the unique-firm row."""
    x = _in(seg)
    items = []
    for y, g in x.groupby("fy"):
        # SOE flags exist from 2003 (controller file); the few earlier rows are not a count.
        soe = float(g["soe"].sum()) if y >= SOE_FIRST_YEAR else np.nan
        items += [(str(y), "listed_firms", float(len(g))), (str(y), "soe_firms", soe),
                  (str(y), "avg_assets_usd_bn", float(g["at_usd_bn"].mean()))]
    items += [("unique", "listed_firms", float(x["stkcd"].nunique())),
              ("unique", "soe_firms", float(x.loc[x["soe"] == 1, "stkcd"].nunique())),
              ("unique", "avg_assets_usd_bn", float(x["at_usd_bn"].mean()))]
    return _rows("TI", seg, items)


# ---------------------------------------------------------------------------------------------
# Figures 1, 2 (monthly buy-and-hold real returns), 4 (ST firms' ROA), 5 (investment, NCF)
# ---------------------------------------------------------------------------------------------

def monthly_real_returns() -> pd.DataFrame:
    """Monthly A-share returns in real terms with size groups (Figures 1-2).
    - weight: total market value at the end of the previous calendar year (Allen: "lagged
      one-year market capitalization");
    - size groups: 30th/70th percentiles of that lagged value, by year;
    - real return: (1 + r) / (1 + monthly CPI inflation) - 1;
    - returns are winsorized at 1%/99% within the figure segment, in bhr()."""
    m = load("stock_month")
    m = m[m["is_a_share"] & m["ret"].notna()][["stkcd", "month", "ret", "mv_total"]].copy()
    m["year"] = m["month"].dt.year
    ye = load("stock_month")
    ye = ye[ye["is_a_share"] & (ye["month"].dt.month == 12)][["stkcd", "month", "mv_total"]]
    ye = ye.assign(year=ye["month"].dt.year + 1).rename(columns={"mv_total": "w"})[["stkcd", "year", "w"]]
    m = m.merge(ye, on=["stkcd", "year"], how="inner")
    cpi = load("cpi").set_index("month")["cpi"]
    infl = cpi / cpi.shift(1) - 1
    m["infl"] = m["month"].map(infl)
    m["ret_real_raw"] = (1 + m["ret"]) / (1 + m["infl"]) - 1
    q = m.groupby("year")["w"].quantile([0.3, 0.7]).unstack()
    m["size"] = np.where(m["w"] <= m["year"].map(q[0.3]), "small", np.where(m["w"] <= m["year"].map(q[0.7]), "medium", "large"))
    return m.dropna(subset=["ret_real_raw"])


FIGURE_START = pd.Period("2000-12", "M")   # lighthouse 3.1: Figures 1-2 monthly 2000-12..2018-12
FIGURE_LAST = pd.Period("2026-08", "M")    # latest month with CPI (lighthouse 6)


def figure_segment(seg: Segment) -> Segment:
    """Monthly span of Figures 1-2 for a segment: value 1 at the end of the start month, then
    compounding. original 2000-12..2018-12; extended 2018-12..2026-08; full 2000-12..2026-08."""
    if seg.name == "original":
        return Segment(seg.name, FIGURE_START, pd.Period("2018-12", "M"))
    if seg.name == "extended":
        return Segment(seg.name, pd.Period("2018-12", "M"), FIGURE_LAST)
    return Segment(seg.name, FIGURE_START, FIGURE_LAST)


def bhr(seg: Segment) -> pd.DataFrame:
    """Cumulative real value of RMB 1 invested at the end of the figure segment's start month:
    all A shares and the three size groups (value-weighted)."""
    m = monthly_real_returns()
    fseg = figure_segment(seg)
    m = m[(m["month"] > fseg.start) & (m["month"] <= fseg.end)].copy()
    lo, hi = m["ret"].quantile([0.01, 0.99])  # winsorized within the segment (SAS Figures 1-2)
    m["ret_real"] = (1 + m["ret"].clip(lo, hi)) / (1 + m["infl"]) - 1
    vw = lambda d: (d["ret_real"] * d["w"]).groupby(d["month"]).sum() / d["w"].groupby(d["month"]).sum()
    out = pd.DataFrame({"all": vw(m), **{g: vw(m[m["size"] == g]) for g in ("small", "medium", "large")}})
    b = (1 + out).cumprod()
    start_row = pd.DataFrame(1.0, index=pd.PeriodIndex([fseg.start], freq="M"), columns=b.columns)
    return pd.concat([start_row, b])


def figures12(seg: Segment) -> pd.DataFrame:
    b = bhr(seg)
    last = b.iloc[-1]
    return _rows("F1-2", seg, [("BHR_end", c, float(last[c])) for c in b.columns])


def figure4(seg: Segment) -> pd.DataFrame:
    """Figure 4 (A-share part): ROA of permanent ST firms in years -5..0 relative to the first
    ST year, weighted by lagged total assets. Permanent ST = still ST/*ST/PT at the end of
    the segment; first ST in the segment. Also returns the ST counts of section III.A.2."""
    ev = D.st_events()
    ev = ev[ev["stkcd"].str[0].isin(["0", "3", "6", "4", "8"])]  # A shares only (no 2xxxxx / 9xxxxx B shares)
    end = seg.end.to_timestamp(how="end")
    start = seg.start.to_timestamp()
    ev = ev[ev["date"] <= end]
    into_st = ev[ev["type"].str[-1].isin(["B", "D", "C"])]
    first = into_st.groupby("stkcd")["date"].min()
    first = first[(first >= start)]
    # Permanent ST: "ST status continues to apply through the end of our sample period" =
    # still ST, *ST or PT at the segment end (the stricter "never re-emerged in between" gives
    # 43 firms vs the printed 65; with footnote 21's requirement of financial data for the five
    # years before the first designation this rule gives 78; deviation_log ALN-7).
    last_type = ev.groupby("stkcd")["type"].last()
    acc_years = D.accounting().dropna(subset=["roa"]).groupby("stkcd")["fy"].apply(set)
    five = lambda s: s in acc_years.index and all((first[s].year - k) in acc_years[s] for k in range(1, 6))
    perm = [s for s in first.index if last_type.get(s, "")[-1:] in ("B", "D", "C") and five(s)]
    p = panel()
    p = p.assign(at_lag=p["at_lag"])
    items = [("ST", "firms_first_st_in_period", float(len(first))), ("ST", "permanent_st_firms", float(len(perm)))]
    rel = p[p["stkcd"].isin(perm)].copy()
    rel["event_year"] = rel["fy"] - rel["stkcd"].map(first.dt.year)
    for k in range(-5, 1):
        g = rel[(rel["event_year"] == k)].dropna(subset=["roa", "at_lag"])
        val = np.average(g["roa"], weights=g["at_lag"]) if len(g) and g["at_lag"].sum() > 0 else np.nan
        items.append((f"year{k}", "roa_weighted", float(val)))
        items.append((f"year{k}", "n", float(len(g))))
    return _rows("F4", seg, items)


def figure5(seg: Segment) -> pd.DataFrame:
    """Figure 5 (A-share part): total-assets-weighted investment (capex / TA) and net cash
    flows per year, and their averages over the segment (text: 4.4% and 1.5%)."""
    x = _in(seg).dropna(subset=["at"])
    items = []
    inv, ncf = [], []
    for y, g in x.groupby("fy"):
        gi, gn = g.dropna(subset=["capx"]), g.dropna(subset=["ncf"])
        vi = np.average(gi["capx"], weights=gi["at"]) * 100
        vn = np.average(gn["ncf"], weights=gn["at"]) * 100
        inv.append(vi)
        ncf.append(vn)
        items += [(str(y), "investment_pct", vi), (str(y), "ncf_pct", vn)]
    items += [("average", "investment_pct", float(np.mean(inv))), ("average", "ncf_pct", float(np.mean(ncf)))]
    return _rows("F5", seg, items)


def load_listing_status() -> pd.DataFrame:
    from csmar.readers import read_raw
    from csmar.panels import parse_csmar_date
    l = read_raw("SPT_LTDSTACHG", columns=["Stkcd", "Execudt", "Stkstatac"])
    return pd.DataFrame({"stkcd": l["Stkcd"], "date": parse_csmar_date(l["Execudt"]), "status": l["Stkstatac"]})


def section3a2(seg: Segment) -> pd.DataFrame:
    """Section III.A.2: delistings per year (average count and share of listed firms) and the
    share of delistings for poor performance."""
    d = D.delistings()
    d = d[d["stkcd"].str[0].isin(["0", "3", "6", "4", "8"])]  # A shares only
    d = d[(d["date"] >= seg.start.to_timestamp()) & (d["date"] <= seg.end.to_timestamp(how="end"))]
    years = list(_years(seg))
    per_year = d.groupby(d["date"].dt.year).size().reindex(years, fill_value=0)
    listed = _in(seg).groupby("fy").size().reindex(years)
    # Poor performance: CSMAR codes most terminations with the generic reason 10, so the reason
    # code cannot separate poor performance from mergers or privatizations. Rule used: a
    # delisting is for poor performance if the stock was under ST, *ST or PT, or suspended
    # from listing (暂停上市 / 退市整理期), when it was delisted. Mergers and privatizations of
    # normally traded stocks are not.
    ev = D.st_events()
    status_at = []
    for s_, dt in zip(d["stkcd"], d["date"]):
        e = ev[(ev["stkcd"] == s_) & (ev["date"] < dt)]
        status_at.append(e["type"].iloc[-1][-1] if len(e) else "A")
    lst = load_listing_status()
    suspended = [((lst["stkcd"] == s_) & (lst["date"] < dt) & lst["status"].isin(["暂停上市", "退市整理期"])).any()
                 for s_, dt in zip(d["stkcd"], d["date"])]
    poor = pd.Series([st in ("B", "C", "D", "T", "S") or sp for st, sp in zip(status_at, suspended)], index=d.index)
    return _rows("S3A2", seg, [("delistings", "avg_per_year", float(per_year.mean())),
                               ("delistings", "avg_pct_of_listed", float((per_year / listed).mean() * 100)),
                               ("delistings", "share_poor_performance_pct", float(poor.mean() * 100) if len(d) else np.nan)])


# ---------------------------------------------------------------------------------------------
# Tables VIII (Panel B and the A-share row of Panel A), IX (Panel B)
# ---------------------------------------------------------------------------------------------

def _describe(s: pd.Series, w: pd.Series | None = None) -> dict:
    s2 = s.dropna()
    mean = float(np.average(s2, weights=w.loc[s2.index])) if w is not None else float(s2.mean())
    return {"mean": mean, "median": float(s2.median()), "std": float(s2.std()), "max": float(s2.max()), "min": float(s2.min())}


def table8(seg: Segment) -> pd.DataFrame:
    x = _in(seg)
    items = []
    # Panel A, Chinese A-share row: means value-weighted by lagged market cap (SAS: proc means
    # with weight), other statistics unweighted.
    # Panel A: the caption reports a value-weighted G-Index-I (lagged market cap); the
    # component means are equal-weighted (printed ownership concentration 0.539: ours is
    # 0.530 equal-weighted and 0.63 value-weighted; deviation_log ALN-2).
    xa = x.dropna(subset=["mcap_lag_usd"])
    for name, col in (("CEO Duality", "ceo_duality"), ("Ownership Concentration", "top5"),
                      ("Executive Holdings", "exec_holdings"), ("Board Size", "board_size"), ("G-Index-I", "g_index_i")):
        d = _describe(xa[col], xa["mcap_lag_usd"] if col == "g_index_i" else None)
        items += [(f"A:{name}", k, v) for k, v in d.items()]
    for name, col in (("G-Index-A", "g_index_a"), ("State Ownership", "state_holdings"), ("RPT Net Out Amt", "rpt_net_out")):
        d = _describe(x[col])
        items += [(f"B:{name}", k, v) for k, v in d.items()]
    # Comparisons (pooled-variance two-sample t, SAS PROC TTEST's first row)
    q = x.groupby("fy")["mcap_lag"].transform(lambda s: s.quantile(0.3))
    q7 = x.groupby("fy")["mcap_lag"].transform(lambda s: s.quantile(0.7))
    small = x.loc[x["mcap_lag"] <= q, "g_index_a"].dropna()
    large = x.loc[x["mcap_lag"] > q7, "g_index_a"].dropna()
    soe = x.loc[x["soe"] == 1, "g_index_a"].dropna()
    non = x.loc[x["soe"] == 0, "g_index_a"].dropna()
    from scipy import stats as sps
    for label, a, b in (("Small-Large", small, large), ("Non-SOE minus SOE", non, soe)):
        t = sps.ttest_ind(a, b, equal_var=True).statistic
        items += [(f"B:{label}", "first", float(a.mean())), (f"B:{label}", "second", float(b.mean())),
                  (f"B:{label}", "difference", float(a.mean() - b.mean())), (f"B:{label}", "t", float(t))]
    return _rows("TVIII", seg, items)


def table9(seg: Segment) -> pd.DataFrame:
    """Table IX Panel B: stock-level turnover. The market-level AH premium needs H-share
    prices, which NYU's CSMAR subscription does not include (not producible)."""
    x = _in(seg)
    d = _describe(x["turnover_year"])
    return _rows("TIX", seg, [("B:Stock-Level Turnover", k, v) for k, v in d.items()])


# ---------------------------------------------------------------------------------------------
# Tables X (Panel B), XI (Panel C), XIII
# ---------------------------------------------------------------------------------------------

CONTROLS = ["size_lag", "leverage_lag", "roa_lag", "sales_growth_lag", "log_firm_age_lag"]
# Authors' SAS: "cluster Industry1 fyear" with Industry1 the CSRC industry letter; fixed
# effects IndNumeric1-80 are the finer CSRC industries. CLUSTER_MODE is set by the
# deviation_log ALN-4 rounds.
CLUSTER = ["industry_letter", "fy"]
CLUSTER_MODE = "cells"


def _ipo_roa_change(seg: Segment) -> pd.Series:
    """ROA[-1,+1]: ROA in the year after the IPO minus ROA in the year before (CSMAR keeps the
    pre-listing statements disclosed in the prospectus for 1,033 firms). Only IPOs whose year
    +1 lies in the segment; winsorized at 1%/99% over those firms."""
    p = panel()
    acc = D.accounting()[["stkcd", "fy", "roa"]]
    lst = p.drop_duplicates("stkcd").set_index("stkcd")["list_date"].dt.year
    acc["ipo"] = acc["stkcd"].map(lst)
    pre = acc[acc["fy"] == acc["ipo"] - 1].set_index("stkcd")["roa"]
    post = acc[(acc["fy"] == acc["ipo"] + 1) & (acc["fy"] <= seg.end.year)].set_index("stkcd")["roa"]
    d = (post - pre).dropna()
    lo, hi = d.quantile([0.01, 0.99])
    return d.clip(lo, hi)


def _norm(s: pd.Series) -> pd.Series:
    return s / s.std()


def table10(seg: Segment) -> pd.DataFrame:
    """Table X Panel B: WLS of annual real returns (percent) on normalized G-Index-A and
    turnover (both lagged), ROA[-1,+1] and contemporaneous ROIC; controls lagged size,
    leverage, ROA, sales growth, log firm age and return volatility; year, industry and
    province fixed effects; weights = lagged market cap (USD); SEs clustered by industry and
    year (authors' SAS code). Columns (2) and (5) use the AH premium: not producible."""
    x = _in(seg).copy()
    x["y"] = x["ret_real"] * 100
    x["G-Index-A"] = _norm(x["g_index_a_lag"])
    x["Stock-Level Turnover"] = _norm(x["turnover_year_lag"])
    x["ROA [-1, +1]"] = _norm(x["stkcd"].map(_ipo_roa_change(seg)))
    x["ROIC"] = _norm(x["roic"])
    x["std_ret_lag"] = x["std_ret_lag"]
    specs = {"(1)": ["G-Index-A"], "(3)": ["Stock-Level Turnover"], "(4)": ["G-Index-A", "ROA [-1, +1]"],
             "(6)": ["G-Index-A", "Stock-Level Turnover"], "(7)": ["G-Index-A", "Stock-Level Turnover", "ROA [-1, +1]"],
             "(8)": ["G-Index-A", "Stock-Level Turnover", "ROA [-1, +1]", "ROIC"]}
    items = []
    for col, regs in specs.items():
        r = panel_regression(x, "y", regs + CONTROLS + ["std_ret_lag"], fe=["fy", "industry", "province"],
                             cluster=CLUSTER, weight="mcap_lag_usd", cluster_mode=CLUSTER_MODE)
        for v in regs:
            items += [(v, col, r.params[v]), (f"t({v})", col, r.tstats[v])]
        items += [("R2 (%)", col, r.r2 * 100), ("Observations", col, float(r.n))]
    return _rows("TX", seg, items)


def table11(seg: Segment) -> pd.DataFrame:
    """Table XI Panel C: OLS of investment, OCF and net cash flows (percent of assets) on
    normalized lagged G-Index-A, with lagged log market cap (USD) and market-to-book; year,
    industry and province fixed effects; SEs clustered by industry and year. Column (4):
    net cash flows, 2010 onward."""
    x = _in(seg).copy()
    x["G-Index-A"] = _norm(x["g_index_a_lag"])
    items = []
    for col, dep, sub in (("(1)", "capx", None), ("(2)", "ocf", None), ("(3)", "ncf", None), ("(4)", "ncf", 2010)):
        d = x if sub is None else x[x["fy"] >= sub]
        d = d.assign(y=d[dep] * 100)
        r = panel_regression(d, "y", ["G-Index-A", "log_mcap_lag_usd", "mb_lag"], fe=["fy", "industry", "province"],
                             cluster=CLUSTER, cluster_mode=CLUSTER_MODE)
        items += [("G-Index-A", col, r.params["G-Index-A"]), ("t(G-Index-A)", col, r.tstats["G-Index-A"]),
                  ("R2 (%)", col, r.r2 * 100), ("Observations", col, float(r.n))]
    return _rows("TXI", seg, items)


def matched_cross_listed(x: pd.DataFrame) -> pd.Series:
    """Each A+H cross-listed firm matched with the non-cross-listed A-share firm in the same
    CSRC industry letter (SAS Industry1) with the closest total assets in the cross-listed
    firm's listing year (Table13.sas: nearest neighbour within industry-year). A cross-listed
    firm without a candidate stays in the matched sample, as the SAS left join keeps it."""
    ever = x.groupby("stkcd")["cross_listed_h"].max()
    ipo = x[x["fy"] == x["list_date"].dt.year].dropna(subset=["at", "industry_letter"])
    cross = ipo[ipo["stkcd"].map(ever) == 1]
    pool = ipo[ipo["stkcd"].map(ever) != 1]
    keep = set(cross["stkcd"])
    for _, r in cross.iterrows():
        cand = pool[(pool["industry_letter"] == r["industry_letter"]) & (pool["fy"] == r["fy"])]
        if len(cand):
            keep.add(cand.iloc[(cand["at"] - r["at"]).abs().argmin()]["stkcd"])
    return pd.Series(sorted(keep))


def table13(seg: Segment) -> pd.DataFrame:
    """Table XIII: cross-listed (A + H) vs other A-share firms. Panel A: RPT amount out (OLS)
    and annual real returns (WLS, lagged market cap) for the full and matched samples.
    Panel B: operating performance in the matched sample. Controls lagged size, leverage,
    ROA, sales growth, log firm age (plus return volatility in the matched return model, as
    in the authors' code); year, industry and location (province) fixed effects, as printed
    ("Year/Industry/Location FE") and in Table13.sas; SEs clustered by industry letter and
    year. Cross-listed in a year = H shares outstanding at that year end."""
    x = _in(seg).copy()
    x["Cross-Listed"] = x["cross_listed_h"]
    # Matching uses every year up to the segment end (a cross-listed firm's listing year can
    # precede the segment), never later years: an H listing after the segment must not make a
    # firm "cross-listed" in it.
    p_upto = panel()
    p_upto = p_upto[p_upto["fy"] <= seg.end.year]
    matched = set(matched_cross_listed(p_upto))
    xm = x[x["stkcd"].isin(matched)]
    items = [("matched", "cross_listed_firms", float(xm.loc[xm["cross_listed_h"] == 1, "stkcd"].nunique()))]
    specs = [("A", "RPT Amt Out", "(1)", x, "rpt_loan_out", None, CONTROLS),
             ("A", "RPT Amt Out", "(2)", xm, "rpt_loan_out", None, CONTROLS),
             ("A", "Stock Returns", "(3)", x, "ret_real", "mcap_lag", CONTROLS),
             ("A", "Stock Returns", "(4)", xm, "ret_real", "mcap_lag", CONTROLS + ["std_ret_lag"]),
             ("B", "ROA", "(1)", xm, "roa", None, CONTROLS), ("B", "ROE", "(2)", xm, "roe", None, CONTROLS),
             ("B", "Net Income Growth", "(3)", xm, "ni_growth", None, CONTROLS),
             ("B", "Operating Cash Flows", "(4)", xm, "ocf", None, CONTROLS),
             ("B", "Investment", "(5)", xm, "capx", None, CONTROLS), ("B", "Net Cash Flows", "(6)", xm, "ncf", None, CONTROLS)]
    for panel_id, dep_name, col, d, dep, w, ctrl in specs:
        d = d.assign(y=d[dep] * (100 if dep == "ret_real" else 1))
        r = panel_regression(d, "y", ["Cross-Listed"] + ctrl, fe=["fy", "industry", "province"], cluster=CLUSTER,
                             weight=w, cluster_mode=CLUSTER_MODE)
        items += [(f"{panel_id}:{dep_name}", f"{col} coef", r.params["Cross-Listed"]),
                  (f"{panel_id}:{dep_name}", f"{col} t", r.tstats["Cross-Listed"]),
                  (f"{panel_id}:{dep_name}", f"{col} R2 (%)", r.r2 * 100),
                  (f"{panel_id}:{dep_name}", f"{col} N", float(r.n))]
    return _rows("TXIII", seg, items)


def text_numbers(seg: Segment) -> pd.DataFrame:
    """Numbers Allen et al. print in the text about the A-share sample (lighthouse 7.3):
    - SOE share of listed firms at the end (printed 30% in 2018; the 2000 value, 70%, is not
      producible because CSMAR's controller file starts in 2003);
    - listed A-share firms in 1991 (printed 13);
    - average dividend yield in the last year (printed 0.8% in 2018; footnote 11): cash
      dividends per share with ex-dates in the year over the year-end close;
    - value-weighted (by assets) mean OCF / assets over the segment (printed 6.5%,
      section III.A.3);
    - small-minus-large G-Index-A gaps in 2004 and 2007 (footnote 32: 0.058 and 0.375)."""
    x = _in(seg)
    last = seg.end.year
    items = []
    g = x[x["fy"] == last]
    items.append(("soe_share_last_year", "pct", float(g["soe"].mean() * 100) if g["soe"].notna().any() else np.nan))
    m = load("stock_month")
    a = m[m["is_a_share"]]
    items.append(("listed_firms_1991", "n", float((a.groupby("stkcd")["month"].min().dt.year <= 1991).sum())))
    # Dividend yield: cash dividends per share with ex-dates in the year (TRD_Cptl, type CA)
    # over the year-end close; equal-weighted average over A shares traded in December.
    from csmar.readers import read_raw
    cp = read_raw("TRD_Cptl", columns=["Stkcd", "Disttyp", "Exdistdt", "Amount"])
    cp = cp[(cp["Disttyp"] == "CA") & cp["Exdistdt"].astype("string").str.startswith(str(last))]
    dps = pd.to_numeric(cp["Amount"], errors="coerce").groupby(cp["Stkcd"]).sum()
    dec = a[a["month"] == pd.Period(f"{last}-12", "M")].set_index("stkcd")["close"]
    dy = (dps.reindex(dec.index).fillna(0.0) / dec).dropna()
    items.append(("dividend_yield_last_year", "pct", float(dy.mean() * 100)))
    ys = []
    for _, gy in x.dropna(subset=["ocf", "at"]).groupby("fy"):
        ys.append(np.average(gy["ocf"], weights=gy["at"]))
    items.append(("vw_mean_ocf", "pct", float(np.mean(ys) * 100)))
    for y in (2004, 2007):
        gy = x[x["fy"] == y]
        if len(gy):
            q3, q7 = gy["mcap_lag"].quantile([0.3, 0.7])
            gap = gy.loc[gy["mcap_lag"] <= q3, "g_index_a"].mean() - gy.loc[gy["mcap_lag"] > q7, "g_index_a"].mean()
        else:
            gap = np.nan
        items.append((f"g_index_a_small_minus_large_{y}", "value", float(gap)))
    # Section III.A.1 (IPO process): average ROA in the year before vs after the IPO (printed
    # 13% -> 6%) and capex / assets (printed 3% -> 7%), equal-weighted over A-share IPOs of the
    # segment that have the pre-IPO year in CSMAR (prospectus statements, 1,033 firms in all).
    acc = D.accounting()[["stkcd", "fy", "roa", "capx"]]
    lst = panel().drop_duplicates("stkcd").set_index("stkcd")["list_date"].dt.year
    acc["k"] = acc["fy"] - acc["stkcd"].map(lst)
    ipo_in = acc["stkcd"].map(lst).between(seg.start.year, seg.end.year - 1)
    a2 = acc[ipo_in & acc["k"].isin([-1, 1])]
    both = a2.groupby("stkcd")["k"].nunique().eq(2)
    a2 = a2[a2["stkcd"].map(both).fillna(False)]
    a2 = D.winsorize(a2, ["roa", "capx"])
    for var, name in (("roa", "ipo_roa"), ("capx", "ipo_capex")):
        items += [(f"{name}_year_minus1", "pct", float(a2.loc[a2["k"] == -1, var].mean() * 100)),
                  (f"{name}_year_plus1", "pct", float(a2.loc[a2["k"] == 1, var].mean() * 100))]
    items.append(("ipo_firms_with_pre_ipo_year", "n", float(a2["stkcd"].nunique())))
    # Figure 5 caption: unique A-share firms with non-missing investment, NCF and assets
    f5 = x.dropna(subset=["capx", "ncf", "at"])
    items.append(("figure5_unique_firms", "n", float(f5["stkcd"].nunique())))
    return _rows("TXT", seg, items)
