"""Month-by-month checks against the authors' replication package (lighthouse 3.3):

- factors: correlation of each self-built factor with allfactors.sas7bdat (>= 0.95),
  2000-07..2019-06;
- anomalies: correlation of each g5-g1 series with the authors' g5_g1_<period>/<name>_2 file
  (>= 0.90) over that file's period, Mainboard-VW, authors' procedure.

Writes results/li_factor_check.csv and results/li_g5g1_check.csv (aggregates only). Misses
are investigated in docs/deviation_log.md (LI-1 factors, LI-3 anomalies).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from csmar.registry import PROJECT_ROOT
from replication.li import catalog as C

PKG = PROJECT_ROOT / "data/raw/external/li_et_al/replication_package_MS-FIN-21-02398"
FACTOR_COLS = {"mkt": "mkt", "smbff3": "smbff3", "hmlff3": "hmlff3", "smbff5": "smbff5", "hml": "hml",
               "rmw": "rmw", "cma": "cma", "me": "me", "ia": "ia", "roe": "roe", "mom": "mom"}


def _read(path: Path) -> pd.DataFrame:
    import pyreadstat
    d, _ = pyreadstat.read_sas7bdat(path)
    d.index = pd.PeriodIndex(d["trdmnt"], freq="M")
    return d


def factor_check(ours: pd.DataFrame) -> pd.DataFrame:
    af = _read(PKG / "allfactors.sas7bdat")
    rows = []
    for k, c in FACTOR_COLS.items():
        x = pd.concat([ours[k].rename("o"), af[c].rename("a")], axis=1).dropna()
        rows.append({"factor": k, "months": len(x), "corr": x["o"].corr(x["a"]),
                     "mean_ours_pct": x["o"].mean() * 100, "mean_authors_pct": x["a"].mean() * 100,
                     "pass": bool(x["o"].corr(x["a"]) >= 0.95)})
    return pd.DataFrame(rows)


def g5g1_check(quintiles: pd.DataFrame) -> pd.DataFrame:
    names = C.author_names()
    q = quintiles[quintiles["proc"] == "Mainboard-VW"].copy()
    q["month"] = pd.PeriodIndex(q["month"], freq="M")
    rows = []
    for period, start in (("2000_2019", "2000-07"), ("2008_2019", "2008-07")):
        for f in sorted((PKG / f"g5_g1_{period}").glob("*.sas7bdat")):
            stem = f.stem
            if stem.endswith("_lsvw") or not stem.endswith("_2"):
                continue
            author = stem[:-2].lower()
            ours = names.get(author)
            a = _read(f)
            row = {"period": period, "author_name": author, "anomaly": ours, "authors_mean_pct": a["g5_g1"].mean() * 100}
            if ours is None or ours not in set(q["anomaly"]):
                row.update(status="not built")
                rows.append(row)
                continue
            o = q[q["anomaly"] == ours].set_index("month").sort_index()
            o = o[(o.index >= pd.Period(start, "M")) & (o.index <= pd.Period("2019-06", "M"))]
            x = pd.concat([o["g5_g1"].rename("o"), a["g5_g1"].rename("a")], axis=1).dropna()
            r = x["o"].corr(x["a"])
            row.update(months=len(x), corr=r, ours_mean_pct=x["o"].mean() * 100,
                       corr_g1=pd.concat([o["g1"], a["g1"]], axis=1).dropna().corr().iloc[0, 1],
                       corr_g5=pd.concat([o["g5"], a["g5"]], axis=1).dropna().corr().iloc[0, 1],
                       status="pass" if r >= 0.90 else "miss")
            rows.append(row)
    return pd.DataFrame(rows)


def run() -> tuple[pd.DataFrame, pd.DataFrame]:
    from replication.li import anomalies as AN
    from replication.li import tables as T
    fc = factor_check(T.factors())
    gc = g5g1_check(AN.load())
    out = PROJECT_ROOT / "results"
    fc.to_csv(out / "li_factor_check.csv", index=False)
    gc.to_csv(out / "li_g5g1_check.csv", index=False)
    return fc, gc


def table5_on_paper_set(panel: str = "A") -> pd.DataFrame:
    """Diagnostic for deviation_log LI-7: Table 5 statistics computed on the paper's
    significant anomalies (Table 4 list, those we can build) instead of our own significant
    set, to separate the composition effect from the alpha estimates."""
    from replication.li import tables as T
    tg = pd.read_csv(PROJECT_ROOT / "targets" / "li_targets.csv", comment="#")
    names = C.author_names()
    rows = tg[(tg["table"] == "T4") & (tg["col"] == "m") & tg["row"].str.startswith(f"{panel}:")]["row"].str[2:]
    paper_set = {names.get(r) for r in rows} - {None}
    s, e = ("2000-07", "2019-06") if panel == "A" else ("2008-07", "2019-06")
    st = T.anomaly_stats(s, e, "Mainboard-VW", tuple(T.MODELS))
    sig = st[st["anomaly"].isin(paper_set)]
    out = []
    for mdl in T.MODELS:
        for grp in ["All", *C.CATEGORIES]:
            g = sig if grp == "All" else sig[sig["category"] == grp]
            g = g.dropna(subset=[f"alpha_{mdl}"])
            out.append({"model": mdl, "group": grp, "n": len(g),
                        "abs_alpha_hl": g[f"alpha_{mdl}"].abs().mean(),
                        "n_t196": int((g[f"t_{mdl}"].abs() >= T.SHT).sum()),
                        "mean_abs_alpha": g[f"absalpha_{mdl}"].mean(),
                        "n_grs_p05": int((g[f"grs_{mdl}"] < 0.05).sum())})
    return pd.DataFrame(out)
