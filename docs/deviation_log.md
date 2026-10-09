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
| LSY-1 | partly resolved | CH-3/CH-4 construction: EP definition and factor means |
| LSY-2 | resolved | 15-trading-day filter in months the market traded fewer than 15 days |
| LSY-3 | deviation | Table 2: printed numbers use the sample incl. the smallest 30% |
| LSY-4 | resolved | Table 4: definition of Panel B's stock set |
| LSY-5 | resolved | Table 1: announcement windows spanning suspensions |
| LSY-6 | deviation | Figures 1–2: reverse mergers identified by rule from CSMAR |
| LSY-7 | deviation | Tables 6–10: reversal, BM and CP anomalies |

LSY numbers are scored in `results/lsy_comparison.csv` (regenerate with
`python -m replication.lsy`). The `deviation` column there points to the entries below.

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

## LSY-1 CH-3/CH-4 construction (partly resolved)

Target: Table 3 and the month-by-month correlation with Stambaugh's series (lighthouse 3.3,
≥ 0.95).

- Round 1:
  - Hypothesis: the factor gap comes from construction choices: EP breakpoints over all
    stocks vs positive EP only; the shell-cut base; the trading filters.
  - Result: VMG moves by at most 0.02 points. These choices are not the cause.
- Round 2:
  - Hypothesis: the earnings definition.
  - Tested year-to-date, trailing twelve months, annual only and single-quarter earnings.
  - Result: single-quarter earnings are best: VMG 1.19% vs printed 1.14%, correlation 0.980
    with the website VMG. For comparison, year-to-date gives 1.04% / 0.968, TTM 0.93% / 0.917,
    and annual only 0.67% / 0.879.
  - Supporting evidence: Table 2's EP+ slope moves from 0.44 to 0.71 (printed 0.95), and the
    paper's appendix measures "ROE at the quarterly frequency".
  - Adopted.
- Round 3:
  - Hypothesis: 11.8% of universe stocks in 2000 lack IAR_Rept.Profitb (net profit excluding
    non-recurring items).
  - Change: fall back to the announced net profit (Profita).
  - Result: VMG correlation 0.959 → 0.967 (year-to-date stage). Adopted.
- Current status:
  - All seven factor series (CH-3 and CH-4 MKT, SMB, VMG, PMO) correlate ≥ 0.96 with the
    website series over 2000-01..2021-12.
  - Table 3: 17 of 18 scored numbers pass. The one miss is the two-factor alpha of MKT,
    1.76 vs 1.57, a source-data difference of 0.19 points.
  - S5.2: the shell-free VMG alpha has t 2.46 vs printed 3.32 (band 1.96–2.78 vs > 2.78),
    with the alpha itself within tolerance.

## LSY-2 15-day filter in short months (resolved)

- Applied literally, "≥ 15 trading records in the most recent month" removes every stock in
  months when the market itself traded fewer than 15 days: 2000-02 (12), 2001-01 (14),
  2002-02 (10), 2004-01 (13), 2005-02 (13) and 2026-02 (14). The following month then has
  no factor return, yet the paper has all 204 months.
- Change: in those months the threshold becomes the market's trading-day count.
- Result: 204 months.

## LSY-3 Table 2 sample (deviation)

- Section 4 says the smallest 30% are excluded. With them excluded, the logME slopes are
  about half the printed ones: column (2) gives -0.0024 (t -1.45) vs printed -0.0049
  (t -2.91).
- Round 1:
  - Hypothesis: ME should be measured by circulating value.
  - Result: -0.0022, so no.
- Round 2:
  - Hypothesis: winsorizing returns would close the gap.
  - Result: -0.0020, so no.
- Round 3:
  - Hypothesis: the printed table keeps the smallest 30%.
  - Result: -0.0051 (t -2.87). Scored matches rise from 55 to 67–68 of 80.
  - Adopted, as `table2(sample="eligible")`. The text-literal version is still available as
    `sample="universe"`.
- Remaining misses (12 of 80):
  - The beta coefficient signs: printed and ours are both within ±0.002 and insignificant.
  - D(CP<0), where we find no significance (t 0.5 vs printed 3.1).
- Marked as a deviation: the cause of the text/table mismatch cannot be verified from the
  paper.

## LSY-4 Table 4 Panel B (resolved)

- "All but the smallest 30%": counting a window when the stock is in the universe only in
  its last month gives Panel B below Panel A (53.4% vs 55.3%), the reverse of the paper.
- Change: count a window only if the stock is in the universe in all 36 months.
- Result: B 55.6% vs A 55.3%. All 8 numbers are within 3 points.

## LSY-5 Table 1 suspended announcement windows (resolved)

- Without exclusion, an announcement made during a suspension is credited with the whole
  price move at resumption. The middle group's t then collapses to 2.8 (printed 12.4).
- SUE winsorization did not help: SUE has no outliers, max 11.8.
- Change: exclude windows containing a trading gap of more than 15 calendar days. Holiday
  closures are at most about 10 days, so they are not excluded.
- Result: all 18 numbers pass, and the printed monotone pattern in b and R² across size
  groups is reproduced.

## LSY-6 Figures 1–2: reverse mergers by rule (deviation)

- WIND flags reverse mergers; CSMAR does not. The identification rule is in
  `src/replication/lsy/shells.py` (CSRC definition: a major restructuring, share-paid asset
  purchase of ≥ 100% of prior-year assets, with a change of actual controller). Lighthouse
  section 8 makes this rule a user-acceptance item.
- Result for 2007–2016:
  - 108 deals vs 133 printed;
  - 66% from the bottom 30% (printed 83%), 38% from the bottom 10% (printed "more than
    half").
- The CSMAR M&A table yields few qualifying deals before 2012 (12 in 2008–2011). As a
  result, the estimated shell value is zero until mid-2011, and the average S/V for
  2009–2016 is 8.9% vs 29.5% printed. The rise after 2012 (fivefold, as printed) is
  reproduced.
- Rounds:
  1. Size decile at deal month - 3 from the latest traded month, because shells are often
     suspended: no stock is missing a decile any more.
  2. Shell gain measured as starting value × cumulative return, because the change in total
     value counts the newly issued shares: S/V 55% → 8.9%.
  3. Relaxing the asset ratio to ≥ 0.5, or dropping the control-change condition: more
     deals (169 / 213), but a less small-stock-concentrated distribution (51–56% bottom
     30%). Not adopted.
- Expected deviation (lighthouse 5.1: "口径与原文 WIND 不同，预期有偏差").

## LSY-7 Tables 6–10 anomalies (deviation)

- 506 of 608 anomaly numbers pass.
- Misses by anomaly: reversal 24, BM 15, abnormal turnover 12, ROE 11, CP 10, MAX 9,
  EP 7, size 7, vol 5, 12-month turnover 2.
- Reversal: the daily one-fifth-slice construction gives a CAPM alpha of 1.16 (t 2.41) vs
  printed 1.49 (t 3.06).
  - Round 1 (min 20 records): no change.
  - Round 2 (holding one day instead of five): 0.22.
  - Round 3 (month-end sort as a check): 0.87.
  - Not resolved. Most likely cause: the daily return series differs (WIND vs CSMAR) on
    limit-hit and resumption days.
- CP:
  - Round 1: single-quarter cash flow, as A.2 defines it: 1.38 → 0.63 (printed 0.73).
- BM, ROE and the rest: the misses are mostly loadings and t-bands near the 1.96 boundary,
  with alphas within 0.10–0.15 points. No separate investigation beyond the shared
  construction rounds of LSY-1.
- Table 9 (27 of 32 pass):
  - The CH-3 GRS10 p-value is 0.019 vs printed 0.15. The rejection comes from the reversal
    and abnormal-turnover alphas, the same direction as in the paper. CH-3 still has by far
    the smallest average |alpha| (ours 0.42 vs CAPM 0.95 and FF-3 0.82; printed 0.45 / 1.02 / 0.90).
