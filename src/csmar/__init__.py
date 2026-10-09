"""CSMAR data layer for the A-share replications.

Layout (see lighthouse.md section 4):
- registry: one entry per raw CSMAR table, with where its CSV parts live and how many rows
  the CSMAR platform reported, so every read can be checked against the download log.
- readers: turn raw CSVs into typed DataFrames without changing any value.
- panels: build the cleaned panels (stock-month, daily, statements, status) used by the
  replications; every convention there is a named parameter.
"""
