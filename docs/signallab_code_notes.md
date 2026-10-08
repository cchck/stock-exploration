# SignalLab code notes and China porting map

Source read: `external/signal-laboratory` at commit `dc727d772643e2bc051ab1a3fbffae71f04f0726`
(upstream `github.com/Chihche-Liew/signal-laboratory`, committed 2026-08-30). Read on 2026-10-07.
Paper: Liu, Liu, Liu & Mei (2026), "Can AI Do Financial Research? LLM-Guided Hypothesis
Discovery in Asset Pricing", SSRN 6569258.

Line references below are to that commit. If the upstream repo moves, re-check them before
relying on them.

## 1. Architecture in one page

```
RunSpec YAML (paper/configs/*.yaml)
  -> lab/runner.py            build task, proposer, evaluator, validator, recorder
     -> lab/loop.py           per generation: propose -> validate -> evaluate -> persist
        -> lab/proposer/*     LLM roles (proposer_critic = B runs; single_agent = A1)
        -> lab/validation.py  grammar + dual-theme rule + dedup (deterministic)
        -> lab/evaluator/signal_agent_adapter.py
           -> agent/signal_evaluator.py      THE GRADER (deterministic)
              -> agent/executor.py           expression -> firm-year values -> monthly panel
              -> assay/sample.py             universe, rank transform, exclusions
              -> portfolio/sorts.py          VW quintiles, L-S, factor alpha
              -> factor_model/fama_macbeth.py  univariate FMB, Newey-West(6)
  -> archive.json / search_universe.json per task
Post-search (scripts/experiments/run_*.py, src/siglab/assay/*):
  multiple_testing.py (Bonferroni/Holm diagnostics, BY gate, Harvey 2017 Bayesian),
  double_bootstrap.py (signed Harvey-Liu), horse_race.py, subsample.py (7 windows + rolling
  decay), run_multi_model_alpha.py (FF5/FF6/q), spanning.py (Chen-Zimmermann controls).
```

The grader is cleanly separated from the LLM side: it takes pandas panels and an expression
string. **Porting to China is mostly a data-adapter job**; the LLM loop needs only vocabulary
changes (variables, themes, prompt wording).

## 2. The grader's data contract (what the China adapter must produce)

`SignalEvaluator(engine, ret_panel, me_panel, ff_factors, nyse_panel, fin_panel, start_date)`
— see `src/siglab/agent/signal_evaluator.py:51` and the US wiring in
`src/siglab/lab/runner.py:340` (`build_agent_from_env`).

| Input | US source | Shape / required columns | China counterpart (to build) |
|---|---|---|---|
| `engine.comp` | Compustat annual + CCM link | firm-year rows: `permno`, `year` (calendar year of fiscal-year end), `form_year` = year+1, one numeric column per catalog variable, `sic` | CSMAR financial statements (annual, consolidated) mapped to the variable catalog; `permno` -> 6-digit stock code |
| `engine.crsp` | "crsp_1960_2024_raw" cache | long table: `permno`, `date`, `month`, `year` | CSMAR monthly return file |
| `engine.sic_panel` | CRSP `siccd` | (month x security), 4-digit SIC | CSRC industry code (see 4.3) |
| `ret_panel` | CRSP `ret` + delisting adj. | (month x security) | dividend-reinvested monthly return |
| `me_panel` | abs(prc) x shrout | (month x security) | circulating or total market cap (convention decision) |
| `nyse_panel` | `exchcd == 1` | bool (month x security): **breakpoint universe** | mainboard flag (Li et al.) or other (decision) |
| `fin_panel` | SIC 6000-6999 | bool (month x security) | CSRC industry J (finance) |
| `ff_factors` | Ken French via pandas-datareader | columns `Mkt-RF, SMB, HML, RMW, CMA, RF` | used only for the discovery-stage L-S alpha; China choice open |

`tests/test_signallab_contract.py::test_evaluator_runs_end_to_end_on_synthetic_panels` runs
the full grader on synthetic versions of exactly these inputs. It is the template for the
China adapter.

**Repository gap:** `runner.py:349` and four scripts load a cache named
`crsp_1960_2024_raw`, but no code in the release writes it. Our adapter must build the long
monthly table itself.

## 3. Behaviours we verified or must preserve

1. **Information timing** (`executor.py`, `_to_monthly_panel`, and `__post_init__` mapping
   months >= 7 to `form_year = year`): fiscal year ending in calendar year y is used July y+1
   through June y+2. Verified by `test_fiscal_year_is_visible_july_next_year_through_june_after`.
   All A-share firms have December fiscal year ends and must publish annual reports by
   April 30 (CSRC may allow delay to June 30), so the convention carries over unchanged. Li et
   al. use the same June rebalance.
2. **Winsorization** at 1/99% within each `form_year` cross-section, at firm-year level, before
   mapping to months (`executor.py: execute`).
3. **Rank transform and imputation** (`utils/panel.py: fill_var`): each month the signal is
   ranked to [-0.5, 0.5] over every security with market equity, then missing values get 0.
   **Ranking happens before the financial and microcap exclusions** (`assay/sample.py:
   prepare_signal_panel`). Verified by `test_ranking_uses_full_cross_section_before_exclusions`.
   The masked stocks are removed afterwards but the survivors' ranks were computed with them
   present.
4. **Imputed zeros enter the quintile sort.** The portfolio sort uses the filled panel, so
   stocks with a missing signal sit at rank 0 and fall in the middle quintile, and the
   NYSE-breakpoint computation sees those zeros too. Low-coverage signals are therefore
   compressed toward the middle. This is SignalLab's design, not a bug, but it matters when
   comparing to Li et al., who sort only stocks with the characteristic.
5. **Microcap rule** (`assay/sample.py:143`): drop stocks below the 10th percentile of
   breakpoint-universe market equity, decided at formation month t.
6. **Lags:** `run_fama_macbeth(..., n_lags=1)` means a one-month lag of the signal relative to
   the return; Newey-West lags default to 6 (`nw_lags=6`). Portfolio assignment and weights
   are lagged one month in `portfolio/returns.py: calc_ptf_rets`.
7. **Coverage screen:** < 1% non-missing aligned coverage -> error, not evaluated
   (`signal_evaluator.py:134`).
8. **Financial exclusion is configurable per task** (`lab/tasks/cross_theme.py`: valuation and
   financing tasks default to `exclude_financials=False`), but the formal runs pass
   `sample_filters: [exclude_financials, exclude_microcap]` in `paper/configs/*.yaml`, which
   overrides the defaults. All 168 shipped `task.json` files record `exclude_financials: true`.
9. **No market equity variable in the catalog.** Theme exemplars write `ceq / ME`, but `ME` is
   not a catalog variable; the agent must build it as `MUL(prcc_f, csho)` (fiscal-year-end
   price x shares). The China catalog needs a fiscal-year-end close price and shares.
10. **Prompt content:** the prompt includes theme variable lists, preferred operators, the
    task's economic story, and conceptual example names (`example_interactions`). The
    `ExemplarSignal` formulas in `agent/themes.py` are **not** rendered into the prompt (only
    `preferred_ops` is; `lab/prompting/cross_theme.py:126`). Keep it that way in the China port.

## 4. Hypothesis language

- **66 variables** (`agent/variables.py`), all Compustat annual mnemonics. 17 are in no theme
  (`aco ajex ao ap fopt itcb lo mib pstk pstkl pstkrv rect seq spi txdi txditc xacc`) but are
  still valid in expressions.
- **32 operators** (`agent/operators.py`), executed in `agent/executor.py`. Lags use
  year-based merges, so gaps produce NaN instead of borrowing a neighbour year.
- **8 themes x 28 pairs** (`agent/themes.py`, `lab/tasks/cross_theme.py`).
- **Dual-theme rule** (`lab/validation.py`, `ProposalValidator.validate`): an expression must use
  at least one variable that belongs to theme A and not B, and one that belongs to B and not A.
  Exclusive-variable counts per pair range from 3 (e.g. quality-distress) to 15.

### 4.1 Porting decisions for the variable catalog (open)

Option A: map CSMAR items onto the same Compustat mnemonics. Reuses all code and prompts.
Risk: the LLM's priors about a mnemonic follow US GAAP while the number follows Chinese
Accounting Standards.

Option B: a China-native catalog with its own names and descriptions. More work; makes the
accounting differences explicit to the agent.

Known semantic gaps either way:
- **R&D**: CAS allows capitalizing development costs (separate "development expenditure"
  balance-sheet item); US GAAP expenses almost all R&D. This directly changes the paper's
  build-versus-buy survivors (Signals 1-2).
- **Book equity**: no US-style preferred stock or deferred-tax/ITC adjustments; the FF book
  equity formula in `data/compustat.py: compute_book_equity` does not transfer.
- Items with no clean CSMAR counterpart (to check field by field): `xad`, `emp`, `xacc`,
  `itcb`, `pstkrv/pstkl`, `ajex`.

### 4.2 Industry operators

`executor.py: _sic2_series` zero-pads a numeric SIC to 4 digits and takes the first two.
CSRC codes are alphanumeric (e.g. `C39`), so that function must be replaced, not fed CSRC codes.
Natural analogue: CSRC 2012 two-digit division (letter + two digits) for manufacturing, letter
section for the rest. Decision needed.

## 5. US-specific constants to replace for China

| Location | US value | Why it must change |
|---|---|---|
| `assay/sample.py:13`, `signal_evaluator.py:70` | start `1963-07-01` | A-share sample starts 2000-07 (Li et al.) or 2000-01 (LSY) |
| `assay/sample.py:143` | 10th pct of NYSE ME | breakpoint universe and cut-off are decisions (LSY: drop bottom 30%) |
| `lab/runner.py:381`, `scripts/experiments/run_subsample.py:161` | SIC 6000-6999 = financials | CSRC section J |
| `assay/subsample.py:22` | NBER recessions | no official Chinese dating; replacement needed |
| `assay/subsample.py:35` | windows 1963-1990, pre/post-2000, post-2010 | needs China-relevant breaks (e.g. split-share reform 2005-07, new accounting standards 2007-01-01) |
| `data/factors.py` | FF5/FF6 (Ken French), q-factors (global-q.org) | China factor models (CH-3/CH-4 from Stambaugh's site; CSMAR FF3/FF5; self-built q) |
| `data/cz_anomalies.py`, `assay/spanning.py` | Chen-Zimmermann 209 predictors | no Chinese equivalent; candidate: Li et al.'s replicated anomalies |
| `data/crsp.py` | Shumway delisting adjustment | A-share delistings are rare; convention needed |

## 6. Things in the paper that the code confirms

- First-pass criterion `d_j * t_FMB > 1.96` (`assay/sample.py: direction_matches`).
- Value-weighted quintiles on breakpoint-universe breakpoints, FF5 L-S alpha at discovery stage
  (`signal_evaluator.py:141`).
- The archive passed back to the proposer contains only formula, declared sign, `fmb_tstat`,
  `ls_alpha`, `ls_talpha`, `ls_sharpe`, `coverage`, `error`
  (`lab/prompting/cross_theme.py: _format_archive_section`), plus the last 12 critic notes and
  diagnostics. No firm-level data reaches the LLM.
