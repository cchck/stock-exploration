# Data layer

What `src/csmar/` produces, every decision it makes, and the evidence behind each. Read this
before using any panel: the decisions here propagate into every replicated number.

Rebuild and re-check:

```
.venv/bin/python -m csmar.build      # raw CSV -> data/interim/raw/*.parquet -> data/processed/*.parquet (~80 s warm)
.venv/bin/python -m csmar.validate   # consistency and paper-count checks -> results/data_layer/*.csv
.venv/bin/python -m pytest           # parser, panel and contract tests
```

Raw files and all firm-level outputs stay on this machine (NYU licence; `data/` is
gitignored). `results/data_layer/` holds aggregates only and is committed.

## 1. Raw tables and readers (`csmar.registry`, `csmar.readers`)

- Every raw table is registered once in `csmar.registry.TABLES` with its platform row count
  (from the CSMAR web page at download time, logged with SHA-256 in `docs/csmar_access.md`).
  `read_raw` raises `RowCountMismatch` if any chunk deviates.
- CSMAR CSV quirks the readers handle:
  - every field is quoted; large exports are split into `<code>.csv`, `<code>1.csv`, ... at
    1,000,000 rows (sorted by stem length, then name);
  - zip entry names are GBK-encoded (extract with `ditto -x -k`, done at download time);
  - free-text fields contain unescaped quotes and raw newlines. `HLD_Contrshr`, `CG_Ybasic`
    and `RPT_Transfer` were re-downloaded without their long text fields (`_notext`);
    `TSR_Stkstat` and `STK_MA_TRADINGMAIN` are read with the quote-aware parser
    (`read_quote_delimited`), which splits on `"\n"` and `","` only.
- The quote-aware parser keeps every record verbatim and logs each record that contains a
  stray quote, on every read (the list is stored with the parquet cache, so a cache hit
  re-logs it). Current files: `TSR_Stkstat` 16 such records (1 of them breaks a standard
  parser), `STK_MA_TRADINGMAIN` 5 (0 / 3 / 1 / 1 by 5-year chunk). Both tables then match
  their platform counts exactly, so no tolerance is used in practice.
- Mixed-type object columns across chunks (seen in `RPT_Transfer`) are cast to string before
  caching; `Stkcd` is zero-padded to 6 digits.
- Each table is cached as parquet with a signature of the source files' sizes and mtimes;
  touching a raw file invalidates the cache.

## 2. Panels (`csmar.panels`, written to `data/processed/`)

| Panel | Key | Rows (build of 2026-10-09, after adding 1999-12 daily) | Source |
|---|---|---|---|
| company_info | stkcd | 6,051 | TRD_Co |
| stock_month | stkcd, month | 953,894 | TRD_Mnth + company_info + st_month |
| st_month | stkcd, month | 907,806 | TRD_Dalyr.Trdsta (1999-12 onward) |
| daily_month | stkcd, month | 907,806 | TRD_Dalyr (1999-12 onward) |
| statements | stkcd, accper | 312,895 | FS_Combas/Comins/Comscfi/Comscfd (Typrep A) + IAR_Rept |
| statements_opening | stkcd, accper | 77,501 | same, Accper = YYYY-01-01 |
| risk_free_1y | month | 432 | TRD_Nrrate (NRI01) |
| cpi | month | 404 | FRED/OECD + NBS |

The panels are paper-neutral: no ST, financial-industry, microcap or price filters are
applied here. Each replication module applies its paper's own rules as named parameters.

### 2.1 Stock-month

- All markets are kept (A and B shares). `board` comes from the market type plus code prefix:
  SH_MAIN, SZ_MAIN (000/001), SZ_SME (002/003, kept separate after the 2021 merger
  because Li et al.'s mainboard excludes it), CHINEXT, STAR, BSE, SH_B, SZ_B. An
  unclassifiable combination raises an error.
- Market values are converted from CSMAR's thousands to units of the trading currency. For
  A shares that is yuan; Shanghai B shares are in USD and Shenzhen B shares in HKD (as are
  their prices and traded value). The `currency` column says which; never sum or rank across
  currencies. Li Table 1 Panel A total and circulating market values are matched within
  0.37% in every year from 1999 to 2018, which confirms the unit.
- CSMAR has no row for a month without any trading day (full-month suspension). Those months
  are not filled in. `month_gap` = months since the previous traded month (NA in the first
  month), so "consecutive months" is an explicit flag, not an assumption.
- Return conventions, verified against the compounded daily dividend-reinvested return:
  - continuing months: 99.996% of 898,219 stock-months agree within 1e-4. The ~35 exceptions
    cluster in 2019-06 (19 cases) and 2020; one is 600018 in 2006-10, its merger-relisting month.
  - resumption months (gap > 1): 100% of 4,582 agree. The resumption-day daily return is
    measured from the last pre-suspension close, so the monthly return in the resumption
    month spans the whole suspension and no return is lost.
  - first traded month: CSMAR leaves `ret` blank (all 4,997 cases). Papers that need the IPO
    month must compute it themselves.
- Industry: `csrc2012` / `csrc2001` are the **current** classification (TRD_Co has no
  history). `is_financial` = CSRC 2012 section J, or CSRC 2001 section I if 2012 is missing.
  Evidence that the deviation is small: with it, Li's yearly non-financial counts match
  exactly (section 4).

### 2.2 ST and trading status

- `st_end` / `st_any`: ST, *ST or PT on the month's last trading day / any trading day.
  The ST codes are {2, 5, 8, 11, 14}, the *ST codes {3, 6, 9, 12, 15} and the PT code 16.
- `trdsta_end`: the raw code on the last trading day. The CSMAR definition is 1 = normal,
  2 = ST, 3 = *ST, 4 = S, 5 = SST, 6 = S*ST, 7 = G, 8 = GST, 9 = G*ST, 10 = U, 11 = UST,
  12 = U*ST, 13 = N, 14 = NST, 15 = N*ST, 16 = PT.
  - Codes 4, 7 and 10 are the split-share-reform prefixes S/G/U: not ST, but not "normal"
    either. (Code 13, N, never occurs at a month end.)
  - 181 stocks had one of these codes at the end of 2005, and 15 were still on one at the
    end of 2025.
- Li et al.'s "abnormal trading status at year end" = `trdsta_end != 1`. This rule, not
  "is ST", reproduces their counts.
- No status exists before 1999-12: the daily download covers 1999-12 onward (1999-12 was
  added so that Li's end-of-1999 sample can be formed).

### 2.3 Daily aggregates

`daily_month` gives generic building blocks:
- `n_days`, `vol_daily` (std of daily returns), `turnover` (sum of shares traded divided by
  circulating shares, where circulating shares = circulating value / close), `amihud`, and
  `max_ret`.
- The listing day is **excluded** from these aggregates. Its return is measured from the IPO
  offer price, and first-day returns of several hundred percent are common. CSMAR's monthly
  file likewise leaves the IPO month's return blank. `listing_day_in_month` flags those
  months. The listing day is detected for 99.98% of IPOs since 2000; the exception is
  600018, a reused code.
- `ret_compounded` compounds all days, including the listing day. It exists to verify the
  monthly file.
- `zero_volume_days` is always 0: the daily file only contains days with trading.

Paper-specific variables (window, minimum days) are computed in each replication module.

### 2.4 Statements

- Consolidated statements only (`Typrep = A`), outer-merged across the four tables on
  (Stkcd, Accper).
- **Originals vs restatements.** Period-end rows hold the figures as originally reported:
  - For firm-years flagged `IfCorrect = 1`, the year-end row differs from the next year's
    opening-balance row (the restated comparative) 23% of the time. The figure is 15% for
    `IfCorrect = 0`.
  - The parent net profit in FS matches the IAR_Rept originally announced profit in more
    than 98% of rows.
  - So CSMAR does not overwrite originals. Restated values exist only in the YYYY-01-01
    opening rows, which are split off into `statements_opening` and must never enter a
    "latest available statement" lookup. This is what makes look-ahead-free signal
    construction possible (lighthouse.md 3.2).
- Restatement flags are kept per table: `IfCorrect_<table>`, `DeclareDate_<table>`.
- `report_type` comes from the period end (03-31 = Q1, 06-30 = semi-annual,
  09-30 = Q3, 12-31 = annual). It agrees with IAR_Rept's own type on every matched row.
- `announce_date` is the actual disclosure date from IAR_Rept. An unknown day "YYYY-MM-00"
  is set to month end, the conservative choice: never earlier than the truth. There are
  none in the current files.
  - **Matching:** dates match for 97.8–99.4% of rows by report type. 95% of the unmatched
    rows are pre-listing statements (prospectus history), and only 216 rows after listing
    have no date. The match rate after listing is at least 99.92%.
  - **Lags:** the median lag is 27 days (Q1), 55 days (semi-annual), 28 days (Q3) and 106
    days (annual). No disclosure precedes its period end, and 0.35% of annual reports came
    out after the April 30 deadline.

### 2.5 Risk-free rate

- `risk_free_1y` gives the CSMAR NRI01 one-year deposit rate, used by LSY, at month end.
  - It follows the PBoC benchmark (1.50% since 2015-10-24) until 2022-09.
  - After that it switches to large-bank posted rates (1.65, 1.55, 1.45, 1.35, 1.10, 0.95).
  - Both segments are kept as published. Each replication states which month-end value it
    uses for month t+1.
- Li et al. use the **3-month** deposit rate, which CSMAR does not carry.
  - Through 2019-06, use the authors' `monthlyrf` series (replication package).
  - After that, use the PBoC 3-month benchmark, 1.10% annual, unchanged since 2015-10-24.
  - This is wired up in milestone 1.4.

### 2.6 CPI

- The base is the OECD level (FRED `CHNCPIALLMINMEI`, sourced from NBS) through 2025-04.
  It is chained forward with the NBS headline month-on-month index (上月=100) through
  2026-08; the `source` column records which.
- On the 19 overlapping months the two month-on-month series differ by at most 0.21 index
  points (NBS publishes to 0.1). This is checked by `csmar.validate`, and the overlap is
  saved in `results/data_layer/cpi_splice_overlap.csv`.
- The 16 NBS-only months (2025-05 onward) can carry a small rounding drift; they are not
  checked against any other source.
- NBS values were read from the public page table, because the download needs a login (see
  `docs/csmar_access.md`).

## 3. Not in the data layer, by design

- **Paper sample filters:** in each replication module.
- **SOE flag:** the 股权性质 table is not subscribed. It is rebuilt from 上市公司控制人文件
  in milestone 1.3.
- **H-share prices for the AH premium:** to be verified in milestone 1.3.

## 4. Validation results (`python -m csmar.validate`, aggregates in `results/data_layer/`)

| Check | Result |
|---|---|
| Unique keys, all panels | pass |
| Li Table 1A, non-financial normal-status stocks, 1999–2018 | **exact in all 20 years, and exact for every board (SH, SZ, SME, GEM)** |
| Li Table 1A, total and circulating market value, 1999–2018 | max deviation 0.37% |
| Allen Table I, listed A-share firms, 2000–2018 | max deviation 2.99% (2010). Their source is Worldscope. Ours counts stocks listed during the year: first traded month <= year <= last traded month, so a stock suspended all year still counts. The stricter "traded in the year" count is also saved; it misses by up to 4.1% (D-006). |
| Monthly vs compounded daily returns | see 2.1 |
| Disclosure dates | see 2.4 |
| CPI splice overlap | see 2.6 |

Yearly A-share, ST and special-status counts for 1999–2025 are in
`results/data_layer/yearly_counts_1999_2026.csv`. 2026 has no December yet; data end in
2026-09. ST counts have no paper benchmark here: neither Li Table 1 nor Allen Table I reports
them. Allen's ST statistics (section III.A.2) are compared in milestone 1.3. Years 2019–2026
lie outside both papers and are reported without a benchmark (D-010).
