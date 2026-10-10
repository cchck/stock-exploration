"""Numbers LSY print in the main text rather than in a table (lighthouse.md 5 intro and 7.3:
every in-scope printed number gets a comparison row). Each function returns tidy rows for
table "TXT" with the section in the row label. Numbers that cannot be produced from our
data are listed in NOT_PRODUCIBLE with the reason; they appear in the comparison as info
rows so that the gap is visible rather than silent.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from replication.common.periods import Segment
from replication.common.stats import fama_macbeth, grs, mean_t, ols
from replication.lsy import anomalies, factors
from replication.lsy import tables as T

NOT_PRODUCIBLE = {
    ("S6.1", "rev_midprice_2012_2016_mean"): "needs daily best bid/ask (WIND); the CSMAR daily file has close prices only",
}


def _r(items, seg):
    return T._rows("TXT", seg, items)


def section4_text(seg: Segment) -> pd.DataFrame:
    """Section 4 (Table 2 text): correlation between the monthly logME and EP+ slopes in column
    (6) (printed 0.42), and the expected-return difference implied by a one-standard-
    deviation difference in EP+ in column (8) (printed 0.52% per month)."""
    p = T.panel()
    x = T.table2_regressors(p)
    x = x[x["eligible"] & seg.mask(x["month"])]
    r6 = fama_macbeth(x, "ret", T.TABLE2_SPECS["(6)"], nw_lags=4)
    corr = r6.coef_series["logME"].corr(r6.coef_series["EP+"])
    r8 = fama_macbeth(x, "ret", T.TABLE2_SPECS["(8)"], nw_lags=4)
    sd = x.groupby("month")["EP+"].std().mean()
    return _r([("S4:corr_slopes_logME_EP+_col6", "value", corr),
               ("S4:one_sd_EP+_effect_col8", "pct_per_month", r8.coef["EP+"] * sd * 100)], seg)


def section5_text(seg: Segment) -> pd.DataFrame:
    """Section 5.1-5.3 text:
    - negative-EP stocks: VW portfolio of negative-EP universe stocks regressed on MKT, SMB and a
      VMG built from positive-EP stocks only; slope on that VMG (printed -0.28, t -3.31);
    - share of negative-EP stocks in the universe, average across months (printed 15%);
    - the smallest 30% of stocks as a share of total market value (printed 7%);
    - section 5.3: GRS p-values of CH-3 alphas for FF-5's non-market factors (printed 0.88)
      and FF-5 alphas for SMB and VMG (printed 0.0003)."""
    p = T.panel()
    pm = p[seg.mask(p["month"])]
    u = pm[pm["in_universe"]]
    neg_share = (u["ep"] < 0).groupby(u["month"]).mean().mean() * 100
    q = p.assign(ep=p["ep"].where(p["ep"] > 0))  # VMG from the positive-EP sample only
    vmg_pos = factors.ch3(q)["vmg"]
    neg = u[u["ep"] < 0].assign(g=1)
    from replication.common.portfolios import weighted_returns
    neg_ret = weighted_returns(neg, ["g"], ret="ret", weight="me")[1]
    c3 = T.ch3_factors()
    df = pd.DataFrame({"y": neg_ret - c3["rf"], "MKT": c3["mkt"], "SMB": c3["smb"], "VMGpos": vmg_pos}).dropna()
    df = df[seg.mask(df.index.to_series())]
    r = ols(df["y"], df[["MKT", "SMB", "VMGpos"]], se="white")
    elig = pm[pm["eligible"]]
    small = elig.groupby("month")["me"].transform(lambda s: s <= s.quantile(0.3))
    cap_share = (elig["me"].where(small).groupby(elig["month"]).sum() / elig.groupby("month")["me"].sum()).mean() * 100

    f5 = factors.ff5(p)
    d = pd.DataFrame({"MKT": c3["mkt"], "SMB": c3["smb"], "VMG": c3["vmg"], "SMB5": f5["smb"], "HML": f5["hml"],
                      "RMW": f5["rmw"], "CMA": f5["cma"]}).dropna()
    d = d[seg.mask(d.index.to_series())]
    g1 = grs(d[["SMB5", "HML", "RMW", "CMA"]], d[["MKT", "SMB", "VMG"]])
    g2 = grs(d[["SMB", "VMG"]], d[["MKT", "SMB5", "HML", "RMW", "CMA"]])
    return _r([("S5.1:negEP_slope_on_positive_VMG", "b", r.params["VMGpos"]),
               ("S5.1:negEP_slope_on_positive_VMG", "t", r.tstats["VMGpos"]),
               ("S5.1:negEP_share_of_universe", "pct", neg_share),
               ("S5.2:bottom30_share_of_market_cap", "pct", cap_share),
               ("S5.3:GRS_CH3_on_FF5_nonmarket", "p", g1.pvalue),
               ("S5.3:GRS_FF5_on_SMB_VMG", "p", g2.pvalue)], seg)


def section6_text(seg: Segment) -> pd.DataFrame:
    """Section 6 text: universe size in 2000 and 2016, the annualized size premium, the
    size-neutral alpha increases, one-month and one-year reversal CAPM alphas (annualized),
    the dropped anomalies' CAPM alphas (investment, accruals/NOA, illiquidity) and
    illiquidity's CH-3 alpha, and section 6.2's average |alpha| over the eight anomalies CH-3
    explains (all but reversal and abnormal turnover)."""
    p = T.panel()
    c3 = T.ch3_factors()
    u = p[p["in_universe"]]
    n_by_month = u.groupby("month").size()
    first, last = n_by_month.loc[seg.start], n_by_month.loc[seg.end]
    smb_annual = mean_t(c3["smb"][seg.mask(c3.index.to_series())]).mean * 12 * 100

    def capm(series):
        df = pd.concat([series.rename("y"), c3["mkt"]], axis=1).dropna()
        df = df[seg.mask(df.index.to_series())] * 100
        return ols(df["y"], df[["mkt"]], se="white")

    def ch3a(series):
        df = pd.concat([series.rename("y"), c3[["mkt", "smb", "vmg"]]], axis=1).dropna()
        df = df[seg.mask(df.index.to_series())] * 100
        return ols(df["y"], df[["mkt", "smb", "vmg"]], se="white")

    t6 = T.table6(seg).pivot(index="row", columns="col", values="value")
    items = [("S6.1:universe_stocks_first_month", "n", float(first)),
             ("S6.1:universe_stocks_last_month", "n", float(last)),
             ("S6.1:size_premium_annual", "pct", smb_annual)]
    for key, label in (("roe", "ROE"), ("ep", "EP"), ("turn12", "12-month turnover")):
        items.append((f"S6.1:size_neutral_alpha_increase_{key}", "pct",
                      t6.loc[f"B:{key}", "alpha"] - t6.loc[f"A:{key}", "alpha"]))
    sp = T.anomaly_spreads()
    rev1 = capm(sp["A:rev"])
    items += [("S6.1:rev_1m_capm_alpha_annual", "pct", rev1.params["alpha"] * 12),
              ("S6.1:rev_1m_capm_alpha_annual", "t", rev1.tstats["alpha"])]
    seg12 = Segment("2012-2016", pd.Period("2012-01", "M"), min(seg.end, pd.Period("2016-12", "M")))
    # Defined only when 2012 lies in the segment; NaN otherwise, so every segment has the same rows.
    in_seg = seg.start <= seg12.start <= seg.end
    items.append(("S6.1:rev_close_2012_2016_mean", "pct",
                  sp["A:rev"][seg12.mask(sp.index.to_series())].mean() * 100 if in_seg else np.nan))
    extra = {}
    for key in anomalies.EXTRA_ANOMALIES:
        for neutral in (False, True):
            extra[(key, neutral)] = anomalies.monthly_sort_spread(p, key, size_neutral=neutral)
    r12 = capm(extra[("rev12", False)])
    items += [("S6.1:rev_12m_capm_alpha_annual", "pct", r12.params["alpha"] * 12),
              ("S6.1:rev_12m_capm_alpha_annual", "t", r12.tstats["alpha"])]
    inv_alpha = max(abs(capm(extra[("inv", n)]).params["alpha"]) for n in (False, True))
    acc_alpha = max(abs(capm(extra[(k, n)]).params["alpha"]) for k in ("accrual", "noa") for n in (False, True))
    illiq = [capm(extra[("illiq", n)]) for n in (False, True)]
    illiq_max = max(r.params["alpha"] for r in illiq)
    illiq_t = max(abs(r.tstats["alpha"]) for r in illiq)
    illiq_ch3 = ch3a(extra[("illiq", False)])
    items += [("S6.1:investment_max_abs_capm_alpha", "pct", inv_alpha),
              ("S6.1:accruals_max_abs_capm_alpha", "pct", acc_alpha),
              ("S6.1:illiquidity_max_capm_alpha", "pct", illiq_max),
              ("S6.1:illiquidity_max_capm_alpha", "max_abs_t", illiq_t),
              ("S6.2:illiquidity_ch3_alpha", "pct", illiq_ch3.params["alpha"]),
              ("S6.2:illiquidity_ch3_alpha", "t", illiq_ch3.tstats["alpha"])]
    eight = [k for k in anomalies.ANOMALIES if k not in ("rev", "abnturn")]
    for panel_id in ("A", "B"):
        keys = [k for k in eight if not (panel_id == "B" and k == "size")]
        for model, fn in (("CH-3", "T7"), ("FF-3", "T8")):
            tab = (T.table7(seg) if fn == "T7" else T.table8(seg)).pivot(index="row", columns="col", values="value")
            avg = np.mean([abs(tab.loc[f"{panel_id}:{k}", "alpha"]) for k in keys])
            items.append((f"S6.2:{panel_id}:avg_abs_alpha_8_explained", model, avg))
    return _r(items, seg)


def section7_text(seg: Segment) -> pd.DataFrame:
    """Section 7 text: CH-4 SMB and PMO annualized means (printed 11% and 12%), the average
    cross-sectional rank correlation between abnormal turnover and the 20-day return
    (printed 0.3), and the CH-4 summary for Table 10 (average |alpha| 0.30, average |t| 0.69,
    GRS10 p 0.41; Panel A), with Panel B computed alongside."""
    c4 = T.ch4_factors()
    f = c4[seg.mask(c4.index.to_series())]
    p = T.panel()
    u = p[p["in_universe"] & seg.mask(p["month"])].dropna(subset=["abn_turn", "rev20"])
    rc = u.groupby("month")[["abn_turn", "rev20"]].apply(lambda g: g["abn_turn"].rank().corr(g["rev20"].rank())).mean()
    items = [("S7.1:CH4_SMB_annual", "pct", f["smb"].mean() * 1200), ("S7.1:CH4_PMO_annual", "pct", f["pmo"].mean() * 1200),
             ("S7.2:rank_corr_abnturn_rev20", "value", rc)]
    sp = T.anomaly_spreads()
    X = T._model_factors("CH-4")
    for panel_id in ("A", "B"):
        cols = [c for c in sp.columns if c.startswith(f"{panel_id}:")]
        df = pd.concat([sp[cols], X], axis=1).dropna()
        df = df[seg.mask(df.index.to_series())] * 100
        res = [ols(df[c], df[X.columns], se="white") for c in cols]
        g = grs(df[cols], df[X.columns])
        items += [(f"T10:{panel_id}:avg_abs_alpha", "CH-4", float(np.mean([abs(r.params["alpha"]) for r in res]))),
                  (f"T10:{panel_id}:avg_abs_t", "CH-4", float(np.mean([abs(r.tstats["alpha"]) for r in res]))),
                  (f"T10:{panel_id}:GRS", "CH-4", g.stat), (f"T10:{panel_id}:p", "CH-4", g.pvalue)]
    return _r(items, seg)


def table4_text(seg: Segment) -> pd.DataFrame:
    """Table 4 text: average R-squared of industry portfolios on MKT alone and on CH-3 (printed
    72% and 82%, Shenyin-Wanguo 37 industries) and of anomaly decile portfolios (printed 85%
    and 90%). Industries here are CSRC 2012 divisions (two-digit codes, merged into their
    section when a division has fewer than 10 stocks): Shenyin-Wanguo classifications are
    not in our data (deviation_log LSY-8). Anomaly deciles: the ten month-end-sorted anomalies
    (reversal is built from daily slices and has no month-end decile portfolios)."""
    p = T.panel()
    c3 = T.ch3_factors()
    from csmar.panels import load
    ci = load("company_info")[["stkcd", "csrc2012"]]
    u = p[p["eligible"] & seg.mask(p["month"])].merge(ci, on="stkcd", how="left").dropna(subset=["csrc2012", "ret"])
    u["div"] = u["csrc2012"].str.slice(0, 3)
    small = u.groupby("div")["stkcd"].nunique()
    u.loc[u["div"].isin(small[small < 10].index), "div"] = u["csrc2012"].str.slice(0, 1)
    from replication.common.portfolios import weighted_returns
    ind = weighted_returns(u, ["div"], ret="ret", weight="me")

    def avg_r2(port: pd.DataFrame) -> tuple[float, float]:
        r_m, r_3 = [], []
        for c in port:
            df = pd.concat([(port[c] - c3["rf"]).rename("y"), c3[["mkt", "smb", "vmg"]]], axis=1).dropna()
            df = df[seg.mask(df.index.to_series())]
            if len(df) < 36:
                continue
            r_m.append(ols(df["y"], df[["mkt"]], se="classic").r2)
            r_3.append(ols(df["y"], df[["mkt", "smb", "vmg"]], se="classic").r2)
        return float(np.mean(r_m)) * 100, float(np.mean(r_3)) * 100

    im, i3 = avg_r2(ind)
    decs = pd.concat([anomalies.monthly_sort_deciles(p, k, size_neutral=False).add_prefix(f"{k}_")
                      for k in anomalies.ANOMALIES if k != "rev"], axis=1)
    dm, d3 = avg_r2(decs)
    return _r([("T4text:industries_avg_R2", "MKT", im), ("T4text:industries_avg_R2", "CH-3", i3),
               ("T4text:industries", "n", float(ind.shape[1])),
               ("T4text:anomaly_deciles_avg_R2", "MKT", dm), ("T4text:anomaly_deciles_avg_R2", "CH-3", d3)], seg)


def figure_text(f2: pd.DataFrame, seg: Segment) -> pd.DataFrame:
    """Section 3.3 text on Figure 2: S/V range (printed 10%-60%), the growth factor of S over
    the sample (printed fivefold), and the average one-year deposit rate 2007-2016 (printed 3%)."""
    s = f2["S"].dropna()
    s = s[s > 0]
    growth = s.iloc[-20:].mean() / s.iloc[:20].mean() if len(s) > 40 else np.nan
    from csmar.readers import read_raw
    r = read_raw("TRD_Nrrate", columns=["Nrr1", "Clsdt", "Nrrdata"])
    r = r[r["Nrr1"] == "NRI01"]
    rate = pd.Series(r["Nrrdata"].astype(float).to_numpy(), index=pd.to_datetime(r["Clsdt"])).sort_index()
    rate = rate[~rate.index.duplicated(keep="last")]
    days = pd.date_range("2007-01-01", "2016-12-31", freq="D")
    avg_rate = rate.reindex(rate.index.union(days)).ffill().reindex(days).mean()
    return _r([("S3.3:S_over_V", "min_pct", f2["S_over_V"].min() * 100), ("S3.3:S_over_V", "max_pct", f2["S_over_V"].max() * 100),
               ("S3.3:shell_value_growth_factor", "x", growth),
               ("S3.3:avg_one_year_deposit_rate_2007_2016", "pct", avg_rate)], seg)


def all_text(seg: Segment) -> pd.DataFrame:
    return pd.concat([section4_text(seg), section5_text(seg), section6_text(seg), section7_text(seg),
                      table4_text(seg)], ignore_index=True)
