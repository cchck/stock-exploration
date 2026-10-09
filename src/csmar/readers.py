"""Read raw CSMAR CSV exports into DataFrames without changing any value.

Design choices (lighthouse.md section 4):
- Raw files are never modified. Readers only parse and type; every cleaning decision lives in
  csmar.panels where it is a named parameter.
- Every read is checked against the record count the CSMAR platform reported at download time
  (csmar.registry). A mismatch raises: a silently truncated download would otherwise bias
  every downstream statistic without any visible symptom.
- Identifier and date-like columns are kept as strings. Stock codes have leading zeros, and
  CSMAR writes partial dates as e.g. "1993-12-00", which a date parser would reject or
  silently coerce; date conversion is done explicitly in the panel layer.
- Parsed tables are cached as parquet under data/interim/raw/. The cache is keyed on the
  source files' sizes and modification times, so replacing a raw file invalidates it.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import pandas as pd

from csmar.registry import INTERIM, RawTable, get

log = logging.getLogger(__name__)

CACHE_DIR = INTERIM / "raw"

# Columns that must never be parsed as numbers: identifiers with leading zeros, categorical
# codes, and CSMAR dates (which may contain "00" placeholders).
STRING_COLUMNS = frozenset({
    "Stkcd", "Trdmnt", "Trddt", "Opndt", "Clsdt", "Capchgdt", "Listdt", "Estbdt", "Favaldt",
    "Ipodt", "Statdt", "Accper", "Annodt", "DeclareDate", "Reptdt", "Annoudt", "Execudt",
    "Indcd", "Nindcd", "Nnindcd", "IndcdZX", "OWNERSHIPTYPECODE", "PROVINCECODE", "CITYCODE",
    "Crcd", "Commnt", "FormerCode", "Typrep", "IfCorrect", "Chgtype", "Chgreas", "Statco",
    "Nrr1", "Reptyp", "Exdistdt", "Regdt", "Shrchgdt", "Shrchgtyp",
})


class RowCountMismatch(RuntimeError):
    """Parsed rows differ from the CSMAR platform count recorded at download time."""


def _csv_parts(folder: Path, code: str) -> list[Path]:
    # Large exports are split into <code>.csv, <code>1.csv, <code>2.csv, ... at 1M rows.
    parts = sorted(folder.glob(f"{code}*.csv"), key=lambda p: (len(p.stem), p.stem))
    if not parts:
        raise FileNotFoundError(f"No CSV parts for {code} in {folder}")
    return parts


def _header(path: Path) -> list[str]:
    with path.open(encoding="utf-8-sig") as fh:
        return [c.strip('"') for c in fh.readline().rstrip("\r\n").split(",")]


def read_quote_delimited(path: Path) -> pd.DataFrame:
    """Parse a CSMAR CSV whose text fields may contain unescaped double quotes.

    CSMAR quotes every field, so a record boundary is `"` + newline + `"` and a field
    boundary is `","`. Splitting on those is immune to stray quotes inside a field, which
    break standard CSV parsers (they then merge or split records). Field contents are kept
    verbatim, including any stray quote or embedded newline.
    """
    text = path.read_text(encoding="utf-8-sig").strip()
    records = re.split(r'"\r?\n"', text)
    if not records or not records[0].startswith('"') or not records[-1].endswith('"'):
        raise ValueError(f"{path} is not fully quoted; quote-aware parsing does not apply")
    records[0] = records[0][1:]
    records[-1] = records[-1][:-1]
    rows = [r.split('","') for r in records]
    header, body = rows[0], rows[1:]
    bad = [i for i, r in enumerate(body) if len(r) != len(header)]
    if bad:
        raise ValueError(
            f"{path}: {len(bad)} records have a field count different from the header "
            f"(first at data row {bad[0]}); quote-aware parsing cannot recover them"
        )
    # Records with a stray quote inside a field are exactly the ones a standard parser would
    # mangle; they are kept as-is here and listed in the log (lighthouse.md 4.1).
    stray = [i for i, r in enumerate(body) if any('"' in f for f in r)]
    for i in stray:
        log.warning("%s: data row %d has an unescaped quote inside a field (kept verbatim): %s",
                    path.name, i, body[i][:2])
    df = pd.DataFrame(body, columns=header).replace({"": None})
    df.attrs["stray_quote_rows"] = stray
    return df


def _read_standard(path: Path, columns: list[str] | None) -> pd.DataFrame:
    header = _header(path)
    usecols = columns if columns is not None else header
    missing = set(usecols) - set(header)
    if missing:
        raise KeyError(f"{path.name}: columns not in file: {sorted(missing)}")
    dtype = {c: "string" for c in usecols if c in STRING_COLUMNS}
    return pd.read_csv(path, usecols=usecols, dtype=dtype, encoding="utf-8-sig", engine="c",
                       low_memory=False)


def _numeric_or_string(df: pd.DataFrame) -> pd.DataFrame:
    """Type a string-only frame (quote-aware path) the same way the standard path would."""
    out = df.copy()
    for c in out.columns:
        if c in STRING_COLUMNS:
            out[c] = out[c].astype("string")
            continue
        converted = pd.to_numeric(out[c], errors="coerce")
        # Only convert columns that are numeric wherever they are non-missing; text columns
        # (names, reasons) stay as strings rather than becoming NaN.
        if converted.notna().sum() == out[c].notna().sum():
            out[c] = converted
        else:
            out[c] = out[c].astype("string")
    return out


def _source_signature(table: RawTable) -> list[list]:
    sig = []
    for sub in table.subdirs:
        for p in _csv_parts(table.folder(sub), table.code):
            st = p.stat()
            sig.append([str(p.relative_to(table.folder(sub).parents[1])), st.st_size, int(st.st_mtime)])
    return sig


def read_raw(code: str, *, columns: list[str] | None = None, use_cache: bool = True) -> pd.DataFrame:
    """Return the full raw table (all parts, all chunks) with row-count verification.

    Adds a `_chunk` column naming the download chunk (subdir) each row came from, so
    overlapping chunks could be detected; the chunk boundaries themselves are documented in
    docs/csmar_access.md.
    """
    table = get(code)
    cache_file = CACHE_DIR / f"{code}.parquet"
    meta_file = CACHE_DIR / f"{code}.json"
    signature = _source_signature(table)

    if use_cache and cache_file.exists() and meta_file.exists():
        meta = json.loads(meta_file.read_text())
        if meta.get("signature") == signature:
            # Repaired records are re-announced on every read, not only on the first parse,
            # so a cache hit never hides them (lighthouse.md 4.1).
            for rec in meta.get("stray_quote_rows", []):
                log.warning("%s: %s data row %d has an unescaped quote inside a field (kept verbatim): %s",
                            code, rec["file"], rec["row"], rec["head"])
            df = pd.read_parquet(cache_file, columns=None if columns is None else [*columns, "_chunk"])
            return df

    frames = []
    stray_records: list[dict] = []
    for i, sub in enumerate(table.subdirs):
        parts = _csv_parts(table.folder(sub), code)
        if table.tolerant_parse:
            parsed = []
            for part in parts:
                raw = read_quote_delimited(part)
                stray_records += [{"file": f"{sub}/{part.name}", "row": r, "head": list(raw.iloc[r, :2])}
                                  for r in raw.attrs["stray_quote_rows"]]
                parsed.append(_numeric_or_string(raw))
            chunk = pd.concat(parsed, ignore_index=True)
        else:
            # Read every column into the cache so later column subsets never trigger a reread.
            chunk = pd.concat([_read_standard(p, None) for p in parts], ignore_index=True)
        expected, tol = table.expected_rows[i], table.tolerance(i)
        if not (expected <= len(chunk) <= expected + tol):
            raise RowCountMismatch(
                f"{code}{sub}: parsed {len(chunk):,} rows, CSMAR platform reported {expected:,}"
                + (f" (+{tol} allowed)" if tol else "")
            )
        chunk["_chunk"] = sub
        frames.append(chunk)
    df = pd.concat(frames, ignore_index=True)
    # A column can be inferred as numeric in one CSV part and as text in another (e.g. an ID
    # that is all digits in one part). Unify such columns as strings rather than coercing:
    # coercion would turn the text values into NaN without any trace.
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].astype("string")
    if "Stkcd" in df.columns:
        df["Stkcd"] = df["Stkcd"].astype("string").str.zfill(6)

    if use_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        df.to_parquet(cache_file, index=False)
        meta_file.write_text(json.dumps({"signature": signature, "rows": len(df),
                                         "stray_quote_rows": stray_records}, ensure_ascii=False))
    return df if columns is None else df[[*columns, "_chunk"]]
