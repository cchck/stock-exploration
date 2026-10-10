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
  - Result: p 0.96 and p## ALN-0 Allen review fixes that changed many numbers (2026-10-10)

The milestone 1.3 guard failed the first version. The fixes, which apply to every ALN
entry below:

1. **Figure 1–2 start month.** Lighthouse 3.1 prescribes monthly from 2000-12 to 2018-12;
   the first version compounded from 2000-01. Corrected, the 2018 value is 1.10, not 1.76
   (ALN-6).
2. **Winsorization within each segment.** It had been pooled over 1990–2026; it is now
   done separately for each sample segment, levels and lags. As a result:
   - turnover max 16.4 becomes 11.95 (paper 12.18);
   - 2018 average assets 3.18 becomes 2.87 (paper 2.78).
3. **A shares only for ST and delistings.** B-share tickers had been counted:
   - first-ST firms: 606 becomes 562 (paper 572);
   - delistings: 6.2 a year becomes 5.3 (paper about 5).
4. **Province fixed effects in Table XIII**, as printed and in Table13.sas.
5. **Clustering as in the SAS code.** "cluster Industry1 fyear" with Industry1 = CSRC
   industry letter (SAS notes). In PROC SURVEYREG, several CLUSTER variables define clusters
   as their combinations, so the clusters are industry-letter by year cells. Fixed effects
   stay at the CSRC two-digit level (IndNumeric1-80).
6. **SOE flag.** Any of a firm-year's controller rows with a state code, comma-joined code
   lists included, makes it SOE. A reported "no controller" counts as non-SOE.
7. **Data definitions.**
   - Missing executive holdings stay missing (not zero).
   - RPT amounts are restricted to RMB and non-negative values.
   - ROIC uses the previous year's invested capital.
   - Return volatility comes from daily returns (Appendix A).
   - Cross-listing is time-varying: H shares outstanding at the year end.
8. **Scoring.** Coefficients in return units (Table X; Table XIII returns) use the
   annualized return rule (1.2 points); investment / NCF levels use the 3-point proportion
   rule.

## ALN-1 Allen Table I (deviation)

- **Listed firms:** all 19 years are within 3%; the unique-firm count is 3,668 vs 3,695.
- **SOE counts:**
  - 2000–2002 are not producible: the controller file starts in 2003.
  - 2003–2014 are 9–15% above the printed counts; 2015–2017 are 6–8% below; 2018 is
    1,082 vs 1,078.
  - The printed series jumps from 879 to 1,081 in 2015; ours is smooth.
  - Rounds 1–2 (code sets without government agencies or without SOE-enterprise
    controllers) improved some years and worsened others. The literal definition is kept.
- **Average assets ($ bn):**
  - 2000–2002 match.
  - After per-segment winsorization, the 2018 value is 2.87 vs 2.78 (+3%) and 2015 is 2.51
    vs 2.38 (+5%). The unique-firm average is 1.82 vs 1.59.
  - Rounds:
    1. Per-year winsorization: worse.
    2. Non-financial firms only: 30% too low.
    3. Per-segment winsorization: adopted, as above.

## ALN-2 Allen Tables VIII–IX: governance and turnover (partly resolved)

- **Within tolerance:**
  - CEO duality: 0.211 vs 0.208.
  - Ownership concentration: 0.530 / 0.533 / 0.154 vs 0.539 / 0.546 / 0.152.
  - Executive holdings: 0.079 vs 0.104 (3-point rule).
  - Board size: 16.9 / 16 / 4.04, min 1, max 54 vs 16.8 / 16 / 4.029 / 1 / 54.
  - State ownership: 0.126 vs 0.116.
  - Turnover mean: 3.05 vs 3.148; max 11.95 vs 12.18.
- **Rounds:**
  1. Board size = directors + supervisors + senior managers (`TotalNumber`). Directors
     alone have a median of 9; the full count reproduces 16.8 / 16.
  2. Panel A means: only G-Index-I is value-weighted. Value-weighting every component gives
     ownership concentration 0.634.
  3. G-Index-I ties follow the caption (middle band includes the percentiles), except
     executive holdings, whose mass point at zero (p30 = 0) would otherwise give a point to
     every firm with zero holdings.
  4. Missing components before 2003 (ownership lists): the index is the sum of the
     remaining components (lighthouse 5.2).
  5. State holdings by holder nature (国家 / 国有法人 holders) instead of share type.
     - Rationale (review): share-type state shares shrink after the split-share reform even
       for SOEs.
     - Result: mean 0.395 / median 0.422 vs printed 0.116 / 0, and the G-Index-A mean fell
       to 2.06.
     - The share-type measure (0.126 / 0 / 0.211 vs 0.116 / 0 / 0.211) is therefore what
       the paper used. It is kept, with the post-reform shrinkage as a known property of the
       paper's own measure.
- **Remaining:**
  - G-Index-A: mean 2.39 vs 2.482 (relative 3% rule: miss, -3.5%); median 2 vs 2; sd 1.28
    vs 1.181.
  - G-Index-I value-weighted: mean 2.66 vs 2.271, median 3 vs 2.
  - SOE vs non-SOE G-Index-A: 1.79 vs 3.07 against printed 2.211 vs 2.845. The difference
    1.27 vs 0.699 comes from the state-holdings component (SOEs held state shares before
    the reform).
- **AH premium:** not producible (no Hong Kong data in NYU's subscription).

## ALN-3 Allen RPT measure (resolved)

Unchanged from the first version. The funds-only "loan" reading gives sd 0.054; every
cash-settled category with the cash direction set per category gives sd 0.127 and a range
-0.57..0.59 against printed 0.117 and -0.475..0.524. The G-Index-A mean then matches best.
Table XIII uses the loan-only outflow, as its text says.

## ALN-4 Allen Tables X–XI (deviation)

- **Table X col (1):** G-Index-A 1.447 vs printed 1.445.
- **Clustering rounds**, t of G-Index-A in col (1) (printed 2.885) and col (6) (printed
  2.795):

  | Clustering | col (1) | col (6) |
  |---|---|---|
  | Industry letter × year cells (SAS spec, adopted) | 2.29 | 2.12 |
  | Letter, two-way | 3.13 | 2.78 |
  | Two-digit industry, two-way | 2.41 | 2.16 |
  | Two-digit × year cells | 2.98 | 2.83 |

  The SAS specification is kept even though another fits better.
- **Turnover:** -0.59 (t -0.82) vs -2.475 (-3.87).
  - Round 1: total vs circulating shares in the denominator. Circulating shares give mean
    turnover 5.3 vs printed 3.148, so total is kept.
  - Round 2: per-segment winsorization. The turnover coefficient stays small.
  - Not resolved. Most likely cause: CSMAR vs WIND turnover in the 2006–2009 reform years,
    when tradable shares changed.
- **ROA[-1,+1]:** CSMAR has pre-IPO financials for only 1,099 firms. Columns (4), (7) and
  (8) have about 2,360 observations vs about 34,000 printed (data limit; Allen used
  Worldscope pre-IPO data).
- **Table XI Panel C:** 10 of 16 pass. Signs agree in every column. The coefficients run
  above the printed ones (0.57 vs 0.387 in col (1)).

## ALN-5 Allen Table XIII (deviation)

- Rounds:
  1. Province FE added.
  2. Matching on CSRC letter, keeping unmatched cross-listed firms, matched on the full
     panel because the listing year can precede 2000. The matched sample N is 2,138–2,193
     vs printed 2,162–2,463.
  3. Time-varying H-share flag: 111 matched cross-listed firms vs 99.
- **Result:**
  - RPT Amt Out, full sample: 0.003 (t 2.24) vs -0.026 (t -2.445), opposite sign. The
    printed scale of loan outflows is larger than what CSMAR's funds transactions give.
  - Matched sample:
    - RPT 0.001 vs 0.001;
    - returns 2.04 vs -0.95, both insignificant;
    - NCF -0.015 vs -0.008;
    - ROA -0.010 vs -0.006.
  - Signs agree for 6 of the 10 coefficients. Our t-statistics are larger with the
    letter × year clusters.

## ALN-6 Allen Figure 1 (partly resolved)

- Round 0 (guard): the lighthouse start month, 2000-12. The 2018 value is 1.10 vs printed
  1.01; the first version's 1.76 came from compounding 2000.
- Earlier rounds (with the wrong start): summed returns, circulating-cap weights and no
  winsorization did not explain the gap.
- The remaining 9% (outside the relative 3% rule) is attributed to the return source
  (CAFR/WIND vs CSMAR).
- Figure 2: small 4.31, medium 1.70, large 1.08. The small-cap outperformance and
  large-cap underperformance are reproduced.

## ALN-7 Allen Figures 4–5 and section III.A.2 (deviation)

- **ST firms:** first-time ST firms 2000–2018: 562 vs 572 (within 3%).
- **Permanent ST:** still ST at the end of 2018, plus footnote 21's five prior years of
  financials: 78 vs 65.
  - Round 1, "never re-emerged": 43.
  - Round 2, no financial-history requirement: 86.
  - Neither matches; the literal definition is kept.
- **Figure 4:** the ROA path is reproduced: positive in -5..-3, negative from -2.
- **Figure 5:** investment 4.9% vs 4.4% and NCF 1.2% vs 1.5%, both within the 3-point
  proportion rule.
- **Delistings:**
  - 5.3 per year vs "about five" (+6%, outside the 3% count rule).
  - Poor-performance share 57% vs "less than half".
  - Round 1, reason codes: CSMAR uses a generic code for most terminations, so it gives
    4%.
  - Round 2, ST/*ST/PT or suspended at delisting: 57%. Kept.
  - The printed "(or 2.7%)" is reported, not scored.

## ALN-8 Allen text numbers (partly resolved)

- **Matching:**
  - SOE share 2018: 30.4% vs 30%.
  - Listed firms in 1991: 13 vs 13.
  - Dividend yield 2018 (cash dividends with 2018 ex-dates over the year-end close): 1.33%
    vs 0.8%, within the 3-point rule.
  - Value-weighted OCF / assets: 7.5% vs 6.5%, within the 3-point rule.
- **Footnote 32** (small-minus-large G-Index-A gap, from the Internet Appendix): 0.33 in
  2004 vs 0.058, and 0.39 in 2007 vs 0.375. The sign rule passes both, but 2004 is far off.
  Our gap in 2004 is already large because the state-holdings component favours small
  firms.
- **Not producible:**
  - the 2000 SOE share (70%);
  - the post-IPO capex rise (needs pre-IPO data);
  - the Figure 4 t-statistics (need US data).
