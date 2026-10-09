"""Tests for the raw CSMAR readers.

Synthetic tests pin the quote-aware parser's behaviour. Data tests (marker `data`) check every
registered table against the CSMAR platform counts recorded in docs/csmar_access.md; they are
skipped on machines without the licensed files.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from csmar.readers import RowCountMismatch, read_quote_delimited, read_raw
from csmar.registry import RAW_CSMAR, TABLES

HAS_DATA = RAW_CSMAR.exists()
needs_data = pytest.mark.skipif(not HAS_DATA, reason="licensed CSMAR files not present")


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "T.csv"
    p.write_text("﻿" + text, encoding="utf-8")
    return p


def test_quote_aware_parser_keeps_stray_quotes_inside_fields(tmp_path):
    # The second record contains an unescaped quote inside a text field, which makes a
    # standard CSV parser split it into too many fields.
    p = _write(tmp_path, '"Stkcd","Reason","V"\n"000001","plain","1.5"\n"600771","say "hi", ok","2"\n')
    df = read_quote_delimited(p)
    assert len(df) == 2
    assert df.loc[1, "Reason"] == 'say "hi", ok'
    assert df.loc[1, "V"] == "2"


def test_quote_aware_parser_keeps_embedded_newlines(tmp_path):
    p = _write(tmp_path, '"A","B"\n"1","line one\nline two"\n"2","x"\n')
    df = read_quote_delimited(p)
    assert df["B"].tolist() == ["line one\nline two", "x"]


def test_quote_aware_parser_maps_empty_fields_to_missing(tmp_path):
    p = _write(tmp_path, '"A","B"\n"1",""\n')
    assert read_quote_delimited(p).loc[0, "B"] is None


def test_quote_aware_parser_rejects_unquoted_files(tmp_path):
    p = _write(tmp_path, "A,B\n1,2\n")
    with pytest.raises(ValueError):
        read_quote_delimited(p)


@needs_data
@pytest.mark.data
@pytest.mark.parametrize("code", sorted(TABLES))
def test_every_table_matches_platform_count(code):
    table = TABLES[code]
    df = read_raw(code)
    # read_raw raises RowCountMismatch per chunk; check the total explicitly as well.
    assert len(df) == sum(table.expected_rows)
    if "Stkcd" in df.columns:
        assert df["Stkcd"].str.len().eq(6).all(), "stock codes must keep leading zeros"


@needs_data
@pytest.mark.data
def test_daily_chunks_do_not_overlap():
    d = read_raw("TRD_Dalyr", columns=["Stkcd", "Trddt"])
    assert not d.duplicated(["Stkcd", "Trddt"]).any()


@needs_data
@pytest.mark.data
def test_monthly_returns_unique_per_stock_month():
    m = read_raw("TRD_Mnth", columns=["Stkcd", "Trdmnt"])
    assert not m.duplicated(["Stkcd", "Trdmnt"]).any()
