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

## Layout

```
README.md                  this file
docs/                      project documentation (start here)
tests/                     executable checks; run with .venv/bin/python -m pytest tests -q
external/signal-laboratory upstream SignalLab, cloned read-only (own .git, pinned commit in docs)
data/raw/csmar/            CSMAR downloads exactly as delivered (never edited, never committed)
data/interim/              cleaned intermediate tables
data/processed/            analysis-ready panels
.venv/                     Python 3.12 environment (SignalLab installed editable)
```

Code for the CSMAR pipeline and the replications will live in `src/` (not created yet).

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

Rebuild every processed panel from `data/raw/` with `.venv/bin/python -m csmar.build`.

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
