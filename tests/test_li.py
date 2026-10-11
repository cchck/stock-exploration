"""Li et al. (2024) replication checks (milestone 1.4). Data tests need the licensed CSMAR
files and the authors' replication package; they are skipped otherwise."""

from __future__ import annotations

import pandas as pd
import pytest

from csmar.registry import PROJECT_ROOT
from replication.common.compare import load_targets

PKG = PROJECT_ROOT / "data/raw/external/li_et_al/replication_package_MS-FIN-21-02398"
needs_pkg = pytest.mark.skipif(not (PKG / "allfactors.sas7bdat").exists(), reason="authors' replication package missing")


def _authors_factors() -> pd.DataFrame:
    import pyreadstat
    af, _ = pyreadstat.read_sas7bdat(PKG / "allfactors.sas7bdat")
    af.index = pd.PeriodIndex(af["trdmnt"], freq="M")
    return af


def test_targets_file_is_well_formed():
    t = load_targets("li")
    assert {"T1", "T2", "T3", "T4", "T5", "T6", "T7", "TXT"} <= set(t["table"])
    assert len(t) == 4270
    assert not t.duplicated(["table", "row", "col"]).any()
    # 78 significant anomalies over the whole period, 61 post-2007 (Table 4)
    sig = t[(t["table"] == "T4") & (t["col"] == "m")]
    assert sig["row"].str.startswith("A:").sum() == 78 and sig["row"].str.startswith("B:").sum() == 61


@needs_pkg
def test_three_month_deposit_rate_matches_authors_every_month():
    from replication.li.rates import rf_monthly
    a = _authors_factors()["monthlyrf"]
    ours = rf_monthly().reindex(a.index)
    assert (ours - a).abs().max() < 1e-6


@pytest.mark.data
def test_table1_panel_a_counts_and_caps_match_paper():
    from replication.li.data import table1_panel_a
    t = load_targets("li")
    t = t[(t["table"] == "T1") & t["row"].str.startswith("A:")]
    ours = table1_panel_a(range(1999, 2019)).set_index("year")
    for _, r in t.iterrows():
        y = int(r["row"][2:])
        col = r["col"]
        assert ours.loc[y, col] == pytest.approx(r["paper"], abs=0.006 if not col.startswith("n_") else 0), (y, col)


@needs_pkg
@pytest.mark.data
def test_factors_correlate_with_authors():
    from replication.li import factors as F
    af = _authors_factors()
    ours = pd.concat([F.mkt(), F.ff_factors(), F.q_factors()], axis=1)
    for c in ["mkt", "smbff3", "hmlff3", "smbff5", "hml", "cma", "me", "ia", "roe"]:
        x = pd.concat([ours[c], af[c]], axis=1).dropna()
        assert x.corr().iloc[0, 1] >= 0.95, c
