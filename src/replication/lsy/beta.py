"""Pre-ranking CAPM beta with a five-lag Dimson (1979) correction (LSY Table 2).

For each stock and month end: regress the stock's daily return on the market's daily return
and its first five lags over the past 12 months, beta = sum of the six slopes.

- Market: value-weighted daily return of the LSY code universe (A shares with codes 60/30/00),
  weighted by the previous trading day's total A-share market value. LSY do not name their
  daily market series; this is the daily analogue of their MKT (before the shell cut).
- Window: the stock's trading records in the past 12 calendar months (ending at the month
  end), at least 120 records, matching the 120-record eligibility filter.
- Lags are market trading days, so a stock's first day back from suspension is regressed on
  the market's returns of the preceding market days, which is what Dimson's correction is for.

Implementation: the window regression needs only the sums of cross-products X'X and X'y over
the window. Those are cumulative sums per stock, differenced at the window edges, so the whole
daily file is processed with vectorised operations and one batched 7x7 solve per stock-month.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from csmar.panels import daily

N_LAGS = 5
MIN_RECORDS = 120


def market_daily(d: pd.DataFrame) -> pd.Series:
    """Value-weighted market return by date, weights = previous record's total A-share value."""
    d = d.sort_values(["stkcd", "date"])
    w = d.groupby("stkcd")["Dsmvtll"].shift(1)
    ok = w.notna() & d["Dretwd"].notna() & (w > 0)
    num = (d.loc[ok, "Dretwd"] * w[ok]).groupby(d.loc[ok, "date"]).sum()
    den = w[ok].groupby(d.loc[ok, "date"]).sum()
    return (num / den).sort_index().rename("mkt")


def dimson_beta_month_end() -> pd.DataFrame:
    d = daily(["Dretwd", "Dsmvtll"])
    d = d[d["board"].isin(["SH_MAIN", "SZ_MAIN", "SZ_SME", "CHINEXT"]) & d["stkcd"].str.slice(0, 2).isin(["60", "30", "00"])]
    d["Dretwd"] = d["Dretwd"].astype(float)
    mkt = market_daily(d)
    lags = pd.DataFrame({f"m{k}": mkt.shift(k) for k in range(N_LAGS + 1)})
    d = d.sort_values(["stkcd", "date"]).reset_index(drop=True)
    X = lags.reindex(d["date"]).to_numpy()  # n x 6, market and its lags by market day
    y = d["Dretwd"].to_numpy()
    valid = ~np.isnan(y) & ~np.isnan(X).any(axis=1)
    Xc = np.column_stack([np.ones(len(d)), X])  # n x 7 with intercept
    Xc[~valid] = 0.0
    yv = np.where(valid, y, 0.0)

    # Month-end rows and the first row of each 12-month window
    month = d["date"].dt.to_period("M")
    is_last = month.ne(month.shift(-1)) | d["stkcd"].ne(d["stkcd"].shift(-1))
    end_idx = np.flatnonzero(is_last.to_numpy())
    grp_start = (np.arange(len(d)) - d.groupby("stkcd").cumcount().to_numpy())[end_idx]
    window_start_date = (month.iloc[end_idx] - 11).dt.to_timestamp(how="start").to_numpy()
    # first row of the same stock with date >= window start: search within the stock's block
    dates = d["date"].to_numpy()
    lo = np.empty(len(end_idx), dtype=np.int64)
    for i, (e, g, ws) in enumerate(zip(end_idx, grp_start, window_start_date)):
        lo[i] = g + np.searchsorted(dates[g:e + 1], ws, side="left")

    def window_sum(v: np.ndarray) -> np.ndarray:
        cs = np.concatenate([[0.0], np.cumsum(v)])
        return cs[end_idx + 1] - cs[lo]

    k = Xc.shape[1]
    xtx = np.empty((len(end_idx), k, k))
    for a in range(k):
        for b in range(a, k):
            s = window_sum(Xc[:, a] * Xc[:, b])
            xtx[:, a, b] = s
            xtx[:, b, a] = s
    xty = np.column_stack([window_sum(Xc[:, a] * yv) for a in range(k)])
    n = xtx[:, 0, 0]
    ok = n >= MIN_RECORDS
    beta = np.full(len(end_idx), np.nan)
    sol = np.linalg.solve(xtx[ok], xty[ok][..., None])[..., 0]
    beta[ok] = sol[:, 1:].sum(axis=1)
    return pd.DataFrame({"stkcd": d["stkcd"].to_numpy()[end_idx], "month": month.to_numpy()[end_idx],
                         "beta": beta, "beta_n": n})
