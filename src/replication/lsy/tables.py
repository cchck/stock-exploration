"""LSY tables. Each function takes a Segment (replication.common.periods) and returns a tidy
DataFrame with one row per reported number: table, row, col, value. The same function
produces the original, extended and full-sample versions (lighthouse.md section 6).
"""

from __future__ import annotations

from functools import lru_cache

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
