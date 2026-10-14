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
    assert len(t) == 4275
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


def test_catalog_counts_match_paper_and_buildable_set():
    from replication.li import catalog as C
    C.check()  # 45/68/36/94/83/143 = 469; 104 single + 73 monthly
    built = [a for v in C.VARS if v.builder for a in v.anomalies]
    assert len(built) == 453
    missing = sorted(v.name for v in C.VARS if v.builder is None)
    assert missing == ["Esba", "Parc", "Qsba", "Vpin"]


def _synthetic_panel():
    """Two formation months, 10 mainboard + 5 GEM stocks; returns equal to q/100 so the
    expected quintile returns are known."""
    months = pd.period_range("2010-01", "2010-04", freq="M")
    rows = []
    for i in range(15):
        for m in months:
            rows.append({"stkcd": f"{i:06d}", "month": m, "ret": 0.0, "mv_float": 100.0 + i, "mv_total": 200.0,
                         "close": 10.0, "board": "SH_MAIN" if i < 10 else "CHINEXT", "mainboard": i < 10,
                         "eligible": True, "normal_status": True, "w": 100.0 + i})
    return pd.DataFrame(rows)


def test_engine_breakpoints_ties_and_holding_average(monkeypatch):
    from replication.li import portfolios as PF
    p = _synthetic_panel()
    monkeypatch.setattr(PF, "_PANEL", p)
    monkeypatch.setattr(PF, "NEGATIVE_BE_SCREEN", False)
    form = pd.Period("2010-01", "M")
    # mainboard values 1..10 -> breakpoints at 2.8, 4.6, 6.4, 8.2; GEM stocks get 2.8 (tie -> lower group) and 9
    vals = list(range(1, 11)) + [2.8, 2.8, 9, 9, 9]
    sig = pd.DataFrame({"stkcd": [f"{i:06d}" for i in range(15)], "form": form, "value": vals})
    g = PF.assign_quintiles(sig, PF.PROCEDURES["Mainboard-VW"]).set_index("stkcd")["q"]
    assert g["000000"] == 1 and g["000009"] == 5 and g["000010"] == 1 and g["000012"] == 5
    # returns: quintile k earns k% in Feb and 10k% in March; 3-month holding averages cohorts
    p.loc[:, "ret"] = 0.0
    qmap = g.to_dict()
    for s, q in qmap.items():
        p.loc[(p["stkcd"] == s) & (p["month"] == form + 1), "ret"] = q / 100
        p.loc[(p["stkcd"] == s) & (p["month"] == form + 2), "ret"] = q / 10
    monkeypatch.setattr(PF, "_PANEL", p)
    sig2 = pd.concat([sig, sig.assign(form=form + 1)])  # second cohort with the same ranks
    res = PF.quintile_returns_multi(sig2, PF.PROCEDURES["Mainboard-EW"], "monthly", (1, 3))
    assert res[1].loc[form + 1, "g5"] == pytest.approx(0.05)
    # month 2010-03: cohort Jan (lag 2, earns q/10) and cohort Feb (lag 1, earns q/10): mean q/10
    assert res[3].loc[form + 2, "g5"] == pytest.approx(0.5)


def test_variant_switch_sets_holding_filter():
    import subprocess, sys, os
    code = ("import sys; sys.path.insert(0,'src'); from replication.li import anomalies as A, portfolios as PF; "
            "print(A.VARIANT, PF.HOLDING_MONTH_FILTER, A.CACHE.name)")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=PROJECT_ROOT,
                         env={**os.environ, "LI_VARIANT": "clean"}).stdout.split()
    assert out == ["clean", "False", "li_quintiles_clean.parquet"]


@needs_pkg
@pytest.mark.data
def test_price_sort_reproduces_authors_series():
    """The engine with the authors' penny / status rules (LI-2) reproduces their Pps1."""
    from replication.li import portfolios as PF, signals_market as M
    from replication.li.checks import _read
    a = _read(PKG / "g5_g1_2000_2019" / "pps_1_2.sas7bdat")
    o = PF.quintile_returns(M.pps(), PF.PROCEDURES["Mainboard-VW"], "monthly", 1)
    x = pd.concat([o["g5_g1"], a["g5_g1"]], axis=1).dropna()
    assert x.corr().iloc[0, 1] > 0.995


@pytest.mark.skipif(not (PROJECT_ROOT / "results/li/extended_tables_clean.csv").exists(), reason="run replication.li first")
def test_segments_share_table_structure():
    """Lighthouse 6: the three segments come from the same functions with the same tables."""
    tabs = {}
    for seg in ("original", "extended", "full"):
        for v in ("", "_clean"):
            t = pd.read_csv(PROJECT_ROOT / f"results/li/{seg}_tables{v}.csv")
            tabs[(seg, v)] = set(t["table"])
    assert len({frozenset(s) for s in tabs.values()}) == 1
