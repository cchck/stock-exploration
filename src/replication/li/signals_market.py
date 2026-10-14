"""Market-data anomaly signals of Li et al. (trading frictions, price momentum, reversal,
seasonality, age). Each function returns a DataFrame (stkcd, form, value), where `form` is the
formation month: the sort happens at the end of `form` (DM: "at the beginning of month t" =
end of t-1) and the first return month is form + 1. Annual sorts use form = June of year t.
Definitions follow the data manual (DM) section given in each docstring.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from replication.li import daily as DY
from replication.li import data as D


def _out(df: pd.DataFrame, value: str) -> pd.DataFrame:
    o = df[["stkcd", "month", value]].rename(columns={"month": "form", value: "value"})
    o = o.replace([np.inf, -np.inf], np.nan).dropna(subset=["value"])
    return o.reset_index(drop=True)


@lru_cache(maxsize=1)
def _daily_month() -> pd.DataFrame:
    return DY.build()


@lru_cache(maxsize=4)
def _window(months: int) -> pd.DataFrame:
    m = _daily_month()
    cols = ["r_n", "r_s1", "r_s2", "tur_n", "tur_s1", "tur_s2", "amt_n", "amt_s1", "amt_s2", "ami_n", "ami_s1"]
    return DY.rolling_window(m, cols, months)


def pps() -> pd.DataFrame:
    """Pps (DM A.6.17): month-end close (Mclsprc) of t-1."""
    p = D.stock_panel()
    return _out(p, "close")


def rtv() -> pd.DataFrame:
    """Rtv (DM A.6.15): average daily RMB volume over t-6..t-1, at least 50 days."""
    w = _window(6)
    w["v"] = (w["amt_s1"] / w["amt_n"]).where(w["amt_n"] >= 50)
    return _out(w, "v")


def tur() -> pd.DataFrame:
    """Tur (DM A.6.13): average daily share turnover over t-6..t-1, at least 50 days."""
    w = _window(6)
    w["v"] = (w["tur_s1"] / w["tur_n"]).where(w["tur_n"] >= 50)
    return _out(w, "v")


def _cv(n, s1, s2):
    mean = s1 / n
    var = (s2 - n * mean ** 2) / (n - 1)
    return np.sqrt(var.clip(lower=0)) / mean


def cvt() -> pd.DataFrame:
    """Cvt (DM A.6.14): sd / mean of daily turnover over t-6..t-1, at least 50 days."""
    w = _window(6)
    w["v"] = _cv(w["tur_n"], w["tur_s1"], w["tur_s2"]).where(w["tur_n"] >= 50)
    return _out(w, "v")


def cvd() -> pd.DataFrame:
    """Cvd (DM A.6.16): sd / mean of daily RMB volume over t-6..t-1, at least 50 days."""
    w = _window(6)
    w["v"] = _cv(w["amt_n"], w["amt_s1"], w["amt_s2"]).where(w["amt_n"] >= 50)
    return _out(w, "v")


def ami() -> pd.DataFrame:
    """Ami (DM A.6.18): average |daily return| / daily RMB volume over t-6..t-1, >= 50 days."""
    w = _window(6)
    w["v"] = (w["ami_s1"] / w["ami_n"]).where(w["ami_n"] >= 50)
    return _out(w, "v")


def mdr() -> pd.DataFrame:
    """Mdr (DM A.6.19): maximum daily return in t-1, at least 10 valid daily returns."""
    m = _daily_month().copy()
    m["v"] = m["r_max"].where(m["r_n"] >= 10)
    return _out(m, "v")


def ts() -> pd.DataFrame:
    """Ts (DM A.6.20): skewness of daily returns in t-1, at least 10 valid returns
    (sample skewness with the n/((n-1)(n-2)) adjustment, as SAS PROC MEANS)."""
    m = _daily_month().copy()
    n = m["r_n"].astype(float)
    mean = m["r_s1"] / n
    m2 = m["r_s2"] / n - mean ** 2
    m3 = m["r_s3"] / n - 3 * mean * m["r_s2"] / n + 2 * mean ** 3
    g1 = m3 / m2 ** 1.5
    m["v"] = (g1 * np.sqrt(n * (n - 1)) / (n - 2)).where(n >= 10)
    return _out(m, "v")


def tv() -> pd.DataFrame:
    """Tv (DM A.6.9): standard deviation of daily returns in t-1, at least 10 returns."""
    m = _daily_month().copy()
    n = m["r_n"].astype(float)
    mean = m["r_s1"] / n
    m["v"] = np.sqrt(((m["r_s2"] - n * mean ** 2) / (n - 1)).clip(lower=0)).where(n >= 10)
    return _out(m, "v")


def srev() -> pd.DataFrame:
    """Srev (DM A.6.27): return of month t-1 (valid return required)."""
    p = D.stock_panel()
    return _out(p, "ret")


def _ret_grid() -> pd.DataFrame:
    p = D.stock_panel()
    lr = np.log1p(p.set_index(["month", "stkcd"])["ret"]).unstack("stkcd")
    return lr.reindex(pd.period_range(lr.index.min(), lr.index.max(), freq="M"))


def _cum(first_lag: int, last_lag: int, min_obs: int | None = None) -> pd.DataFrame:
    """Compounded return over months t-first_lag..t-last_lag, stored at form = t-1
    (lags counted from the holding month t)."""
    lr = _ret_grid()
    k = first_lag - last_lag + 1
    s = lr.shift(last_lag - 1).rolling(k, min_periods=min_obs or k).sum()
    out = np.expm1(s).stack().rename("v").reset_index()
    return out.rename(columns={"level_0": "month"})


def r6() -> pd.DataFrame:
    """R6 (DM A.1.3): return over t-7..t-2 (skip t-1)."""
    return _out(_cum(7, 2), "v")


def r11() -> pd.DataFrame:
    """R11 (DM A.1.4): return over t-12..t-2."""
    return _out(_cum(12, 2), "v")


def rev() -> pd.DataFrame:
    """Rev (DM A.2.8): return over t-60..t-13."""
    return _out(_cum(60, 13), "v")


def _avg_lags(lags: list[int]) -> pd.DataFrame:
    """Average simple return over the given lags of the holding month t, stored at t-1."""
    p = D.stock_panel()
    r = p.set_index(["month", "stkcd"])["ret"].unstack("stkcd")
    r = r.reindex(pd.period_range(r.index.min(), r.index.max(), freq="M"))
    acc = sum(r.shift(l - 1) for l in lags) / len(lags)
    return acc.stack().rename("v").reset_index().rename(columns={"level_0": "month"})


def r1a() -> pd.DataFrame:
    """R1a (DM A.5.36): return in month t-12."""
    return _out(_avg_lags([12]), "v")


def r1n() -> pd.DataFrame:
    """R1n: average return over t-11..t-1."""
    return _out(_avg_lags(list(range(1, 12))), "v")


def r25a() -> pd.DataFrame:
    """R[2,5]a: average return across t-24, t-36, t-48, t-60."""
    return _out(_avg_lags([24, 36, 48, 60]), "v")


def r25n() -> pd.DataFrame:
    """R[2,5]n: average return over t-60..t-13 skipping lags 24, 36, 48, 60."""
    return _out(_avg_lags([l for l in range(13, 61) if l not in (24, 36, 48, 60)]), "v")


def r610a() -> pd.DataFrame:
    """R[6,10]a: average return across t-72, ..., t-120."""
    return _out(_avg_lags([72, 84, 96, 108, 120]), "v")


def r610n() -> pd.DataFrame:
    """R[6,10]n: average return over t-120..t-61 skipping lags 72, 84, 96, 108, 120."""
    return _out(_avg_lags([l for l in range(61, 121) if l not in (72, 84, 96, 108, 120)]), "v")


def w52() -> pd.DataFrame:
    """52w (DM A.1.7): daily close at the end of t-1 over the highest daily close during the
    past 12 months (t-12..t-1)."""
    m = _daily_month()
    hi = m.pivot(index="month", columns="stkcd", values="px_max")
    hi = hi.reindex(pd.period_range(hi.index.min(), hi.index.max(), freq="M")).rolling(12, min_periods=1).max()
    last = m.pivot(index="month", columns="stkcd", values="px_last").reindex(hi.index)
    v = (last / hi).stack().rename("v").reset_index().rename(columns={"level_0": "month"})
    return _out(v, "v")


def me_june() -> pd.DataFrame:
    """Me (DM A.6.1): market equity at the end of June of year t (annual sort)."""
    p = D.stock_panel()
    j = p[p["month"].dt.month == 6]
    return _out(j, "mv_float")


def age() -> pd.DataFrame:
    """Age (DM A.5.13): months from the stock's first appearance in CSMAR to the end of t-1."""
    p = D.stock_panel()[["stkcd", "month"]].copy()
    first = p.groupby("stkcd")["month"].transform("min")
    p["v"] = (p["month"] - first).apply(lambda x: x.n).astype(float)
    return _out(p, "v")
