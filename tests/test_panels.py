"""Tests for the processed panels (src/csmar/panels.py).

Synthetic tests pin the date and board rules that every downstream number depends on. Data
tests (marker `data`) check structural invariants of the built panels and are skipped when
data/processed/ has not been built on this machine.
"""

from __future__ import annotations

import pandas as pd
import pytest

from csmar.panels import board_of, load, parse_csmar_date
from csmar.registry import PROCESSED

HAS_PANELS = (PROCESSED / "stock_month.parquet").exists()
needs_panels = pytest.mark.skipif(not HAS_PANELS, reason="run `python -m csmar.build` first")


def test_unknown_day_becomes_month_end():
    # Month end is the conservative availability date: never earlier than the truth.
    out = parse_csmar_date(pd.Series(["1993-12-00", "2004-02-00", "2020-05-17"]))
    assert out.tolist() == [pd.Timestamp("1993-12-31"), pd.Timestamp("2004-02-29"), pd.Timestamp("2020-05-17")]


def test_unknown_month_is_missing():
    out = parse_csmar_date(pd.Series(["1993-00-00", None]))
    assert out.isna().all()


def test_board_splits_shenzhen_sme_by_code_prefix():
    stk = pd.Series(["600000", "000001", "002001", "003816", "300750", "688981", "830799", "900901", "200002"])
    mt = pd.Series([1, 4, 4, 4, 16, 32, 64, 2, 8])
    assert board_of(stk, mt).tolist() == [
        "SH_MAIN", "SZ_MAIN", "SZ_SME", "SZ_SME", "CHINEXT", "STAR", "BSE", "SH_B", "SZ_B"]


def test_board_rejects_unknown_combination():
    # A Shenzhen A-share code outside 000/001/002/003 must not be silently left unclassified.
    with pytest.raises(ValueError):
        board_of(pd.Series(["004001"]), pd.Series([4]))


@needs_panels
@pytest.mark.data
@pytest.mark.parametrize("name,key", [
    ("stock_month", ["stkcd", "month"]), ("st_month", ["stkcd", "month"]),
    ("statements", ["stkcd", "accper"]), ("statements_opening", ["stkcd", "accper"]),
    ("company_info", ["stkcd"]), ("risk_free_1y", ["month"]), ("cpi", ["month"]),
])
def test_panel_keys_are_unique(name, key):
    assert not load(name).duplicated(key).any()


@needs_panels
@pytest.mark.data
def test_opening_rows_never_enter_period_statements():
    assert not load("statements")["accper"].str.endswith("-01-01").any()
    assert load("statements_opening")["accper"].str.endswith("-01-01").all()


@needs_panels
@pytest.mark.data
def test_disclosure_never_precedes_period_end():
    s = load("statements")
    assert not (s["announce_date"] < s["period_end"]).any()


@needs_panels
@pytest.mark.data
def test_month_gap_is_positive_and_first_month_missing():
    m = load("stock_month")
    assert (m["month_gap"].dropna() >= 1).all()
    first = m.groupby("stkcd")["month"].transform("min") == m["month"]
    assert m.loc[first, "month_gap"].isna().all()


@needs_panels
@pytest.mark.data
def test_st_status_codes_are_known():
    # Any new CSMAR status code must be classified deliberately before use.
    known = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16}
    assert set(load("st_month")["trdsta_end"].unique()) <= known


@needs_panels
@pytest.mark.data
def test_market_values_are_in_yuan():
    # Kweichow Moutai's total market value was about 2.2 trillion yuan at end-2023.
    m = load("stock_month")
    mv = m.loc[(m["stkcd"] == "600519") & (m["month"] == pd.Period("2023-12", "M")), "mv_total"].iloc[0]
    assert 1.5e12 < mv < 3e12


@needs_panels
@pytest.mark.data
def test_stock_months_are_complete_relative_to_daily_trading():
    # "Months contiguous" (lighthouse 4.2) is read as: no month in which the stock traded is
    # missing. Months without any trading day are absent by design and flagged by month_gap.
    m = load("stock_month")
    d = load("daily_month")
    m_keys = set(zip(m.loc[m["month"] >= pd.Period("1999-12", "M"), "stkcd"], m.loc[m["month"] >= pd.Period("1999-12", "M"), "month"]))
    d_keys = set(zip(d["stkcd"], d["month"]))
    assert m_keys == d_keys


@needs_panels
@pytest.mark.data
def test_monthly_return_equals_compounded_daily_return():
    x = load("stock_month").merge(load("daily_month"), on=["stkcd", "month"])
    x = x.dropna(subset=["ret", "ret_compounded"])
    agree = ((x["ret"] - x["ret_compounded"]).abs() < 1e-4).mean()
    assert agree >= 0.9999, agree


@needs_panels
@pytest.mark.data
def test_b_shares_carry_foreign_currency():
    m = load("stock_month")
    assert set(m.loc[m["board"] == "SH_B", "currency"]) == {"USD"}
    assert set(m.loc[m["board"] == "SZ_B", "currency"]) == {"HKD"}
    assert set(m.loc[m["is_a_share"], "currency"]) == {"CNY"}


@needs_panels
@pytest.mark.data
def test_listing_day_excluded_from_daily_aggregates():
    # In an IPO month n_days counts the trading days after the listing day only.
    x = load("daily_month").merge(load("stock_month")[["stkcd", "month", "trading_days"]], on=["stkcd", "month"])
    ipo = x[x["listing_day_in_month"]]
    assert len(ipo) > 4000
    assert (ipo["n_days"] <= ipo["trading_days"] - 1).all()
