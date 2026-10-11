"""Risk-free rate for Li et al.: the PBoC benchmark three-month time-deposit rate (data
manual p.1: "We treat China's 3-month RMB deposit rate as risk-free rate ... convert it into
monthly risk-free rate"). CSMAR's TRD_Nrrate only carries the one-year rate, so the benchmark
changes are listed here from the PBoC's published history of RMB deposit benchmark rates.

The PBoC has not changed the benchmark since 2015-10-24 (1.10%). Banks' posted rates have
moved since 2022 but the paper's definition is the benchmark, so the series stays at 1.10%
in the extension (stated in the table notes).

Checked month by month against the authors' `monthlyrf` (allfactors.sas7bdat, 2000-07 to
2019-06) in tests/test_li.py: monthly rate = annual / 12, applying the rate in force on the
15th of the month. That rule reproduces all 228 authors' months; "rate on the first day"
misses the 8 months with a change between the 1st and the 15th (e.g. 2011-02-09), and
"rate on the last day" misses 16.
"""

from __future__ import annotations

import pandas as pd

# (effective date, annual % three-month time deposit)
THREE_MONTH_DEPOSIT = [
    ("1999-06-10", 1.98),
    ("2002-02-21", 1.71),
    ("2006-08-19", 1.80),
    ("2007-03-18", 1.98),
    ("2007-05-19", 2.07),
    ("2007-07-21", 2.34),
    ("2007-08-22", 2.61),
    ("2007-09-15", 2.88),
    ("2007-12-21", 3.33),
    ("2008-10-09", 3.15),
    ("2008-10-30", 2.88),
    ("2008-11-27", 1.98),
    ("2008-12-23", 1.71),
    ("2010-10-20", 1.91),
    ("2010-12-26", 2.25),
    ("2011-02-09", 2.60),
    ("2011-04-06", 2.85),
    ("2011-07-07", 3.10),
    ("2012-06-08", 2.85),
    ("2012-07-06", 2.60),
    ("2014-11-22", 2.35),
    ("2015-03-01", 2.10),
    ("2015-05-11", 1.85),
    ("2015-06-28", 1.60),
    ("2015-08-26", 1.35),
    ("2015-10-24", 1.10),
]


def rf_monthly(start: str = "1999-07", end: str = "2026-12", day: int = 15) -> pd.Series:
    """Monthly risk-free rate (decimal) indexed by month: the annual rate in force on `day` of
    the month, divided by 12."""
    s = pd.Series({pd.Timestamp(d): r for d, r in THREE_MONTH_DEPOSIT})
    months = pd.period_range(start, end, freq="M")
    when = months.to_timestamp(how="start") + pd.Timedelta(days=day - 1)
    rate = s.reindex(s.index.union(when)).ffill().loc[when]
    return pd.Series(rate.to_numpy() / 1200, index=months, name="rf")
