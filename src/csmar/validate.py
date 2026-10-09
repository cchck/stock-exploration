"""Data-layer validation (lighthouse.md section 4.2): checks the processed panels against
CSMAR's own internal consistency and against counts published in the papers.

Run:  python -m csmar.validate          (needs `python -m csmar.build` first)

Writes aggregate-only CSVs to results/data_layer/ (safe to commit: no firm-level rows) and
prints a pass/fail line per check. Firm-level diagnostics stay in memory. The meaning of
every check, and why its tolerance is what it is, is in docs/data_layer.md.
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from csmar.panels import A_SHARE_MARKETTYPES, load
from csmar.readers import read_raw
from csmar.registry import PROJECT_ROOT

OUT = PROJECT_ROOT / "results" / "data_layer"

# Li, Liu, Liu & Wei (MS), Table 1 Panel A: non-financial A-shares with normal trading
# status at year end. Columns: total, SH main, SZ main, SME, GEM (ChiNext).
LI_TABLE1A = {
    1999: (844, 434, 410, 0, 0), 2000: (968, 516, 452, 0, 0), 2001: (1041, 587, 454, 0, 0),
    2002: (1080, 648, 432, 0, 0), 2003: (1105, 695, 410, 0, 0), 2004: (1190, 743, 409, 38, 0),
    2005: (1019, 621, 348, 50, 0), 2006: (1104, 679, 342, 83, 0), 2007: (1242, 704, 358, 180, 0),
    2008: (1363, 729, 383, 251, 0), 2009: (1456, 731, 385, 305, 35),
    2010: (1775, 740, 379, 505, 151), 2011: (2054, 775, 384, 618, 277),
    2012: (2252, 840, 394, 669, 349), 2013: (2264, 848, 426, 654, 336),
    2014: (2324, 873, 415, 659, 377), 2015: (2499, 937, 404, 698, 460),
    2016: (2748, 1043, 404, 759, 542), 2017: (3156, 1241, 397, 841, 677),
    2018: (3357, 1320, 429, 874, 734),
}
# Li Table 1 Panel A: A-share total / circulating market value, trillion yuan, same sample.
LI_TABLE1A_MV = {
    1999: (2.40, 0.73), 2000: (4.42, 1.44), 2001: (3.97, 1.24), 2002: (3.43, 1.07),
    2003: (3.75, 1.10), 2004: (3.34, 1.00), 2005: (2.34, 0.68), 2006: (5.03, 1.83),
    2007: (22.24, 6.91), 2008: (8.30, 3.27), 2009: (17.43, 10.04), 2010: (19.58, 13.89),
    2011: (15.43, 11.68), 2012: (16.36, 12.75), 2013: (17.87, 14.28), 2014: (26.23, 21.27),
    2015: (40.77, 30.66), 2016: (39.03, 29.08), 2017: (42.85, 32.47), 2018: (32.93, 25.89),
}
# Allen, Qian, Shan & Zhu (JF 2024), Table I Panel A column (1): listed A-share firms.
# Their source is Worldscope, not CSMAR, so only the 3% proportion tolerance applies.
ALLEN_TABLE1A = {
    2000: 1062, 2001: 1143, 2002: 1205, 2003: 1267, 2004: 1356, 2005: 1352, 2006: 1435,
    2007: 1548, 2008: 1603, 2009: 1751, 2010: 2106, 2011: 2341, 2012: 2470, 2013: 2515,
    2014: 2632, 2015: 2823, 2016: 3118, 2017: 3495, 2018: 3591,
}

COUNT_TOL_PCT = 3.0  # lighthouse.md 3.3: counts compared as proportions, within 3 pp
DAILY_START = pd.Period("1999-12", "M")  # the daily download starts in 1999-12


class CheckFailed(AssertionError):
    pass


def _report(name: str, ok: bool, detail: str, failures: list[str]) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    if not ok:
        failures.append(name)


def check_monthly_vs_daily(failures: list[str]) -> pd.DataFrame:
    """Monthly dividend-reinvested return (Mretwd) vs the compounded daily return (Dretwd).

    Also answers how CSMAR treats full-month suspensions: if the resumption month's return
    equals the compounded daily returns of that month alone, the resumption-day daily return
    must be measured from the last pre-suspension close, so no return is lost.
    """
    d = read_raw("TRD_Dalyr", columns=["Stkcd", "Trddt", "Dretwd"]).drop(columns="_chunk")
    d["month"] = pd.PeriodIndex(d["Trddt"].str.slice(0, 7), freq="M")
    d["lr"] = np.log1p(d["Dretwd"].astype(float))
    g = d.groupby(["Stkcd", "month"])
    comp = pd.DataFrame({"ret_daily": np.expm1(g["lr"].sum(min_count=1)), "n_days": g.size()})
    comp = comp.reset_index().rename(columns={"Stkcd": "stkcd"})

    m = load("stock_month")
    m = m[m["month"] >= DAILY_START]
    x = m.merge(comp, on=["stkcd", "month"], how="outer", indicator=True)
    unmatched = (x["_merge"] != "both").sum()
    _report("monthly/daily key coverage", unmatched == 0,
            f"{unmatched} stock-months present in only one of the two tables", failures)
    x = x[x["_merge"] == "both"]
    x["abs_diff"] = (x["ret"] - x["ret_daily"]).abs()

    rows = []
    groups = {
        "continuing (gap=1)": x["month_gap"].eq(1),
        "after full-month suspension (gap>1)": x["month_gap"].gt(1),
        "first traded month": x["month_gap"].isna(),
    }
    for label, mask in groups.items():
        sub = x[mask.fillna(False)]
        valid = sub.dropna(subset=["ret", "ret_daily"])
        rows.append({
            "group": label, "n": len(sub), "n_both_nonmissing": len(valid),
            "share_abs_diff_lt_1e-4": (valid["abs_diff"] < 1e-4).mean() if len(valid) else np.nan,
            "ret_missing_share": sub["ret"].isna().mean(),
        })
    out = pd.DataFrame(rows)
    cont = out.iloc[0]
    _report("monthly = compounded daily (continuing months)", cont["share_abs_diff_lt_1e-4"] >= 0.999,
            f"{cont['share_abs_diff_lt_1e-4']:.5f} of {cont['n_both_nonmissing']:,} within 1e-4", failures)
    gap = out.iloc[1]
    _report("monthly = compounded daily (resumption months)", gap["share_abs_diff_lt_1e-4"] >= 0.999,
            f"{gap['share_abs_diff_lt_1e-4']:.5f} of {gap['n_both_nonmissing']:,} within 1e-4", failures)
    first = out.iloc[2]
    _report("first traded month has no monthly return", first["ret_missing_share"] == 1.0,
            f"missing share {first['ret_missing_share']:.3f} (CSMAR leaves the IPO month blank)", failures)
    days_ok = (x["trading_days"] == x["n_days"]).mean()
    _report("trading-day counts agree", days_ok >= 0.9999, f"{days_ok:.6f}", failures)
    return out


def _year_end_sample() -> pd.DataFrame:
    """A-share stocks trading in December, with year-end status and market values."""
    m = load("stock_month")  # carries the st_month columns (panels.stock_month)
    dec = m[m["is_a_share"] & (m["month"].dt.month == 12)].copy()
    dec["year"] = dec["month"].dt.year
    return dec


def check_li_counts(failures: list[str]) -> pd.DataFrame:
    dec = _year_end_sample()
    li = dec[~dec["is_financial"] & dec["trdsta_end"].eq(1)]
    by_board = li.groupby(["year", "board"])["stkcd"].nunique().unstack(fill_value=0)
    mv = li.groupby("year")[["mv_total", "mv_float"]].sum() / 1e12
    rows = []
    for year, (tot, sh, sz, sme, gem) in LI_TABLE1A.items():
        ours = by_board.loc[year] if year in by_board.index else pd.Series(dtype=float)
        rows.append({
            "year": year, "paper_total": tot, "ours_total": int(ours.sum()),
            "paper_sh": sh, "ours_sh": int(ours.get("SH_MAIN", 0)),
            "paper_sz": sz, "ours_sz": int(ours.get("SZ_MAIN", 0)),
            "paper_sme": sme, "ours_sme": int(ours.get("SZ_SME", 0)),
            "paper_gem": gem, "ours_gem": int(ours.get("CHINEXT", 0)),
            "paper_tmv": LI_TABLE1A_MV[year][0], "ours_tmv": mv["mv_total"].get(year, np.nan),
            "paper_cmv": LI_TABLE1A_MV[year][1], "ours_cmv": mv["mv_float"].get(year, np.nan),
        })
    out = pd.DataFrame(rows)
    out["total_pct_diff"] = (out["ours_total"] / out["paper_total"] - 1) * 100
    out["tmv_pct_diff"] = (out["ours_tmv"] / out["paper_tmv"] - 1) * 100
    out["cmv_pct_diff"] = (out["ours_cmv"] / out["paper_cmv"] - 1) * 100
    # All years are scored: the daily download covers 1999-12, so the year-end status
    # filter applies to the 1999 row too.
    scored = out
    worst = scored["total_pct_diff"].abs().max()
    _report("Li Table 1A stock counts 1999-2018", worst <= COUNT_TOL_PCT,
            f"max |diff| {worst:.2f}% (exact years: {(scored['total_pct_diff'] == 0).sum()}/{len(scored)})", failures)
    # Each board-year against its own count: 3% of that board's paper count; a board the
    # paper reports as empty (0) must be empty in ours too.
    board_ok, board_gap = True, 0
    for b in ("sh", "sz", "sme", "gem"):
        gap = (scored[f"ours_{b}"] - scored[f"paper_{b}"]).abs()
        board_gap = max(board_gap, int(gap.max()))
        allowed = scored[f"paper_{b}"] * COUNT_TOL_PCT / 100
        board_ok &= bool((gap <= allowed).all())
    _report("Li Table 1A counts by board 1999-2018", board_ok,
            f"max absolute gap in any board-year: {board_gap} stocks", failures)
    worst_mv = scored[["tmv_pct_diff", "cmv_pct_diff"]].abs().max().max()
    _report("Li Table 1A market values 1999-2018", worst_mv <= COUNT_TOL_PCT,
            f"max |diff| {worst_mv:.2f}%", failures)
    return out


def check_allen_counts(failures: list[str]) -> pd.DataFrame:
    """Allen et al. count firms listed in a year. "Listed" is measured as the stock's traded
    span covering the year: first traded month <= year <= last traded month. A stock
    suspended for the whole year is still listed, so it counts. The stricter "traded in at
    least one month of the year" count is reported alongside (column ours_traded_in_year)
    but is not the scored definition."""
    m = load("stock_month")
    a = m[m["is_a_share"]]
    span = a.groupby("stkcd")["month"].agg(["min", "max"])
    traded_years = a.assign(year=a["month"].dt.year).groupby("year")["stkcd"].nunique()
    rows = []
    for year, paper in ALLEN_TABLE1A.items():
        ours = int(((span["min"].dt.year <= year) & (span["max"].dt.year >= year)).sum())
        rows.append({"year": year, "paper": paper, "ours": ours,
                     "ours_traded_in_year": int(traded_years.get(year, 0))})
    out = pd.DataFrame(rows)
    out["pct_diff"] = (out["ours"] / out["paper"] - 1) * 100
    worst = out["pct_diff"].abs().max()
    _report("Allen Table I listed firms 2000-2018", worst <= COUNT_TOL_PCT,
            f"max |diff| {worst:.2f}% (source differs: Worldscope)", failures)
    return out


def yearly_counts() -> pd.DataFrame:
    """Year-end A-share counts 1999-2026 (lighthouse.md 4.2): all, non-financial, normal
    status (Li's sample), ST/*ST at year end, and other special status (reform prefixes)."""
    dec = _year_end_sample()
    dec = dec[dec["year"] >= 1999]
    g = dec.groupby("year")
    out = pd.DataFrame({
        "a_shares_trading_in_december": g["stkcd"].nunique(),
        "st_or_star_st_at_year_end": g["st_end"].sum(),
        "star_st_at_year_end": g["star_st_end"].sum(),
        "other_special_status_at_year_end": g.apply(
            lambda x: (x["trdsta_end"].ne(1) & ~x["st_end"].astype(bool)).sum(), include_groups=False),
        "li_sample_nonfinancial_normal": g.apply(
            lambda x: (~x["is_financial"] & x["trdsta_end"].eq(1)).sum(), include_groups=False),
    })
    out["st_share"] = out["st_or_star_st_at_year_end"] / out["a_shares_trading_in_december"]
    return out.reset_index()


def check_statements(failures: list[str]) -> pd.DataFrame:
    s = load("statements").merge(load("company_info")[["stkcd", "list_date"]], on="stkcd", how="left")
    s["lag_days"] = (s["announce_date"] - s["period_end"]).dt.days
    post = s[s["period_end"] >= s["list_date"]]
    rows = []
    for rt, sub in s.groupby("report_type"):
        p = post[post["report_type"] == rt]
        rows.append({
            "report_type": int(rt), "n": len(sub),
            "announce_match_share": sub["announce_date"].notna().mean(),
            "announce_match_share_post_listing": p["announce_date"].notna().mean(),
            "lag_median": sub["lag_days"].median(), "lag_p99": sub["lag_days"].quantile(0.99),
            "lag_max": sub["lag_days"].max(), "negative_lag": int((sub["lag_days"] < 0).sum()),
        })
    out = pd.DataFrame(rows)
    _report("statement disclosure dates matched (post-listing)",
            out["announce_match_share_post_listing"].min() >= 0.995,
            f"min share {out['announce_match_share_post_listing'].min():.4f}", failures)
    _report("no disclosure before period end", out["negative_lag"].sum() == 0,
            f"{out['negative_lag'].sum()} rows", failures)
    type_agree = (s["iar_report_type"].isna() | (s["iar_report_type"] == s["report_type"])).all()
    _report("report type from period end agrees with IAR_Rept type", bool(type_agree), "", failures)
    return out


def check_cpi_overlap(failures: list[str]) -> pd.DataFrame:
    """OECD vs NBS month-on-month CPI on the months both cover: the splice in panels.cpi()
    is only valid if the two agree (rounding of NBS to 0.1 allows small differences)."""
    from csmar.registry import RAW_EXTERNAL
    oecd = pd.read_csv(RAW_EXTERNAL / "fred" / "CHNCPIALLMINMEI.csv")
    oecd["month"] = pd.PeriodIndex(oecd["observation_date"].str.slice(0, 7), freq="M")
    lvl = oecd.set_index("month")["CHNCPIALLMINMEI"].astype(float)
    oecd_mom = (lvl / lvl.shift(1) * 100).dropna()
    nbs = pd.concat([pd.read_csv(RAW_EXTERNAL / "nbs" / f, encoding="utf-8-sig")
                     for f in ("nbs_cpi_mom_table_2021_2025.csv", "nbs_cpi_mom_table_2026.csv")])
    nbs = nbs[nbs["indicator"] == "居民消费价格指数(上月=100)"].copy()
    nbs["month"] = pd.PeriodIndex(nbs["month"], freq="M")
    nbs_mom = nbs.drop_duplicates("month").set_index("month")["value"].astype(float)
    both = pd.DataFrame({"oecd_mom": oecd_mom, "nbs_mom": nbs_mom}).dropna()
    both["abs_diff"] = (both["oecd_mom"] - both["nbs_mom"]).abs()
    worst = both["abs_diff"].max()
    _report("CPI splice: OECD vs NBS month-on-month on overlap", worst <= 0.25,
            f"{len(both)} months, max |diff| {worst:.3f} index points (NBS rounded to 0.1)", failures)
    return both.reset_index()


def check_keys(failures: list[str]) -> None:
    for name, key in [("stock_month", ["stkcd", "month"]), ("st_month", ["stkcd", "month"]),
                      ("statements", ["stkcd", "accper"]), ("company_info", ["stkcd"]),
                      ("risk_free_1y", ["month"]), ("cpi", ["month"])]:
        dups = load(name).duplicated(key).sum()
        _report(f"unique keys {name}", dups == 0, f"{dups} duplicates", failures)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    check_keys(failures)
    check_statements(failures).to_csv(OUT / "statements_disclosure.csv", index=False)
    check_cpi_overlap(failures).to_csv(OUT / "cpi_splice_overlap.csv", index=False)
    check_li_counts(failures).to_csv(OUT / "li_table1a_counts.csv", index=False)
    check_allen_counts(failures).to_csv(OUT / "allen_table1a_counts.csv", index=False)
    yearly_counts().to_csv(OUT / "yearly_counts_1999_2026.csv", index=False)
    check_monthly_vs_daily(failures).to_csv(OUT / "monthly_vs_daily_returns.csv", index=False)
    print(f"\n{len(failures)} failed check(s)" + (": " + ", ".join(failures) if failures else ""))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
