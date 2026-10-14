"""Paper-vs-ours comparison with the tolerances of lighthouse.md section 3.3.

Paper numbers live in machine-readable target files (targets/<paper>_targets.csv, one row
per printed number: table, row, col, paper, kind). `kind` selects the tolerance rule:

| kind        | rule (lighthouse 3.3)                                                   |
|-------------|-------------------------------------------------------------------------|
| pct_return  | mean return, alpha, factor mean, in % per month: |ours - paper| <= 0.10  |
| pct_std     | standard deviation in % per month: same 0.10 rule (used by LSY, scored  |
|             | before the 2026-10-10 revision; Li's standard deviations use rel10)     |
| t           | same significance band: |t| < 1.96 / 1.96-2.78 / > 2.78               |
| coef        | non-return coefficient (incl. correlations, R-squared slopes): same     |
|             | sign (the t-band half of the rule is checked on the paired t row).      |
|             | A coefficient printed as 0.00 has no sign: not scored here (None); its  |
|             | paired t row carries the verdict.                                       |
| count       | count (deals, stocks): |ours / paper - 1| <= 3% (3.3: counts are       |
|             | compared as proportions within 3 points)                               |
| share_pct   | proportion in %: |ours - paper| <= 3 points                            |
| share_frac  | proportion stored as a fraction (0.539): |ours - paper| <= 0.03         |
| pvalue      | same reject / not-reject conclusion at 5%. A p-value printed as 0.05   |
|             | (rounded, so on the boundary) passes when ours also rounds to 0.05.    |
| series_corr | month-by-month correlation with a published series >= the threshold    |
|             | stored in the paper column (0.95 or 0.90)                               |
| pct_annual  | an annualized return in % per year: |ours - paper| <= 1.2 (the monthly  |
|             | 0.10-point rule times 12)                                               |
| upper_bound | the paper states "x or less": ours <= paper (the bound as printed)     |
| lower_bound | the paper states "at least x" / "more than x": ours >= paper           |
| rel10       | continuous descriptive statistic or small financial ratio (averages,    |
|             | index mean/sd, turnover, dividend yield, investment, OCF, buy-and-hold  |
|             | value): |ours / paper - 1| <= 10% (lighthouse 3.3, revision 2026-10-10)|
| info        | reported, not scored (e.g. number of months)                            |
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

TARGETS_DIR = Path(__file__).resolve().parents[3] / "targets"


def t_band(t: float) -> int:
    a = abs(t)
    return 0 if a < 1.96 else (1 if a <= 2.78 else 2)


def judge(kind: str, paper: float, ours: float) -> bool | None:
    if kind == "info":  # reported, never scored, even when our value is missing
        return None
    if ours is None or (isinstance(ours, float) and np.isnan(ours)):
        return False
    if kind in ("pct_return", "pct_std"):
        return abs(ours - paper) <= 0.10 + 1e-9
    if kind == "t":
        return t_band(ours) == t_band(paper)
    if kind == "coef":
        if paper == 0:
            return None
        return np.sign(ours) == np.sign(paper)
    if kind == "count":
        if paper == 0:
            return abs(ours) <= 1e-9
        return abs(ours / paper - 1) * 100 <= 3.0 + 1e-9
    if kind == "rel10":
        if paper == 0:
            return abs(ours) <= 1e-9
        return abs(ours / paper - 1) <= 0.10 + 1e-9
    if kind == "pct_annual":
        return abs(ours - paper) <= 1.2 + 1e-9
    if kind == "upper_bound":
        return ours <= paper + 1e-9
    if kind == "lower_bound":
        return ours >= paper - 1e-9
    if kind == "share_frac":
        return abs(ours - paper) <= 0.03 + 1e-9
    if kind == "share_pct":
        return abs(ours - paper) <= 3.0 + 1e-9
    if kind == "pvalue":
        if round(paper, 2) == 0.05:
            return round(ours, 2) == 0.05 or ((ours < 0.05) == (paper < 0.05))
        return (ours < 0.05) == (paper < 0.05)
    if kind == "series_corr":
        return ours >= paper
    if kind == "info":
        return None
    raise ValueError(f"unknown tolerance kind {kind!r}")


def load_targets(paper: str) -> pd.DataFrame:
    path = TARGETS_DIR / f"{paper}_targets.csv"
    t = pd.read_csv(path, comment="#")
    need = {"table", "row", "col", "paper", "kind"}
    if not need <= set(t.columns):
        raise ValueError(f"{path} lacks columns {need - set(t.columns)}")
    if t.duplicated(["table", "row", "col"]).any():
        raise ValueError(f"{path} has duplicate (table, row, col) keys")
    return t


def compare(paper: str, ours: pd.DataFrame, deviations: dict[tuple[str, str, str], str] | None = None) -> pd.DataFrame:
    """Join targets with our original-segment numbers (columns table, row, col, value) and
    judge each. Every target row appears in the output; a target we did not produce is a
    failure with ours = NaN, so nothing silently drops out of the comparison."""
    t = load_targets(paper)
    o = ours[["table", "row", "col", "value"]].rename(columns={"value": "ours"})
    x = t.merge(o, on=["table", "row", "col"], how="left", validate="one_to_one")
    x["diff"] = x["ours"] - x["paper"]
    x["pass"] = [judge(k, p, v) for k, p, v in zip(x["kind"], x["paper"], x["ours"])]
    dev = deviations or {}
    x["deviation"] = [dev.get((a, b, c), "") for a, b, c in zip(x["table"], x["row"], x["col"])]
    return x
