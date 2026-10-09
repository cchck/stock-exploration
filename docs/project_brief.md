# Project brief

## Goal

Advisor's instruction (received before 2026-10-07):

> Use Claude Code / Codex on CSMAR to replicate some main results of the three papers below,
> then run our AI for signal discovery.

1. Liu, Stambaugh & Yuan (2019, JFE), "Size and value in China".
2. Li, Liu, Liu & Wei (Management Science, forthcoming), "Replicating and digesting anomalies
   in the Chinese A-share market".
3. Allen, Qian, Shan & Zhu (2024, JF), "Dissecting the long-term performance of the Chinese
   stock market".

"Our AI for signal discovery" = SignalLab (Liu, Liu, Liu & Mei 2026, SSRN 6569258), code in
`external/signal-laboratory`.

## Why the order matters

The replications are not a warm-up. Matching published numbers is how we validate the CSMAR
data pipeline (cleaning, market-cap convention, report timing, portfolio construction). The
SignalLab China grader is built on that pipeline; an unvalidated pipeline makes every
AI-discovered signal uninterpretable.

## Phases

| Phase | Content | Status |
|---|---|---|
| 0 | CSMAR access, SignalLab code reading, project skeleton | done 2026-10-07 |
| 1 | CSMAR download + cleaning layer (monthly/daily trading, statements, disclosure dates, ST, risk-free) | done 2026-10-09 (lighthouse milestone 1.1, reviewed; evidence in `data_layer.md`) |
| 2 | Replicate LSY (CH-3/CH-4), check against Stambaugh's published series | |
| 3 | Replicate Li et al. (all 469 anomalies, Mainboard-VW vs All-EW, factor model comparison) | Online Appendix and replication package obtained |
| 4 | Replicate Allen et al. within-A-share results | |
| 5 | SignalLab China adapter (data contract in `signallab_code_notes.md` section 2) | |
| 6 | SignalLab China discovery runs + post-search protocol | needs API budget |

## Decision log

Decisions are recorded with date, who decided, and the reason. Open items are the advisor's
call unless noted.

### Decided

- 2026-10-07 (user): all project material lives in `~/Desktop/stock-exploration`.
- 2026-10-08 (user): project moved to `~/Downloads/stock-exploration`. Reason: the Desktop is
  synced to iCloud, which was uploading the licensed CSMAR data (against the data-stays-local
  rule) and breaking the venv by hiding `.pth` files. Downloads is not iCloud-synced.
- 2026-10-07: each paper is replicated under its own original conventions; no single
  convention is imposed during replication.
- 2026-10-07: raw CSMAR data stays local and out of version control (NYU academic licence).

### Open (needed before phase 5, not before phases 1-4)

1. **Universe and breakpoints for SignalLab China.** LSY: drop bottom 30% (shell value), total
   cap weights. Li et al.: mainboard breakpoints, circulating cap weights, keep small caps.
   Allen et al. find A-share underperformance is concentrated in large caps and small caps did
   well after 2014, which is exactly the segment LSY drops.
2. **ST stocks.** Li et al. drop them; Allen et al. show ST firms are where A-share distress
   lives (few delistings). Dropping them truncates the distress theme.
3. **Sample start.** 2000 (both LSY and Li et al.) vs post-2007 (split-share reform, new
   accounting standards; Li et al. call it cleaner).
4. **Factor-model gate.** Replace FF5/FF6/q with China models (CH-3, CH-4, q per Li et al.).
   Also: which model for the discovery-stage L-S alpha shown to the agent.
5. **Published-predictor library for the spanning gate** (replaces Chen-Zimmermann). Li et
   al.'s anomalies are the natural candidate; requires building firm-month signals.
6. **Variable catalog**: map CSMAR onto Compustat mnemonics vs a China-native catalog; R&D
   capitalization under CAS changes the meaning of `xrd`/`intan`.
7. **Industry definition** for IND_ADJ/IND_ZSCORE/IND_RANK (CSRC 2012 code granularity).
8. **Subsample windows and a recession analogue** for the stability gate.
9. **LLM budget and API keys** for discovery runs (10,080 request slots per six-run design in
   the original paper).

### Known gaps

- Li et al. Online Appendix (variable definitions) not yet obtained.
- CSMAR 股权性质 (SOE flag) not subscribed; rebuild from 上市公司控制人文件 if needed.
- WRDS copy of CSMAR not yet checked.
