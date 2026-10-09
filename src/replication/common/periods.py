"""Sample periods (lighthouse.md section 6).

Every table is produced for three segments by the same function with the same parameters,
only the dates change:
- original: the paper's own sample period;
- extended: from the month after the paper's end to the latest month the data allow;
- full: from the paper's start (or 2000-01, whichever is later) to the latest month.
The data caps per source are fixed here so that every table truncates the same way.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# Last month each source covers (lighthouse.md section 6). Tables using a source stop there.
DATA_END = {
    "monthly_returns": pd.Period("2026-09", "M"),
    "statements": pd.Period("2026-06", "M"),
    "cpi": pd.Period("2026-08", "M"),
    "stambaugh": pd.Period("2021-12", "M"),
}


@dataclass(frozen=True)
class Segment:
    name: str
    start: pd.Period
    end: pd.Period

    def mask(self, months: pd.Series) -> pd.Series:
        return (months >= self.start) & (months <= self.end)

    @property
    def n_months(self) -> int:
        return (self.end - self.start).n + 1

    def __str__(self) -> str:
        return f"{self.name} {self.start}..{self.end}"


def segments(paper_start: str, paper_end: str, data_end: pd.Period | None = None) -> dict[str, Segment]:
    """The three segments for a paper whose own sample is paper_start..paper_end (YYYY-MM)."""
    start, end = pd.Period(paper_start, "M"), pd.Period(paper_end, "M")
    last = data_end or DATA_END["monthly_returns"]
    if last <= end:
        raise ValueError(f"data end {last} is not after the paper's end {end}: nothing to extend")
    full_start = max(start, pd.Period("2000-01", "M"))
    return {
        "original": Segment("original", start, end),
        "extended": Segment("extended", end + 1, last),
        "full": Segment("full", full_start, last),
    }
