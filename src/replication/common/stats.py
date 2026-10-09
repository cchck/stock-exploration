"""Test statistics used across the three papers.

Each function states the standard-error convention it implements, because the papers differ:
LSY report White (1980) heteroskedasticity-consistent t-statistics for time-series
regressions and plain t-statistics for factor means; Li et al. use Newey-West. The choice is
always an explicit argument, never a hidden default that differs from a paper.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats as sps


@dataclass(frozen=True)
class MeanStat:
    mean: float
    std: float
    t: float
    n: int


def mean_t(x: pd.Series, *, nw_lags: int | None = None) -> MeanStat:
    """Mean, standard deviation and t-statistic of a time series.

    nw_lags=None gives the plain t-statistic mean / (std / sqrt(n)), which is what LSY
    Table 3 reports (0.66 / (8.09 / sqrt(204)) = 1.16). With nw_lags, the standard error is
    Newey-West with Bartlett weights.
    """
    v = pd.Series(x, dtype=float).dropna().to_numpy()
    n = len(v)
    if n < 2:
        raise ValueError("mean_t needs at least two observations")
    m, s = v.mean(), v.std(ddof=1)
    if nw_lags is None:
        se = s / np.sqrt(n)
    else:
        se = np.sqrt(_nw_long_run_variance(v - m, nw_lags) / n)
    return MeanStat(mean=m, std=s, t=m / se, n=n)


def _nw_long_run_variance(u: np.ndarray, lags: int) -> float:
    n = len(u)
    lrv = u @ u / n
    for lag in range(1, lags + 1):
        w = 1 - lag / (lags + 1)
        lrv += 2 * w * (u[lag:] @ u[:-lag]) / n
    return float(lrv)


@dataclass(frozen=True)
class OLSResult:
    params: pd.Series
    tstats: pd.Series
    resid: np.ndarray
    r2: float
    n: int
    se_type: str


def ols(y: pd.Series, X: pd.DataFrame, *, se: str = "white", nw_lags: int | None = None,
        add_const: bool = True) -> OLSResult:
    """Time-series OLS with a stated standard-error type.

    se="white": White (1980) HC0, as in LSY Tables 5-10. se="nw": Newey-West with nw_lags.
    se="classic": homoskedastic. Rows with any missing value are dropped (and counted in n).
    """
    data = pd.concat([pd.Series(y, name="__y"), X], axis=1).dropna()
    yv = data["__y"].to_numpy(float)
    Xd = data.drop(columns="__y")
    if add_const:
        Xd = pd.concat([pd.Series(1.0, index=Xd.index, name="alpha"), Xd], axis=1)
    Xv = Xd.to_numpy(float)
    n, k = Xv.shape
    if n <= k:
        raise ValueError(f"ols: {n} observations for {k} parameters")
    xtx_inv = np.linalg.inv(Xv.T @ Xv)
    beta = xtx_inv @ Xv.T @ yv
    resid = yv - Xv @ beta
    if se == "classic":
        cov = xtx_inv * (resid @ resid / (n - k))
    elif se == "white":
        meat = (Xv * resid[:, None]).T @ (Xv * resid[:, None])
        cov = xtx_inv @ meat @ xtx_inv
    elif se == "nw":
        if nw_lags is None:
            raise ValueError("se='nw' needs nw_lags")
        Xu = Xv * resid[:, None]
        meat = Xu.T @ Xu
        for lag in range(1, nw_lags + 1):
            w = 1 - lag / (nw_lags + 1)
            g = Xu[lag:].T @ Xu[:-lag]
            meat += w * (g + g.T)
        cov = xtx_inv @ meat @ xtx_inv
    else:
        raise ValueError(f"unknown se type {se!r}")
    sd = np.sqrt(np.diag(cov))
    tss = ((yv - yv.mean()) ** 2).sum()
    return OLSResult(
        params=pd.Series(beta, index=Xd.columns), tstats=pd.Series(beta / sd, index=Xd.columns),
        resid=resid, r2=1 - resid @ resid / tss, n=n, se_type=se,
    )


@dataclass(frozen=True)
class GRSResult:
    stat: float
    pvalue: float
    n_assets: int
    n_periods: int
    n_factors: int


def grs(test_assets: pd.DataFrame, factors: pd.DataFrame) -> GRSResult:
    """Gibbons, Ross and Shanken (1989) test that all alphas are zero.

    test_assets: T x N excess returns; factors: T x K factor returns (excess where needed).
    Uses the finite-sample F form: (T/N)(T-N-K)/(T-K-1) * a' S^-1 a / (1 + mu' O^-1 mu),
    with S and O the MLE (divide by T) covariance matrices of residuals and factors.
    """
    data = pd.concat([test_assets, factors], axis=1, keys=["a", "f"]).dropna()
    R, F = data["a"].to_numpy(float), data["f"].to_numpy(float)
    T, N = R.shape
    K = F.shape[1]
    if T - N - K <= 0:
        raise ValueError(f"GRS needs T > N + K (T={T}, N={N}, K={K})")
    X = np.column_stack([np.ones(T), F])
    B = np.linalg.lstsq(X, R, rcond=None)[0]
    alpha = B[0]
    E = R - X @ B
    sigma = E.T @ E / T
    mu = F.mean(axis=0)
    omega = np.cov(F, rowvar=False, bias=True).reshape(K, K)
    stat = (T / N) * ((T - N - K) / (T - K - 1)) * (alpha @ np.linalg.solve(sigma, alpha)) / (
        1 + mu @ np.linalg.solve(omega, mu))
    return GRSResult(stat=float(stat), pvalue=float(sps.f.sf(stat, N, T - N - K)),
                     n_assets=N, n_periods=T, n_factors=K)


@dataclass(frozen=True)
class FMResult:
    coef: pd.Series
    tstats: pd.Series
    avg_r2: float
    avg_adj_r2: float
    n_periods: int
    coef_series: pd.DataFrame


def fama_macbeth(df: pd.DataFrame, y: str, xs: list[str], *, time: str = "month",
                 nw_lags: int | None = None, min_obs: int | None = None) -> FMResult:
    """Fama-MacBeth (1973): cross-sectional OLS each period, then time-series means.

    t-statistics are plain (nw_lags=None) or Newey-West on the coefficient series.
    A period is skipped if it has fewer than min_obs complete rows (default: len(xs) + 2).
    """
    need = min_obs or len(xs) + 2
    rows, r2s, adj = {}, [], []
    for t, g in df[[time, y, *xs]].dropna().groupby(time):
        if len(g) < need:
            continue
        X = np.column_stack([np.ones(len(g)), g[xs].to_numpy(float)])
        yy = g[y].to_numpy(float)
        b = np.linalg.lstsq(X, yy, rcond=None)[0]
        e = yy - X @ b
        r2 = 1 - e @ e / ((yy - yy.mean()) ** 2).sum()
        r2s.append(r2)
        adj.append(1 - (1 - r2) * (len(yy) - 1) / (len(yy) - len(xs) - 1))
        rows[t] = b
    if not rows:
        raise ValueError("fama_macbeth: no period had enough observations")
    coefs = pd.DataFrame.from_dict(rows, orient="index", columns=["const", *xs]).sort_index()
    means, ts = {}, {}
    for c in coefs:
        s = mean_t(coefs[c], nw_lags=nw_lags)
        means[c], ts[c] = s.mean, s.t
    return FMResult(coef=pd.Series(means), tstats=pd.Series(ts), avg_r2=float(np.mean(r2s)), avg_adj_r2=float(np.mean(adj)),
                    n_periods=len(coefs), coef_series=coefs)
