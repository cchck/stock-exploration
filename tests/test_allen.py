"""Allen et al. replication checks (milestone 1.3)."""

from __future__ import annotations

import pandas as pd
import pytest

from csmar.registry import PROJECT_ROOT
from replication.common.compare import load_targets
from replication.allen import tables as T

HAS_PANEL = T.PANEL_CACHE.exists()
needs_panel = pytest.mark.skipif(not HAS_PANEL, reason="run `python -m replication.allen --rebuild` first")
COMPARISON = PROJECT_ROOT / "results" / "allen_comparison.csv"


def test_targets_file_is_well_formed():
    t = load_targets("allen")
    assert {"TI", "TVIII", "TIX", "TX", "TXI", "TXIII", "F1-2", "F4", "F5", "S3A2"} <= set(t["table"])
    allowed = {"pct_return", "pct_std", "t", "coef", "share_pct", "share_frac", "pvalue", "series_corr", "info",
               "count", "pct_annual", "upper_bound", "lower_bound"}
    assert set(t["kind"]) <= allowed


@needs_panel
@pytest.mark.data
def test_g_indices_are_in_range_and_panel_keys_unique():
    p = T.panel()
    assert not p.duplicated(["stkcd", "fy"]).any()
    assert p["g_index_a"].dropna().between(0, 6).all()
    assert p["g_index_i"].dropna().between(0, 7).all()


@pytest.mark.skipif(not COMPARISON.exists(), reason="run `python -m replication.allen` first")
def test_comparison_covers_every_target_and_links_misses():
    c = pd.read_csv(COMPARISON)
    assert len(c) == len(load_targets("allen"))
    assert c.loc[c["kind"] != "info", "ours"].notna().all()
    misses = c[c["pass"].astype(str) == "False"]
    assert misses["deviation"].fillna("").str.startswith("ALN-").all()


@needs_panel
@pytest.mark.data
def test_original_segment_is_self_contained():
    # No 2000-2018 number may depend on later years: winsorization and matching are per segment.
    seg = T.allen_segments()["original"]
    x = T._in(seg)
    assert x["fy"].between(2000, 2018).all()
    p = T.panel()
    upto = p[p["fy"] <= 2018]
    treated_upto = set(upto.loc[upto["cross_listed_h"] == 1, "stkcd"])
    treated_ever = set(p.loc[p["cross_listed_h"] == 1, "stkcd"])
    m = set(T.matched_cross_listed(upto))
    # Firms that list H shares only after 2018 may be controls, never treated firms.
    assert treated_upto <= m
    t13 = T.table13(seg)
    n_treated = t13.loc[t13["col"] == "cross_listed_firms", "value"].iloc[0]
    assert n_treated == len(treated_upto & m) < len(treated_ever)


@needs_panel
@pytest.mark.data
def test_figure1_starts_at_one_in_2000_12():
    b = T.bhr(T.allen_segments()["original"])
    assert b.index[0] == pd.Period("2000-12", "M") and (b.iloc[0] == 1.0).all()
    assert b.index[-1] == pd.Period("2018-12", "M")
