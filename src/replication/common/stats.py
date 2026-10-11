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
    F = (T - N - K) / N * a' S^-1 a / (1 + mu' O^-1 mu), with S and O the MLE (divide by T)
    covariance matrices of residuals and factors; F ~ F(N, T - N - K) under the null.
    Check: with N = 1 this equals the squared classical t-statistic of the alpha.
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
    stat = (T - N - K) / N * (alpha @ np.linalg.solve(sigma, alpha)) / (1 + mu @ np.linalg.solve(omega, mu))
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


@dataclass(frozen=True)
class PanelResult:
    params: pd.Series
    tstats: pd.Series
    r2: float
    n: int
    cov: pd.DataFrame | None = None  # covariance of const and xs (for contrasts such as b1 - b2)

    def contrast_t(self, a: str, b: str) -> tuple[float, float]:
        """Difference params[a] - params[b] and its t-statistic, using the same clustered
        covariance as the coefficients."""
        diff = float(self.params[a] - self.params[b])
        var = float(self.cov.loc[a, a] + self.cov.loc[b, b] - 2 * self.cov.loc[a, b])
        return diff, diff / np.sqrt(var) if var > 0 else float("nan")


def panel_regression(df: pd.DataFrame, y: str, xs: list[str], *, fe: list[str] = (), cluster: list[str] = (),
                     weight: str | None = None, cluster_mode: str = "twoway") -> PanelResult:
    """OLS or WLS with fixed effects as dummies and one- or two-way clustered standard errors.

    - fe: categorical columns entered as dummies (first level dropped), like the industry,
      year and province dummies in Allen et al.'s SAS PROC SURVEYREG code.
    - cluster: one or two columns. Two-way clustering follows Cameron, Gelbach and Miller
      (2011): V = V_a + V_b - V_ab. A finite-sample factor G/(G-1) * (N-1)/(N-K) is applied
      to each component, as SAS SURVEYREG does for its cluster variance.
    - cluster_mode="cells": with two cluster columns, clusters are their unique combinations
      (e.g. industry-by-year cells), which is how SAS PROC SURVEYREG forms clusters from
      several CLUSTER variables; "twoway" is the CGM estimator above.
    - weight: WLS weights (rows are multiplied by sqrt(weight)).
    R-squared is that of the (weighted) regression including the fixed effects. Rows with any
    missing value in y, xs, fe, cluster or weight are dropped.
    """
    # A column may serve as both a fixed effect and a cluster dimension (industry, year):
    # select it once.
    cols = list(dict.fromkeys([y, *xs, *fe, *cluster] + ([weight] if weight else [])))
    d = df[cols].dropna()
    if weight:
        d = d[d[weight] > 0]
    X = d[list(xs)].astype(float)
    for f in fe:
        X = pd.concat([X, pd.get_dummies(d[f].astype(str), prefix=f, drop_first=True, dtype=float)], axis=1)
    X.insert(0, "const", 1.0)
    Xv, yv = X.to_numpy(float), d[y].to_numpy(float)
    if weight:
        w = np.sqrt(d[weight].to_numpy(float))
        Xv, yv = Xv * w[:, None], yv * w
    n, k = Xv.shape
    xtx_inv = np.linalg.pinv(Xv.T @ Xv)
    beta = xtx_inv @ Xv.T @ yv
    e = yv - Xv @ beta

    def meat(groups: np.ndarray) -> tuple[np.ndarray, int]:
        u = Xv * e[:, None]
        s = pd.DataFrame(u).groupby(groups).sum().to_numpy()
        G = s.shape[0]
        return s.T @ s * (G / (G - 1)) * ((n - 1) / (n - k)), G

    if len(cluster) == 0:
        V = xtx_inv @ ((Xv * e[:, None]).T @ (Xv * e[:, None])) @ xtx_inv
    elif len(cluster) == 1:
        V = xtx_inv @ meat(d[cluster[0]].astype(str).to_numpy())[0] @ xtx_inv
    elif len(cluster) == 2 and cluster_mode == "cells":
        cells = (d[cluster[0]].astype(str) + "|" + d[cluster[1]].astype(str)).to_numpy()
        V = xtx_inv @ meat(cells)[0] @ xtx_inv
    elif len(cluster) == 2:
        a = d[cluster[0]].astype(str).to_numpy()
        b = d[cluster[1]].astype(str).to_numpy()
        ab = np.char.add(np.char.add(a.astype(str), "|"), b.astype(str))
        Va = xtx_inv @ meat(a)[0] @ xtx_inv
        Vb = xtx_inv @ meat(b)[0] @ xtx_inv
        V = Va + Vb - xtx_inv @ meat(ab)[0] @ xtx_inv
        # The two-way estimate can have a negative diagonal (e.g. a regressor constant within
        # firm and few clusters). Following Cameron, Gelbach and Miller (2011), such entries
        # fall back to the larger one-way variance instead of returning no standard error.
        neg = np.diag(V) <= 0
        if neg.any():
            fallback = np.maximum(np.diag(Va), np.diag(Vb))
            V[np.diag_indices_from(V)] = np.where(neg, fallback, np.diag(V))
    else:
        raise ValueError("at most two cluster dimensions")
    se = np.sqrt(np.clip(np.diag(V), 0, None))
    ybar = np.average(d[y], weights=d[weight]) if weight else d[y].mean()
    yc = (d[y].to_numpy(float) - ybar) * (np.sqrt(d[weight].to_numpy(float)) if weight else 1)
    names = X.columns
    keep = ["const", *xs]
    params = pd.Series(beta, index=names)[keep]
    tstats = pd.Series(beta / np.where(se > 0, se, np.nan), index=names)[keep]
    idx = [list(names).index(c) for c in keep]
    cov = pd.DataFrame(V[np.ix_(idx, idx)], index=keep, columns=keep)
    return PanelResult(params=params, tstats=tstats, r2=float(1 - e @ e / (yc @ yc)), n=n, cov=cov)
