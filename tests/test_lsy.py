"""LSY replication checks (milestone 1.2). Data tests need the licensed CSMAR files and the
cached LSY panel (built by `python -m replication.lsy`); they are skipped otherwise."""

from __future__ import annotations

import pandas as pd
import pytest

from csmar.registry import PROJECT_ROOT
from replication.common.compare import load_targets
from replication.lsy import tables as T

HAS_PANEL = T.PANEL_CACHE.exists()
needs_panel = pytest.mark.skipif(not HAS_PANEL, reason="run `python -m replication.lsy` first")
COMPARISON = PROJECT_ROOT / "results" / "lsy_comparison.csv"


def test_targets_file_is_well_formed():
    t = load_targets("lsy")
    assert {"T1", "T2", "T3", "T4", "T5", "S5.2", "T6", "T7", "T8", "T9", "T10", "F1", "F2", "TXT"} <= set(t["table"])
    assert t["kind"].isin(["pct_return", "pct_std", "t", "coef", "share_pct", "pvalue", "series_corr", "info", "count", "pct_annual", "upper_bound", "lower_bound"]).all()


@needs_panel
@pytest.mark.data
def test_factor_series_correlate_with_stambaugh():
    fc = T.factor_series_check()
    corr = fc[fc["col"] == "corr"].set_index("row")["value"]
    assert (corr.drop(index=[r for r in corr.index if r.endswith(" rf")]) >= 0.95).all(), corr


@needs_panel
@pytest.mark.data
def test_original_segment_has_204_months():
    t3 = T.table3(T.lsy_segments()["original"])
    assert t3.loc[t3["col"] == "n_months", "value"].iloc[0] == 204


@pytest.mark.data
def test_single_quarter_earnings_moutai_2025():
    # Moutai FY2025: YTD Q3 64.68bn, FY 82.29bn -> Q4 flow 17.61bn (IAR_Rept.Profitb)
    from replication.lsy.data import earnings_announcements
    e = earnings_announcements()
    row = e[(e["stkcd"] == "600519") & (e["period_end"] == "2025-12-31")]
    assert row["earnings"].iloc[0] == pytest.approx(8.229311e10 - 6.468062e10, rel=1e-5)


@pytest.mark.skipif(not COMPARISON.exists(), reason="run `python -m replication.lsy` first")
def test_comparison_covers_every_target_and_links_misses():
    c = pd.read_csv(COMPARISON)
    assert len(c) == len(load_targets("lsy"))
    # Only 'info' rows may lack our number (e.g. items listed as not producible)
    assert c.loc[c["kind"] != "info", "ours"].notna().all()
    misses = c[c["pass"].astype(str) == "False"]
    assert misses["deviation"].fillna("").str.startswith("LSY-").all()


def test_latest_report_carries_the_whole_row():
    # A NaN in the newest report must stay NaN, never be back-filled from an older report.
    import numpy as np
    from replication.lsy.data import latest_by_month_end
    ev = pd.DataFrame({"stkcd": ["a", "a"], "announce_date": pd.to_datetime(["2003-04-20", "2003-08-20"]),
                       "period_end": pd.to_datetime(["2003-03-31", "2003-06-30"]), "x": [1.0, np.nan], "y": [5.0, 6.0]})
    out = latest_by_month_end(ev, pd.period_range("2003-03", "2003-09", freq="M"), ["x", "y"]).set_index("month")
    assert np.isnan(out.loc[pd.Period("2003-03", "M"), "y"])  # nothing released yet
    assert out.loc[pd.Period("2003-07", "M"), "x"] == 1.0
    assert np.isnan(out.loc[pd.Period("2003-08", "M"), "x"]) and out.loc[pd.Period("2003-08", "M"), "y"] == 6.0
