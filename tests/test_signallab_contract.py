"""Executable notes on SignalLab's data contract, checked on synthetic data.

Why this file exists
--------------------
Porting SignalLab to China means replacing its CRSP/Compustat inputs with
CSMAR-built panels. Before writing that adapter we pin down, in code, what the
grader actually consumes and how it times information. If a future SignalLab
update changes any of these behaviours, these tests fail loudly instead of the
China port silently drifting.

Each test documents one fact we rely on (see docs/signallab_code_notes.md):

1. Information timing: a firm-year with fiscal-year end in calendar year y is
   visible from July of y+1 through June of y+2 (SignalEngine._to_monthly_panel).
2. Grader inputs: SignalEvaluator needs exactly a firm-year table plus
   (month x security) panels for returns, market equity, and a boolean
   "breakpoint universe" panel (NYSE in the US; the analogue for China is ours
   to choose), plus a factor table.
3. Ranking happens before universe exclusions: fill_var ranks the signal on the
   full cross-section and only afterwards are financials/microcaps masked.

Synthetic data only: no CSMAR/WRDS access and no network calls.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from siglab.agent.executor import SignalEngine
from siglab.agent.signal_evaluator import SignalEvaluator
from siglab.utils.panel import fill_var

N_FIRMS = 60
FISCAL_YEARS = range(2000, 2012)
MONTHS = pd.date_range("2001-01-31", "2013-12-31", freq="ME")


def _synthetic_firm_years(seed: int = 0) -> pd.DataFrame:
    """Firm-year accounting table in the shape SignalEngine expects.

    SignalEngine requires `permno`, `year` (calendar year of the fiscal-year
    end) and `form_year` (= year + 1); every other numeric column is treated as
    an accounting variable usable in expressions.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for firm in range(1, N_FIRMS + 1):
        for fy in FISCAL_YEARS:
            assets = float(rng.uniform(100, 1000))
            revenue = assets * float(rng.uniform(0.5, 1.5))
            rows.append({
                "permno": firm,
                "year": fy,
                "form_year": fy + 1,
                "at": assets,
                "revt": revenue,
                "cogs": revenue * float(rng.uniform(0.4, 0.9)),
                "sic": 2000 + 100 * (firm % 5),  # five 2-digit industries
            })
    return pd.DataFrame(rows)


def _synthetic_monthly_frame() -> pd.DataFrame:
    """Long monthly table with the columns SignalEngine reads from `crsp`."""
    frame = pd.MultiIndex.from_product(
        [range(1, N_FIRMS + 1), MONTHS], names=["permno", "date"]
    ).to_frame(index=False)
    frame["month"] = frame["date"].dt.month
    frame["year"] = frame["date"].dt.year
    return frame


def test_fiscal_year_is_visible_july_next_year_through_june_after():
    """Fact 1: FY y data appears July y+1 .. June y+2, never earlier."""
    comp = _synthetic_firm_years()
    engine = SignalEngine(comp=comp, crsp=_synthetic_monthly_frame())

    panel = engine.execute("at", winsorize_pct=0)

    firm = 7
    fy2005_assets = comp.loc[
        (comp["permno"] == firm) & (comp["year"] == 2005), "at"
    ].item()
    fy2004_assets = comp.loc[
        (comp["permno"] == firm) & (comp["year"] == 2004), "at"
    ].item()

    # June 2006 must still show FY2004: FY2005 is not yet public by convention.
    assert panel.loc["2006-06-30", firm] == pytest.approx(fy2004_assets)
    # July 2006 switches to FY2005 and holds it through June 2007.
    assert panel.loc["2006-07-31", firm] == pytest.approx(fy2005_assets)
    assert panel.loc["2007-06-30", firm] == pytest.approx(fy2005_assets)
    assert panel.loc["2007-07-31", firm] != pytest.approx(fy2005_assets)


def test_ranking_uses_full_cross_section_before_exclusions():
    """Fact 3: fill_var ranks over every stock with market equity.

    Consequence for China: if we drop ST stocks or the smallest 30% (Liu,
    Stambaugh & Yuan 2019), the surviving stocks' ranks are still relative to
    the pre-exclusion cross-section unless we exclude them from the inputs
    themselves. The adapter must decide which of the two it wants.
    """
    raw = pd.DataFrame([[1.0, 2.0, 3.0, 4.0]], index=[pd.Timestamp("2010-01-31")])
    me = pd.DataFrame([[1.0, 1.0, 1.0, 1.0]], index=raw.index)

    ranked = fill_var(raw, me)

    # Four stocks -> ranks 0.25..1.0 shifted by -0.5.
    assert ranked.iloc[0].tolist() == pytest.approx([-0.25, 0.0, 0.25, 0.5])
    # Missing signal with valid market equity is imputed at the median rank 0.
    raw_missing = raw.copy()
    raw_missing.iloc[0, 1] = np.nan
    assert fill_var(raw_missing, me).iloc[0, 1] == 0.0


def test_evaluator_runs_end_to_end_on_synthetic_panels():
    """Fact 2: the full grader runs on exactly these inputs.

    This is the template for the China adapter: replace each synthetic panel
    with its CSMAR-built counterpart and nothing else in SignalLab changes.
    """
    rng = np.random.default_rng(1)
    comp = _synthetic_firm_years()
    crsp_long = _synthetic_monthly_frame()

    shape = (len(MONTHS), N_FIRMS)
    columns = pd.Index(range(1, N_FIRMS + 1))
    returns = pd.DataFrame(rng.normal(0.01, 0.08, shape), index=MONTHS, columns=columns)
    market_equity = pd.DataFrame(rng.uniform(50, 5000, shape), index=MONTHS, columns=columns)
    # Breakpoint universe: in the US this is NYSE membership. Here: half the firms.
    breakpoint_universe = pd.DataFrame(
        np.tile(columns.to_numpy() % 2 == 0, (len(MONTHS), 1)),
        index=MONTHS,
        columns=columns,
    )
    factors = pd.DataFrame(
        rng.normal(0, 0.03, (len(MONTHS), 6)),
        index=MONTHS,
        columns=["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"],
    )

    evaluator = SignalEvaluator(
        engine=SignalEngine(comp=comp, crsp=crsp_long),
        ret_panel=returns,
        me_panel=market_equity,
        ff_factors=factors,
        nyse_panel=breakpoint_universe,
        start_date="2001-07-01",
    )
    result = evaluator.evaluate_signal(
        "RATIO(SUB(revt, cogs), at)",
        exclude_financials=False,
        exclude_microcap=True,
        alpha_factor_model=5,
    )

    assert result.error is None, result.error
    assert np.isfinite(result.fmb_tstat)
    assert np.isfinite(result.ls_talpha)
    assert len(result.quintile_rets) == 5
