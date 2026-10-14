"""Li, Liu, Liu & Wei (2024) tables (lighthouse 5.3). Tidy rows (table, segment, row, col,
value) like the other papers; row / column names follow targets/li_targets.csv
(scripts/build_li_targets.py), anomaly rows use the authors' variable names where the
replication package gives one (catalog.author_names).

Segments: original = 2000-07..2019-06 (228 months; the post-2007 subsample 2008-07..2019-06
is "Panel B" of Tables 1, 4-6), extended = 2019-07..latest, full = 2000-07..latest. The
CH-3 / CH-4 series end in 2021-12 (Stambaugh's website), so CH-model statistics stop there.

Statistics follow the authors' SAS code (Table4&6/1.reg_macro.sas): means and t-statistics
from PROC MEANS (classical), alphas from PROC REG (classical OLS standard errors), GRS on the
five quintiles' excess returns.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from replication.common.periods import Segment
from replication.common.stats import grs
from replication.li import anomalies as AN
from replication.li import catalog as C
from replication.li import data as D
from replication.li import factors as F
from replication.li.rates import rf_monthly

PAPER_START, PAPER_END = pd.Period("2000-07", "M"), pd.Period("2019-06", "M")
POST2007_START = pd.Period("2008-07", "M")
SHT, MHT = 1.96, 2.78
MODELS = {
    "CAPM": ["mkt"], "FF3": ["mkt", "smbff3", "hmlff3"], "FF5": ["mkt", "smbff5", "hml", "rmw", "cma"],
    "q": ["mkt", "me", "ia", "roe"], "CH3": ["mktch", "smbch3", "vmg"], "CH4": ["mktch", "smbch4", "vmg", "pmo"],
    "Car4": ["mkt", "smbff3", "hmlff3", "mom"],
}


def li_segments() -> dict[str, Segment]:
    last = D.stock_panel()["month"].max()
    return {"original": Segment("original", PAPER_START, PAPER_END),
            "extended": Segment("extended", PAPER_END + 1, last),
            "full": Segment("full", PAPER_START, last)}


def _rows(table: str, seg: Segment, items) -> pd.DataFrame:
    return pd.DataFrame([{"table": table, "segment": seg.name, "start": str(seg.start), "end": str(seg.end),
                          "row": r, "col": c, "value": v} for r, c, v in items])


@lru_cache(maxsize=1)
def factors() -> pd.DataFrame:
    """Monthly factors (decimal): self-built MKT, FF3, FF5, q, MOM; CH-3 / CH-4 from
    Stambaugh's website (MKT-CH and SMB-CH4, VMG, PMO from the monthly CH-4 file; SMB-CH3
    from the daily CH-3 file compounded), and the three-month deposit rate."""
    from replication.lsy.factors import stambaugh_ch3_monthly, stambaugh_monthly
    f = F.mkt().to_frame().join(F.ff_factors(), how="outer").join(F.q_factors(), how="outer").join(F.mom(), how="outer")
    ch4, ch3 = stambaugh_monthly(), stambaugh_ch3_monthly()
    f = f.join(pd.DataFrame({"mktch": ch4["mkt"], "smbch4": ch4["smb"], "vmg": ch4["vmg"], "pmo": ch4["pmo"],
                             "smbch3": ch3["smb"]}), how="left")
    f["rf"] = rf_monthly().reindex(f.index)
    return f


def _window(df: pd.DataFrame, start: pd.Period, end: pd.Period) -> pd.DataFrame:
    return df[(df.index >= start) & (df.index <= end)]


# ---------------------------------------------------------------------------------------------
# Table 1
# ---------------------------------------------------------------------------------------------

T1_FACTORS = {"MKT": "mkt", "ME": "me", "I/A": "ia", "ROE": "roe", "SMB-FF5": "smbff5", "HML-FF5": "hml",
              "RMW": "rmw", "CMA": "cma", "MKT-CH": "mktch", "SMB-CH3": "smbch3", "SMB-CH4": "smbch4",
              "VMG": "vmg", "PMO": "pmo"}


def table1(seg: Segment) -> pd.DataFrame:
    items = []
    years = range(max(1999, seg.start.year - 1 if seg.name != "extended" else seg.start.year), seg.end.year + (0 if seg.end.month < 12 else 1))
    a = D.table1_panel_a(years).set_index("year")
    cols = {"n_ashares": "n_ashares", "n_sh_main": "n_sh_main", "n_sz_main": "n_sz_main", "n_sme": "n_sme",
            "n_gem": "n_gem", "tmv": "tmv", "cmv": "cmv", "sh_tmv": "sh_tmv", "sh_cmv": "sh_cmv", "sz_tmv": "sz_tmv",
            "sz_cmv": "sz_cmv", "sme_tmv": "sme_tmv", "sme_cmv": "sme_cmv", "gem_tmv": "gem_tmv", "gem_cmv": "gem_cmv"}
    for y in a.index:
        for k, c in cols.items():
            items.append((f"A:{y}", k, float(a.loc[y, c])))
    f = factors()
    panels = [("B", seg.start, seg.end)]
    if seg.start <= POST2007_START <= seg.end:
        panels.append(("C", POST2007_START, seg.end))
    for panel, s, e in panels:
        w = _window(f, s, e)
        for name, c in T1_FACTORS.items():
            x = w[c].dropna()
            if len(x) < 2:
                continue
            items += [(f"{panel}:{name}", "mean", x.mean() * 100), (f"{panel}:{name}", "t", x.mean() / x.std() * np.sqrt(len(x))),
                      (f"{panel}:{name}", "std", x.std() * 100)]
        cp = {"B": "D", "C": "E"}[panel]
        corr = w[list(T1_FACTORS.values())].corr()
        names = list(T1_FACTORS)
        for i, ni in enumerate(names):
            for j in range(i):
                items.append((f"{cp}:{ni}", names[j], corr.iloc[i, j]))
    return _rows("T1", seg, items)


# ---------------------------------------------------------------------------------------------
# Anomaly statistics
# ---------------------------------------------------------------------------------------------

@lru_cache(maxsize=1)
def quintiles() -> pd.DataFrame:
    q = AN.load()
    q["month"] = pd.PeriodIndex(q["month"], freq="M")
    return q


def _alpha(y: pd.Series, X: pd.DataFrame) -> tuple[float, float]:
    d = pd.concat([y, X], axis=1).dropna()
    if len(d) < X.shape[1] + 3:
        return np.nan, np.nan
    Z = np.column_stack([np.ones(len(d)), d.iloc[:, 1:].to_numpy()])
    yv = d.iloc[:, 0].to_numpy()
    b, *_ = np.linalg.lstsq(Z, yv, rcond=None)
    e = yv - Z @ b
    s2 = e @ e / (len(d) - Z.shape[1])
    se = np.sqrt(s2 * np.linalg.inv(Z.T @ Z)[0, 0])
    return float(b[0]), float(b[0] / se)


@lru_cache(maxsize=16)
def anomaly_stats(start: str, end: str, proc: str = "Mainboard-VW", models: tuple = ("CAPM", "FF3")) -> pd.DataFrame:
    """Per anomaly: mean g5-g1 (%), t; H-L alpha (%) and t per model; mean |alpha| over the five
    quintiles (%) and GRS p per model."""
    s, e = pd.Period(start, "M"), pd.Period(end, "M")
    q = quintiles()
    q = q[(q["proc"] == proc) & (q["month"] >= s) & (q["month"] <= e)]
    f = _window(factors(), s, e)
    out = []
    for name, g in q.groupby("anomaly"):
        g = g.set_index("month").sort_index()
        hl = g["g5_g1"].dropna()
        row = {"anomaly": name, "var": g["var"].iloc[0], "category": g["category"].iloc[0], "n": len(hl)}
        if len(hl) < 12:
            out.append(row)
            continue
        row["m"] = hl.mean() * 100
        row["t"] = hl.mean() / hl.std() * np.sqrt(len(hl))
        ex = g[["g1", "g2", "g3", "g4", "g5"]].sub(f["rf"].reindex(g.index), axis=0)
        for mdl in models:
            X = f[MODELS[mdl]].reindex(g.index)
            if X.dropna().shape[0] < 24:
                continue
            a, t = _alpha(hl, X)
            row[f"alpha_{mdl}"], row[f"t_{mdl}"] = a * 100, t
            alphas = [_alpha(ex[c], X)[0] for c in ex.columns]
            row[f"absalpha_{mdl}"] = float(np.nanmean(np.abs(alphas))) * 100
            try:
                row[f"grs_{mdl}"] = grs(ex, X).pvalue
            except ValueError:
                row[f"grs_{mdl}"] = np.nan
        out.append(row)
    return pd.DataFrame(out)


def _author(name: str) -> str:
    inv = {v: k for k, v in C.author_names().items()}
    return inv.get(name, name)


def _panels(seg: Segment):
    out = [("A", seg.start, seg.end)]
    if seg.start <= POST2007_START <= seg.end:
        out.append(("B", POST2007_START, seg.end))
    return out


# ---------------------------------------------------------------------------------------------
# Table 3: significance rates by category and procedure
# ---------------------------------------------------------------------------------------------

def table3(seg: Segment) -> pd.DataFrame:
    """Shares of anomalies with |t| >= 1.96 / 2.78 for raw spreads (Panel A) and, among those,
    significant CAPM (B) and FF3 (C) alphas, by category and procedure. The denominator is
    the number of anomalies we can build in the category (the paper's totals are 45 / 68 /
    36 / 94 / 83 / 143; the counts we build are reported as row 'n_available')."""
    items = []
    for proc in ("Mainboard-VW", "All-VW", "Mainboard-EW", "All-EW"):
        st = anomaly_stats(str(seg.start), str(seg.end), proc)
        groups = {c: st[st["category"] == c] for c in C.CATEGORIES} | {"All categories": st}
        for cat, g in groups.items():
            n = len(g)
            if proc == "Mainboard-VW":
                items.append((f"n_available", cat, float(n)))
            for cut, lab in ((SHT, "SHT"), (MHT, "MHT")):
                raw = g["t"].abs() >= cut
                items.append((f"A:{proc}", f"{cat}:{lab}", raw.mean() * 100 if n else np.nan))
                for panel, mdl in (("B", "CAPM"), ("C", "FF3")):
                    ok = raw & (g[f"t_{mdl}"].abs() >= cut)
                    items.append((f"{panel}:{proc}", f"{cat}:{lab}", ok.mean() * 100 if n else np.nan))
    return _rows("T3", seg, items)


# ---------------------------------------------------------------------------------------------
# Tables 4 and 6: individual anomalies
# ---------------------------------------------------------------------------------------------

def table4(seg: Segment) -> pd.DataFrame:
    """Raw H-L spreads (m, %) and t for every anomaly (paper rows: the significant ones),
    with the count of significant anomalies per panel."""
    items = []
    for panel, s, e in _panels(seg):
        st = anomaly_stats(str(s), str(e))
        for _, r in st.iterrows():
            a = _author(r["anomaly"])
            items += [(f"{panel}:{a}", "m", r.get("m", np.nan)), (f"{panel}:{a}", "t", r.get("t", np.nan))]
        items.append((f"{panel}:count", "significant", float((st["t"].abs() >= SHT).sum())))
    return _rows("T4", seg, items)


def table6(seg: Segment) -> pd.DataFrame:
    """FF5 / q / CH3 / CH4 H-L alphas (%), t, mean |alpha| over the quintiles (%) and GRS p
    for every anomaly (paper rows: the significant ones)."""
    items = []
    names = {"FF5": "FF5", "q": "q", "CH3": "CH3", "CH4": "CH4"}
    for panel, s, e in _panels(seg):
        st = anomaly_stats(str(s), str(e), "Mainboard-VW", ("FF5", "q", "CH3", "CH4"))
        for _, r in st.iterrows():
            a = _author(r["anomaly"])
            for mdl, lab in names.items():
                for stat, key in (("alpha", "alpha"), ("t", "t"), ("mean_abs_alpha", "absalpha"), ("grs_p", "grs")):
                    items.append((f"{panel}:{a}", f"{stat}_{lab}", r.get(f"{key}_{mdl}", np.nan)))
    return _rows("T6", seg, items)


# ---------------------------------------------------------------------------------------------
# Table 5: factor models over the significant anomalies
# ---------------------------------------------------------------------------------------------

def table5(seg: Segment) -> pd.DataFrame:
    items = []
    groups = ["All", *C.CATEGORIES]
    for panel, s, e in _panels(seg):
        st = anomaly_stats(str(s), str(e), "Mainboard-VW", tuple(MODELS))
        sig = st[st["t"].abs() >= SHT]
        for mdl in MODELS:
            for grp in groups:
                g = sig if grp == "All" else sig[sig["category"] == grp]
                if f"alpha_{mdl}" not in g:
                    continue
                g = g.dropna(subset=[f"alpha_{mdl}"])
                items += [(f"{panel}:{mdl}", f"{grp}:abs_alpha_hl", g[f"alpha_{mdl}"].abs().mean()),
                          (f"{panel}:{mdl}", f"{grp}:n_t196", float((g[f"t_{mdl}"].abs() >= SHT).sum())),
                          (f"{panel}:{mdl}", f"{grp}:mean_abs_alpha", g[f"absalpha_{mdl}"].mean()),
                          (f"{panel}:{mdl}", f"{grp}:n_grs_p05", float((g[f"grs_{mdl}"] < 0.05).sum()))]
    return _rows("T5", seg, items)


# ---------------------------------------------------------------------------------------------
# Table 2: microcaps and investment capacity
# ---------------------------------------------------------------------------------------------

def table2(seg: Segment) -> pd.DataFrame:
    """Panel A: size groups by the Mainboard 20th / 50th percentiles of circulating ME at the
    end of t-1 (Fama and French 2008; HXZ 2020), over eligible stocks with a month-t return:
    average number of firms, share of total / circulating market cap, VW and EW mean and
    standard deviation of monthly returns (%), and the average cross-sectional standard
    deviation of returns (%). Panels B-D from anomalies.membership_stats, averaged over time
    within each anomaly and then across the anomalies of a category (each base variable
    counts once per anomaly it contributes)."""
    items = []
    p = D.stock_panel().sort_values(["stkcd", "month"]).copy()
    # Lagged values only when the previous row is the previous calendar month (a stock
    # resuming after a suspension has no end-of-(t-1) record).
    consec = p.groupby("stkcd")["month"].shift(1) == p["month"] - 1
    lag = lambda c: p.groupby("stkcd")[c].shift(1).where(consec)
    p["mv_prev"] = lag("mv_float")
    p["tmv_prev"] = lag("mv_total")
    p["elig_prev"] = lag("eligible").astype("boolean").fillna(False).astype(bool)
    p["mb_prev"] = lag("mainboard").astype("boolean").fillna(False).astype(bool)
    p["close_prev"] = lag("close")
    # Sample: eligible at t-1 with price >= 5 (the portfolios' formation filter). Calibrated:
    # 1,544 stocks and 464 microcaps a month, EW market 1.29%, against the printed 1,563,
    # 449 and 1.28% (without the price filter: 1,755, 515, 1.35%).
    x = p[p["elig_prev"] & (p["close_prev"] >= 5) & p["ret"].notna() & (p["mv_prev"] > 0)
          & (p["month"] >= seg.start) & (p["month"] <= seg.end)].copy()
    cuts = x[x["mb_prev"]].groupby("month")["mv_prev"].quantile([0.2, 0.5]).unstack()
    x["c20"], x["c50"] = x["month"].map(cuts[0.2]), x["month"].map(cuts[0.5])
    x["grp"] = np.where(x["mv_prev"] < x["c20"], "Micro", np.where(x["mv_prev"] < x["c50"], "Small", "Big"))
    groups = {"Market": x, "Micro": x[x["grp"] == "Micro"], "Small": x[x["grp"] == "Small"],
              "Big": x[x["grp"] == "Big"], "All-but-micro": x[x["grp"] != "Micro"]}
    tot_t = x.groupby("month")["tmv_prev"].sum()
    tot_c = x.groupby("month")["mv_prev"].sum()
    for name, g in groups.items():
        bym = g.groupby("month")
        vw = (g["ret"] * g["mv_prev"]).groupby(g["month"]).sum() / bym["mv_prev"].sum()
        ew = bym["ret"].mean()
        items += [(f"A:{name}", "n_firms", bym.size().mean()),
                  (f"A:{name}", "pct_tmv", (bym["tmv_prev"].sum() / tot_t).mean() * 100),
                  (f"A:{name}", "pct_cmv", (bym["mv_prev"].sum() / tot_c).mean() * 100),
                  (f"A:{name}", "vw_mean", vw.mean() * 100), (f"A:{name}", "vw_std", vw.std() * 100),
                  (f"A:{name}", "ew_mean", ew.mean() * 100), (f"A:{name}", "ew_std", ew.std() * 100),
                  (f"A:{name}", "xs_std", bym["ret"].std().mean() * 100)]
    try:
        m = pd.read_parquet(AN.MEMBER_CACHE)
    except FileNotFoundError:
        return _rows("T2", seg, items)
    m["form"] = pd.PeriodIndex(m["form"], freq="M")
    short = {"Momentum": "Mom", "Value-versus-growth": "VvG", "Investment": "Inv", "Profitability": "Prof",
             "Intangibles": "Intan", "Trading frictions": "Fric"}
    w = m[(m["form"] >= seg.start - 1) & (m["form"] < seg.end)]
    per = w.groupby(["var", "category", "proc", "q", "n_anomalies"])[["micro_share", "capacity_frac"]].mean().reset_index()
    dec = m[m["form"] == pd.Period(f"{min(seg.end.year, 2018) if seg.name == 'original' else seg.end.year - 1}-12", "M")]
    dec_ann = m[m["form"] == pd.Period(f"{min(seg.end.year, 2018) if seg.name == 'original' else seg.end.year - 1}-06", "M")]
    cap = pd.concat([dec, dec_ann[~dec_ann["var"].isin(dec["var"])]])
    for proc in ("Mainboard-VW", "Mainboard-EW", "All-VW", "All-EW"):
        for side, qv in (("Low", 1), ("High", 5)):
            sel = per[(per["proc"] == proc) & (per["q"] == qv)]
            selc = cap[(cap["proc"] == proc) & (cap["q"] == qv)]
            for cat in ["All", *C.CATEGORIES]:
                s = sel if cat == "All" else sel[sel["category"] == cat]
                c = selc if cat == "All" else selc[selc["category"] == cat]
                lab = f"{side}-{'All' if cat == 'All' else short[cat]}"
                wts = s["n_anomalies"]
                items += [(f"B:{proc}", lab, np.average(s["micro_share"], weights=wts) * 100 if len(s) else np.nan),
                          (f"C:{proc}", lab, np.average(s["capacity_frac"], weights=wts) * 100 if len(s) else np.nan),
                          (f"D:{proc}", lab, np.average(c["capacity"], weights=c["n_anomalies"]) / 1e12 if len(c) else np.nan)]
    return _rows("T2", seg, items)


# ---------------------------------------------------------------------------------------------
# Table 7: SOE vs non-SOE subsamples
# ---------------------------------------------------------------------------------------------

T7_MODELS = ["CAPM", "FF3", "FF5", "q", "CH3", "CH4", "Car4"]


def _stats_from(q: pd.DataFrame, s: pd.Period, e: pd.Period, models) -> pd.DataFrame:
    f = _window(factors(), s, e)
    q = q[(q["month"] >= s) & (q["month"] <= e)]
    out = []
    for name, g in q.groupby("anomaly"):
        g = g.set_index("month").sort_index()
        hl = g["g5_g1"].dropna()
        row = {"anomaly": name, "category": g["category"].iloc[0]}
        if len(hl) >= 12:
            row["t"] = hl.mean() / hl.std() * np.sqrt(len(hl))
            for mdl in models:
                X = f[MODELS[mdl]].reindex(hl.index)
                if X.dropna().shape[0] >= 24:
                    row[f"t_{mdl}"] = _alpha(hl, X)[1]
        out.append(row)
    return pd.DataFrame(out)


def table7(seg: Segment) -> pd.DataFrame:
    """Counts of anomalies with significant raw spreads and, among them, significant alphas
    (SHT and MHT) in the SOE and non-SOE subsamples, Mainboard-VW; periods from 2004-07
    (ownership data start at 2003-12-31) and from 2008-07, to the segment end."""
    try:
        q = pd.read_parquet(AN.SOE_CACHE)
    except FileNotFoundError:
        return _rows("T7", seg, [])
    q["month"] = pd.PeriodIndex(q["month"], freq="M")
    items = []
    starts = {"0407": max(seg.start, pd.Period("2004-07", "M")), "0807": max(seg.start, POST2007_START)}
    for soe, (sht_panel, mht_panel) in ((1, ("A", "B")), (0, ("C", "D"))):
        qs = q[q["soe"] == soe]
        for per, s in starts.items():
            if s > seg.end:
                continue
            st = _stats_from(qs, s, seg.end, T7_MODELS)
            for cut, panel in ((SHT, sht_panel), (MHT, mht_panel)):
                for cat in [*C.CATEGORIES, "Total"]:
                    g = st if cat == "Total" else st[st["category"] == cat]
                    raw = g["t"].abs() >= cut
                    items.append((f"{panel}:{cat}", f"{per}:Raw", float(raw.sum())))
                    for mdl in T7_MODELS:
                        col = f"t_{mdl}"
                        n = float((raw & (g[col].abs() >= cut)).sum()) if col in g else np.nan
                        items.append((f"{panel}:{cat}", f"{per}:{mdl}", n))
    return _rows("T7", seg, items)


# ---------------------------------------------------------------------------------------------
# Numbers printed in the text (abstract, introduction, sections 2.1 and 3.3)
# ---------------------------------------------------------------------------------------------

def text_numbers(seg: Segment) -> pd.DataFrame:
    items = []
    st = anomaly_stats(str(seg.start), str(seg.end), "Mainboard-VW", tuple(MODELS))
    n = len(st)
    raw = st["t"].abs() >= SHT
    for lab, ok in (("raw", raw), ("capm", raw & (st["t_CAPM"].abs() >= SHT)), ("ff3", raw & (st["t_FF3"].abs() >= SHT))):
        items.append((f"abstract:failure_rate_{lab}", "pct", (1 - ok.mean()) * 100))
    items += [("S1:sig_full_sht", "n", float(raw.sum())), ("S1:sig_full_mht", "n", float((st["t"].abs() >= MHT).sum()))]
    sig = st[raw]
    for mdl in ("CH3", "CH4", "q"):
        items.append((f"S1:explained_full_{mdl}", "pct", float((sig[f"t_{mdl}"].abs() < SHT).mean() * 100)))
    if seg.start <= POST2007_START <= seg.end:
        st2 = anomaly_stats(str(POST2007_START), str(seg.end), "Mainboard-VW", tuple(MODELS))
        raw2 = st2["t"].abs() >= SHT
        items += [("S1:sig_post2007_sht", "n", float(raw2.sum())), ("S1:sig_post2007_mht", "n", float((st2["t"].abs() >= MHT).sum())),
                  ("S1:explained_post2007_q", "pct", float((st2[raw2]["t_q"].abs() < SHT).mean() * 100))]
    for nm in ("Roeq1", "Roeq3"):
        r = st[st["anomaly"] == nm]
        if len(r):
            items += [(f"S3.3:{nm}_m", "pct", float(r["m"].iloc[0])),
                      (f"S3.3:{nm}_insignificant", "abs_t_below_1.96", float(abs(r["t"].iloc[0])))]
    # SOE share at the end of 2003 (section 2.1): eligible A shares with a 2003 flag
    p = D.stock_panel()
    dec = p[(p["month"] == pd.Period("2003-12", "M")) & p["eligible"]][["stkcd"]]
    from replication.allen.data import soe_flags
    f = soe_flags()
    f = f[f["fy"] == 2003]
    m = dec.merge(f, on="stkcd", how="inner")
    items.append(("S2.1:soe_share_2003", "pct", float(m["soe"].mean() * 100)))
    return _rows("TXT", seg, items)


def hxz_us(seg: Segment) -> pd.DataFrame:
    """Section 4.2: significance of the HXZ (2020) U.S. anomalies (global-q.org testing
    portfolios, value-weighted deciles, high-minus-low = decile 10 - decile 1) over the same
    windows. Today's files (2025 vintage) hold a different set than the 187 of the paper."""
    import zipfile
    from csmar.registry import RAW_EXTERNAL
    hl = {}
    for z in sorted((RAW_EXTERNAL / "hxz").glob("*_monthly_2025.zip")):
        with zipfile.ZipFile(z) as zf:
            for name in zf.namelist():
                if not name.endswith(".csv"):
                    continue
                with zf.open(name) as fh:
                    d = pd.read_csv(fh)
                rank = [c for c in d.columns if c.startswith("rank_")][0]
                d["month"] = pd.PeriodIndex.from_fields(year=d["year"], month=d["month"], freq="M")
                w = d.pivot_table(index="month", columns=rank, values="ret_vw")
                if 10 in w.columns and 1 in w.columns:
                    hl[name.split("/")[-1]] = w[10] - w[1]
    hl = pd.DataFrame(hl)
    items = [("S4.2:us_n_anomalies", "n", float(hl.shape[1]))]
    windows = [("full", seg.start, seg.end)]
    if seg.start <= POST2007_START <= seg.end:
        windows.append(("post2007", POST2007_START, seg.end))
    for lab, s, e in windows:
        w = _window(hl, s, e)
        t = w.mean() / w.std() * np.sqrt(w.count())
        items += [(f"S4.2:us_sig_rate_{lab}_sht", "pct", float((t.abs() >= SHT).mean() * 100)),
                  (f"S4.2:us_sig_rate_{lab}_mht", "pct", float((t.abs() >= MHT).mean() * 100))]
    return _rows("TXT", seg, items)
