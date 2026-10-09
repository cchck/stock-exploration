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
