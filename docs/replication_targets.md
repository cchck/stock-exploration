# Replication targets

Each paper is replicated under **its own** conventions. Choosing one convention for SignalLab
China comes later (see `project_brief.md`, decision log). Numbers below were transcribed from
the PDFs; page/table references let a reader re-check them.

Status legend: `todo` / `in progress` / `matched` / `deviates (see note)`.

## 1. Liu, Stambaugh & Yuan (2019, JFE 134:48-69), "Size and value in China"

Conventions: WIND data (we use CSMAR); Jan 2000 - Dec 2016 (204 months); stock codes starting
60/30/00; exclude bottom 30% by previous month-end total market cap; exclude stocks listed < 6
months, < 120 trading days in past 12 months, or < 15 days in the past month; weights = total
market cap including non-tradable shares; risk-free = one-year deposit rate; financial data =
latest statement publicly released before month end (quarterly from 2002, semi-annual before);
negative-EP stocks kept and classed as growth. Factors: 2x3 sorts, size split at median, EP
30/40/30.

| Target | Paper value | Status |
|---|---|---|
| Table 3: MKT mean / t | 0.66% / 1.16 | todo |
| Table 3: SMB mean / t | 1.03% / 3.25 | todo |
| Table 3: VMG mean / t | 1.14% / 4.34 | todo |
| Table 3: corr(SMB, VMG) | -0.62 | todo |
| Monthly CH-3/CH-4 series vs Stambaugh website | correlation (threshold to agree) | todo |
| Table 2 col 8: EP+ coefficient t | 4.38 (BM 1.31, AM 0.99, CP 1.35) | todo |
| Table 5: CH-3 alphas of FF-3 SMB/HML | -4 bp (t -0.66) / 34 bp (t 0.97); GRS p 0.41 | todo |
| Table 5: FF-3 alpha of VMG | 139 bp/month (t 7.93); GRS p < 1e-12 | todo |
| Table 9 Panel A: avg abs alpha CAPM / FF-3 / CH-3 | 1.02 / 0.90 / 0.45; GRS10 p for CH-3 0.15 | todo |
| Table 10: CH-4 explains all 10 anomalies | avg abs alpha 0.30; GRS p 0.41 | todo |

## 2. Li, Liu, Liu & Wei (Management Science, forthcoming), "Replicating and digesting anomalies in the Chinese A-share market"

Conventions: CSMAR; returns Jul 2000 - Jun 2019 (228 months), post-2007 = Jul 2008 - Jun 2019
(132 months); exclude negative book equity, financials (CSRC), ST/PT/abnormal status; drop
price < 5 yuan after forming quintiles; **mainboard breakpoints**, **circulating-cap value
weights**, quintiles; annual sorts at end of June using fiscal year t-1; quarterly items
other than earnings lagged 4 months; risk-free = 3-month deposit rate (PBoC website);
SHT |t| >= 1.96, MHT |t| >= 2.78.

**Blocker:** the 469 variable definitions are in the paper's Online Appendix (Table A1), not
in our copy.

| Target | Paper value | Status |
|---|---|---|
| Table 2 Panel B: microcap weight in lowest quintile, All-EW vs Mainboard-VW | 26.86% vs 8.20% | todo |
| Table 3 Panel A: share significant (SHT), Mainboard-VW vs All-EW | 16.63% vs 47.55% | todo |
| Abstract: failure rate raw / CAPM / FF3 | 83.37% / 84.22% / 86.99% | todo |
| Table 1 Panel B: ME, I/A, ROE, VMG, PMO means (t) | 0.78 (3.12), 0.29 (2.10), 0.54 (2.36), 1.20 (4.82), 0.93 (3.98) | todo |
| Section 1: significant count, full / post-2007 (SHT) | 78/469, 61/469 | todo |
| Section 1: significant count, post-2007 (MHT) | 22 (the conclusion says 21; 22/469 = 4.69% matches the stated rate) | todo |
| Table 5: share explained, CH3 / CH4 / q (full) | 53.85% / 47.44% / 25.64% | todo |
| Table 5: share explained by q (post-2007) | 73.77% | todo |
| Representative subset of Table 4 anomalies across 6 categories | per-anomaly m | todo |

## 3. Allen, Qian, Shan & Zhu (2024, JF 79(2):993-1054), "Dissecting the long-term performance of the Chinese stock market"

Only the within-A-share parts are in scope; cross-country tests need Worldscope, BoardEx,
RiskMetrics and the NBS industrial firm database, which we do not have.

| Target | Paper value | Status |
|---|---|---|
| Figure 1: real value of RMB 1 in VW A-share portfolio, 2000 -> 2018 | 1.01 | todo |
| Figure 2: BHR of large / medium / small A-shares (30/70 pct of lagged market cap) | plot | todo |
| Table XII Panel A: Large / SOE coefficients in annual return regression | -6.353 (t -3.95) / -2.793 (t -1.84) | todo |
| Table VIII Panel B: G-Index-A mean, small vs large, SOE vs non-SOE | 2.722 vs 2.235; 2.211 vs 2.845 | todo |
| Section III.A.2: delistings per year 2000-2018 | about 5 (2.7%) | todo |

SOE status must be rebuilt from 上市公司控制人文件 (the 股权性质 table is not subscribed).
The JF site provides replication code (Supporting Information) to check against.
