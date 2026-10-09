"""Reverse mergers (借壳上市) and shell values: LSY Figures 1 and 2 (section 3.3, A.4).

LSY take reverse mergers from WIND, which flags them following the CSRC's 2007 criteria.
CSMAR's M&A table (STK_MA_TRADINGMAIN) has no such flag, so the deals are identified by a
rule built from the CSRC definition (上市公司重大资产重组管理办法: a listed company buys,
from the party that gains control of it, assets worth at least 100% of its own total assets
at the prior year end). Every condition is a named parameter so the rule can be audited
and changed; lighthouse.md section 8 makes this rule a user-acceptance item.

Rule (all must hold):
1. MajorRestructuringSign = Y (the deal is a major asset restructuring);
2. the listed company is the buyer (TradingPositionID S3101) in an asset acquisition
   (S3001) or an asset swap (S3003);
3. it pays at least partly with its own shares (PayTypeID Q1603 share or Q1607
   cash-and-share);
4. the deal succeeded (IsSucceed = Y);
5. the assessed value of the assets bought is at least `min_asset_ratio` (default 1.0)
   times the listed company's total assets at the prior fiscal year end;
6. the actual controller (HLD_Contrshr.S0701b) at the fiscal year end after completion
   differs from the one at the fiscal year end before the first announcement.
Deal date = first announcement (FirstDeclareDate); "approval" = completion announcement
(FinishDeclareDate), the closest available date to the CSRC approval used in A.4.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from csmar.panels import load, parse_csmar_date
from csmar.readers import read_raw

SHARE_PAY = {"Q1603", "Q1607"}


def _norm(s: pd.Series) -> pd.Series:
    return s.astype("string").str.replace(r"\s+", "", regex=True).str.replace("（", "(").str.replace("）", ")")


def reverse_mergers(*, min_asset_ratio: float = 1.0, require_control_change: bool = True,
                    start: str = "2007-01-01", end: str = "2026-12-31") -> pd.DataFrame:
    ma = read_raw("STK_MA_TRADINGMAIN")
    d = pd.DataFrame({
        "event": ma["EventID"].astype("string"), "stkcd": ma["Symbol"].astype("string").str.zfill(6),
        "first": parse_csmar_date(ma["FirstDeclareDate"]), "finish": parse_csmar_date(ma["FinishDeclareDate"]),
        "position": ma["TradingPositionID"], "rtype": ma["RestructuringTypeID"], "major": ma["MajorRestructuringSign"],
        "pay": ma["PayTypeID"].astype("string"), "ok": ma["IsSucceed"],
        "value": pd.to_numeric(ma["EvaluationValue"], errors="coerce"),
    })
    d = d[(d["major"] == "Y") & (d["position"] == "S3101") & d["rtype"].isin(["S3001", "S3003"])
          & d["pay"].isin(SHARE_PAY) & (d["ok"] == "Y")]
    d = d[(d["first"] >= start) & (d["first"] <= end) & d["stkcd"].str.slice(0, 2).isin(["60", "30", "00"])]
    d = d.dropna(subset=["first"]).drop_duplicates(["event", "stkcd"])

    st = load("statements")
    st = st[st["report_type"] == 4][["stkcd", "period_end", "A001000000"]]
    st["fy"] = st["period_end"].dt.year
    d["fy_before"] = d["first"].dt.year - 1
    d = d.merge(st.rename(columns={"fy": "fy_before", "A001000000": "assets_before"})[["stkcd", "fy_before", "assets_before"]],
                on=["stkcd", "fy_before"], how="left")
    d["asset_ratio"] = d["value"] / d["assets_before"]
    d = d[d["asset_ratio"] >= min_asset_ratio]

    if require_control_change:
        h = read_raw("HLD_Contrshr", columns=["Stkcd", "Reptdt", "S0701b"])
        h = pd.DataFrame({"stkcd": h["Stkcd"], "fy": pd.to_datetime(h["Reptdt"]).dt.year, "ctrl": _norm(h["S0701b"])})
        h = h.drop_duplicates(["stkcd", "fy"], keep="last")
        d["fy_after"] = d["finish"].dt.year.fillna(d["first"].dt.year + 1).astype(int)
        d = d.merge(h.rename(columns={"fy": "fy_before", "ctrl": "ctrl_before"}), on=["stkcd", "fy_before"], how="left")
        d = d.merge(h.rename(columns={"fy": "fy_after", "ctrl": "ctrl_after"}), on=["stkcd", "fy_after"], how="left")
        d = d[d["ctrl_before"].notna() & d["ctrl_after"].notna() & (d["ctrl_before"] != d["ctrl_after"])]
    # One deal per company and first-announcement date (an event can list several assets)
    d = d.sort_values("value", ascending=False).drop_duplicates(["stkcd", "first"])
    return d.sort_values("first").reset_index(drop=True)


def size_deciles_three_months_before(deals: pd.DataFrame) -> pd.Series:
    """Fig. 1: the shell's size decile among all A shares (codes 60/30/00), by month-end total
    market value three months before the deal month. Shells are often suspended for months
    around a deal, so when the stock has no row in that month the latest earlier traded month
    is used (its percentile within that month's cross-section)."""
    m = load("stock_month")
    m = m[m["is_a_share"] & m["stkcd"].str.slice(0, 2).isin(["60", "30", "00"])][["stkcd", "month", "mv_total"]]
    m["pct"] = m.groupby("month")["mv_total"].rank(pct=True)
    m["t"] = m["month"].dt.to_timestamp()
    key = deals.assign(t=(deals["first"].dt.to_period("M") - 3).dt.to_timestamp())[["stkcd", "t"]].reset_index()
    x = pd.merge_asof(key.sort_values("t"), m.sort_values("t")[["stkcd", "t", "pct"]], on="t", by="stkcd",
                      direction="backward").set_index("index").sort_index()
    return np.ceil(x["pct"] * 10).clip(1, 10)


def figure1(deals: pd.DataFrame) -> pd.Series:
    dec = size_deciles_three_months_before(deals).dropna()
    return dec.value_counts(normalize=True).reindex(range(1, 11), fill_value=0.0).rename("fraction")


def figure2(deals: pd.DataFrame, *, r: float = 0.03, start: str = "2009-01-01", end: str = "2016-12-31") -> pd.DataFrame:
    """Fig. 2 (A.4): daily p, G, S = pG/(r+p) and S/V with V the median market value of the
    bottom 30%.

    - p: among stocks in the bottom 30% (by total market value that day), the fraction
      involved in a reverse merger first announced in the past 730 days, halved to a
      one-year rate.
    - G: average value appreciation of bottom-30% reverse-merger shells whose windows ended
      in the past 730 days; window = 60 days before the first announcement to 60 days after
      the completion announcement; appreciation = the shell's starting market value times its
      cumulative return over the window (gain to the shell's existing shareholders).
    """
    from csmar.panels import daily
    dd = daily(["Dsmvtll", "Dretwd"])
    dd = dd[dd["stkcd"].str.slice(0, 2).isin(["60", "30", "00"]) & dd["board"].isin(["SH_MAIN", "SZ_MAIN", "SZ_SME", "CHINEXT"])]
    dd["pct"] = dd.groupby("date")["Dsmvtll"].rank(pct=True)
    bottom = dd[dd["pct"] <= 0.3]

    by_stock = {}
    for k, g in dd[dd["stkcd"].isin(deals["stkcd"])].groupby("stkcd"):
        g = g.sort_values("date").copy()
        g["cum"] = np.log1p(g["Dretwd"].astype(float)).fillna(0.0).cumsum()
        by_stock[k] = g

    def last_on_or_before(stk, date, col):
        g = by_stock.get(stk)
        if g is None:
            return np.nan
        i = g["date"].searchsorted(date, side="right") - 1
        return g[col].iloc[i] if i >= 0 else np.nan

    deals = deals.copy()
    deals["w_start"] = deals["first"] - pd.Timedelta(days=60)
    deals["w_end"] = deals["finish"].fillna(deals["first"]) + pd.Timedelta(days=60)
    deals["mv0"] = [last_on_or_before(s, t, "Dsmvtll") for s, t in zip(deals["stkcd"], deals["w_start"])]
    # Appreciation for the shell's existing shareholders: starting value times the cumulative
    # (split- and dividend-adjusted) return over the window. The raw change in total market
    # value would wrongly count the new shares issued to the incoming owner as a gain.
    c0 = np.array([last_on_or_before(s, t, "cum") for s, t in zip(deals["stkcd"], deals["w_start"])])
    c1 = np.array([last_on_or_before(s, t, "cum") for s, t in zip(deals["stkcd"], deals["w_end"])])
    deals["gain"] = deals["mv0"] * np.expm1(c1 - c0)
    deals["bottom30"] = [last_on_or_before(s, t, "pct") <= 0.3 for s, t in zip(deals["stkcd"], deals["w_start"])]
    shells = deals[deals["bottom30"]]

    days = pd.to_datetime(sorted(bottom["date"].unique()))
    days = days[(days >= start) & (days <= end)]
    n_bottom = bottom.groupby("date")["stkcd"].nunique()
    median_v = bottom.groupby("date")["Dsmvtll"].median()
    rows = []
    for t in days:
        lo = t - pd.Timedelta(days=730)
        live = shells[(shells["first"] > lo) & (shells["first"] <= t)]
        p2 = live["stkcd"].nunique() / n_bottom.loc[t]
        p = p2 / 2
        ended = shells[(shells["w_end"] > lo) & (shells["w_end"] <= t)]
        G = ended["gain"].mean() if len(ended) else np.nan
        S = p * G / (r + p) if p > 0 and pd.notna(G) else np.nan
        rows.append({"date": t, "p": p, "G": G, "S": S, "V": median_v.loc[t], "S_over_V": S / median_v.loc[t]})
    return pd.DataFrame(rows).set_index("date")
