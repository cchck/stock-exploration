"""LSY tables. Each function takes a Segment (replication.common.periods) and returns a tidy
DataFrame with one row per reported number: table, row, col, value. The same function
produces the original, extended and full-sample versions (lighthouse.md section 6).
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from csmar.registry import INTERIM
from replication.common.periods import DATA_END, Segment, segments
from replication.common.stats import mean_t, ols
from replication.lsy import data, factors

PAPER_START, PAPER_END = "2000-01", "2016-12"
PANEL_CACHE = INTERIM / "lsy_panel.parquet"


def lsy_segments() -> dict[str, Segment]:
    return segments(PAPER_START, PAPER_END)


@lru_cache(maxsize=1)
def panel(rebuild: bool = False) -> pd.DataFrame:
    """The LSY holding-month panel, cached under data/interim (firm-level: never committed)."""
    if PANEL_CACHE.exists() and not rebuild:
        return pd.read_parquet(PANEL_CACHE)
    p = data.build_panel()
    PANEL_CACHE.parent.mkdir(parents=True, exist_ok=True)
    p.to_parquet(PANEL_CACHE, index=False)
    return p


@lru_cache(maxsize=1)
def ch4_factors() -> pd.DataFrame:
    return factors.ch4(panel())


@lru_cache(maxsize=1)
def ch3_factors() -> pd.DataFrame:
    return factors.ch3(panel())


def _rows(table: str, seg: Segment, items: list[tuple[str, str, float]]) -> pd.DataFrame:
    return pd.DataFrame([{"table": table, "segment": seg.name, "start": str(seg.start), "end": str(seg.end),
                          "row": r, "col": c, "value": v} for r, c, v in items])


def table3(seg: Segment) -> pd.DataFrame:
    """Table 3: CH-3 factor means, standard deviations, t-statistics (plain), correlations,
    in percent per month; plus the two-factor alphas quoted in the text (section 5.1,
    White t-statistics)."""
    f = ch3_factors()
    f = f[seg.mask(f.index.to_series())][["mkt", "smb", "vmg"]] * 100
    items = []
    names = {"mkt": "MKT", "smb": "SMB", "vmg": "VMG"}
    for c in f:
        st = mean_t(f[c])
        items += [(names[c], "mean", st.mean), (names[c], "std", st.std), (names[c], "t", st.t)]
    corr = f.corr()
    for a in f:
        for b in f:
            items.append((names[a], f"corr_{names[b]}", corr.loc[a, b]))
    for c in f:
        others = [o for o in f if o != c]
        r = ols(f[c], f[others], se="white")
        items += [(names[c], "alpha_2f", r.params["alpha"]), (names[c], "t_alpha_2f", r.tstats["alpha"])]
    items.append(("all", "n_months", float(len(f))))
    return _rows("T3", seg, items)


def factor_series_check(seg: Segment | None = None) -> pd.DataFrame:
    """Month-by-month comparison with Stambaugh's published series (lighthouse.md 3.3:
    correlation >= 0.95 over 2000-01..2021-12). CH-4 monthly series are published; CH-3
    monthly series are compounded from the published daily file."""
    seg = seg or Segment("stambaugh_overlap", pd.Period("2000-01", "M"), DATA_END["stambaugh"])
    ours4, web4 = ch4_factors(), factors.stambaugh_monthly()
    ours3, web3 = ch3_factors(), factors.stambaugh_ch3_monthly()
    items = []
    for model, ours, web, cols in (("CH-4", ours4, web4, ["rf", "mkt", "smb", "vmg", "pmo"]),
                                   ("CH-3", ours3, web3, ["rf", "mkt", "smb", "vmg"])):
        x = ours[cols].join(web[cols], rsuffix="_web", how="inner")
        x = x[seg.mask(x.index.to_series())]
        for c in cols:
            items += [(f"{model} {c}", "corr", x[c].corr(x[f"{c}_web"])),
                      (f"{model} {c}", "mean_ours_pct", x[c].mean() * 100),
                      (f"{model} {c}", "mean_web_pct", x[f"{c}_web"].mean() * 100),
                      (f"{model} {c}", "n_months", float(len(x)))]
    return _rows("factor_check", seg, items)


# Table 2 specifications: column -> regressors (paper's column numbering)
TABLE2_SPECS = {
    "(1)": ["beta"],
    "(2)": ["logME"],
    "(3)": ["beta", "logME"],
    "(4)": ["beta", "logME", "logBM"],
    "(5)": ["beta", "logME", "logAM"],
    "(6)": ["beta", "logME", "EP+", "D(EP<0)"],
    "(7)": ["beta", "logME", "CP+", "D(CP<0)"],
    "(8)": ["beta", "logME", "logBM", "logAM", "EP+", "D(EP<0)", "CP+", "D(CP<0)"],
    "(9)": ["beta", "logME", "logBM", "EP+", "D(EP<0)"],
}


def table2_regressors(p: pd.DataFrame) -> pd.DataFrame:
    """Table 2 regressors from end-of-(t-1) characteristics.

    - logME: log of total A-share market value in millions of yuan. The unit only moves the
      intercept; millions is the unit consistent with the paper's intercept (0.058 with a
      logME slope of -0.0049 implies a typical logME near 9).
    - logBM, logAM: logs of positive ratios; a firm with non-positive book equity has no
      logBM and drops out of the specifications that include it (Fama and French 1992).
    - EP+ = EP if EP > 0 else 0; D(EP<0) = 1 if EP < 0; CP+ and D(CP<0) likewise.
    """
    import numpy as np
    out = p[["stkcd", "month", "ret", "in_universe", "eligible", "beta"]].copy()
    out["logME"] = np.log(p["me"] / 1e6)
    out["logBM"] = np.log(p["bm"].where(p["bm"] > 0))
    out["logAM"] = np.log(p["am"].where(p["am"] > 0))
    out["EP+"] = p["ep"].clip(lower=0)
    out["D(EP<0)"] = (p["ep"] < 0).astype(float).where(p["ep"].notna())
    out["CP+"] = p["cp"].clip(lower=0)
    out["D(CP<0)"] = (p["cp"] < 0).astype(float).where(p["cp"].notna())
    return out


def table2(seg: Segment, *, sample: str = "eligible") -> pd.DataFrame:
    """Table 2: Fama-MacBeth slopes (decimal monthly returns), Newey-West (4 lags) t-statistics,
    and the average adjusted R-squared.

    sample="eligible" (default): all stocks passing the listing/trading filters, smallest
    30% kept. sample="universe": smallest 30% excluded, as section 4's text states.
    The default follows the printed numbers, not the text: with the smallest 30% kept,
    68 of 80 scored Table 2 numbers match (size slope -0.0051, t -2.87 vs printed -0.0049,
    -2.91); with them excluded, 55 of 80 match and the size slope halves (deviation_log LSY-3).
    """
    from replication.common.stats import fama_macbeth
    p = panel()
    x = table2_regressors(p)
    keep = {"universe": x["in_universe"], "eligible": x["eligible"]}[sample]
    x = x[keep & seg.mask(x["month"])]
    items = []
    for col, regs in TABLE2_SPECS.items():
        r = fama_macbeth(x, "ret", regs, nw_lags=4)
        items.append(("Intercept", col, r.coef["const"]))
        items.append(("t(Intercept)", col, r.tstats["const"]))
        for v in regs:
            items += [(v, col, r.coef[v]), (f"t({v})", col, r.tstats[v])]
        items.append(("R2", col, r.avg_adj_r2))
    return _rows("T2", seg, items)


# ---------------------------------------------------------------------------------------------
# Section 5.2, Table 5: mutual pricing of CH-3 and FF-3
# ---------------------------------------------------------------------------------------------

@lru_cache(maxsize=1)
def ff3_factors() -> pd.DataFrame:
    return factors.ff3(panel())


def table5(seg: Segment) -> pd.DataFrame:
    """Table 5: alphas (% per month, White t) of each model's size and value factors with
    respect to the other model, and GRS tests of joint zero alphas."""
    from replication.common.stats import grs
    c3, f3 = ch3_factors(), ff3_factors()
    df = pd.DataFrame({"MKT": c3["mkt"], "SMB": c3["smb"], "VMG": c3["vmg"],
                       "FFSMB": f3["smb"], "FFHML": f3["hml"]}).dropna()
    df = df[seg.mask(df.index.to_series())] * 100
    items = []
    for y in ("FFSMB", "FFHML"):
        r = ols(df[y], df[["MKT", "SMB", "VMG"]], se="white")
        items += [(y, "alpha_CH3", r.params["alpha"]), (y, "t_alpha_CH3", r.tstats["alpha"])]
    for y in ("SMB", "VMG"):
        r = ols(df[y], df[["MKT", "FFSMB", "FFHML"]], se="white")
        items += [(y, "alpha_FF3", r.params["alpha"]), (y, "t_alpha_FF3", r.tstats["alpha"])]
    g1 = grs(df[["FFSMB", "FFHML"]], df[["MKT", "SMB", "VMG"]])
    g2 = grs(df[["SMB", "VMG"]], df[["MKT", "FFSMB", "FFHML"]])
    items += [("FFSMB+FFHML", "GRS_CH3", g1.stat), ("FFSMB+FFHML", "p_CH3", g1.pvalue),
              ("SMB+VMG", "GRS_FF3", g2.stat), ("SMB+VMG", "p_FF3", g2.pvalue)]
    return _rows("T5", seg, items)


def section52(seg: Segment) -> pd.DataFrame:
    """Section 5.2: factors built without the shell cut, and the alphas of the shell-free SMB
    and VMG with respect to the three shell-inclusive factors."""
    sh = factors.ch3(factors.with_shells(panel()))
    base = ch3_factors()
    df = pd.DataFrame({"MKT_s": sh["mkt"], "SMB_s": sh["smb"], "VMG_s": sh["vmg"],
                       "SMB": base["smb"], "VMG": base["vmg"]}).dropna()
    df = df[seg.mask(df.index.to_series())] * 100
    items = [("SMB_with_shells", "mean", df["SMB_s"].mean()), ("VMG_with_shells", "mean", df["VMG_s"].mean())]
    for y in ("SMB", "VMG"):
        r = ols(df[y], df[["MKT_s", "SMB_s", "VMG_s"]], se="white")
        items += [(y, "alpha_vs_shell_factors", r.params["alpha"]), (y, "t_alpha_vs_shell_factors", r.tstats["alpha"])]
    return _rows("S5.2", seg, items)


# ---------------------------------------------------------------------------------------------
# Tables 6-10: anomalies
# ---------------------------------------------------------------------------------------------

ANOMALY_CACHE = INTERIM / "lsy_anomaly_spreads.parquet"


@lru_cache(maxsize=1)
def anomaly_spreads(rebuild: bool = False) -> pd.DataFrame:
    """Monthly long-short spreads, columns 'A:<key>' (unconditional) and 'B:<key>' (size-neutral),
    decimal. Cached under data/interim because the daily reversal construction is slow."""
    from replication.lsy import anomalies
    if ANOMALY_CACHE.exists() and not rebuild:
        out = pd.read_parquet(ANOMALY_CACHE)
        out.index = pd.PeriodIndex(out.index, freq="M")
        return out
    a = anomalies.all_spreads(panel(), size_neutral=False).add_prefix("A:")
    b = anomalies.all_spreads(panel(), size_neutral=True).add_prefix("B:")
    out = a.join(b, how="outer")
    out.index.name = "month"
    saved = out.copy()
    saved.index = saved.index.astype(str)
    saved.to_parquet(ANOMALY_CACHE)
    return out


def _model_factors(model: str) -> pd.DataFrame:
    c4, c3, f3 = ch4_factors(), ch3_factors(), ff3_factors()
    if model == "CAPM":
        return pd.DataFrame({"b_mkt": c3["mkt"]})
    if model == "CH-3":
        return pd.DataFrame({"b_mkt": c3["mkt"], "b_smb": c3["smb"], "b_vmg": c3["vmg"]})
    if model == "FF-3":
        return pd.DataFrame({"b_mkt": c3["mkt"], "b_smb": f3["smb"], "b_hml": f3["hml"]})
    if model == "CH-4":
        return pd.DataFrame({"b_mkt": c4["mkt"], "b_smb": c4["smb"], "b_vmg": c4["vmg"], "b_pmo": c4["pmo"]})
    if model == "Unadjusted":
        return pd.DataFrame(index=c3.index)
    raise ValueError(model)


def _anomaly_regressions(seg: Segment, model: str, table: str) -> pd.DataFrame:
    sp = anomaly_spreads()
    X = _model_factors(model)
    items = []
    for col in sp.columns:
        panel_id, key = col.split(":")
        df = pd.concat([sp[col].rename("y"), X], axis=1).dropna()
        df = df[seg.mask(df.index.to_series())] * 100
        if model == "CAPM" and table == "T6":
            items += [(f"{panel_id}:{key}", "Rbar", df["y"].mean()),
                      (f"{panel_id}:{key}", "t(Rbar)", mean_t(df["y"]).t)]
        r = ols(df["y"], df.drop(columns="y"), se="white")
        names = {"alpha": "alpha", **{c: c for c in X.columns}}
        if model == "CAPM":
            names["b_mkt"] = "beta"
        for k, v in r.params.items():
            items += [(f"{panel_id}:{key}", names[k], v), (f"{panel_id}:{key}", f"t({names[k]})", r.tstats[k])]
    return _rows(table, seg, items)


def table6(seg: Segment) -> pd.DataFrame:
    return _anomaly_regressions(seg, "CAPM", "T6")


def table7(seg: Segment) -> pd.DataFrame:
    return _anomaly_regressions(seg, "CH-3", "T7")


def table8(seg: Segment) -> pd.DataFrame:
    return _anomaly_regressions(seg, "FF-3", "T8")


def table10(seg: Segment) -> pd.DataFrame:
    return _anomaly_regressions(seg, "CH-4", "T10")


def table9(seg: Segment) -> pd.DataFrame:
    """Table 9: average |alpha|, average |t(alpha)|, GRS (all anomalies; and the seven that
    exclude size, EP and BM) for Unadjusted, CAPM, FF-3 and CH-3."""
    from replication.common.stats import grs
    sp = anomaly_spreads()
    items = []
    for panel_id, n_all in (("A", 10), ("B", 9)):
        cols = [c for c in sp.columns if c.startswith(f"{panel_id}:")]
        seven = [c for c in cols if c.split(":")[1] not in ("size", "ep", "bm")]
        for model in ("Unadjusted", "CAPM", "FF-3", "CH-3"):
            X = _model_factors(model)
            df = pd.concat([sp[cols], X], axis=1).dropna()
            df = df[seg.mask(df.index.to_series())] * 100
            alphas, ts = [], []
            for c in cols:
                if model == "Unadjusted":
                    st = mean_t(df[c])
                    alphas.append(st.mean)
                    ts.append(st.t)
                else:
                    r = ols(df[c], df[X.columns], se="white")
                    alphas.append(r.params["alpha"])
                    ts.append(r.tstats["alpha"])
            items += [(f"{panel_id}:avg_abs_alpha", model, float(np.mean(np.abs(alphas)))),
                      (f"{panel_id}:avg_abs_t", model, float(np.mean(np.abs(ts))))]
            fac = df[X.columns] if len(X.columns) else pd.DataFrame(index=df.index)
            for name, cs in ((f"GRS{n_all}", cols), ("GRS7", seven)):
                g = _grs_any(df[cs], fac)
                p_name = "p" + name[3:]
                items += [(f"{panel_id}:{name}", model, g[0]), (f"{panel_id}:{p_name}", model, g[1])]
    return _rows("T9", seg, items)


def _grs_any(assets: pd.DataFrame, fac: pd.DataFrame) -> tuple[float, float]:
    """GRS with K factors, or with no factors (Unadjusted): the Hotelling T^2 test of zero
    means, F = (T-N)/(N(T-1)) * T * m' S^-1 m with S the sample covariance."""
    from scipy import stats as sps
    from replication.common.stats import grs
    if fac.shape[1]:
        g = grs(assets, fac)
        return g.stat, g.pvalue
    R = assets.dropna().to_numpy(float)
    T, N = R.shape
    m = R.mean(axis=0)
    S = np.cov(R, rowvar=False)
    f = (T - N) / (N * (T - 1)) * T * m @ np.linalg.solve(S, m)
    return float(f), float(sps.f.sf(f, N, T - N))


# ---------------------------------------------------------------------------------------------
# Table 4: average R-squared of individual stocks on CH-3 factors
# ---------------------------------------------------------------------------------------------

TABLE4_MODELS = {"MKT": ["mkt"], "MKT, SMB": ["mkt", "smb"], "MKT, VMG": ["mkt", "vmg"], "MKT, SMB, VMG": ["mkt", "smb", "vmg"]}


def _rolling_r2(y: np.ndarray, X: np.ndarray, window: int) -> np.ndarray:
    """R-squared of OLS(y on [1, X]) over every trailing window of `window` rows (rows of
    one stock, consecutive calendar months). NaN unless all rows in the window are complete."""
    n, k = X.shape
    ok = ~np.isnan(y) & ~np.isnan(X).any(axis=1)
    Z = np.column_stack([np.ones(n), np.where(ok[:, None], X, 0.0)])
    yz = np.where(ok, y, 0.0)

    def roll(v):
        cs = np.concatenate([np.zeros((1,) + v.shape[1:]), np.cumsum(v, axis=0)])
        return cs[window:] - cs[:-window]

    cnt = roll(ok.astype(float))
    zz = roll(Z[:, :, None] * Z[:, None, :])
    zy = roll(Z * yz[:, None])
    yy = roll(yz * yz)
    sy = roll(yz)
    out = np.full(n, np.nan)
    full = cnt == window
    if full.any():
        b = np.linalg.solve(zz[full], zy[full][..., None])[..., 0]
        sse = yy[full] - np.einsum("ij,ij->i", b, zy[full])
        sst = yy[full] - sy[full] ** 2 / window
        out[window - 1:][full] = 1 - sse / sst
    return out


def table4(seg: Segment, window: int = 36) -> pd.DataFrame:
    """Table 4: for each stock, 36-month rolling regressions of monthly excess returns on the
    factors; R-squared averaged over time per stock, then across stocks.

    Panel A ("all individual stocks", codes 60/30/00): every window with 36 complete months.
    Panel B ("all but the smallest 30%"): windows in which the stock is in the universe (top
    70% after filters) in every one of the 36 months. This reading reproduces the paper's
    ordering (B above A); counting a window when the stock is in the universe only at its
    last month puts B below A (deviation_log LSY-4). Windows lie inside the segment.
    """
    p = panel()
    f = ch3_factors()[["mkt", "smb", "vmg", "rf"]]
    months = pd.period_range(seg.start, seg.end, freq="M")
    d = p[p["month"].isin(months)][["stkcd", "month", "ret", "in_universe"]]
    grid = pd.MultiIndex.from_product([d["stkcd"].unique(), months], names=["stkcd", "month"])
    d = d.set_index(["stkcd", "month"]).reindex(grid).reset_index()
    d = d.merge(f, left_on="month", right_index=True, how="left")
    d["exret"] = d["ret"] - d["rf"]
    u = d["in_universe"].astype("boolean").fillna(False).astype(float)
    d["u_share"] = u.groupby(d["stkcd"]).transform(lambda x: x.rolling(window).mean())
    groups = d.groupby("stkcd").indices
    items = []
    for label, cols in TABLE4_MODELS.items():
        r2 = np.full(len(d), np.nan)
        for idx in groups.values():
            r2[idx] = _rolling_r2(d["exret"].to_numpy()[idx], d[cols].to_numpy()[idx], window)
        d["r2"] = r2
        for panel_id, mask in (("A", pd.Series(True, index=d.index)), ("B", d["u_share"].eq(1))):
            per_stock = d[mask & d["r2"].notna()].groupby("stkcd")["r2"].mean()
            items.append((f"{panel_id}:{label}", "avg_R2_pct", float(per_stock.mean()) * 100))
    return _rows("T4", seg, items)


# ---------------------------------------------------------------------------------------------
# Table 1: return reactions to earnings surprises across size groups (China columns)
# ---------------------------------------------------------------------------------------------

def sue_events() -> pd.DataFrame:
    """Earnings events with standardized unexpected earnings (section 3.4).

    SUE = (E_q - E_{q-4}) / std of that year-over-year change over the last eight quarters
    (including q, eight non-missing changes required). E_q is single-quarter earnings
    excluding non-recurring items (the same series as EP), so events start in 2002 when
    quarterly reports begin, and SUE is first available about two years later.
    """
    e = data.earnings_announcements()
    e = e[e["announce_date"] >= data.QUARTERLY_FROM].copy()
    e["q"] = e["fiscal_year"] * 4 + e["report_type"].astype(int)
    e = e.drop_duplicates(["stkcd", "q"]).set_index(["stkcd", "q"]).sort_index()
    prev = e["earnings"].rename("prev")  # E_{q-4}: shift the quarter index forward by four
    prev.index = pd.MultiIndex.from_arrays([prev.index.get_level_values(0), prev.index.get_level_values(1) + 4])
    e = e.join(prev, how="left")
    e["delta"] = e["earnings"] - e["prev"]
    # rolling std over the last eight quarters of the same stock, on a complete quarter grid
    out = []
    for s, g in e.groupby(level=0):
        qs = g.index.get_level_values(1)
        full = pd.Series(np.nan, index=np.arange(qs.min(), qs.max() + 1))
        full.loc[qs] = g["delta"].to_numpy()
        sd = full.rolling(8, min_periods=8).std()
        gg = g.reset_index()
        gg["sigma"] = sd.reindex(gg["q"]).to_numpy()
        out.append(gg)
    ev = pd.concat(out, ignore_index=True)
    ev["sue"] = ev["delta"] / ev["sigma"].where(ev["sigma"] > 0)
    return ev.dropna(subset=["sue"])[["stkcd", "announce_date", "sue", "report_type"]]


def table1(seg: Segment, *, max_gap_days: int | None = 15, winsor: float | None = None) -> pd.DataFrame:
    """Table 1 (China): panel regression R_{t-k,t+k} = a + b SUE within size groups.

    - t is the first trading day of the stock on or after the announcement date.
    - R is the stock's compounded return over its trading days t-k..t+k minus the compounded
      value-weighted market return over the same days (market as in the beta module).
    - Size groups: bottom 30%, middle 40%, top 30% of the previous month-end market value
      across all stocks with codes 60/30/00 (the whole universe, shell stocks included).
    - b is multiplied by 100; White t-statistics; R-squared reported in percent.
    - max_gap_days=15: windows containing a trading gap longer than 15 calendar days (a
      suspension; holiday closures are at most about 10 days) are excluded. Without this,
      an announcement made during a suspension is credited with the whole price move at
      resumption and the small/middle groups' t-statistics collapse (Middle 2.8 vs printed
      12.4); with it the printed pattern is reproduced (deviation_log LSY-5). The paper's
      own filters exclude returns that follow long suspensions for the same reason (A.1).
    """
    from csmar.panels import daily as load_daily, load
    from replication.lsy.beta import market_daily
    ev = sue_events()
    ev = ev[(ev["announce_date"].dt.to_period("M") >= seg.start) & (ev["announce_date"].dt.to_period("M") <= seg.end)]
    d = load_daily(["Dretwd", "Dsmvtll"])
    d = d[d["stkcd"].str.slice(0, 2).isin(["60", "30", "00"]) & d["board"].isin(["SH_MAIN", "SZ_MAIN", "SZ_SME", "CHINEXT"])]
    d["Dretwd"] = d["Dretwd"].astype(float)
    mkt = market_daily(d)
    d = d.sort_values(["stkcd", "date"]).reset_index(drop=True)
    d["lr"] = np.log1p(d["Dretwd"]).fillna(0.0)
    d["lm"] = np.log1p(d["date"].map(mkt)).fillna(0.0)
    starts = d.groupby("stkcd").cumcount().to_numpy()
    starts = np.arange(len(d)) - starts
    ends = starts + d.groupby("stkcd")["date"].transform("size").to_numpy() - 1
    cs_r = np.concatenate([[0.0], np.cumsum(d["lr"].to_numpy())])
    cs_m = np.concatenate([[0.0], np.cumsum(d["lm"].to_numpy())])

    # event day position: first record of the stock on or after the announcement date
    pos = []
    blocks = d.groupby("stkcd").indices
    dates = d["date"].to_numpy()
    for s, a in zip(ev["stkcd"], ev["announce_date"].to_numpy()):
        idx = blocks.get(s)
        if idx is None:
            pos.append(-1)
            continue
        j = np.searchsorted(dates[idx[0]:idx[-1] + 1], a, side="left")
        pos.append(idx[0] + j if j < len(idx) else -1)
    ev = ev.assign(pos=np.array(pos))
    ev = ev[ev["pos"] >= 0].copy()

    # size group from the previous month-end market value, all 60/30/00 A shares
    m = load("stock_month")
    m = m[m["is_a_share"] & m["stkcd"].str.slice(0, 2).isin(["60", "30", "00"])][["stkcd", "month", "mv_total"]]
    m["month"] = m["month"] + 1
    ev["month"] = ev["announce_date"].dt.to_period("M")
    ev = ev.merge(m, on=["stkcd", "month"], how="left").dropna(subset=["mv_total"])
    # Breakpoints come from all stocks that month, not only the announcers
    bps = m.groupby("month")["mv_total"].quantile([0.3, 0.7]).unstack()
    b = bps.reindex(ev["month"]).to_numpy()
    v = ev["mv_total"].to_numpy()
    ev["size_g"] = np.array(["Smallest", "Middle", "Largest"], dtype=object)[(v[:, None] > b).sum(axis=1)]

    stock_start = starts[ev["pos"].to_numpy()]
    stock_end = ends[ev["pos"].to_numpy()]
    items = []
    for k, panel_id in ((0, "A"), (3, "B")):
        lo, hi = ev["pos"].to_numpy() - k, ev["pos"].to_numpy() + k
        ok = (lo >= stock_start) & (hi <= stock_end)
        rr = np.expm1(cs_r[hi + 1] - cs_r[lo]) - np.expm1(cs_m[hi + 1] - cs_m[lo])
        if max_gap_days is not None:
            # exclude windows that contain a trading gap (suspension) longer than max_gap_days
            dd = dates.astype("datetime64[D]").astype(np.int64)
            gap = np.concatenate([[0], np.diff(dd)])
            gmax = np.array([gap[a + 1:b + 1].max() if b > a else 0 for a, b in zip(lo - 1 if k == 0 else lo, hi)])
            ok &= gmax <= max_gap_days
        sub = ev.assign(R=rr)[ok]
        if winsor is not None:
            lo_q, hi_q = sub["R"].quantile([winsor, 1 - winsor])
            sub = sub.assign(R=sub["R"].clip(lo_q, hi_q))
        for g in ("Smallest", "Middle", "Largest"):
            x = sub[sub["size_g"] == g]
            r = ols(x["R"], x[["sue"]], se="white")
            items += [(f"{panel_id}:b", g, r.params["sue"] * 100), (f"{panel_id}:t(b)", g, r.tstats["sue"]),
                      (f"{panel_id}:R2_pct", g, r.r2 * 100), (f"{panel_id}:n", g, float(r.n))]
    return _rows("T1", seg, items)
