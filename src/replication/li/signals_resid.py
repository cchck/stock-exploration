"""Regression-based anomaly signals of Li et al.: idiosyncratic volatility and skewness
(DM A.6.2-A.6.8, A.6.21-A.6.26), Dimson beta (A.6.12), market beta (A.6.11), residual
momentum (A.1.8-A.1.9) and price delay (A.5.14). Same (stkcd, form, value) convention.

Daily regressions run per stock and month t-1 with at least 10 valid daily returns (DM:
"a minimum of 10 valid daily returns", relaxed from HXZ's 15 because of the Spring
Festival). They are solved in batch: per stock-month cross-product sums are accumulated and
the normal equations solved for all groups at once.

Daily factors: MKT and the self-built FF3 / FF5 / q factors from factors.daily_factors();
CH-3 / CH-4 from Stambaugh's website, available to 2021-12, so Ivch / Isch end there
(lighthouse 6: tables truncated at data availability and noted).
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from replication.li import data as D
from replication.li import factors as F
from replication.li.rates import rf_monthly

MIN_DAYS = 10

MODELS = {
    "capm": ["mkt"],
    "ff3": ["mkt", "smbff3", "hmlff3"],
    "ff5": ["mkt", "smbff5", "hml", "rmw", "cma"],
    "q": ["mkt", "me", "ia", "roe"],
    "ch3": ["mktch", "smbch3", "vmgch3"],
    "ch4": ["mktch", "smbch4", "vmgch4", "pmo"],
}


def _out(df: pd.DataFrame, value: str = "v") -> pd.DataFrame:
    o = df[["stkcd", "form", value]].rename(columns={value: "value"})
    return o.replace([np.inf, -np.inf], np.nan).dropna(subset=["value"]).reset_index(drop=True)


@lru_cache(maxsize=1)
def _daily() -> pd.DataFrame:
    """Daily stock excess returns joined with every daily factor."""
    from csmar.panels import daily
    d = daily(["Dretwd"])
    d = d[d["board"].isin(D.BOARDS_EXTENSION)]
    d = pd.DataFrame({"stkcd": d["stkcd"].astype("string"), "date": d["date"],
                      "r": pd.to_numeric(d["Dretwd"], errors="coerce")}).dropna(subset=["r"])
    f = F.daily_factors().join(F.ch_daily(), how="left")
    d = d.merge(f, left_on="date", right_index=True, how="inner")
    d["y"] = d["r"] - d["rf"]
    d["month"] = d["date"].dt.to_period("M")
    return d.sort_values(["stkcd", "date"]).reset_index(drop=True)


def batch_ols(y: np.ndarray, X: np.ndarray, g: np.ndarray, n_groups: int):
    """OLS of y on [1, X] separately for each group id in g (0..n_groups-1). Returns
    (coefficients [G, k+1], residuals [n], observations per group [G])."""
    n, k = X.shape
    Z = np.column_stack([np.ones(n), X])
    K = k + 1
    xtx = np.zeros((n_groups, K, K))
    xty = np.zeros((n_groups, K))
    for i in range(K):
        np.add.at(xty[:, i], g, Z[:, i] * y)
        for j in range(i, K):
            np.add.at(xtx[:, i, j], g, Z[:, i] * Z[:, j])
            xtx[:, j, i] = xtx[:, i, j]
    cnt = np.bincount(g, minlength=n_groups)
    beta = np.full((n_groups, K), np.nan)
    ok = cnt >= K + 1
    try:
        beta[ok] = np.linalg.solve(xtx[ok], xty[ok][..., None])[..., 0]
    except np.linalg.LinAlgError:
        for idx in np.flatnonzero(ok):
            beta[idx] = np.linalg.lstsq(xtx[idx], xty[idx], rcond=None)[0]
    resid = y - np.einsum("ij,ij->i", Z, beta[g])
    return beta, resid, cnt


def _moments(resid: np.ndarray, g: np.ndarray, n_groups: int, n_params: int):
    """Residual standard deviation (n - p degrees of freedom) and sample skewness by group."""
    cnt = np.bincount(g, minlength=n_groups).astype(float)
    s1 = np.bincount(g, weights=resid, minlength=n_groups)
    s2 = np.bincount(g, weights=resid ** 2, minlength=n_groups)
    s3 = np.bincount(g, weights=resid ** 3, minlength=n_groups)
    with np.errstate(divide="ignore", invalid="ignore"):
        mean = s1 / cnt
        sd = np.sqrt(np.clip(s2 - cnt * mean ** 2, 0, None) / (cnt - n_params))
        m2 = s2 / cnt - mean ** 2
        m3 = s3 / cnt - 3 * mean * s2 / cnt + 2 * mean ** 3
        skew = m3 / m2 ** 1.5 * np.sqrt(cnt * (cnt - 1)) / (cnt - 2)
    return sd, skew, cnt


@lru_cache(maxsize=8)
def _idio(model: str) -> pd.DataFrame:
    """Per stock and month: residual sd and skewness of the daily model regression."""
    cols = MODELS[model]
    d = _daily().dropna(subset=cols)
    key = d["stkcd"].astype(str) + "|" + d["month"].astype(str)
    g, uniq = pd.factorize(key)
    beta, resid, cnt = batch_ols(d["y"].to_numpy(), d[cols].to_numpy(), g, len(uniq))
    sd, skew, n = _moments(resid, g, len(uniq), len(cols) + 1)
    out = d.groupby(g)[["stkcd", "month"]].first()
    out["sd"], out["skew"], out["n"] = sd, skew, n
    out = out[out["n"] >= MIN_DAYS]
    return out.rename(columns={"month": "form"})


def _iv(model):
    return _out(_idio(model).rename(columns={"sd": "v"}))


def _is(model):
    return _out(_idio(model).rename(columns={"skew": "v"}))


def ivc(): return _iv("capm")
def ivff3(): return _iv("ff3")
def ivff5(): return _iv("ff5")
def ivq(): return _iv("q")
def ivch3(): return _iv("ch3")
def ivch4(): return _iv("ch4")
def isc(): return _is("capm")
def isff3(): return _is("ff3")
def isff5(): return _is("ff5")
def isq(): return _is("q")
def isch3(): return _is("ch3")
def isch4(): return _is("ch4")


def beta_d() -> pd.DataFrame:
    """βD (A.6.12): sum of the slopes on the lagged, current and lead daily market excess
    return, month t-1, the lead day within the month; at least 10 observations."""
    d = _daily()[["stkcd", "date", "month", "y"]].copy()
    m = F.daily_factors()["mkt"]
    days = m.index
    lag = pd.Series(m.shift(1).to_numpy(), index=days)
    lead = pd.Series(m.shift(-1).to_numpy(), index=days)
    lead_month = pd.Series(pd.PeriodIndex(days, freq="M"), index=days).shift(-1)
    d["m0"], d["m_1"], d["m1"] = d["date"].map(m), d["date"].map(lag), d["date"].map(lead)
    same = d["date"].map(lead_month) == d["month"]
    d = d[same].dropna(subset=["m0", "m_1", "m1"])
    key = d["stkcd"].astype(str) + "|" + d["month"].astype(str)
    g, uniq = pd.factorize(key)
    beta, _, cnt = batch_ols(d["y"].to_numpy(), d[["m_1", "m0", "m1"]].to_numpy(), g, len(uniq))
    out = d.groupby(g)[["stkcd", "month"]].first()
    out["v"] = beta[:, 1:].sum(axis=1)
    out = out[cnt >= MIN_DAYS].rename(columns={"month": "form"})
    return _out(out)


@lru_cache(maxsize=1)
def _monthly_excess() -> tuple[pd.DataFrame, pd.DataFrame]:
    p = D.stock_panel()
    r = p.pivot(index="month", columns="stkcd", values="ret")
    full = pd.period_range(r.index.min(), r.index.max(), freq="M")
    r = r.reindex(full)
    rf = rf_monthly().reindex(full)
    fac = F.mkt().to_frame().join(F.ff_factors()[["smbff3", "hmlff3"]], how="left").reindex(full)
    return r.sub(rf, axis=0), fac


def _rolling_ols_wide(Y: pd.DataFrame, X: pd.DataFrame, window: int, min_obs: int):
    """Rolling-window OLS of each column of Y on [1, X] (same X for all stocks), windows
    ending at each row, rows with a missing y dropped stock by stock. Returns a dict of
    coefficient frames {name: DataFrame} with the same shape as Y."""
    cols = ["const", *X.columns]
    Xa = np.column_stack([np.ones(len(X)), X.to_numpy()])
    K = Xa.shape[1]
    Yv = Y.to_numpy()
    valid = ~np.isnan(Yv) & ~np.isnan(Xa).any(axis=1)[:, None]
    Yz = np.where(valid, Yv, 0.0)
    Xz = np.where(np.isnan(Xa), 0.0, Xa)
    # cumulative sums of X'X and X'y per stock (X'X differs by stock through the valid mask)
    xtx = np.einsum("ti,tj,ts->tsij", Xz, Xz, valid.astype(float))
    xty = np.einsum("ti,ts->tsi", Xz, Yz)
    cxtx, cxty, cn = np.cumsum(xtx, axis=0), np.cumsum(xty, axis=0), np.cumsum(valid, axis=0)
    def win(c):
        out = c.copy()
        out[window:] = c[window:] - c[:-window]
        return out
    wxtx, wxty, wn = win(cxtx), win(cxty), win(cn)
    beta = np.full(wxty.shape, np.nan)
    ok = wn >= min_obs
    sub = np.linalg.pinv(wxtx[ok]) @ wxty[ok][..., None]
    beta[ok] = sub[..., 0]
    return {c: pd.DataFrame(beta[..., i], index=Y.index, columns=Y.columns) for i, c in enumerate(cols)}, valid


def beta() -> pd.DataFrame:
    """β (A.6.11): slope of monthly excess returns on MKT over t-60..t-1 (>= 24 months)."""
    Y, fac = _monthly_excess()
    b, _ = _rolling_ols_wide(Y, fac[["mkt"]], 60, 24)
    v = b["mkt"].stack().rename("value").reset_index().rename(columns={"level_0": "form"})
    return v.dropna()


def _resid_mom(first_lag: int, last_lag: int) -> pd.DataFrame:
    """Residual momentum (A.1.8-A.1.9, Blitz, Huij and Martens 2011): FF3 regression over
    the 36 months t-36..t-1 (>= 15 observations); the mean of the residuals of months
    t-first_lag..t-last_lag over their standard deviation. Stored at form = t-1."""
    Y, fac = _monthly_excess()
    X = fac[["mkt", "smbff3", "hmlff3"]]
    b, valid = _rolling_ols_wide(Y, X, 36, 15)
    Xa = np.column_stack([np.ones(len(X)), X.to_numpy()])
    Yv = Y.to_numpy()
    T, S = Yv.shape
    out = np.full((T, S), np.nan)
    B = np.stack([b[c].to_numpy() for c in ["const", *X.columns]], axis=-1)  # T x S x K
    k0, k1 = last_lag - 1, first_lag - 1  # offsets back from row t-1
    for t in range(T):
        if np.isnan(B[t]).all():
            continue
        rows = np.arange(t - k1, t - k0 + 1)
        rows = rows[rows >= 0]
        if len(rows) < (k1 - k0 + 1):
            continue
        fitted = np.einsum("rk,sk->rs", Xa[rows], B[t])
        e = Yv[rows] - fitted
        n = np.sum(~np.isnan(e), axis=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            out[t] = np.where(n == len(rows), np.nanmean(e, axis=0) / np.nanstd(e, axis=0, ddof=1), np.nan)
    v = pd.DataFrame(out, index=Y.index, columns=Y.columns).stack().rename("value").reset_index()
    return v.rename(columns={"level_0": "form"}).dropna()


def eps6() -> pd.DataFrame:
    """ϵ6 (A.1.8): residuals of t-7..t-2."""
    return _resid_mom(7, 2)


def eps11() -> pd.DataFrame:
    """ϵ11 (A.1.9): residuals of t-12..t-2."""
    return _resid_mom(12, 2)


def iv() -> pd.DataFrame:
    """Iv (A.6.2): residual volatility of daily excess returns on the market excess return,
    July t-1 to June t, at least 100 days; sorted at June t."""
    d = _daily()[["stkcd", "date", "month", "y", "mkt"]].dropna().copy()
    d["year"] = np.where(d["month"].dt.month >= 7, d["month"].dt.year + 1, d["month"].dt.year)
    key = d["stkcd"].astype(str) + "|" + d["year"].astype(str)
    g, uniq = pd.factorize(key)
    _, resid, cnt = batch_ols(d["y"].to_numpy(), d[["mkt"]].to_numpy(), g, len(uniq))
    sd, _, n = _moments(resid, g, len(uniq), 2)
    out = d.groupby(g)[["stkcd", "year"]].first()
    out["v"] = sd
    out = out[n >= 100]
    out["form"] = pd.PeriodIndex([pd.Period(f"{y}-06", "M") for y in out["year"]], freq="M")
    return _out(out)


@lru_cache(maxsize=1)
def _delay() -> pd.DataFrame:
    """Price delay (A.5.14, Hou and Moskowitz 2005): weekly returns over the year to June t
    on the contemporaneous and four lagged weekly market returns (>= 15 weeks). Weekly
    returns compounded from daily returns (Friday weeks); market = daily VW MKT + rf."""
    d = _daily()[["stkcd", "date", "r"]].copy()
    d["week"] = d["date"].dt.to_period("W-FRI")
    wk = np.expm1(np.log1p(d["r"]).groupby([d["stkcd"], d["week"]]).sum()).rename("r").reset_index()
    f = F.daily_factors()
    m = np.expm1(np.log1p(f["mkt"] + f["rf"]).groupby(pd.PeriodIndex(f.index, freq="W-FRI")).sum())
    lags = pd.DataFrame({f"m{k}": m.shift(k) for k in range(5)})
    wk = wk.merge(lags, left_on="week", right_index=True, how="inner").dropna()
    end = wk["week"].dt.end_time
    wk["year"] = np.where(end.dt.month >= 7, end.dt.year + 1, end.dt.year)
    key = wk["stkcd"].astype(str) + "|" + wk["year"].astype(str)
    g, uniq = pd.factorize(key)
    y = wk["r"].to_numpy()
    full_b, full_e, cnt = batch_ols(y, wk[[f"m{k}" for k in range(5)]].to_numpy(), g, len(uniq))
    rest_b, rest_e, _ = batch_ols(y, wk[["m0"]].to_numpy(), g, len(uniq))
    def r2(e):
        ybar = np.bincount(g, weights=y, minlength=len(uniq)) / np.maximum(cnt, 1)
        sst = np.bincount(g, weights=(y - ybar[g]) ** 2, minlength=len(uniq))
        sse = np.bincount(g, weights=e ** 2, minlength=len(uniq))
        return 1 - sse / sst
    r2f, r2r = r2(full_e), r2(rest_e)
    # standard errors of the unrestricted regression
    Z = np.column_stack([np.ones(len(y)), wk[[f"m{k}" for k in range(5)]].to_numpy()])
    K = Z.shape[1]
    xtx = np.zeros((len(uniq), K, K))
    for i in range(K):
        for j in range(K):
            np.add.at(xtx[:, i, j], g, Z[:, i] * Z[:, j])
    sse = np.bincount(g, weights=full_e ** 2, minlength=len(uniq))
    s2 = sse / np.maximum(cnt - K, 1)
    ok = cnt >= 15
    se = np.full((len(uniq), K), np.nan)
    se[ok] = np.sqrt(np.einsum("gii->gi", np.linalg.pinv(xtx[ok])) * s2[ok, None])
    b, dl = full_b[:, 1], full_b[:, 2:]
    kk = np.arange(1, 5)
    out = wk.groupby(g)[["stkcd", "year"]].first()
    out["d1"] = 1 - r2r / r2f
    out["d2"] = (dl * kk).sum(axis=1) / (b + dl.sum(axis=1))
    tb, tdl = b / se[:, 1], dl / se[:, 2:]
    out["d3"] = (tdl * kk).sum(axis=1) / (tb + tdl.sum(axis=1))
    out = out[ok]
    out["form"] = pd.PeriodIndex([pd.Period(f"{y}-06", "M") for y in out["year"]], freq="M")
    return out


def d1(): return _out(_delay().rename(columns={"d1": "v"}))
def d2(): return _out(_delay().rename(columns={"d2": "v"}))
def d3(): return _out(_delay().rename(columns={"d3": "v"}))


@lru_cache(maxsize=1)
def ps_liquidity() -> pd.Series:
    """Aggregate liquidity innovations L_t (Pástor and Stambaugh 2003), rebuilt from daily
    data because CSMAR's series (因子研究系列 -> 股票流动性) is not subscribed (deviation_log
    LI-4). Per stock-month with at least 15 days: r^e_{d+1} = θ + φ r_d + γ sign(r^e_d) v_d,
    v = RMB volume in millions, excess over the daily MKT return as in PS; γ_t = mean γ over
    stocks; scaled level (m_t / m_1) γ_t with m = aggregate circulating ME; innovations are
    the residuals of Δγ_t on Δγ_{t-1} and (m_{t-1}/m_1) γ_{t-1}, divided by 100."""
    from csmar.panels import daily
    d = daily(["Dretwd", "Dnvaltrd", "Dsmvosd"])
    d = d[d["board"].isin(D.BOARDS_EXTENSION)].copy()
    d["r"] = pd.to_numeric(d["Dretwd"], errors="coerce")
    d["v"] = pd.to_numeric(d["Dnvaltrd"], errors="coerce") / 1e6
    m = F.daily_factors()["mkt"] + F.daily_factors()["rf"]
    d["re"] = d["r"] - d["date"].map(m)
    d = d.sort_values(["stkcd", "date"])
    d["month"] = d["date"].dt.to_period("M")
    g = d.groupby("stkcd")
    d["re_next"] = g["re"].shift(-1)
    d["next_month"] = g["month"].shift(-1)
    d = d[(d["next_month"] == d["month"])].dropna(subset=["re_next", "r", "re", "v"])
    d["sv"] = np.sign(d["re"]) * d["v"]
    key = d["stkcd"].astype(str) + "|" + d["month"].astype(str)
    gid, uniq = pd.factorize(key)
    beta, _, cnt = batch_ols(d["re_next"].to_numpy(), d[["r", "sv"]].to_numpy(), gid, len(uniq))
    st = d.groupby(gid)[["stkcd", "month"]].first()
    st["gamma"], st["n"] = beta[:, 2], cnt
    st = st[st["n"] >= 15]
    # PS trim extreme estimates per month (keep the central 98%)
    lo = st.groupby("month")["gamma"].transform(lambda s: s.quantile(0.01))
    hi = st.groupby("month")["gamma"].transform(lambda s: s.quantile(0.99))
    gam = st[(st["gamma"] >= lo) & (st["gamma"] <= hi)].groupby("month")["gamma"].mean()
    mcap = D.stock_panel().groupby("month")["mv_float"].sum().reindex(gam.index)
    scale = mcap / mcap.iloc[0]
    x = pd.DataFrame({"dg": (scale * gam).diff(), "dg1": (scale * gam).diff().shift(1), "lvl": (scale.shift(1) * gam.shift(1))}).dropna()
    Z = np.column_stack([np.ones(len(x)), x["dg1"], x["lvl"]])
    b, *_ = np.linalg.lstsq(Z, x["dg"].to_numpy(), rcond=None)
    return pd.Series((x["dg"].to_numpy() - Z @ b) / 100, index=x.index, name="liq")


def beta_ps() -> pd.DataFrame:
    """βPS (A.6.30): slope on L_t in a regression of monthly excess returns on L_t and the FF3
    factors over t-60..t-1 (>= 24 months)."""
    Y, fac = _monthly_excess()
    X = fac[["mkt", "smbff3", "hmlff3"]].join(ps_liquidity(), how="left")
    b, _ = _rolling_ols_wide(Y, X, 60, 24)
    v = b["liq"].stack().rename("value").reset_index().rename(columns={"level_0": "form"})
    return v.dropna()
