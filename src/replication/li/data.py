"""Sample and inputs for Li, Liu, Liu & Wei (2024). Every convention is a named parameter
with its source in the data manual (data/raw/external/li_et_al/.../Data Manual ...pdf, "DM")
or the paper (accepted version, references/Li_2023_MS_accepted.pdf).

Universe (DM p.1-2; paper Table 1 note):
- A shares on the Shanghai and Shenzhen mainboards, the SME board and GEM (ChiNext). STAR
  (from 2019-07) is added for the extension, BSE is left out (BOARDS / BOARDS_EXTENSION).
- Financial firms (CSRC industry) are excluded.
- "ST, PT or any other abnormal trading status" is excluded: only trading status 1 (正常交易)
  at the formation month end is kept. Checked against Table 1 Panel A: keeping status 1 only
  reproduces every yearly count by board exactly, including 2005 (1,019) and 2006 (1,104),
  where the G / S / U markers of the split-share reform are dropped as "abnormal".
- Negative book equity is excluded when forming portfolios (portfolios.py).
- Penny stocks (price < 5 yuan at formation) are dropped after quintiles are formed
  (portfolios.py).
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from csmar.panels import load

BOARDS = ("SH_MAIN", "SZ_MAIN", "SZ_SME", "CHINEXT")  # paper sample (DM p.1)
BOARDS_EXTENSION = BOARDS + ("STAR",)  # STAR opened 2019-07, after the paper's sample
MAINBOARD = ("SH_MAIN", "SZ_MAIN")  # breakpoints (DM p.2: "Mainboard breakpoints")
NORMAL_TRADING = 1  # CSMAR Trdsta 1 = 正常交易


@lru_cache(maxsize=1)
def stock_panel() -> pd.DataFrame:
    """Stock-month panel of A shares on the sample boards: return with dividends reinvested,
    circulating and total market cap (RMB), close, board, and the eligibility flag
    (non-financial, normal trading status at the month end)."""
    m = load("stock_month")
    m = m[m["is_a_share"] & m["board"].isin(BOARDS_EXTENSION)].copy()
    m["eligible"] = (~m["is_financial"].fillna(False).astype(bool)) & (m["trdsta_end"] == NORMAL_TRADING)
    m["normal_status"] = m["trdsta_end"] == NORMAL_TRADING
    m["mainboard"] = m["board"].isin(MAINBOARD)
    cols = ["stkcd", "month", "ret", "mv_float", "mv_total", "close", "board", "mainboard", "eligible", "normal_status",
            "trading_days", "csrc2012", "csrc2001", "list_date", "volume", "turnover_value"]
    return m[cols].sort_values(["stkcd", "month"]).reset_index(drop=True)


def table1_panel_a(years: range) -> pd.DataFrame:
    """Table 1 Panel A: year-end number of eligible firms by board and total / circulating
    market cap (trillion yuan)."""
    p = stock_panel()
    rows = []
    for y in years:
        d = p[(p["month"] == pd.Period(f"{y}-12", "M")) & p["eligible"]]
        out = {"year": y, "n_ashares": len(d)}
        for b, key in (("SH_MAIN", "sh"), ("SZ_MAIN", "sz"), ("SZ_SME", "sme"), ("CHINEXT", "gem"), ("STAR", "star")):
            g = d[d["board"] == b]
            out[{"sh": "n_sh_main", "sz": "n_sz_main"}.get(key, f"n_{key}")] = len(g)
            out[f"{key}_tmv"] = g["mv_total"].sum() / 1e12
            out[f"{key}_cmv"] = g["mv_float"].sum() / 1e12
        out["tmv"] = d["mv_total"].sum() / 1e12
        out["cmv"] = d["mv_float"].sum() / 1e12
        rows.append(out)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------
# Accounting data
# ---------------------------------------------------------------------------------------------

# CSMAR items named in the data manual.
BE = "A003000000"  # stockholders' book equity (DM A.2.1)
TA = "A001000000"  # total assets
NI = "B002000000"  # net income / income before extraordinary items (DM A.1.1, A.4.1)
OP = "B001300000"  # operating profit (DM B.1: operating profitability)
REV = "B001100000"  # total operating revenue (DM A.1.5)


@lru_cache(maxsize=1)
def statements() -> pd.DataFrame:
    """Consolidated period-end statements (originally reported figures, csmar.panels) with the
    fiscal period end, report type (Q1, H1, Q3, annual) and the actual announcement date."""
    s = load("statements")
    s = s[s["report_type"].notna()].copy()
    s["period_end"] = pd.to_datetime(s["period_end"])
    s["announce_date"] = pd.to_datetime(s["announce_date"])
    return s


def annual(items: list[str]) -> pd.DataFrame:
    """Annual-report values by (stkcd, fiscal year)."""
    s = statements()
    a = s[s["period_end"].dt.month.eq(12) & s["period_end"].dt.day.eq(31)]
    out = a[["stkcd", "period_end", *items]].copy()
    out["fy"] = out["period_end"].dt.year
    return out.drop(columns="period_end").drop_duplicates(["stkcd", "fy"], keep="last")


def quarterly_flows(items: list[str]) -> pd.DataFrame:
    """Single-quarter values of income-statement / cash-flow items: the year-to-date figure
    minus the previous quarter's year-to-date figure of the same fiscal year (DM p.3:
    "quarterly variables from the income statement are calculated as the quarterly change in
    the year-to-date corresponding variables"). Before 2002 only semi-annual and annual
    reports exist; their half-year flows are divided by two to a quarterly frequency
    (paper footnote 10 for ROE). Rows: (stkcd, period_end, announce_date, items...)."""
    s = statements()
    q = s[["stkcd", "period_end", "announce_date", *items]].sort_values(["stkcd", "period_end"]).copy()
    q["fy"] = q["period_end"].dt.year
    q["qtr"] = q["period_end"].dt.quarter
    prev = q.groupby(["stkcd", "fy"])[items].shift(1)
    prev_qtr = q.groupby(["stkcd", "fy"])["qtr"].shift(1)
    first = prev_qtr.isna()
    for c in items:
        ytd = q[c]
        flow = ytd - prev[c]
        # The first report of a fiscal year is its own flow over qtr quarters; a gap (e.g. H1
        # after no Q1) spans qtr - prev_qtr quarters. Scale both to one quarter.
        span = np.where(first, q["qtr"], q["qtr"] - prev_qtr)
        base = np.where(first, ytd, flow)
        q[c] = base / np.where(span > 0, span, np.nan)
    return q.drop(columns=["fy"])


def quarterly_stocks(items: list[str]) -> pd.DataFrame:
    """Balance-sheet values at each fiscal quarter end (stkcd, period_end, announce_date)."""
    s = statements()
    return s[["stkcd", "period_end", "announce_date", *items]].sort_values(["stkcd", "period_end"]).reset_index(drop=True)
