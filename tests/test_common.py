"""Unit tests for replication.common: statistics against statsmodels / closed forms, and the
sorting rules every factor depends on. Synthetic data only, so they run anywhere."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm

from replication.common.compare import judge, t_band
from replication.common.periods import segments
from replication.common.portfolios import assign_groups, weighted_returns
from replication.common.stats import fama_macbeth, grs, mean_t, ols


@pytest.fixture
def ts():
    rng = np.random.default_rng(0)
    T = 240
    f = pd.DataFrame(rng.normal(0.5, 4, (T, 2)), columns=["f1", "f2"])
    y = 0.3 + f @ np.array([1.0, -0.5]) + rng.normal(0, 2, T) * (1 + np.abs(f["f1"]) / 4)
    return y, f


def test_mean_t_plain_matches_lsy_table3_arithmetic():
    # LSY Table 3: mean 0.66, std 8.09, 204 months -> t 1.16
    x = pd.Series(np.r_[np.full(102, 0.66 + 8.09), np.full(102, 0.66 - 8.09)])
    st = mean_t(x)
    assert st.mean == pytest.approx(0.66)
    assert st.t == pytest.approx(0.66 / (st.std / np.sqrt(204)))


def test_ols_white_matches_statsmodels_hc0(ts):
    y, f = ts
    ours = ols(y, f, se="white")
    ref = sm.OLS(y, sm.add_constant(f)).fit(cov_type="HC0")
    assert np.allclose(ours.params.to_numpy(), ref.params.to_numpy())
    assert np.allclose(ours.tstats.to_numpy(), ref.tvalues.to_numpy())


def test_ols_newey_west_matches_statsmodels_hac(ts):
    y, f = ts
    ours = ols(y, f, se="nw", nw_lags=4)
    ref = sm.OLS(y, sm.add_constant(f)).fit(cov_type="HAC", cov_kwds={"maxlags": 4, "use_correction": False})
    assert np.allclose(ours.tstats.to_numpy(), ref.tvalues.to_numpy())


def test_grs_single_asset_equals_squared_classical_alpha_t(ts):
    # With N = 1 the exact GRS F statistic equals the squared homoskedastic t-statistic of
    # the alpha (an independent check: computed by the OLS routine, not by the GRS formula).
    y, f = ts
    t_alpha = ols(y, f, se="classic").tstats["alpha"]
    assert grs(pd.DataFrame({"a": y}), f).stat == pytest.approx(t_alpha ** 2, rel=1e-10)


def test_grs_rejects_large_alphas_and_not_zero_alphas():
    rng = np.random.default_rng(1)
    T = 300
    f = pd.DataFrame({"m": rng.normal(0.5, 5, T)})
    noise = rng.normal(0, 1, (T, 5))
    null = pd.DataFrame(f.to_numpy() * 1.0 + noise)
    alt = null + 1.0
    assert grs(alt, f).pvalue < 1e-6
    assert grs(null, f).pvalue > 0.01


def test_fama_macbeth_recovers_constant_slope():
    rng = np.random.default_rng(2)
    rows = []
    for t in range(60):
        x = rng.normal(size=200)
        rows.append(pd.DataFrame({"month": t, "x": x, "y": 0.1 + 2.0 * x + rng.normal(0, 0.1, 200)}))
    r = fama_macbeth(pd.concat(rows), "y", ["x"])
    assert r.coef["x"] == pytest.approx(2.0, abs=0.01)
    assert r.n_periods == 60


def test_assign_groups_ties_go_to_lower_group_and_mask_sets_breakpoints():
    df = pd.DataFrame({"month": 1, "v": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10.0]})
    g = assign_groups(df, "v", [0.5], labels=["S", "B"])
    assert g.tolist() == ["S"] * 5 + ["B"] * 5  # median 5.5
    # Breakpoints from the first five rows only: median 3 -> 3 itself goes to the lower group
    mask = pd.Series([True] * 5 + [False] * 5)
    g2 = assign_groups(df, "v", [0.5], breakpoint_mask=mask, labels=["S", "B"])
    assert g2.tolist() == ["S"] * 3 + ["B"] * 7


def test_weighted_returns_value_weights_and_skips_missing():
    df = pd.DataFrame({"month": [1, 1, 1], "g": ["a", "a", "a"], "ret": [0.1, 0.0, np.nan], "weight": [3, 1, 100]})
    out = weighted_returns(df, ["g"])
    assert out.loc[1, "a"] == pytest.approx(0.075)


def test_segments_are_contiguous():
    s = segments("2000-01", "2016-12", data_end=pd.Period("2026-09", "M"))
    assert s["extended"].start == s["original"].end + 1
    assert s["full"].start == s["original"].start and s["full"].end == s["extended"].end
    assert s["original"].n_months == 204


def test_tolerance_rules():
    assert t_band(1.95) == 0 and t_band(2.0) == 1 and t_band(2.79) == 2
    assert judge("pct_return", 1.14, 1.05) and not judge("pct_return", 1.14, 1.03)
    assert judge("t", 4.34, 3.0) and not judge("t", 2.30, 2.9)
    assert judge("pvalue", 0.41, 0.2) and not judge("pvalue", 0.41, 0.01)
    assert judge("coef", -0.62, -0.1) and not judge("coef", -0.62, 0.1)
    assert judge("pct_return", 1.0, float("nan")) is False
    assert judge("coef", 0.0, -0.01) is None  # printed 0.00 has no sign
    assert judge("pvalue", 0.05, 0.049) and judge("pvalue", 0.05, 0.051)
    assert judge("count", 133, 130) and not judge("count", 133, 108)
    assert judge("info", 1.0, float("nan")) is None


def test_bound_and_annual_rules():
    assert judge("upper_bound", 0.42, 0.42) and not judge("upper_bound", 0.42, 0.46)
    assert judge("lower_bound", 50, 51) and not judge("lower_bound", 50, 38)
    assert judge("pct_annual", 12.36, 11.2) and not judge("pct_annual", 18, 13.9)
    assert judge("share_pct", 15, 17.9) and not judge("share_pct", 82, 77.7)
    assert judge("rel10", 2.78, 2.87) and not judge("rel10", 0.8, 1.33)
    assert judge("rel10", 0, 0) and not judge("rel10", 0, 0.1)


def test_contrast_t_matches_statsmodels_t_test():
    import statsmodels.api as sm
    from replication.common.stats import panel_regression
    rng = np.random.default_rng(5)
    n = 500
    d = pd.DataFrame({"a": rng.normal(size=n), "b": rng.normal(size=n), "g": rng.integers(0, 25, n)})
    d["y"] = 0.5 * d["a"] + 0.2 * d["b"] + rng.normal(size=n)
    r = panel_regression(d, "y", ["a", "b"], cluster=["g"])
    m = sm.OLS(d["y"], sm.add_constant(d[["a", "b"]])).fit(cov_type="cluster", cov_kwds={"groups": d["g"]})
    diff, t = r.contrast_t("a", "b")
    assert diff == pytest.approx(m.params["a"] - m.params["b"])
    assert t == pytest.approx(float(np.squeeze(m.t_test("a - b = 0").tvalue)), rel=1e-6)


def test_panel_regression_matches_statsmodels_one_way_cluster():
    from replication.common.stats import panel_regression
    rng = np.random.default_rng(3)
    n = 600
    df = pd.DataFrame({"g": rng.integers(0, 30, n), "yr": rng.integers(0, 10, n), "x": rng.normal(size=n)})
    df["y"] = 1 + 0.5 * df["x"] + 0.3 * (df["yr"] % 3) + rng.normal(size=n) + df["g"] * 0.01
    ours = panel_regression(df, "y", ["x"], fe=["yr"], cluster=["g"])
    X = sm.add_constant(pd.concat([df[["x"]], pd.get_dummies(df["yr"].astype(str), prefix="yr", drop_first=True, dtype=float)], axis=1))
    ref = sm.OLS(df["y"], X).fit(cov_type="cluster", cov_kwds={"groups": df["g"]})
    assert ours.params["x"] == pytest.approx(ref.params["x"])
    assert ours.tstats["x"] == pytest.approx(ref.tvalues["x"], rel=1e-6)
