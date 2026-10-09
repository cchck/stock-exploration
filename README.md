# stock-exploration

Research workspace for an NYU faculty-supervised project: replicate three A-share asset
pricing papers on CSMAR data, then port **SignalLab** (LLM-guided hypothesis discovery in
asset pricing) to the Chinese market.

**If you are an agent picking this up, read in this order:**

1. `docs/project_brief.md`: goal, phases, status, decision log (what is decided, what is the
   advisor's call).
2. `docs/csmar_access.md`: how data access works and which CSMAR tables we have.
3. `docs/replication_targets.md`: the published numbers each replication must match.
4. `docs/signallab_code_notes.md`: how SignalLab works, its data contract, and every
   US-specific piece that must change for China.
5. `docs/data_layer.md`: what each processed panel contains, every cleaning decision, and
   the validation evidence. `docs/deviation_log.md`: every number that does not match yet.
6. `lighthouse.md` (frozen target, Chinese) and `benchmark.md` (progress log, Chinese).

## Layout

```
README.md                  this file
docs/                      project documentation (start here)
tests/                     executable checks; run with .venv/bin/python -m pytest tests -q
external/signal-laboratory upstream SignalLab, cloned read-only (own .git, pinned commit in docs)
data/raw/csmar/            CSMAR downloads exactly as delivered (never edited, never committed)
data/interim/              cleaned intermediate tables
data/processed/            analysis-ready panels (firm-level, never committed)
src/csmar/                 data layer: registry, readers, panels, build and validate CLIs
results/data_layer/        aggregate validation tables (committed)
.venv/                     Python 3.12 environment (SignalLab installed editable)
```

Replication code will live in `src/replication/{lsy,allen,li}` (milestones 1.2-1.4).

## Environment

```bash
cd ~/Downloads/stock-exploration
.venv/bin/python -m pytest tests -q
```

The system Python 3.9 on this machine has a broken pandas build and SignalLab requires
Python >= 3.10, so always use `.venv/bin/python`. Recreate the venv with:

```bash
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/pip install -e 'external/signal-laboratory[paper]' -e '.[dev]' python-docx
```

Rebuild every processed panel from `data/raw/` with `.venv/bin/python -m csmar.build`, then
check it with `.venv/bin/python -m csmar.validate` (all checks must print PASS).

**Location matters.** The project lives in `~/Downloads/stock-exploration`, outside iCloud.
It was moved off the Desktop on 2026-10-08 because the Desktop is synced to iCloud, which was
uploading the licensed CSMAR data and also set the macOS "hidden" flag on `.pth` files inside
`.venv` (Python 3.12 skips hidden `.pth` files, so `import csmar` / `import siglab` failed).
Do not move it back into Desktop or Documents.

## Ground rules

- **Data licence.** CSMAR data is licensed to NYU for academic use. Raw or derived firm-level
  data never goes into a public repository or anywhere outside this machine.
- **Credentials.** Agents never type passwords or API keys. CSMAR is reached through the
  signed-in Chrome profile "Rami · nyu.edu"; if a login prompt appears, stop and ask the user.
  Downloads run on the user's licensed account and need the user's go-ahead.
- **Provenance.** Every downloaded file is logged in `docs/csmar_access.md` (date, table,
  fields, date range, file name). Raw files are never modified; all cleaning is code.
- **Conventions are explicit.** Every sample filter, timing rule, and weighting choice is a
  named parameter tied to a paper section, not a buried default. When a choice is open, it is
  listed in the decision log, not silently resolved.
- **Replicate under the original paper's conventions first**, and report deviations with the
  number, the paper's number, and the suspected cause.
- **Do not edit `external/signal-laboratory`.** China-specific code goes in our own `src/` and
  wraps or replaces SignalLab components; the upstream copy stays comparable to the paper.
- Code and documentation are written in English; comments explain why, not what.
