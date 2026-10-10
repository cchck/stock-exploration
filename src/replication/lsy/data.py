"""LSY sample: stock-month panel with the filters and sorting characteristics of
Liu, Stambaugh & Yuan (2019), Appendix A.1-A.2 and the Online Appendix (B.1).

Timing: a row for holding month t carries the return over t and characteristics known at
the END of month t-1 (sorting date). All characteristic columns are suffixed by nothing but
are, by construction, end-of-(t-1) values.

Paper conventions implemented (page refs to the JFE version):
- Universe: A shares whose code starts with 60, 30 or 00 (A.1). STAR (688), BSE and B shares
  are therefore excluded, also in the extension years.
- Filters at the end of t-1 (A.1): listed at least six months; at least 120 trading records
  in the past 12 months; at least 15 trading records in month t-1 (in the few months when
  the market itself traded fewer than 15 days: every market day).
- Shell filter: drop the bottom 30% by market cap at the end of t-1 (A.1). Which stocks
  define the 30th percentile is not stated; `shell_cut_base` makes it explicit
  ("filtered" = after the other filters, the default; "all" = all universe stocks).
- Size (ME): close x total A shares incl. non-tradable (Online Appendix B.1(a)) = CSMAR
  Msmvttl. Used both as the size sort variable and as the value weight.
- EP: net profit excluding non-recurring gains and losses (WIND NET_PROFIT_AFTER_DED_NR_LP,
  original-statement type 408005000) / (close x total shares incl. B and H). CSMAR
  IAR_Rept.Profitb is the same item as originally announced (checked: Moutai FY2019
  41.41bn, Vanke FY2019 38.31bn), falling back to announced net profit when missing.
  Earnings are the latest single quarter (half-year before 2002), derived from the
  year-to-date reports; see earnings_announcements() for the evidence.
  Latest report released on or before the end of t-1; semi-annual and annual reports
  only before 2002-01-01 (A.1).
- Abnormal turnover (CH-4): average daily turnover over the past 20 trading days divided
  by the average over the past 250 trading days; daily turnover = shares traded / shares
  outstanding (B.1(h)).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from csmar.panels import company_info, daily, load
from csmar.readers import read_raw

CODE_PREFIXES = ("60", "30", "00")
QUARTERLY_FROM = pd.Timestamp("2002-01-01")  # before this, semi-annual and annual reports only


# ---------------------------------------------------------------------------------------------
# Earnings and total shares
# ---------------------------------------------------------------------------------------------

def earnings_announcements(*, fallback_to_net_profit: bool = True) -> pd.DataFrame:
    """One row per (stock, report): single-period earnings as originally announced, with the
    announcement date.

    - Item: IAR_Rept.Profitb, net profit excluding non-recurring items. When Profitb is
      missing (mostly 1999-2000 reports) it falls back to Profita, the announced net profit,
      so those firms stay in the sorts.
    - Period: Chinese reports are year-to-date. The earnings used are the flow of the latest
      period: the quarter for quarterly reports (Q2 = H1 - Q1, Q3 = 9M - H1, Q4 = FY - 9M),
      and before 2002, when only semi-annual and annual reports are used, the half-year
      (H2 = FY - H1). A flow whose preceding report in the same fiscal year is missing is
      left missing rather than mixing a cumulative figure with quarterly ones.
    Evidence for both choices is in docs/deviation_log.md (LSY-1). Single-quarter earnings
    give VMG 2000-2016 1.19% (paper 1.14%) and a 0.980 correlation with Stambaugh's series;
    year-to-date earnings give 1.04% and 0.968; trailing twelve months 0.93% and 0.917.
    The Table 2 EP+ slope moves from 0.44 to 0.71 (paper 0.95). This also fits the paper's
    "ROE at the quarterly frequency".
    """
    r = read_raw("IAR_Rept", columns=["Stkcd", "Accper", "Reptyp", "Annodt", "Profita", "Profitb"])
    from csmar.panels import parse_csmar_date  # local: keeps the module import list short
    ytd = pd.to_numeric(r["Profitb"], errors="coerce")
    if fallback_to_net_profit:
        ytd = ytd.fillna(pd.to_numeric(r["Profita"], errors="coerce"))
    out = pd.DataFrame({
        "stkcd": r["Stkcd"],
        "period_end": parse_csmar_date(r["Accper"]),
        "report_type": pd.to_numeric(r["Reptyp"], errors="coerce").astype("Int64"),
        "announce_date": parse_csmar_date(r["Annodt"]),
        "earnings_ytd": ytd,
    }).dropna(subset=["period_end", "announce_date"])
    # Before 2002 only semi-annual (2) and annual (4) reports are used (A.1).
    early_quarterly = (out["announce_date"] < QUARTERLY_FROM) & out["report_type"].isin([1, 3])
    out = out[~early_quarterly].copy()
    out["fiscal_year"] = out["period_end"].dt.year
    out = out.sort_values(["stkcd", "fiscal_year", "report_type"]).reset_index(drop=True)
    prev = out.groupby(["stkcd", "fiscal_year"])["earnings_ytd"].shift(1)
    first = out.groupby(["stkcd", "fiscal_year"]).cumcount().eq(0)
    # The first report of a fiscal year is its own flow only if it is Q1, or H1 when
    # quarterlies are not used; otherwise the preceding report is missing.
    own_flow = first & (out["report_type"].eq(1) | (out["report_type"].eq(2) & (out["announce_date"] < QUARTERLY_FROM)))
    out["earnings"] = np.where(own_flow, out["earnings_ytd"], out["earnings_ytd"] - prev)
    out.loc[first & ~own_flow, "earnings"] = np.nan
    return out


def latest_by_month_end(events: pd.DataFrame, months: pd.PeriodIndex, value_cols: list[str],
                        date_col: str = "announce_date") -> pd.DataFrame:
    """For each stock and month end, the values of the most recent report released on or
    before the month end. If two reports were released on the same day, the one with the
    later period end is the more recent report.

    The whole row of that report is carried forward, missing values included: a NaN in the
    latest report (e.g. a quarterly flow whose preceding report is missing) stays NaN and is
    never back-filled from an older report column by column."""
    ev = events.sort_values([date_col, "period_end"]).copy()
    ev["month"] = ev[date_col].dt.to_period("M")
    last = ev.groupby(["stkcd", "month"]).tail(1).set_index(["stkcd", "month"])[[*value_cols, "period_end"]]
    last["__row"] = np.arange(len(last), dtype=float)
    grid = pd.MultiIndex.from_product([last.index.get_level_values(0).unique(), months], names=["stkcd", "month"])
    row = last["__row"].reindex(last.index.union(grid)).groupby(level=0).ffill().reindex(grid)
    vals = last.drop(columns="__row").reset_index(drop=True)
    out = vals.reindex(row.to_numpy()).set_index(grid)  # NaN row id -> all-NaN row
    return out.reset_index()


def total_shares_month_end(months: pd.PeriodIndex) -> pd.DataFrame:
    """Total shares outstanding (A + B + H + other, TRD_Capchg.Nshrttl) in force at each month
    end: the latest change dated on or before the month end."""
    c = read_raw("TRD_Capchg", columns=["Stkcd", "Shrchgdt", "Nshrttl"])
    from csmar.panels import parse_csmar_date
    ev = pd.DataFrame({"stkcd": c["Stkcd"], "date": parse_csmar_date(c["Shrchgdt"]),
                       "total_shares": pd.to_numeric(c["Nshrttl"], errors="coerce")}).dropna()
    ev["period_end"] = ev["date"]
    return latest_by_month_end(ev, months, ["total_shares"], date_col="date").drop(columns="period_end")


def single_period_flow(df: pd.DataFrame, ytd_col: str) -> pd.Series:
    """Single-period flow from year-to-date figures: the quarter for quarterly reports, the
    half-year before 2002 (only semi-annual and annual reports are used then). Rows must
    hold one report per (stkcd, fiscal_year, report_type). A flow whose preceding report in
    the same fiscal year is missing is NaN (never a cumulative figure posing as a flow)."""
    d = df.sort_values(["stkcd", "fiscal_year", "report_type"])
    prev = d.groupby(["stkcd", "fiscal_year"])[ytd_col].shift(1)
    first = d.groupby(["stkcd", "fiscal_year"]).cumcount().eq(0)
    own = first & (d["report_type"].eq(1) | (d["report_type"].eq(2) & (d["announce_date"] < QUARTERLY_FROM)))
    flow = pd.Series(np.where(own, d[ytd_col], d[ytd_col] - prev), index=d.index)
    flow[first & ~own] = np.nan
    return flow.reindex(df.index)


def statement_items_month_end(months: pd.PeriodIndex) -> pd.DataFrame:
    """Balance-sheet and cash-flow items from the latest consolidated statement released on or
    before each month end (Online Appendix B.1(b)):
    - book_equity: equity attributable to parent shareholders (A003100000; CSMAR fills it for
      all years, and total equity A003000000 includes minority interest, so it is not used);
    - total_assets: A001000000 (for AM, as in Fama and French 1992);
    - cash_flow: "the net change in cash or cash equivalents between the two most recent cash
      flow statements" (A.2): the single-quarter change, from the year-to-date net increase
      in cash and equivalents C005000000. Before 2002 "half the net change between the two
      most recent semi-annual statements" (footnote 6): the half-year change divided by two.
    Only period-end rows (never the restated opening rows) are used; before 2002-01-01 only
    semi-annual and annual reports (A.1).
    """
    st = load("statements")[["stkcd", "period_end", "report_type", "announce_date",
                             "A003100000", "A001000000", "C005000000"]].dropna(subset=["announce_date"])
    st = st.rename(columns={"A003100000": "book_equity", "A001000000": "total_assets", "C005000000": "cash_ytd"})
    early_quarterly = (st["announce_date"] < QUARTERLY_FROM) & st["report_type"].isin([1, 3])
    st = st[~early_quarterly].copy()
    st["fiscal_year"] = st["period_end"].dt.year
    st["cash_flow"] = single_period_flow(st, "cash_ytd")
    semi = st["announce_date"] < QUARTERLY_FROM
    st.loc[semi, "cash_flow"] = st.loc[semi, "cash_flow"] / 2
    return latest_by_month_end(st, months, ["book_equity", "total_assets", "cash_flow"])


def annual_items_month_end(months: pd.PeriodIndex) -> pd.DataFrame:
    """Annual-report characteristics for the anomalies LSY test but do not keep (section 6.1,
    A.2, Online Appendix B.1(e)-(f)), from the latest annual report released on or before
    each month end (original values, period-end rows only):
    - asset_growth: total assets / previous year's total assets - 1 (investment);
    - accruals: Sloan (1996), 2 x [(dCA - dCash) - (dCL - dSTD - dTP) - Dep] / (TA_t-1 + TA_t),
      with Cash = ending cash and equivalents (C006000000, else 货币资金 A001101000),
      STD = current portion of non-current liabilities (A002125000) + notes payable
      (A002107000) exactly as LSY's Online Appendix B.1(f) lists it ("STD is the sum of
      long-term debt due in one year and notes payable"; short-term borrowings are not in
      it), TP = taxes payable (A002113000), Dep = depreciation (D000103000) +
      amortization of intangibles (D000104000);
    - op: operating profitability, annual (revenue - COGS - selling - administrative -
      financial expenses) / book equity, for FF-5's RMW;
    - noa: [(TA - cash - short-term investments) - (TA - short-term borrowing - long-term
      borrowing - minority interest - book equity)] / TA_t-1 (Hirshleifer et al. 2004).
    Components missing from a report (an item the firm does not have) count as zero;
    total assets, current assets and current liabilities must be present.
    """
    cols = {"A001000000": "ta", "A001100000": "ca", "A001101000": "cash_bs", "C006000000": "cash_cf",
            "A002100000": "cl", "A002125000": "cur_ncl", "A002107000": "notes_pay", "A002113000": "tax_pay",
            "D000103000": "dep", "D000104000": "amort", "A001107000": "st_inv", "A002101000": "st_borrow",
            "A002201000": "lt_borrow", "A003200000": "minority", "A003100000": "be",
            "B001101000": "revenue", "B001201000": "cogs", "B001209000": "selling", "B001210000": "admin",
            "B001211000": "fin_exp"}
    st = load("statements")
    st = st[st["report_type"] == 4][["stkcd", "period_end", "announce_date", *cols]].rename(columns=cols)
    st = st.dropna(subset=["announce_date"]).sort_values(["stkcd", "period_end"])
    st["fy"] = st["period_end"].dt.year
    for c in ("notes_pay", "tax_pay", "cur_ncl", "dep", "amort", "st_inv", "st_borrow", "lt_borrow", "minority",
              "cogs", "selling", "admin", "fin_exp"):
        st[c] = st[c].fillna(0.0)
    st["cash"] = st["cash_cf"].fillna(st["cash_bs"])
    prev = st.groupby("stkcd").shift(1)
    consecutive = (st["fy"] - prev["fy"]).eq(1)
    d = lambda c: (st[c] - prev[c]).where(consecutive)
    acc = (d("ca") - d("cash")) - (d("cl") - (d("cur_ncl") + d("notes_pay")) - d("tax_pay")) - (st["dep"] + st["amort"])
    st["asset_growth"] = (st["ta"] / prev["ta"] - 1).where(consecutive & (prev["ta"] > 0))
    st["accruals"] = 2 * acc / (prev["ta"] + st["ta"]).where(consecutive)
    oa = st["ta"] - st["cash"] - st["st_inv"]
    ol = st["ta"] - st["st_borrow"] - st["lt_borrow"] - st["minority"] - st["be"]
    st["noa"] = ((oa - ol) / prev["ta"]).where(consecutive & (prev["ta"] > 0))
    # Operating profitability (Fama and French 2015): revenue - cost of goods sold - selling,
    # general/administrative and interest (financial) expenses, over book equity.
    st["op"] = ((st["revenue"] - st["cogs"] - st["selling"] - st["admin"] - st["fin_exp"]) / st["be"]).where(st["be"] > 0)
    return latest_by_month_end(st, months, ["asset_growth", "accruals", "noa", "op"])


# ---------------------------------------------------------------------------------------------
# Daily characteristics at month end
# ---------------------------------------------------------------------------------------------

def _rolling_sum_count(values: np.ndarray, starts: np.ndarray, window: int) -> tuple[np.ndarray, np.ndarray]:
    """Trailing sum and count of non-missing values over the last `window` records of the
    same stock (records = the stock's own trading days). `starts` holds, for each row, the
    row index where that stock's records begin."""
    ok = ~np.isnan(values)
    cs = np.concatenate([[0.0], np.cumsum(np.where(ok, values, 0.0))])
    cn = np.concatenate([[0.0], np.cumsum(ok.astype(float))])
    idx = np.arange(len(values))
    lo = np.maximum(idx - window + 1, starts)
    return cs[idx + 1] - cs[lo], cn[idx + 1] - cn[lo]


def _rolling_mean(values, starts, window, min_obs):
    s, n = _rolling_sum_count(values, starts, window)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = s / n
    out[n < min_obs] = np.nan
    return out


def daily_characteristics_month_end() -> pd.DataFrame:
    """Month-end values of the daily-data characteristics LSY use (B.1(d), (g), (h), (i)).

    Windows count the stock's own trading records. Minimum records: 15 of 20 for 20-day
    measures (the 15-day filter guarantees this for eligible stocks) and 120 of 250 for
    250-day measures (the 120-record filter).
    - turn20 / turn250: average daily turnover (shares traded / total A shares outstanding,
      shares = Dsmvtll / Clsprc) over 20 / 250 records; abn_turn = turn20 / turn250.
    - vol20: std of daily returns over 20 records; max20: maximum daily return over 20 records.
    - illiq20: mean of |r| / traded value (yuan) over 20 records (Amihud).
    - rev20: cumulative return over the last 20 records.
    """
    d = daily(["Clsprc", "Dnshrtrd", "Dnvaltrd", "Dsmvtll", "Dretwd"])
    d = d.sort_values(["stkcd", "date"]).reset_index(drop=True)
    starts = d.groupby("stkcd").cumcount().to_numpy()
    starts = np.arange(len(d)) - starts
    # The listing day's return runs from the IPO offer price and its turnover is an IPO
    # event, so the listing day is left out of every window (same rule as
    # csmar.panels.daily_to_month).
    listing = d["stkcd"].map(company_info().set_index("stkcd")["list_date"])
    not_listing_day = ~d["date"].eq(listing).to_numpy()
    r = d["Dretwd"].astype(float).where(not_listing_day).to_numpy()
    shares = (d["Dsmvtll"] / d["Clsprc"].astype(float)).to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):
        turn = np.where(not_listing_day, d["Dnshrtrd"].astype(float).to_numpy() / np.where(shares > 0, shares, np.nan), np.nan)
        illiq = np.abs(r) / np.where(d["Dnvaltrd"].astype(float).to_numpy() > 0, d["Dnvaltrd"].astype(float).to_numpy(), np.nan)
    out = pd.DataFrame({"stkcd": d["stkcd"], "month": d["date"].dt.to_period("M")})
    out["turn20"] = _rolling_mean(turn, starts, 20, 15)
    out["turn250"] = _rolling_mean(turn, starts, 250, 120)
    out["abn_turn"] = out["turn20"] / out["turn250"]
    s1, n = _rolling_sum_count(r, starts, 20)
    s2, _ = _rolling_sum_count(r * r, starts, 20)
    with np.errstate(invalid="ignore", divide="ignore"):
        var = (s2 - s1 * s1 / n) / (n - 1)
    out["vol20"] = np.where(n >= 15, np.sqrt(np.maximum(var, 0)), np.nan)
    out["illiq20"] = _rolling_mean(illiq, starts, 20, 15)
    slr, nlr = _rolling_sum_count(np.log1p(r), starts, 20)
    out["rev20"] = np.where(nlr >= 15, np.expm1(slr), np.nan)
    out["max20"] = (pd.Series(r).groupby(d["stkcd"].to_numpy()).rolling(20, min_periods=15).max()
                    .reset_index(level=0, drop=True).sort_index().to_numpy())
    # The month's last record, as a whole row (a NaN there stays NaN; never a value from an
    # earlier day of the month).
    return out.groupby(["stkcd", "month"], sort=False).tail(1).reset_index(drop=True)


# ---------------------------------------------------------------------------------------------
# The LSY stock-month panel
# ---------------------------------------------------------------------------------------------

def build_panel(*, shell_cut: float = 0.30, shell_cut_base: str = "filtered", min_listed_months: int = 6,
                min_records_12m: int = 120, min_records_month: int = 15) -> pd.DataFrame:
    """Holding-month panel: one row per (stock, month t) with ret_t and end-of-(t-1) characteristics.

    Columns: stkcd, month (holding month t), ret (Mretwd over t), me (A-share total value at
    end of t-1, yuan), ep, abn_turn and the other daily characteristics, eligible (passes
    the listing/trading filters), in_universe (eligible and not in the bottom shell_cut).

    Filter parameters, all from LSY Appendix A.1: min_listed_months (6, "public within the
    past six months" excluded), min_records_12m (120 trading records in the past 12 months),
    min_records_month (15 in the most recent month), shell_cut (bottom 30% by market cap).
    """
    if shell_cut_base not in ("filtered", "all"):
        raise ValueError("shell_cut_base must be 'filtered' or 'all'")
    m = load("stock_month")
    m = m[m["is_a_share"] & m["stkcd"].str.slice(0, 2).isin(CODE_PREFIXES)].copy()

    # Sorting-date frame: one row per (stock, month s) for every calendar month s from the
    # first traded month, so that suspensions show up as zero trading days.
    span = m.groupby("stkcd")["month"].agg(["min", "max"])
    all_months = pd.period_range(m["month"].min(), m["month"].max(), freq="M")
    grid = pd.MultiIndex.from_tuples(
        [(s, p) for s, (lo, hi) in span.iterrows() for p in pd.period_range(lo, hi, freq="M")],
        names=["stkcd", "month"])
    s = m.set_index(["stkcd", "month"])[["ret", "mv_total", "close", "trading_days"]].reindex(grid).reset_index()
    s["trading_days"] = s["trading_days"].fillna(0).astype(float)
    s["days_12m"] = s.groupby("stkcd")["trading_days"].transform(lambda x: x.rolling(12, min_periods=1).sum())

    info = company_info().set_index("stkcd")["list_date"]
    month_end = s["month"].dt.to_timestamp(how="end").dt.normalize()
    s["listed_6m"] = s["stkcd"].map(info) <= (month_end - pd.DateOffset(months=min_listed_months))

    # EP at month end s: earnings / (close x total shares)
    earn = latest_by_month_end(earnings_announcements(), all_months, ["earnings"])
    shares = total_shares_month_end(all_months)
    s = s.merge(earn[["stkcd", "month", "earnings"]], on=["stkcd", "month"], how="left")
    s = s.merge(shares, on=["stkcd", "month"], how="left")
    s["ep"] = s["earnings"] / (s["close"] * s["total_shares"])

    items = statement_items_month_end(all_months)
    s = s.merge(items[["stkcd", "month", "book_equity", "total_assets", "cash_flow"]], on=["stkcd", "month"], how="left")
    mv_all = s["close"] * s["total_shares"]  # valuation ratios scale by all shares (footnote 5)
    s["bm"] = s["book_equity"] / mv_all
    s["am"] = s["total_assets"] / mv_all
    s["cp"] = s["cash_flow"] / mv_all

    ann = annual_items_month_end(all_months)
    s = s.merge(ann[["stkcd", "month", "asset_growth", "accruals", "noa", "op"]], on=["stkcd", "month"], how="left")

    dch = daily_characteristics_month_end()
    s = s.merge(dch, on=["stkcd", "month"], how="left")
    from replication.lsy.beta import dimson_beta_month_end
    s = s.merge(dimson_beta_month_end(), on=["stkcd", "month"], how="left")

    # The 15-record rule cannot be applied literally in months when the whole market traded
    # fewer than 15 days (Spring Festival: 2000-02 had 12, 2001-01 14, 2002-02 10, 2004-01 13,
    # 2005-02 13, 2026-02 14). Applied literally, no stock qualifies and the following month
    # has no factor return, yet the paper reports all 204 months. In those months the
    # threshold becomes the market's own trading-day count (deviation_log LSY-2).
    market_days = s.groupby("month")["trading_days"].transform("max")
    min_days = np.minimum(min_records_month, market_days)
    s["eligible"] = (s["listed_6m"].fillna(False) & (s["days_12m"] >= min_records_12m) & (s["trading_days"] >= min_days)
                     & s["mv_total"].notna())

    # Shift: characteristics at the end of s become the sorting variables for holding month s+1.
    chars = s.drop(columns=["ret"]).rename(columns={"mv_total": "me"})
    chars["month"] = chars["month"] + 1
    hold = s[["stkcd", "month", "ret"]]
    panel = chars.merge(hold, on=["stkcd", "month"], how="left")

    base = panel["eligible"] if shell_cut_base == "filtered" else panel["me"].notna()
    cut = panel[base].groupby("month")["me"].quantile(shell_cut)
    panel["in_universe"] = panel["eligible"] & (panel["me"] > panel["month"].map(cut))
    return panel
