"""Build cleaned panels from the raw CSMAR tables.

Scope (lighthouse.md section 4): this module produces paper-neutral building blocks. It does
NOT apply any paper's sample filters (ST exclusion, microcap cut-offs, financial-industry
exclusion, price floors): those differ across the three papers and live in each replication
module as named parameters. What this module does decide is documented inline, because each
decision affects every downstream number.

Outputs (parquet under data/processed/):
- stock_month: one row per stock-month in which the stock traded, plus board, listing info,
  industry and ST status.
- st_month: ST / *ST / PT status per stock-month from the daily trading-status code.
- daily_month: generic monthly aggregates of the daily file (volatility, turnover, Amihud).
- statements: consolidated statements (balance sheet, income, both cash-flow statements) at
  period ends, with report type and the actual disclosure date.
- statements_opening: the restated opening-balance rows (Accper = YYYY-01-01), kept apart.
- risk_free_1y: one-year deposit rate per month (LSY convention).
- cpi: monthly CPI index, OECD level chained forward with NBS month-on-month changes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from csmar.readers import read_raw
from csmar.registry import PROCESSED, RAW_EXTERNAL

A_SHARE_MARKETTYPES = (1, 4, 16, 32, 64)  # SH A (ex-STAR), SZ A (ex-ChiNext), ChiNext, STAR, BSE

# CSMAR daily trading-status codes (TRD_Dalyr.Trdsta). Codes for ST and *ST variants across the
# split-share-reform prefixes S/G/U/N; 16 = PT (particular transfer, 1999-2002).
TRDSTA_ST = frozenset({2, 5, 8, 11, 14})
TRDSTA_STAR_ST = frozenset({3, 6, 9, 12, 15})
TRDSTA_PT = frozenset({16})


# ---------------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------------

def parse_csmar_date(s: pd.Series, *, missing_day: str = "month_end") -> pd.Series:
    """Parse CSMAR dates, which use "00" for unknown day or month (e.g. "1993-12-00").

    missing_day="month_end": an unknown day is set to the last day of the month. For
    disclosure dates this is the conservative choice: information is assumed available only
    at the end of the month, never earlier, so it cannot introduce look-ahead.
    An unknown month ("YYYY-00-00") yields NaT.
    """
    s = s.astype("string")
    month_known = ~s.str.slice(5, 7).eq("00")
    day_missing = s.str.slice(8, 10).eq("00")
    fixed = s.where(~day_missing, s.str.slice(0, 8) + "01")
    out = pd.to_datetime(fixed.where(month_known), errors="coerce", format="%Y-%m-%d")
    if missing_day == "month_end":
        out = out.where(~day_missing.fillna(False), out + pd.offsets.MonthEnd(0))
    else:
        raise ValueError(f"unknown missing_day policy {missing_day!r}")
    return out


def board_of(stkcd: pd.Series, markettype: pd.Series) -> pd.Series:
    """Board from CSMAR market type, with Shenzhen SME split out by code prefix.

    Markettype 4 (Shenzhen A) covers both the Shenzhen main board (000/001) and the SME board
    (002/003; merged into the main board in April 2021). Li et al. use "mainboard" breakpoints
    that exclude SME and ChiNext, so the distinction must be kept even after the merger:
    a paper's own rule decides how to treat 002/003 stocks.
    """
    mt = markettype.astype("Int64")
    prefix = stkcd.str.slice(0, 3)
    board = pd.Series(pd.NA, index=stkcd.index, dtype="string")
    board[mt.eq(1)] = "SH_MAIN"
    board[mt.eq(4) & prefix.isin(["000", "001"])] = "SZ_MAIN"
    board[mt.eq(4) & prefix.isin(["002", "003"])] = "SZ_SME"
    board[mt.eq(16)] = "CHINEXT"
    board[mt.eq(32)] = "STAR"
    board[mt.eq(64)] = "BSE"
    board[mt.eq(2)] = "SH_B"
    board[mt.eq(8)] = "SZ_B"
    unknown = board.isna() & mt.notna()
    if unknown.any():
        examples = pd.DataFrame({"stkcd": stkcd[unknown], "markettype": mt[unknown]}).drop_duplicates().head()
        raise ValueError(f"Unclassified market type / code prefix combinations:\n{examples}")
    return board


def _save(df: pd.DataFrame, name: str) -> pd.DataFrame:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PROCESSED / f"{name}.parquet", index=False)
    return df


def load(name: str) -> pd.DataFrame:
    path = PROCESSED / f"{name}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"{path} missing; run `python -m csmar.build` first")
    return pd.read_parquet(path)


# ---------------------------------------------------------------------------------------------
# Company information
# ---------------------------------------------------------------------------------------------

def company_info() -> pd.DataFrame:
    """Listing date, current status, and industry codes per stock (TRD_Co).

    Industry codes are the CURRENT classification only (CSRC 2001 and 2012 versions); CSMAR's
    company file carries no history. Using today's industry for past years is a known
    deviation for papers that classify by the industry at the time (logged in the report).
    """
    co = read_raw("TRD_Co")
    out = pd.DataFrame({
        "stkcd": co["Stkcd"],
        "name": co["Stknme"],
        "list_date": parse_csmar_date(co["Listdt"]),
        "markettype": co["Markettype"].astype("Int64"),
        "status": co["Statco"],
        "status_date": parse_csmar_date(co["Statdt"]),
        "csrc2001": co["Nindcd"],
        "csrc2012": co["Nnindcd"],
        "ownership_type": co["OWNERSHIPTYPE"],
        "h_share_code": co["Commnt"],
        "b_share_code": co["Crcd"],
    })
    out["board"] = board_of(out["stkcd"], out["markettype"])
    # Financial industry: CSRC 2012 section J; CSRC 2001 section I (banking and insurance).
    out["is_financial"] = out["csrc2012"].str.startswith("J").fillna(False) | (
        out["csrc2012"].isna() & out["csrc2001"].str.startswith("I").fillna(False)
    )
    return out


# ---------------------------------------------------------------------------------------------
# Stock-month panel
# ---------------------------------------------------------------------------------------------

def stock_month(st: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per stock-month with trading activity (TRD_Mnth), all markets.

    - CSMAR omits months without any trading day (full-month suspensions). Those months are
      NOT filled in here; `month_gap` gives the number of calendar months since the stock's
      previous traded month so that return compounding across suspensions is visible.
    - Market values are converted from CSMAR's thousands of yuan to yuan.
    - `ret` is the dividend-reinvested monthly return (Mretwd); `ret_nodiv` excludes dividends.
      CSMAR leaves `ret` blank in a stock's first traded month. In the month a stock resumes
      after a full-month suspension, `ret` runs from the last pre-suspension close, so no
      return is lost across the gap (verified against compounded daily returns:
      csmar.validate).
    - ST status columns come from st_month() (daily status code; months before 2000 have none).
      Pass a prebuilt `st` to avoid recomputing it from the daily file.
    """
    m = read_raw("TRD_Mnth")
    out = pd.DataFrame({
        "stkcd": m["Stkcd"],
        "month": pd.PeriodIndex(m["Trdmnt"], freq="M"),
        "ret": m["Mretwd"].astype(float),
        "ret_nodiv": m["Mretnd"].astype(float),
        "mv_total": m["Msmvttl"].astype(float) * 1_000,
        "mv_float": m["Msmvosd"].astype(float) * 1_000,
        "close": m["Mclsprc"].astype(float),
        "volume": m["Mnshrtrd"].astype(float),
        "turnover_value": m["Mnvaltrd"].astype(float),
        "trading_days": m["Ndaytrd"].astype("Int64"),
        "markettype": m["Markettype"].astype("Int64"),
    })
    out["board"] = board_of(out["stkcd"], out["markettype"])
    out["is_a_share"] = out["markettype"].isin(A_SHARE_MARKETTYPES)
    out = out.sort_values(["stkcd", "month"]).reset_index(drop=True)

    prev = out.groupby("stkcd")["month"].shift(1)
    out["month_gap"] = (out["month"] - prev).apply(lambda x: x.n if pd.notna(x) else pd.NA).astype("Int64")

    info = company_info()[["stkcd", "list_date", "is_financial", "csrc2012", "csrc2001"]]
    out = out.merge(info, on="stkcd", how="left", validate="many_to_one")
    st = st_month() if st is None else st
    out = out.merge(st, on=["stkcd", "month"], how="left", validate="one_to_one")
    if out.duplicated(["stkcd", "month"]).any():
        raise ValueError("stock_month has duplicate (stkcd, month) keys")
    return out


# ---------------------------------------------------------------------------------------------
# ST status
# ---------------------------------------------------------------------------------------------

def st_month() -> pd.DataFrame:
    """ST status per stock-month from the daily trading-status code (TRD_Dalyr.Trdsta).

    Columns:
    - st_end: status on the last trading day of the month is ST or *ST (or PT).
    - st_any: ST, *ST or PT on any trading day of the month.
    - trdsta_end: the raw status code on the month's last trading day. Code 1 is "normal";
      every other code is a special status: ST/*ST/PT, and also the split-share-reform
      prefixes (S/G/N, codes 4, 7, 10) that are not ST. Li et al.'s "abnormal trading status"
      means trdsta_end != 1: with that rule and the financial-industry exclusion, our
      year-end counts equal their Table 1 Panel A for every year 2000-2018
      (docs/data_layer.md, section 4).
    The daily code is preferred over the event file (SPT_Trdchg) because it reflects the
    status actually in force on each trading day; the event file is used for validation.
    Coverage starts in 2000 (the daily download), so months before 2000 have no row.
    """
    d = read_raw("TRD_Dalyr", columns=["Stkcd", "Trddt", "Trdsta"])
    d = d.rename(columns={"Stkcd": "stkcd"})
    d["month"] = pd.PeriodIndex(d["Trddt"].str.slice(0, 7), freq="M")
    code = d["Trdsta"].astype(int)
    flagged = code.isin(TRDSTA_ST | TRDSTA_STAR_ST | TRDSTA_PT)
    d["flag"] = flagged
    d["star"] = code.isin(TRDSTA_STAR_ST)
    d["pt"] = code.isin(TRDSTA_PT)
    d["code"] = code
    d = d.sort_values(["stkcd", "Trddt"])
    g = d.groupby(["stkcd", "month"], sort=False)
    out = pd.DataFrame({
        "st_end": g["flag"].last(),
        "st_any": g["flag"].any(),
        "star_st_end": g["star"].last(),
        "pt_any": g["pt"].any(),
        "trdsta_end": g["code"].last().astype("int16"),
    }).reset_index()
    return out


# ---------------------------------------------------------------------------------------------
# Financial statements
# ---------------------------------------------------------------------------------------------

_REPORT_TYPE_BY_MONTH_DAY = {"03-31": 1, "06-30": 2, "09-30": 3, "12-31": 4}
_STATEMENT_TABLES = ("FS_Combas", "FS_Comins", "FS_Comscfi", "FS_Comscfd")
_KEY = ["Stkcd", "Accper"]


def _consolidated(code: str) -> pd.DataFrame:
    df = read_raw(code)
    df = df[df["Typrep"] == "A"].drop(columns=["Typrep", "_chunk", "ShortName"], errors="ignore")
    if df.duplicated(_KEY).any():
        raise ValueError(f"{code}: duplicate consolidated rows per (Stkcd, Accper)")
    return df


def statements() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Consolidated statements merged across the four tables, split into period-end and
    opening-balance rows, with report type and actual disclosure date.

    Findings that shape this function (docs/data_layer.md):
    - Period-end rows hold the figures AS ORIGINALLY REPORTED. Year-end rows differ from the
      next year's opening-balance rows (the restated comparatives) for 23% of firm-years
      flagged IfCorrect=1, which could not happen if CSMAR overwrote originals with
      restatements. Restated values live only in the YYYY-01-01 opening rows.
    - Opening rows (Accper = YYYY-01-01) are not a reporting period; they are returned
      separately and must never enter a "latest available statement" lookup.
    - The disclosure date comes from IAR_Rept (annual/semi-annual/quarterly report dates),
      matched on (Stkcd, Accper). Restatement flags (IfCorrect, DeclareDate) are kept from
      each table with a table suffix.
    """
    merged = None
    for code in _STATEMENT_TABLES:
        df = _consolidated(code)
        flags = {"IfCorrect": f"IfCorrect_{code}", "DeclareDate": f"DeclareDate_{code}"}
        df = df.rename(columns=flags)
        merged = df if merged is None else merged.merge(df, on=_KEY, how="outer", validate="one_to_one")

    merged = merged.rename(columns={"Stkcd": "stkcd", "Accper": "accper"})
    merged["period_end"] = parse_csmar_date(merged["accper"])
    md = merged["accper"].str.slice(5, 10)
    is_opening = md.eq("01-01")
    opening = merged[is_opening].copy()
    period = merged[~is_opening].copy()

    period["report_type"] = period["accper"].str.slice(5, 10).map(_REPORT_TYPE_BY_MONTH_DAY).astype("Int64")
    odd = period["report_type"].isna()
    if odd.any():
        # Rare non-standard period ends (e.g. firms with non-December fiscal years before
        # listing). Kept but flagged; papers' rules decide whether to use them.
        period.loc[odd, "report_type"] = pd.NA

    rept = read_raw("IAR_Rept")[["Stkcd", "Accper", "Reptyp", "Annodt"]].rename(
        columns={"Stkcd": "stkcd", "Accper": "accper", "Reptyp": "iar_report_type", "Annodt": "announce_raw"})
    if rept.duplicated(["stkcd", "accper"]).any():
        raise ValueError("IAR_Rept has duplicate (Stkcd, Accper)")
    period = period.merge(rept, on=["stkcd", "accper"], how="left", validate="one_to_one")
    period["announce_date"] = parse_csmar_date(period["announce_raw"])
    period["iar_report_type"] = pd.to_numeric(period["iar_report_type"], errors="coerce").astype("Int64")
    return period.reset_index(drop=True), opening.reset_index(drop=True)


# ---------------------------------------------------------------------------------------------
# Rates and prices
# ---------------------------------------------------------------------------------------------

def risk_free_1y() -> pd.DataFrame:
    """Monthly one-year deposit rate (CSMAR TRD_Nrrate, NRI01), as a monthly decimal rate.

    The rate in force at the END of month t is used as the risk-free return for month t+1 by
    the papers that use it; this function only reports the month-end value. CSMAR follows the
    PBoC benchmark (1.50% from 2015-10-24) until 2022-09, then switches to large-bank posted
    rates (1.65% ... 0.95%); see docs/data_layer.md.
    """
    r = read_raw("TRD_Nrrate")
    r = r[r["Nrr1"] == "NRI01"].copy()
    r["date"] = pd.to_datetime(r["Clsdt"])
    r["month"] = r["date"].dt.to_period("M")
    last = r.sort_values("date").groupby("month").last()
    return pd.DataFrame({
        "month": last.index,
        "annual_pct": last["Nrrdata"].astype(float).to_numpy(),
        "monthly_compound": last["Nrrmtdt"].astype(float).to_numpy() / 100,
        "monthly_simple": last["Nrrdata"].astype(float).to_numpy() / 1200,
    })


def cpi() -> pd.DataFrame:
    """Monthly China CPI index (2015 = 100).

    OECD level (FRED CHNCPIALLMINMEI, sourced from NBS) through 2025-04, then chained forward
    with the NBS headline month-on-month index (居民消费价格指数(上月=100)). On the 19
    overlapping months the two month-on-month changes agree within 0.2 index points.
    """
    oecd = pd.read_csv(RAW_EXTERNAL / "fred" / "CHNCPIALLMINMEI.csv")
    oecd["month"] = pd.PeriodIndex(oecd["observation_date"].str.slice(0, 7), freq="M")
    level = oecd.set_index("month")["CHNCPIALLMINMEI"].astype(float)

    nbs = pd.concat([
        pd.read_csv(RAW_EXTERNAL / "nbs" / f, encoding="utf-8-sig")
        for f in ("nbs_cpi_mom_table_2021_2025.csv", "nbs_cpi_mom_table_2026.csv")
    ])
    head = nbs[nbs["indicator"] == "居民消费价格指数(上月=100)"].copy()
    head["month"] = pd.PeriodIndex(head["month"], freq="M")
    mom = head.drop_duplicates("month").set_index("month")["value"].astype(float).sort_index()

    out = level.copy()
    source = pd.Series("OECD", index=level.index)
    for month in mom.index[mom.index > level.index.max()]:
        prev = month - 1
        if prev not in out.index:
            raise ValueError(f"CPI chain broken: no level for {prev}")
        out.loc[month] = out.loc[prev] * mom.loc[month] / 100
        source.loc[month] = "NBS_MoM"
    return pd.DataFrame({"month": out.index, "cpi": out.to_numpy(), "source": source.reindex(out.index).to_numpy()})


# ---------------------------------------------------------------------------------------------
# Daily
# ---------------------------------------------------------------------------------------------

def daily(columns: list[str] | None = None) -> pd.DataFrame:
    """Daily stock records with typed dates and board; A-shares and B-shares both kept.

    Volume and value of zero mean no trade that day. Market values in yuan.
    """
    base = ["Stkcd", "Trddt", "Markettype"]
    cols = list(dict.fromkeys(base + (columns or [])))
    d = read_raw("TRD_Dalyr", columns=cols).drop(columns="_chunk")
    d = d.rename(columns={"Stkcd": "stkcd"})
    d["date"] = pd.to_datetime(d.pop("Trddt"))
    for c in ("Dsmvosd", "Dsmvtll"):
        if c in d.columns:
            d[c] = d[c].astype(float) * 1_000
    d["board"] = board_of(d["stkcd"], d.pop("Markettype"))
    return d


def daily_to_month() -> pd.DataFrame:
    """Generic monthly aggregates of the daily file, one row per stock-month with trading.

    These are building blocks, not any paper's exact variable: each replication module states
    its own definition (window length, minimum days) and may recompute from daily().
    - n_days: trading days with a non-missing daily return.
    - vol_daily: standard deviation of daily dividend-reinvested returns (needs >= 2 days).
    - turnover: sum over days of shares traded / circulating shares, where circulating shares
      = circulating market value / close (CSMAR has no daily share count column).
    - amihud: mean of |daily return| / traded value in yuan over days with positive value.
    - max_ret: largest daily return in the month.
    - zero_volume_days: days on the file with no shares traded.
    """
    d = daily(["Clsprc", "Dnshrtrd", "Dnvaltrd", "Dsmvosd", "Dretwd"])
    d["month"] = d["date"].dt.to_period("M")
    r = d["Dretwd"].astype(float)
    value = d["Dnvaltrd"].astype(float)
    float_shares = d["Dsmvosd"] / d["Clsprc"].astype(float)
    d["turn"] = d["Dnshrtrd"].astype(float) / float_shares.where(float_shares > 0)
    d["illiq"] = (r.abs() / value).where(value > 0)
    d["r"] = r
    d["zero"] = d["Dnshrtrd"].astype(float).eq(0)
    g = d.groupby(["stkcd", "month"], sort=False)
    out = pd.DataFrame({
        "n_days": g["r"].count(),
        "vol_daily": g["r"].std(),
        "turnover": g["turn"].sum(min_count=1),
        "amihud": g["illiq"].mean(),
        "max_ret": g["r"].max(),
        "zero_volume_days": g["zero"].sum(),
    }).reset_index()
    return out


# ---------------------------------------------------------------------------------------------
# Build everything
# ---------------------------------------------------------------------------------------------

def build_all() -> dict[str, int]:
    sizes = {}
    sizes["company_info"] = len(_save(company_info(), "company_info"))
    st = _save(st_month(), "st_month")
    sizes["st_month"] = len(st)
    sizes["stock_month"] = len(_save(stock_month(st), "stock_month"))
    sizes["daily_month"] = len(_save(daily_to_month(), "daily_month"))
    period, opening = statements()
    sizes["statements"] = len(_save(period, "statements"))
    sizes["statements_opening"] = len(_save(opening, "statements_opening"))
    sizes["risk_free_1y"] = len(_save(risk_free_1y(), "risk_free_1y"))
    sizes["cpi"] = len(_save(cpi(), "cpi"))
    return sizes
