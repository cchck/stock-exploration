# Deviation log

Every number that does not match its target within the lighthouse.md 3.3 tolerance gets an
entry here. Each investigation round is one line: hypothesis -> change -> result. At most
3 rounds per entry (lighthouse.md 3.4). After that the entry is marked **deviation** with
our number, the paper's number, and the most likely cause with evidence. Known data
caveats that may cause future deviations are listed too, marked **caveat**.

| ID | Status | Area |
|---|---|---|
| D-001 | caveat | Industry codes are current only |
| D-002 | resolved (milestone 1.1) | Li Table 1A, 1999 row |
| D-003 | resolved (milestone 1.1) | Li Table 1A, 2005–2007 counts |
| D-004 | caveat | Li risk-free rate (3-month deposit) not in CSMAR |
| D-005 | caveat | CSMAR NRI01 regime change in 2022-09 |
| D-006 | note | Allen Table I counts: source and definition |
| D-007 | note | TRD_Co row count: file 6,051 vs page header 6,030 |
| D-008 | note | "Months contiguous" (lighthouse 4.2) interpretation |
| D-009 | note | Quote-aware parser instead of Python's `csv` module (lighthouse 4.1) |
| D-010 | note | Yearly ST counts and 2019–2026 have no paper benchmark |

## D-001 Industry codes are current only (caveat)

- TRD_Co carries today's CSRC 2001 and 2012 codes, with no history. A firm that changed
  industry is classified by its latest code in all years.
- Evidence it is small: Li Table 1A non-financial counts match exactly in 1999–2018 with
  current codes (D-003).
- It may matter for the industry-adjusted anomalies in Li (milestone 1.4). Revisit if their
  numbers deviate.

## D-002 Li Table 1A, 1999 row (resolved)

- Before: ours 892, paper 844. The year-end status filter needs the daily trading status,
  and the daily download started in 2000-01.
- Round 1:
  - Hypothesis: the gap equals the stocks with a special status at the end of 1999.
  - Change: downloaded TRD_Dalyr for 1999-12-01 to 1999-12-31 (user approved on
    2026-10-09; 21,194 rows, equal to the platform count). Added it as chunk `_1999_12`.
  - Result: 844 = 844, and every board is exact (SH 434, SZ 410). Market values are within
    0.37%. Li Table 1A is now exact in all 20 years, 1999–2018.

## D-003 Li Table 1A, 2005–2007 counts (resolved)

- Round 1:
  - Hypothesis: the sample is non-financial and not ST/*ST/PT at year end.
  - Change: `st_end` filter.
  - Result: exact for 2000–2004, but 2005 was 1,195 vs 1,019 (+17%), 2006 +9% and 2007 +3%.
- Round 2:
  - Hypothesis: "abnormal trading status" also covers the split-share-reform codes
    (Trdsta 4/7/10).
  - Change: filter `trdsta_end == 1`, added to st_month.
  - Result: exact in all 19 years 2000–2018, and exact for every board.

## D-004 Li risk-free rate (caveat)

- Li uses the 3-month deposit rate (PBoC website). CSMAR TRD_Nrrate has no 3-month series.
- Plan (milestone 1.4):
  - 2000-07 to 2019-06: the authors' `monthlyrf` from the replication package (exact).
  - After that: the PBoC 3-month benchmark, 1.10% annual, unchanged since 2015-10-24.
- The extension segment therefore uses the benchmark rate, not bank posted rates.

## D-005 CSMAR NRI01 regime change (caveat)

- NRI01 follows the PBoC one-year benchmark (1.50%) until 2022-09. It then switches to
  large-bank posted rates (1.65 -> 0.95%).
- This affects only the extension segment of LSY-convention excess returns, by under 0.05%
  per month. Kept as published, and stated in table notes.

## D-006 Allen Table I counts: source and definition (note)

- Allen et al. count A-share firms from Worldscope, not CSMAR, so an exact match is not
  expected.
- Scored definition: a stock is listed in year y if its first traded month is no later than
  y and its last traded month no earlier than y. A stock suspended for the whole year still
  counts as listed, which matches the meaning of "listed firms".
  - Maximum deviation 2.99% (2010: 2,043 vs 2,106), within the 3% tolerance.
- The stricter count, "traded in at least one month of y", is saved as
  `ours_traded_in_year` in `results/data_layer/allen_table1a_counts.csv`.
  - It misses by up to 4.1% (2009: 1,680 vs 1,751; 2010: 2,020 vs 2,106).
  - It is not the scored definition, because whole-year suspensions are still listed firms.
- Why 2009–2010 are the worst years is not established. An earlier version of this entry
  attributed it to IPO-year coverage without evidence; that claim is withdrawn. Not
  investigated further: the residual is within tolerance and the source differs.

## D-007 TRD_Co row count (note)

- On the download date the query page header said 6,030 records. The delivered file has
  6,051 rows with 6,051 unique codes.
- The registry and the row-count test use the file count (6,051), so for this one table the
  test does not compare with the page figure. We treat the header as stale: a company file
  cannot hold more unique codes than exist, and every code in the monthly file is found in
  it.
- Recorded in `docs/csmar_access.md` (batch 1 notes).

## D-008 "Months contiguous" (lighthouse 4.2) interpretation (note)

- CSMAR's monthly file has no row for a month with no trading day (full-month suspension).
  Filling such months would invent a return that does not exist.
- Interpretation used: the panel must contain every month in which the stock traded, and
  the gaps must be explicit.
  - `month_gap` gives the months since the previous traded month.
  - The test `test_stock_months_are_complete_relative_to_daily_trading` asserts that the
    monthly and daily stock-month sets are identical from 1999-12.
- No return is lost across a gap: the resumption month's return runs from the last
  pre-suspension close (verified for 4,582 resumption months).

## D-009 Quote-aware parser instead of Python's `csv` module (note)

- Lighthouse 4.1 says to read TSR_Stkstat and STK_MA_TRADINGMAIN "with Python's `csv`
  module, logging affected rows, never silently dropping".
- Python's `csv` module cannot parse these files correctly: a stray unescaped quote makes
  it split or merge records. STK_MA's 2017–2021 chunk parsed to 47,958 rows instead of 47,957, which
  is why the lighthouse allowed +1.
- `read_quote_delimited` splits only on `"\n"` and `","`, which CSMAR's always-quoted format
  makes unambiguous. The result:
  - every chunk equals its platform count, so the +1 allowance is unused;
  - the 21 affected records (TSR 16, STK_MA 5) are kept verbatim;
  - they are logged on every read, including cache hits.
- The intent of 4.1 is met with a stricter result. The wording difference is recorded here
  rather than changing the frozen lighthouse.

## D-010 Yearly ST counts and 2019–2026 have no paper benchmark (note)

- Lighthouse 4.2 asks for yearly stock and ST counts compared with Li Table 1A and Allen
  Table I. Neither table reports ST counts, so the ST counts are produced
  (`results/data_layer/yearly_counts_1999_2026.csv`) but not compared here.
- Allen's ST statistics (section III.A.2) are part of milestone 1.3 and will be compared
  there.
- Both papers end in 2018, so 2019–2026 counts are reported without a benchmark.
