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
| LSY-5 | deviation | Table 1: announcement windows spanning suspensions (filter not in the paper) |
| LSY-6 | deviation | Figures 1–2: reverse mergers identified by rule from CSMAR |
| LSY-7 | deviation | Tables 6–10 and section 6–7 text: anomalies, reversal, CH-4 summary |
| LSY-8 | resolved | Table 4 text: industry portfolios (Shenyin-Wanguo not available) |
| LSY-9 | resolved | Section 5.3 text: FF-5 comparison |
| ALN-1 | deviation | Allen Table I: SOE counts (controller file from 2003) and average assets |
| ALN-2 | partly resolved | Allen Tables VIII-IX: governance components, G-indices, turnover |
| ALN-3 | resolved | Allen RPT measure: which related-party transactions count as cash outflows |
| ALN-4 | deviation | Allen Tables X-XI: return and operating-performance regressions |
| ALN-5 | deviation | Allen Table XIII: cross-listed firms |
| ALN-6 | partly resolved | Allen Figure 1: real buy-and-hold value of RMB 1 |
| ALN-7 | deviation | Allen Figures 4-5 and section III.A.2: ST firms, delistings, investment |
| ALN-8 | partly resolved | Allen text numbers (SOE share, dividend yield, OCF, governance gaps) |

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
  - S5.2: the shell-free VMG alpha has t 2.47 vs printed 3.32 (band 1.96–2.78 vs > 2.78),
    with the alpha itself within tolerance.
  - Section 7.1: CH-4's SMB averages 9.3% a year vs printed 11%. That is 0.15 points a
    month, just outside the annualized 1.2-point rule. The CH-3 SMB is close (0.98% vs
    1.03% a month); the difference sits in the turnover-neutral half of the CH-4 SMB.
    Same source-data cause as the other LSY-1 items.

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

## LSY-5 Table 1 suspended announcement windows (deviation)

- Without exclusion, an announcement made during a suspension is credited with the whole
  price move at resumption. The middle group's t then collapses to 2.8 (printed 12.4), and
  the smallest group's to 0.3 (printed 6.3).
- SUE winsorization did not help: SUE has no outliers, max 11.8.
- Change: exclude windows that contain a trading gap of more than 15 calendar days
  (`table1(max_gap_days=15)`). Holiday closures are at most about 10 days.
  - **This filter is not stated in the paper.** It is our choice, motivated by the paper's
    own exclusion of returns after long suspensions in its sample filters (A.1).
  - The 15-day threshold was chosen after seeing the results, so it is a tuning choice and
    is labelled as such here.
- Result: all 18 numbers are within the lighthouse tolerances. Caveats:
  - Those tolerances are loose for this table. The R² values (printed 0.3–2.1%) are scored
    with the 3-point proportion rule; it fails only above about 5%.
  - The b values are scored by sign plus the t band, and every printed t is above 2.78.
  - The printed pattern holds for Panel A (b and t increase with size) and for R² in both
    panels. It does **not** hold in Panel B:
    - b: ours 0.58 / 0.72 / 0.67 (Smallest / Middle / Largest) vs printed 0.43 / 0.58 / 0.59;
    - t: ours 10.8 / 19.1 / 20.0 vs printed 9.74 / 17.91 / 17.60.
  - Our b values are 13–42% above the printed ones.
  - Review fix (2026-10-09): the gap filter now checks every return in the window, including
    the one ending on the window's first day, for both k = 0 and k = 3. It also no longer
    compares a stock's first record with the previous stock.
- Marked as a deviation, not resolved.

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
  2009–2016 is 8.9% vs 29.5% printed.
- Further consequences:
  - S/V ranges from 0% to 41% vs printed 10%–60%.
  - S grows 27-fold vs the printed "fivefold". The ratio is large because S starts near
    zero; it is reported, not scored.
  - The shape (flat, then rising from 2012, a peak in 2015) matches; the level does not.
- Rounds:
  1. Size decile at deal month - 3 from the latest traded month, because shells are often
     suspended: no stock is missing a decile any more.
  2. Shell gain measured as starting value × cumulative return, because the change in total
     value counts the newly issued shares: S/V 55% → 8.9%.
  3. Relaxing the asset ratio to ≥ 0.5, or dropping the control-change condition: more
     deals (169 / 213), but a less small-stock-concentrated distribution (51–56% bottom
     30%). Not adopted.
- Expected deviation (lighthouse 5.1: "口径与原文 WIND 不同，预期有偏差").

## LSY-7 Tables 6–10 and section 6–7 text: anomalies (deviation)

- Tables 6, 7, 8 and 10: 507 of 604 numbers pass. Table 9: 26 of 32 (rerun 2026-10-09 after the review fixes).
- Misses by anomaly: reversal 23, BM 16, ROE 11, abnormal turnover 10, MAX 8, size 7,
  CP 7, vol 5, EP 5, 12-month turnover 5.
- Rounds shared by all anomalies:
  - the construction rounds of LSY-1;
  - single-quarter earnings and cash flow (CP 1.38 → 0.63, printed 0.73);
  - listing day excluded from the daily characteristics (review fix, 2026-10-09).
- Reversal (CAPM alpha 1.16, t 2.41 vs printed 1.49, 3.06):
  - Round 1, minimum of 20 records: no change.
  - Round 2, one-day holding: 0.22.
  - Round 3, month-end sort as a check: 0.87.
  - Not resolved. Most likely cause: the daily return series differs (WIND vs CSMAR) on
    limit-hit and resumption days.
  - Section 6.1 text: one-month reversal 13.9% a year (t 2.41) vs printed 18% (2.96). The
    close-price 2012–2016 mean matches (2.11 vs 2.15). The mid-price version needs bid/ask
    quotes we do not have; it is listed as not producible.
- One round per remaining anomaly. Score = passes among that anomaly's Table 6/7/8/10
  numbers.
  - BM: sort on positive BM only, 47 → 50 of 63. **Not adopted**: the paper restricts only
    EP and CP to positive values (section 6.1), so BM keeps negative values.
  - ROE: book equity lagged one quarter, 53 → 53 of 64. No effect.
  - Abnormal turnover: 20-day turnover alone as a check, 53 → 20 of 63, so the ratio
    definition is right. Remaining misses: CAPM alpha 1.21 (t 2.77) vs 1.27 (2.92), t
    bands just below 2.78.
  - MAX and vol: affected only through the listing-day fix. Remaining misses are mostly
    t-bands near 1.96 (MAX CAPM t 1.93 vs printed 2.02).
- Section 6.1 text:
  - Universe size 607 (2000-01) vs 610 printed; 1,795 (2016-12) vs 1,872 printed (-4.1%,
    just outside the 3% count rule).
  - Size-neutral alpha increases: ROE +0.70 vs +0.57, EP +0.39 vs +0.52, 12-month
    turnover +0.22 vs +0.21.
  - One-year reversal: 4.3% a year vs 6%; the insignificant t (0.69 vs 0.90) matches.
- CH-4 summary (section 7.2), round 1:
  - Hypothesis: the gap comes from our CH-4 factors rather than from the anomaly
    portfolios.
  - Change: replace our factors with Stambaugh's published CH-4 series (all four, then PMO
    alone).
  - Result: average |alpha| 0.41 and GRS p 0.013 with the website factors (0.40 / 0.028
    with our factors plus the website PMO). That is no better than ours (0.44 / 0.014), so
    the factors are not the cause. The gap is in the anomaly spreads built from CSMAR data.
- CH-4 summary details:
  - Average |alpha| 0.44 vs printed 0.30. Average |t| 1.17 vs 0.69 (same band).
  - GRS10 p 0.014 vs 0.41.
  - The gap is spread across several anomalies. Reversal and MAX match: 0.52 vs 0.49 and
    -0.57 vs -0.59. The larger CH-4 alphas are:
    - abnormal turnover -0.35 vs -0.00;
    - ROE -0.52 vs -0.29;
    - vol -0.49 vs -0.27;
    - BM 0.94 vs 0.75;
    - size 0.37 vs 0.23 (t 2.57 vs 1.41).
  - Size's significant alpha, together with the overall small alpha differences, drives the
    GRS rejection.
  - Most likely cause (after round 1): the anomaly spreads themselves differ. The CSMAR
    and WIND daily and statement data feed into size, BM, ROE, vol and abnormal turnover.
    Not the factors.
  - Panel B (computed, no printed number): average |alpha| 0.49, p 0.18.
- Section 6 counts (consequences of the per-anomaly differences above):
  - CAPM-significant anomalies: 7 of 14 vs 10. Explained by CH-3: 8 vs 8. Explained by
    FF-3: 5 vs 3.
  - Categories where FF-3 leaves a significant alpha: 4 vs 5.
  - Smallest universe / 10: 52 vs "at least 60" (our universe dips to 521 stocks in early
    2000).
- Section 6.2 Panel B "eight anomalies": the size-neutral panel has no size anomaly, so
  the average covers the 7 remaining explained anomalies. Ours is 0.19 vs printed 0.26
  (within tolerance).
- Table 9: the CH-3 GRS10 p is 0.018 vs printed 0.15. The rejection comes from the
  reversal and abnormal-turnover alphas. CH-3 still has by far the smallest average
  |alpha|: ours 0.43 vs CAPM 0.94 and FF-3 0.85; printed 0.45 / 1.02 / 0.90.

## LSY-8 Table 4 text: industry portfolios (resolved)

- The paper uses 37 Shenyin-Wanguo industries; that classification is not in our data.
  CSRC 2012 codes are used instead, current classification only (D-001).
- Round 1:
  - Hypothesis: the gap comes from industry granularity.
  - Change: 65 CSRC divisions (67.1% / 77.7% vs printed 72% / 82%) replaced by CSRC
    sections with manufacturing split into its divisions: 41 industries, close to SW's 37.
  - Result: 71.7% / 82.7%, within tolerance. Adopted (`industry_groups(level="section_c_split")`).
- Anomaly deciles: 87.8% / 92.2% vs printed 85% / 90%, within tolerance.

## LSY-9 Section 5.3 text: FF-5 comparison (resolved)

- Printed (details in the paper's Appendix A.7, following Guo et al. 2017):
  - CH-3 prices FF-5's non-market factors: GRS p 0.88.
  - FF-5 does not price SMB and VMG: p 0.0003.
- Round 1:
  - Setup: profitability = quarterly ROE (the same single-quarter earnings as VMG).
  - Result: p 0.31 (same conclusion) and p 0.71 (opposite conclusion). RMW absorbs VMG.
- Round 2:
  - Hypothesis: the paper's FF-5 uses operating profitability, as in Fama and French
    (2015) and Guo et al.
  - Change: RMW from annual operating profitability = (revenue - COGS - selling -
    administrative - financial expenses) / book equity.
  - Result: p 0.96 and p## ALN-0 Allen review fixes (2026-10-10, two review rounds)

The milestone 1.3 guard failed twice. The fixes below apply to every ALN entry. All
numbers in ALN-1..8 are those of the committed `results/allen_comparison.csv`.

- **First review:**
  1. Figures 1–2 compounded from 2000-01; lighthouse 3.1 prescribes 2000-12..2018-12.
  2. Winsorization was pooled over 1990–2026; it is now done within each segment.
  3. ST and delisting counts included B shares; they are now A shares only.
  4. Table XIII lacked the province fixed effects.
  5. Clustering was not as in the SAS code. It is now SAS "cluster Industry1 fyear":
     Industry1 is the CSRC letter, and SURVEYREG forms clusters from the combinations of
     the CLUSTER variables, i.e. industry-letter by year cells.
  6. SOE flag: year-end controller rows; comma-joined codes are handled.
  7. Missing executive holdings stay missing; RPT amounts are RMB and non-negative only;
     ROIC uses lagged capital; volatility comes from daily returns; cross-listing is
     time-varying (H shares outstanding).
- **Second review:**
  8. Winsorization follows the lists in Winsorize.sas: 1%/99% for the variables named
     there and their lags, including the lagged market-cap weight, log size and log firm
     age; then lagged sales growth and NCF at 5%/95%. Not winsorized, because they are not
     in the lists: board size, state holdings, CEO duality, ROE. One addition: net-income
     growth (see ALN-5).
  9. Sales growth uses the current-year denominator (Appendix A). Revenue falls back to
     total operating revenue, which financial firms report.
  10. Table XIII matching uses information up to the segment end only. Before, a later H
      listing could make a firm "cross-listed" in 2000–2018 (look-ahead).
  11. ROA[-1,+1] covers only IPOs whose year +1 lies in the segment, and is winsorized
      within it.
  12. Scoring:
      - coefficients in return units: annualized return rule (1.2 points);
      - continuous descriptive statistics and small ratios (average assets, index and
        turnover moments, group levels and differences, footnote 32's gaps, Figure 1's
        end value, investment / NCF / OCF / dividend-yield levels, IPO ROA and capex):
        relative 10% (`rel10`, lighthouse 3.3 revision of 2026-10-10, user decision);
      - proportion variables (G-Index components stored as fractions, SOE share,
        R-squared): 3 points; counts: relative 3%.

## ALN-1 Allen Table I (deviation)

- **Listed firms:** all 19 years are within 3%; the unique-firm count is 3,668 vs 3,695.
- **SOE counts:**
  - 2000–2002: the controller file starts in 2003, so each firm's earliest observed status
    is carried back (ALN-9 round 3). 2000: 765 vs 744 (+2.8%); 2001: 826 vs 751 (+10%);
    2002: 883 vs 816 (+8%), in line with the +10–19% of 2003–2014.
  - 2003–2014 are 10–19% above the printed counts (2005: 933 vs 784, +19%).
  - 2015–2017 are 6–8% below; 2018 is 1,082 vs 1,078.
  - The printed series jumps by 23% in 2015 (879 to 1,081) while ours moves by 0.5%.
  - Rounds:
    1. Government controllers only (2xxx codes): 2003–2014 within -1% to -9%, but
       2015–2018 between -11% and -21%.
    2. Without government agencies (1100 + 2100 + 2120): +2% to +9% in 2003–2014, -4% to
       -11% after.
    3. Year-end rows only, any row with a state code: the current numbers.
  - Most likely cause: the paper's SOE source (WIND "ultimate controller", per the Table I
    note) reclassifies firms differently, e.g. the break in 2015, which is not in CSMAR's
    controller file.
- **Average assets ($ bn):**
  - All 19 years are within the relative 10% rule: 2000–2003 match, 2004–2018 are 3–8%
    above the printed values (2018: 2.87 vs 2.78).
  - Miss: the unique-firm average is 1.82 vs 1.59 (+14%).
  - Rounds:
    1. Per-year winsorization: worse.
    2. Non-financial firms only: about 30% too low.
    3. Winsorization within the segment: the current numbers.
  - Most likely cause: a different treatment of the largest (financial) firms. The printed
    values lie between all-firm and non-financial averages.

## ALN-2 Allen Tables VIII–IX: governance and turnover (partly resolved)

- **Within tolerance:**
  - CEO duality: 0.211 vs 0.208.
  - Ownership concentration: 0.530 / 0.533 / 0.154 vs 0.539 / 0.546 / 0.152.
  - Executive holdings: 0.079 vs 0.104.
  - Board size: 16.9 / 16 / 4.04, range 1–54, vs 16.8 / 16 / 4.029, range 1–54.
  - State ownership: 0.126 / 0 / 0.218 vs 0.116 / 0 / 0.211.
  - RPT net out: median 0 = 0, sd 0.127 vs 0.117 (scored with rel10 since the 2026-10-10
    revision: it is a small signed ratio, not a share).
  - Turnover: mean 3.05 vs 3.148; max 11.95 vs 12.18.
  - G-Index-A small-large difference: 0.480 vs 0.487.
- **Rounds:**
  1. Board size = directors + supervisors + senior managers (`TotalNumber`). Directors
     alone have a median of 9.
  2. Panel A means: only G-Index-I is value-weighted. Value-weighting every component gives
     ownership concentration 0.63.
  3. G-Index-I ties follow the caption, except executive holdings, whose mass point at
     zero would otherwise give a point to every firm with zero holdings.
  4. Missing components before 2003: the index is the sum of the remaining components
     (lighthouse 5.2).
  5. State holdings by holder nature (国家 / 国有法人 holders): mean 0.395 / median 0.422
     vs printed 0.116 / 0.
     - The share-type measure is therefore what the paper used, and it is kept.
     - Its known property: it falls towards zero after the split-share reform even for
       SOEs. This drives the SOE vs non-SOE gap (ours 1.79 vs 3.08, printed 2.211 vs 2.845,
       difference 1.28 vs 0.699).
- **Within the relative 10% rule (lighthouse 3.3 revision 2026-10-10):**
  - G-Index-A: mean 2.39 vs 2.482, sd 1.28 vs 1.181, median 2 = 2, range 0–6.
  - Small / large levels: 2.56 / 2.08 vs 2.722 / 2.235 (both 6% low).
  - Turnover: mean, median 2.35 vs 2.487, sd 2.47 vs 2.383, max.
  - Non-SOE level 3.08 vs 2.845.
- **Remaining misses:**
  - G-Index-I (value-weighted): mean 2.79 vs 2.271, median 3 vs 2.
  - SOE level 1.79 vs 2.211 and the non-SOE minus SOE difference 1.28 vs 0.699 (state
    holdings measure, round 5).
  - Extremes:
    - state-ownership max 0.922 vs 1 (no top-10 list in CSMAR sums to 100% state
      shares);
    - RPT net out mean -0.0068 vs 0.007 (opposite sign). Rounds (all winsorized at
      1%/99% within the segment):
      1. Funds-only measure (ALN-3): mean -0.0085, sd 0.054.
      2. Cash by category (kept): mean -0.0062 before the panel's winsorization list.
      3. Goods sold to related parties counted as outflows (credit sales as tunneling):
         mean -0.0106, sd 0.129, max 0.520.
      No CSMAR reading gives a positive mean; the printed mean (0.007) is small relative to
      its sd (0.117), so a different coverage of RPT rows can flip it.
    - RPT net out max / min 0.590 / -0.573 vs 0.524 / -0.475 (+13% / +21%; the winsorization tail is
      set by our own RPT distribution, ALN-3).
  - Turnover min 0.20 vs 0.271 (-26%).
    - Round 1: circulating shares as denominator gives a mean of 5.3, which is worse.
    - Round 2: the SAS winsorization list: the max now matches, the median does not.
    - Most likely cause: CSMAR vs WIND trading volume in the reform years.
- **AH premium:** not producible (no Hong Kong data in NYU's subscription).

## ALN-3 Allen RPT measure (resolved)

- Funds-only "loan" reading: sd 0.054, which is far too narrow.
- Every cash-settled category, with the cash direction set per category: sd 0.127 and a
  range of -0.57..0.59, against printed 0.117 and -0.475..0.524.
- The G-Index-A mean then matches best (2.39 vs 2.80 with loans only; printed 2.482).
- Table XIII's "RPT Amt Out" is described as loan-based, so it uses the funds-only
  outflow.

## ALN-4 Allen Tables X–XI (deviation)

- **Table X, original segment** (printed in brackets):
  - G-Index-A col (1): 1.085, t 1.90 (1.445, 2.885).
  - Turnover col (3): -0.80, t -1.33 (-2.475, -3.87).
  - R² about 50% (52%).
  - N 30,256 (36,044).
- **Rounds on G-Index-A col (1):**
  1. The first version (incomplete winsorization) gave 1.447. With the SAS winsorization
     lists it is 1.085. The close match was an artifact of the winsorization choice.
  2. Clustering (with the first version's data): letter × year cells 2.29, letter two-way
     3.13, two-digit two-way 2.41, two-digit × year cells 2.98. The SAS specification
     (cells) is kept.
  3. SOE and ST controls, named in the caption but absent from Table10.sas: 1.20 (t 2.16)
     with N 27,296, because there are no SOE flags before 2003. The SAS specification (no
     SOE / ST) is kept, as the paper's own code.
- **N gap** (36,044 vs 30,256): of 38,453 firm-years, the missing values are
  - lagged G-Index-A 4,874;
  - lagged sales growth 5,163 (needs two consecutive annual reports);
  - lagged daily volatility 4,564 (needs 60 trading days in the previous year);
  - lagged market cap 2,879.
  The paper keeps more firm-years. Its WIND sample likely fills lagged values that CSMAR
  leaves missing in IPO years. Not resolved.
- **ROA[-1,+1] columns (4), (7), (8):**
  - CSMAR has pre-IPO financials for only 1,033 firms, so N is 2,408–2,413 vs about
    34,000.
  - These columns are a different, IPO-heavy sample. Their coefficients (e.g. ROIC 13.3 vs
    8.0; turnover -3.6 vs -1.57 in col (7)) are not comparable.
- **Table XI Panel C:**
  - Signs agree in all four columns.
  - Coefficients are above the printed ones: 0.56 vs 0.387 in col (1), 0.14 vs 0.066 in
    col (3).
  - NCF t is 2.00 vs 0.82, so our cols (3)–(4) are significant where the paper's are not.
  - N 32,936 vs 31,085: the indices cover 2000–2002 via the remaining components.

## ALN-5 Allen Table XIII (deviation)

- **Rounds:**
  1. Province FE added.
  2. Matching on the CSRC letter, keeping unmatched cross-listed firms, using information
     up to the segment end only.
  3. Time-varying H-share flag: 111 cross-listed firms vs 99. The matched-sample N is
     1,835–2,024 vs printed 2,162–2,463.
- **Result:**
  - RPT Amt Out, full sample: 0.003 (t 2.58) vs -0.026 (-2.445), opposite sign. The
    printed scale of loan outflows is larger than CSMAR's funds transactions.
  - Matched sample: 6 of the 10 coefficients agree in sign. The four that disagree are RPT
    (1), RPT (2), returns (4) and ROE.
  - NCF -0.021 (t -3.90) vs -0.008 (-1.64).
- **Net-income growth:** a ratio over last year's net income, which can be near zero.
  - Unwinsorized (as in the SAS lists) its coefficient is -3.1 vs printed -0.041; at
    1%/99% it is -0.263 (t -1.07).
  - Winsorized, as the one addition to the SAS lists.

## ALN-6 Allen Figure 1 (partly resolved)

- With the lighthouse start month 2000-12, the 2018 value is 1.10 vs printed 1.01 (+9%).
  The first version's 1.76 came from compounding 2000.
- Rounds with the wrong start (summed returns, circulating-cap weights, no winsorization)
  did not explain the gap. The remaining 9% is attributed to the return source (CAFR / WIND
  vs CSMAR).
- Figure 2: small 4.31, medium 1.70, large 1.08. The small-cap outperformance and large-cap
  underperformance are reproduced.

## ALN-7 Allen Figures 4–5 and section III.A.2 (deviation)

- **ST firms:** first-time ST firms 2000–2018: 562 vs 572 (within 3%).
- **Permanent ST:** 78 vs 65.
  - Round 1, never re-emerged: 43.
  - Round 2, still ST at the end of 2018 without the financial-history requirement: 86.
  - Round 3, the literal rule plus footnote 21's five prior years: 78, kept.
- **Figure 4:** the ROA path is reproduced: positive in -5..-3, negative from -2.
- **Figure 5:** investment 4.9% vs 4.4% (+12%), NCF 1.1% vs 1.5% (-24%): both miss the
  relative 10% rule. The unique firms with non-missing
  investment / NCF / assets are 3,569 vs 3,695 (-3.4%).
- **Delistings:**
  - 5.3 per year vs "about five".
    - Round 1: A shares only (was 6.2 with B shares).
    - Round 2: terminations from the listing-status file, which CSMAR records at the
      termination date. Gives 101 A-share terminations in 2000–2018.
    - The remaining +6% is outside the 3% count rule for a printed "about five".
  - Poor-performance share 57% vs "less than half".
    - Round 1, reason codes: 4% (CSMAR uses a generic code for most).
    - Round 2, ST / *ST / PT or suspended at delisting: 57%, kept.
  - The printed "(or 2.7%)" is inconsistent with "five stocks a year" (five of about 1,700
    listed firms is 0.3%; ours is 0.31%). It is reported, not scored.

## ALN-8 Allen text numbers (partly resolved)

- **Within tolerance:**
  - SOE share 2018: 30.4% vs 30%.
  - Listed firms in 1991: 13 vs 13.
  - Footnote 32's 2007 gap: 0.392 vs 0.375.
- **Misses under the relative 10% rule** (all passed the earlier 3-point rule, ALN-0 item
  12):
  - IPO ROA 14.3% the year before (+10.02%, just outside) and 7.2% the year after (+20%),
    printed 13% and 6%; the pre-IPO year is in CSMAR for 1,033 firms. The direction of the
    drop is reproduced.
  - Capex one year after the IPO: 8.1% vs 7% (+16%).
  - Dividend yield 2018: 1.33% vs 0.8% (+66%). Footnote 11 gives no definition; ours is
    cash dividends per share with 2018 ex-dates over the year-end close, equal-weighted
    over A shares (non-payers count as zero). Rounds:
    1. Value-weighted by total market cap: 2.28%.
    2. Dividend payers only: 1.70%.
    3. Cross-sectional median: 0.83%, which matches the printed 0.8%. The footnote says
       "average", so the mean is kept and scored; the median is reported here only.
  - Value-weighted OCF / assets: 7.5% vs 6.5% (+16%).
- **Other misses:**
  - Capex the year before the IPO: 7.4% vs 3%. CSMAR's prospectus-year cash-flow
    statements already show high capex; most likely a definition difference in the
    pre-IPO year.
  - Footnote 32 (small minus large G-Index-A, Internet Appendix): 2004 0.333 vs 0.058 and
    2007 0.392 vs 0.375 (passes). The 2004 gap is driven by the state-holdings component (SOEs held
    state shares before the reform).
- **SOE share in 2000:** 73.2% vs 70% (3.2 points, just outside the 3-point rule), with
  2000–2002 statuses carried back from 2003 (ALN-9).
- **Not producible:**
  - the Figure 4 t-statistics against US firms (need US data).

## ALN-9 Allen Table XII Panel A (deviation)

In scope since the lighthouse revision of 2026-10-10. Specification from Table12.sas: Large
= lagged market cap above the year's 70th percentile; SOE2 = actual controller; lagged
size, leverage, ROA, sales growth, log firm age (plus return volatility in column 1); year,
CSRC industry and province dummies; clusters = industry letter x year cells; column 1 WLS on
lagged market cap.

- **SOE before 2003:** the printed N equals Table X's (36,044), so every firm-year from 2000
  is classified, but CSMAR's controller file starts in 2003.
  - Round 1, drop 2000–2002: N 30,144; SOE in column 2 negative and significant.
  - Round 2, missing = non-SOE (a SAS dummy default): SOE share 0% in 2000.
  - Round 3, each firm's earliest observed status carried back: SOE share 73% in 2000 vs
    the 70% printed in section I.A. Kept.
- **Reproduced:** Large in columns 2–4 (sign and t band: investment 0.58 (6.8) vs 0.46
  (6.0); OCF -0.22 (-1.0) vs -0.28 (-1.3); NCF -0.51 (-3.0) vs -0.77 (-3.8)); the t bands of
  Large and SOE in column 1; SOE in column 3; all four R-squared within 3 points; the
  Large - SOE difference in columns 2–4.
- **Misses:**
  - Column 1 (returns, coefficients in percent per year, 1.2-point rule): Large -8.03 vs
    -6.353, SOE -1.02 vs -2.793, Large - SOE -7.01 vs -3.560. Rounds:
    1. Weights in RMB instead of USD (SAS `lag_mkt_cap` is not labelled): -7.62 / -0.83 /
       -6.79.
    2. The 70th-percentile cut computed on the regression sample only: -7.64 / -0.99 /
       -6.65.
    3. OLS (to see whether weighting drives it): -7.53 / -2.28 / -5.25.
    Large stays 1.3–1.7 points too negative and SOE too small in every variant. Most likely
    cause: the SOE classification (below) and the sample gap (N), not the specification.
  - SOE in investment: -0.38 (t -4.3) vs 0.074 (1.05). SOE in NCF: t 2.44 vs 0.92 (same
    sign). Most likely cause: the CSMAR controller classification differs from the
    authors' WIND-based SOE2 (ALN-1: our SOE counts are 10–19% higher in 2003–2014).
  - Large - SOE in returns: t -3.19 vs -1.60 (our SOE coefficient is smaller).
  - N is 9% (returns) and 5–8% (operating) below the printed values: our Table X N shows
    the same gap (ALN-4).

## LI-1 Li factors vs the authors' allfactors (partly resolved)

Table 1 Panel A (sample, linked here): 299 of 300 cells match; 2004 SME circulating cap is
0.012 vs a printed 0.01 trillion (a two-digit rounding of a tiny value under the rel10 rule).
Four Table 1 correlations printed as 0.00 have no sign and are not scored (coef rule).


Standard: month-by-month correlation >= 0.95 with `allfactors.sas7bdat`, 2000-07..2019-06
(lighthouse 3.3). Current (tests/test_li.py checks the passing ones):

| Factor | Corr | Median abs. monthly gap (pp) |
|---|---|---|
| MKT | 1.000 | 0.02 |
| SMB-FF3 / SMB-FF5 | 0.997 / 0.997 | 0.08 / 0.07 |
| HML-FF3 / HML-FF5 | 0.958 / 0.961 | 0.11 / 0.10 |
| RMW | **0.906** (0.997 without 2006-10) | 0.11 |
| CMA | 0.992 | 0.11 |
| ME / I/A / ROE | 0.996 / 0.965 / 0.980 | 0.09 / 0.09 / 0.11 |
| MOM | **0.70** | — |

Rounds that set the kept choices:
1. Weights: previous month-end circulating cap (fixed June weights lower every
   correlation). Market cap base: circulating for size, B/M and weights (total-cap variants
   are lower, HML-FF3 down to 0.77).
2. Sample filters: the holding-month filter of LI-2 lifts every factor (SMB 0.961 -> 0.997,
   ME 0.940 -> 0.996, CMA 0.888 -> 0.992). A formation price filter lowers them, so the
   factors use none.
3. FF5 sorts use the stocks with B/M, OP and INV all available (the authors' HML-FF5 differs
   from their HML-FF3): HML-FF5 0.948 -> 0.961, SMB-FF5 0.992 -> 0.997. OP = CSMAR operating
   profit / book equity (the Fama-French revenue-minus-costs version gives RMW 0.874).

Remaining:
- **RMW, HML in 2006-10:** one month carries most of the gap (authors' HML-FF3 23.6% vs our
  5.8%, RMW gap 22.7 pp). No stock in today's CSMAR data has a return large enough; most
  likely a record in the authors' (2019-2021) CSMAR vintage around the split-share reform.
- **MOM (0.70):** good in 2000-2005 and 2010-2019 (0.94-1.00 by year), poor in 2006-2007
  (0.3-0.6) and 2015 (0.66), the years with mass suspensions and share bonuses. Rounds: (a)
  prior return on a full calendar grid with 11 / 9 / 6 / 1 required months: 0.66-0.71;
  (b) unadjusted price ratios (a guess at the authors' compounding): 2006-07 improves to
  0.6-0.8 but 2015 falls to 0.0-0.45, overall 0.69-0.72; (c) non-ST reform statuses (G, S,
  U, N) allowed at formation: 0.69. Not resolved; MOM enters only the Carhart model.

## LI-2 Li penny-stock and status filter: a look-ahead in the authors' procedure

DM p.2: penny stocks (price < 5) are excluded "after forming quintiles but before calculating
quintile returns". Calibrated on the authors' quintile series for the price sort
(`g5_g1_2000_2019/pps_1_2`), whose lowest quintile is the most sensitive:
- filter at formation only (literal reading): our lowest quintile is empty in 78 months and
  earns 0.4% vs the authors' 1.1% a month;
- formation filter before the breakpoints: all months filled, but 1.1% vs 2.3%;
- formation filter before the breakpoints **and** dropping stocks whose return-month record
  has price < 5 or an abnormal trading status: every quintile within 0.05 pp of the
  authors' in 210-228 of 228 months (median gap 0.000-0.002 pp; correlation 0.997-1.000).

The second filter uses the month-end price and status of the return month, which are not
known when the portfolio is formed. It removes stocks that fall below 5 yuan or become ST
during the month, which raises low-price and distressed portfolios' returns (here the price
sort's lowest quintile: 2.3% a month with it, 1.1% without). The comparison with the printed
numbers uses the authors' procedure (lighthouse 3.1: each paper's own conventions);
`portfolios.HOLDING_MONTH_FILTER=False` gives the look-ahead-free version, reported next to
it. User decision (2026-10-11): the extended and full segments headline the look-ahead-free
version, with the authors' procedure shown alongside; the original segment's comparison with
the printed numbers uses the authors' procedure.

## LI-3 Li anomaly signals: month-by-month check against the authors' quintile series

The authors' replication package holds the monthly quintile returns of their significant
anomalies (`g5_g1_2000_2019`, `g5_g1_2008_2019`). `replication.li.checks` compares every one
of them with ours (Mainboard-VW, authors' procedure) on each run and writes
`results/li_g5g1_check.csv` (lighthouse 3.3: g5-g1 correlation >= 0.90). Current result:
**99 of 117 series we can build pass; 18 miss; 22 are spread / VPIN series we cannot build
(LI-4).** The engine itself is exact: the price sort (Pps1..Pps12) matches at 0.998-1.000
(tests/test_li.py).

Engine-level choices kept, with their rounds:
- Market equity in price ratios: circulating (Epq 0.984 vs 0.953 with total; Ndp 0.905 vs
  0.762). Bmj uses total cap (its definition is per total share).
- Value weights: previous month-end circulating ME, updated monthly also for annual sorts
  (June weights lower I/A 0.844 -> 0.823, dPia 0.944 -> 0.906).
- Negative book equity (latest annual report) excluded, per the data manual; it moves
  results by less than 0.01 pp.

Variable-level changes adopted after rounds against the authors' series:
- Rdmq: ME at the end of t-1 instead of the data manual's "end of last calendar year":
  0.977 vs 0.832 (round 2, announced timing: 0.796; round 3, total ME: 0.806).
- R[2,5]n (and the other seasonality averages): mean over the available lags: 0.867 vs 0.810
  with every lag required (at least half the lags: 0.863; compounded: 0.817). This follows the
  authors' series, not the data manual's wording ("the average return across months"), and a
  stock with a single available lag gets that month's return.
- Sue, Rs: standard deviation over the eight previous quarters: Sue6 / Sue9 0.886 / 0.869
  vs 0.870 / 0.838 (all eight required: 0.877 / 0.844).
- Abr: an event enters the sort only after its day +1 (reviewer finding: the window's last
  day could fall in the holding month).

The 18 misses and their rounds:

| Series | Corr | Rounds (result) | Most likely cause |
|---|---|---|---|
| Cei (2008-19) | 0.48 | circulating vs total ME (0.48 / -0.20); 60 / 48 / any months (0.48-0.53); returns with / without dividends (0.48 / 0.46) | share-count changes around the split-share reform in CSMAR's market cap |
| βPS3, βPS6 (2008-19) | 0.67, 0.66 | value-weighted aggregation of the stock-level γ (0.607); no 1%/99% trimming of γ (0.645); CSMAR's series not subscribed (LI-4) | different liquidity series |
| Isq1, Isq3 | 0.87, 0.80 | plain vs adjusted skewness (0.884 vs 0.869); >= 15 days (0.883); FF3 residuals as a check (0.637) | daily q factors (I/A daily 0.93 to the authors' monthly) |
| Noa (2000-19, 2008-19) | 0.82, 0.90 | as I/A below; formation weights (0.778); December listing required (0.910) | single months (e.g. 2015-04) where large firms sit in different quintiles; CSMAR vintage of balance-sheet items |
| ϵ6 (3, 6 months) | 0.84, 0.88 | sd of all 36 residuals (0.847); >= 24 months (0.843); full 36 months (0.778) | our FF3 factors (HML-FF3 0.958, LI-1) |
| I/A (2008-19) | 0.85 | restated prior-year assets (0.810); December listing (0.841); stale weights for resumed stocks (0.829). Further checks, informational (beyond the three rounds): BE screen (0.851), formation weights (0.823) | as Noa |
| Atoq1-9 | 0.86-0.88 | four-month rule instead of announced (0.886, but mean 0.72 vs 0.64); current Noa (0.867); operating revenue (0.871) | net operating assets inputs (cash, short-term investments before / after 2007) |
| R[2,5]n | 0.87 | see above (adopted round) | sparse long lags for recently listed stocks |
| Sue6, Sue9 | 0.89, 0.87 | see above (adopted round) | quarterly statement vintage (LI-6) |
| Svr1 (2008-19) | 0.88 | U.S. dVXO of the previous calendar day (0.088) or business day (0.165): same-date matching is right | VXO day matching on U.S. holidays |

Other measures reported but not scored by an authors' series: Rtv / Cvt correlate 0.956 /
0.920 at one month (their low-volume quintile differs; daily vs monthly volume and minimum-day
rules did not close it).

## LI-4 Li variables with substituted or missing inputs (lighthouse 5.3)

Access checked on CSMAR 2026-10-13 (docs/csmar_access.md batch 6).

- **R&D (Rdm, Rds):** the annual R&D table (研发投入情况表, RDSpendSum) is not subscribed.
  The paper proxies R&D with management fees (B001210000, Chen, Kim, Yao and Yu 2010) for
  Rdmq, Rdsq and Rca; Rdm and Rds use the same proxy here. The income-statement R&D line
  (B001216000) and the R&D notes table start only in 2018.
- **Fop:** CSMAR's RelativeOptimism is per analyst report (AF_ANAFOREFEATURE); the data manual
  gives no aggregation rule. We average the reports dated in calendar year t-1.
- **Gov:** six of the seven principal-component inputs; institutional ownership (机构投资者)
  is not subscribed. Inputs come from 治理结构 and 股东 tables instead of the 经营困境
  sub-database the paper names (not subscribed); shares balance = (top-5 - top-1) / top-1.
- **Dac (and Pda):** CSMAR's DisAcc is not in our tables; rebuilt with the modified Jones
  model (Dechow, Sloan and Sweeney 1995) by CSRC industry letter and fiscal year (>= 10
  firms), the method the data manual attributes to CSMAR.
- **Not producible (16 of 469 anomalies):**
  - Parc (1): patents (上市公司研发创新) not subscribed;
  - Esba, Qsba, Vpin (15): 已实现指标 (intraday-based spreads and VPIN) not subscribed. In the
    paper 12 of the 78 significant anomalies are among them (Esba1-12, Qsba1-12, Vpin3, Vpin6),
    so our significance counts cannot reach the printed totals.
  - (Svr is built: FRED VXOCLS, approved 2026-10-13; VXO ends 2021-09, so Svr stops there.
    g5-g1 correlation with the authors' Svr1: 0.911 at one month in 2000-19 (no authors' file
    for that period) and 0.882 against their 2008-19 Svr1 file, LI-3.)
- **Substituted (built):**
  - βPS (5): CSMAR's innovations in aggregate liquidity (因子研究系列 -> 股票流动性) are not
    subscribed (checked 2026-10-13). Rebuilt from daily data with the Pástor and
    Stambaugh (2003) method (lighthouse 5.3: construct an A-share version); built, g5-g1
    correlation with the authors' βPS3 / βPS6: 0.67 / 0.66 (the rebuilt liquidity series
    differs from CSMAR's). As in Pástor and Stambaugh (2003), the AR regression that defines
    the innovations is fitted over the whole sample, so each month's innovation uses
    coefficients estimated with later data (a property of the published method).
  Significance rates use the anomalies we can build as the denominator (Table 3 reports the
  counts as 'n_available').

## LI-5 Li Table 2: size groups and microcaps

- **Sample:** eligible at t-1 with price >= 5 (the portfolios' formation filter), t-1 values
  from the previous calendar month only. Now 1,530 stocks / 459 microcaps / EW market 1.25%
  vs the printed 1,563 / 449 / 1.28%.
- **Within tolerance:** all eight market cells, the micro and small counts, every market-cap
  share, VW means and standard deviations, and all 56 Panel B microcap weights.
- **Also missing:** the counts of big stocks (621 vs 657) and all-but-micro (1,071 vs 1,114),
  and the EW means of small, big and all-but-micro stocks (lower than printed).
- **Misses:** microcap returns are higher (VW 1.60% vs 1.40%, EW 1.95% vs 1.69%) and the
  microcap cross-sectional standard deviation is higher (11.7% vs 9.9%). Rounds:
  1. Lagged values only from the previous calendar month (reviewer finding): microcap VW
     1.73 -> 1.60%, EW 2.08 -> 1.95%, market EW 1.29 -> 1.25%; all eight market cells now
     pass. Kept.
  2. Adding the portfolios' holding-month filter (price >= 5 and normal status in month t):
     market EW 1.48% (further from 1.28%). Not kept.
  3. No price filter at t-1: counts 1,755 / 515 (vs 1,563 / 449). Not kept.
  Most likely cause of the remaining gap: resumption months after long suspensions, whose
  returns are large and fall mostly on microcaps (the paper does not describe Panel A's
  sample beyond the breakpoints). Panels C-D (capacity) are reported in
  results/li_comparison.csv.

## LI-6 Li Tables 3-4 and the introduction's counts: which anomalies are significant

- **Overall rates are close:** 79 of the 453 anomalies we build (17.4%) are significant at
  |t| >= 1.96 (Mainboard-VW, 2000-07..2019-06) vs 78 of 469 (16.6%); failure rates 82.6 /
  82.8 / 85.4% vs 83.4 / 84.2 / 87.0% (raw / CAPM / FF3), within 3 points; post-2007 58
  significant vs 61.
- **The composition differs:**
  - Trading frictions 21.9% vs 32.2%: 12 of the paper's 78 significant anomalies are the
    spread and VPIN variables we cannot build (LI-4).
  - Momentum 28.9% vs 15.6% and profitability (see results/li_comparison.csv, T3): quarterly earnings-based sorts
    (Roeq, Roaq, Rnaq, Glaq, Sgq, Tes, Rs) are stronger in our data. Roeq1 earns 0.81% (t
    2.29) vs the printed 0.48% (insignificant).
  - Of the paper's 66 buildable significant anomalies, see results/li_g5g1_check.csv for
    the month-by-month agreement (LI-3).
- **Rounds:**
  1. Signal-level calibration against the authors' quintile series (LI-3): the earnings
     signals that have a series (Sue, dRoe, dRoa, Epq, Atoq) correlate 0.87-0.98, with our
     spreads within 0.07-0.19 pp of theirs; so the timing rules are right.
  2. The quarterly ROE used in the q-factor (same events) reproduces the authors' ROE factor
     at 0.98 (LI-1); Roeq has no author series (insignificant in the paper), so its stronger
     spread cannot be traced to a single input.
  3. The MHT counts (19 vs 29 full; 18 vs 22 post-2007) are lower largely because 9 of the
     paper's 29 MHT anomalies are spread variables (Esba, Qsba).
- **Not resolved:** the stronger quarterly-earnings anomalies. Most likely cause: CSMAR data
  vintage differences in quarterly statements and announcement dates (CSMAR revises
  IAR_Rept), which move firms across the extreme quintiles of earnings-based sorts.

## LI-7 Li Tables 5-6: factor models

- The models are run on our significant set (LI-6), so Table 5 averages differ when the set
  differs: e.g. CH3 leaves 21 of 79 H-L alphas significant vs 36 of 78; mean |alpha| 0.36%
  vs 0.64%. The paper's unexplained anomalies are concentrated in trading frictions, where
  the 12 spread / VPIN variables are missing for us.
- Table 6 is scored anomaly by anomaly for the paper's significant ones; 352 cells belong to
  the spread / VPIN variables we cannot build.
- Factor differences (LI-1: HML-FF5, RMW and MOM below 0.95) feed into the FF5 and Car4
  alphas.
- **Round (composition):** Table 5 recomputed on the paper's own significant set
  (`checks.table5_on_paper_set`, the 66 of its 78 we can build). H-L alphas still significant
  under CH3: 22 of 66 (paper 36 of 78; 24 once its 12 spread / VPIN anomalies, all with
  large alphas, are set aside); under q 39 of 66 (paper 58, 46 without them); under FF3 42
  (49 without them). So most of the gap is the missing spread / VPIN anomalies; the rest is
  smaller alphas in our data (mean |alpha| under q 0.62% vs 0.83%).
- **Round (scoring):** Table 5 / 7 counts are scored with the relative 3% count rule; for
  counts of 10-50 one anomaly is 2-10%, so most count cells fail on a one- or two-anomaly
  difference.

## LI-8 Li Table 7: SOE vs non-SOE

- SOE flag: actual controller (Allen's soe_flags) instead of CSMAR's equity-nature file (not
  subscribed). End-2003 SOE share 75.1% vs the printed 74.57%.
- SOE subsample 2004-07..2019-06: 43 significant raw spreads vs 44; CAPM 40 = 40, FF3 35
  vs 33, FF5 37 vs 36. The q / CH3 / CH4 counts are lower (q 18 vs 24; CH4 11 vs 24).
- Non-SOE subsample 2004-07..2019-06: 74 vs 90 raw. By category: value-versus-growth 13 vs
  27 and trading frictions 24 vs 36 (spread / VPIN, LI-4); momentum 10 vs 3 and intangibles
  15 vs 9 the other way, the same pattern as the full sample (LI-6).
- Rounds: (1) the SOE flag cannot follow the paper's source (not subscribed); our end-2003
  share is 75.1% vs 74.57%; (2) the composition rounds of LI-6 / LI-7 apply unchanged.
- Counts are scored with the relative 3% rule, which is strict for counts of 10-50 (one
  anomaly is 2-10%).

## LI-9 Li section 4.2: HXZ U.S. anomalies

- Today's global-q.org testing portfolios hold 187 anomalies, the number in the paper.
  2008-07..2019-06: 16.04% / 4.81% significant, exactly as printed; 2000-07..2019-06: 25.1% /
  5.3% vs 24.06% / 4.81% (47 vs 45 anomalies), within 3 points. The two extra anomalies are
  most likely revisions in the 2025 vintage of the portfolios.
