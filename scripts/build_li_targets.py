"""Build targets/li_targets.csv from the published (accepted) version of Li, Liu, Liu & Wei
(Management Science 70(8), 2024), lighthouse.md section 2 and milestone 1.4.

Sources:
- Tables 1, 2, 3, 5, 7: parsed from `pdftotext -layout references/Li_2023_MS_accepted.pdf`
  (the printed numbers, as published).
- Tables 4 and 6: the printed values are taken from the authors' result files in the
  replication package (Table4&6/Table4.xls, Table6.xls), which carry the same numbers at full
  precision plus the t-statistics behind the printed a/b significance marks. Every value is
  checked against the PDF: the rounded spreadsheet value must appear as printed, in order,
  so a spreadsheet that differed from the publication would stop the build.

Usage: .venv/bin/python scripts/build_li_targets.py <Li_accepted.txt>
Units: percent as printed (returns, alphas, std in % per month; shares in %); counts as is.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "data/raw/external/li_et_al/replication_package_MS-FIN-21-02398"
OUT = ROOT / "targets/li_targets.csv"

FACTORS = ["MKT", "ME", "I/A", "ROE", "SMB-FF5", "HML-FF5", "RMW", "CMA", "MKT-CH", "SMB-CH3", "SMB-CH4", "VMG", "PMO"]
CATS = ["Momentum", "Value-versus-growth", "Investment", "Profitability", "Intangibles", "Trading frictions"]
NUM = r"-?\d[\d,]*\.?\d*"

rows: list[tuple] = []


def add(table, row, col, paper, kind, source):
    rows.append((table, row, col, paper, kind, source))


def nums(line: str) -> list[float]:
    # Significance letters (a/b/c) are glued to numbers in the PDF ("0.81c"); strip them.
    return [float(x.replace(",", "")) for x in re.findall(NUM, re.sub(r"(?<=\d)[abc]\b", "", line))]


def section(text: str, start: str, end: str) -> list[str]:
    i = text.index(start)
    j = text.index(end, i)
    return text[i:j].splitlines()


def table1(text: str) -> None:
    lines = section(text, "Panel A: Overview of the stocks in our sample", "Table 2. ")
    cols = ["n_ashares", "n_sh_main", "n_sz_main", "n_sme", "n_gem", "tmv", "cmv", "sh_tmv", "sh_cmv",
            "sz_tmv", "sz_cmv", "sme_tmv", "sme_cmv", "gem_tmv", "gem_cmv"]
    years = 0
    for ln in lines:
        m = re.match(r"\s*(19\d\d|20\d\d)\s+(.*)", ln)
        if m and int(m.group(1)) <= 2018:
            v = nums(m.group(2))
            assert len(v) == 15, ln
            for c, x in zip(cols, v):
                # Market caps in trillion yuan: continuous levels (rel10); counts: relative 3%.
                add("T1", f"A:{m.group(1)}", c, x, "count" if c.startswith("n_") else "rel10", "Table 1 Panel A")
            years += 1
    assert years == 20
    stats = {"Mean (in %)": ("mean", "pct_return"), "t-stat": ("t", "t"), "Std Dev (in %)": ("std", "pct_std")}
    seen = {}
    for ln in lines:
        for lab, (name, kind) in stats.items():
            if ln.strip().startswith(lab):
                k = seen.get(lab, 0)
                panel = "B" if k == 0 else "C"
                seen[lab] = k + 1
                v = nums(ln.strip()[len(lab):])
                assert len(v) == 13, ln
                for f, x in zip(FACTORS, v):
                    add("T1", f"{panel}:{f}", name, x, kind, f"Table 1 Panel {panel}")
    assert seen == {k: 2 for k in stats}
    # Correlation matrices: lower triangle, Panel D then Panel E.
    corr_rows = []
    for ln in lines:
        s = ln.strip()
        for f in sorted(FACTORS, key=len, reverse=True):
            if re.match(re.escape(f) + r"\s+-?\d", s):
                corr_rows.append((f, nums(s[len(f):])))
                break
    assert len(corr_rows) == 26, len(corr_rows)
    for k, (f, v) in enumerate(corr_rows):
        panel = "D" if k < 13 else "E"
        i = FACTORS.index(f)
        assert len(v) == i + 1, (f, v)
        for j in range(i):  # diagonal (1.00) is not a result
            add("T1", f"{panel}:{f}", FACTORS[j], v[j], "coef", f"Table 1 Panel {panel} (correlation; sign rule)")


def table2_3(text: str) -> None:
    lines = section(text, "Panel A: Average monthly values", "Table 4. ")
    acols = ["n_firms", "pct_tmv", "pct_cmv", "vw_mean", "vw_std", "ew_mean", "ew_std", "xs_std"]
    akinds = ["count", "share_pct", "share_pct", "pct_return", "pct_std", "pct_return", "pct_std", "pct_std"]
    for g in ["Market", "Micro", "Small", "Big", "All-but-micro"]:
        ln = next(x for x in lines if x.strip().startswith(g + " "))
        v = nums(ln.strip()[len(g):])
        assert len(v) == 8, ln
        for c, k, x in zip(acols, akinds, v):
            add("T2", f"A:{g}", c, x, k, "Table 2 Panel A")
    hl = [f"{s}-{c}" for s in ("Low", "High") for c in ("All", "Mom", "VvG", "Inv", "Prof", "Intan", "Fric")]
    hl = hl[:7] + hl[7:]  # printed order: All-Low..Fric-Low, All-High..Fric-High
    procs = ["Mainboard-VW", "Mainboard-EW", "All-VW", "All-EW"]
    blocks = [x for x in lines if x.strip().split(" ")[0] in procs]
    assert len(blocks) == 4 * 3 + 4 * 3, len(blocks)
    t3_cols = [f"{c}:{h}" for c in CATS + ["All categories"] for h in ("SHT", "MHT")]
    for b, ln in enumerate(blocks):
        p = ln.strip().split(" ")[0]
        v = nums(ln.strip()[len(p):])
        assert len(v) == 14, ln
        if b < 12:
            panel = "BCD"[b // 4]
            kind = "share_pct" if panel in "BC" else "rel10"  # D: trillion yuan
            for c, x in zip(hl, v):
                add("T2", f"{panel}:{p}", c, x, kind, f"Table 2 Panel {panel}")
        else:
            panel = "ABC"[(b - 12) // 4]
            for c, x in zip(t3_cols, v):
                add("T3", f"{panel}:{p}", c, x, "share_pct", f"Table 3 Panel {panel}")


def table5(text: str) -> None:
    lines = section(text, "Panel A: The whole sample period (2000/07", "Table 6. ")
    models = ["CAPM", "FF3", "FF5", "q", "CH3", "CH4", "Car4"]
    stats = [("abs_alpha_hl", "pct_return"), ("n_t196", "count"), ("mean_abs_alpha", "pct_return"), ("n_grs_p05", "count")]
    blocks = [ln for ln in lines if ln.strip().split(" ")[0] in models and re.search(r"\d", ln)]
    assert len(blocks) == 28, len(blocks)
    groups = [["All", "Momentum", "Value-versus-growth", "Investment"], ["Profitability", "Intangibles", "Trading frictions"]]
    for b, ln in enumerate(blocks):
        panel = "A" if b < 14 else "B"
        grp = groups[(b % 14) // 7]
        mdl = ln.strip().split(" ")[0]
        v = nums(ln.strip()[len(mdl):])
        assert len(v) == 4 * len(grp), ln
        for gi, g in enumerate(grp):
            for si, (s, k) in enumerate(stats):
                add("T5", f"{panel}:{mdl}", f"{g}:{s}", v[gi * 4 + si], k, f"Table 5 Panel {panel}")


def table7(text: str) -> None:
    lines = section(text, "Panel A: SOEs subsample (SHT", "\f")
    cols = [f"{per}:{m}" for per in ("0407", "0807") for m in ("Raw", "CAPM", "FF3", "FF5", "q", "CH3", "CH4", "Car4")]
    panel = None
    for ln in lines:
        s = ln.strip()
        m = re.match(r"Panel ([ABCD]):", s)
        if m:
            panel = m.group(1)
            continue
        for c in CATS + ["Total"]:
            if s.startswith(c + " "):
                v = nums(s[len(c):])
                assert len(v) == 17, s
                for col, x in zip(cols, v[1:]):
                    add("T7", f"{panel}:{c}", col, x, "count", f"Table 7 Panel {panel}")
    assert sum(r[0] == "T7" for r in rows) == 4 * 7 * 16


def printed_m(text: str, start: str, end: str) -> list[float]:
    # Table 4's "m" rows (the average spreads), in reading order. Other lines carry variable
    # names with digits (Sue1, R[2,5]) and column indices.
    out = []
    for ln in section(text, start, end):
        s = ln.strip()
        if s.startswith("m "):
            out += nums(s[2:])
    return out


def tables4_6(text: str) -> None:
    t4 = pd.read_excel(PKG / "Table4&6/Table4.xls", sheet_name=None, header=None)
    t6 = pd.read_excel(PKG / "Table4&6/Table6.xls", sheet_name=None, header=None)
    for panel, sheet4, sheet6 in (("A", "Table4_PanelA", "Table6_PanelA"), ("B", "Table4_PanelB", "Table6_PanelB")):
        a = t4[sheet4].set_index(0).T.set_index("x")
        b = t6[sheet6].set_index(0)
        b.columns = b.loc["x"]
        b = b.drop(index="x")
        # Table 6's rows come in (alpha, t) pairs; name the t rows after their alpha.
        labels = list(b.index)
        for i, lab in enumerate(labels):
            if lab == "t":
                labels[i] = f"t_{labels[i - 1]}"
        b.index = labels
        names = list(a.index)
        assert names == list(b.columns), f"Table 4/6 panel {panel}: anomaly lists differ"
        start = f"Panel {panel}: Raw return spreads for each significant anomaly"
        end = "Panel B: Raw return spreads" if panel == "A" else "Table 5. "
        pdf_m = printed_m(text, start, end)
        assert len(pdf_m) == len(names), (panel, len(pdf_m), len(names))
        for k, n in enumerate(names):
            m = float(a.loc[n, "g5-g1"]) * 100
            assert round(m, 2) == pdf_m[k], (panel, n, m, pdf_m[k])
            add("T4", f"{panel}:{n.lower()}", "m", round(m, 2), "pct_return", f"Table 4 Panel {panel}")
            add("T4", f"{panel}:{n.lower()}", "t", round(float(a.loc[n, "t"]), 2), "t",
                f"Table 4 Panel {panel} (t from Table4.xls; printed as an a/b mark)")
            for mdl in ("FF5", "Q4", "CH3", "CH4"):
                name = {"Q4": "q"}.get(mdl, mdl)
                add("T6", f"{panel}:{n.lower()}", f"alpha_{name}", round(float(b.loc[mdl, n]) * 100, 2), "pct_return", f"Table 6 Panel {panel}")
                add("T6", f"{panel}:{n.lower()}", f"t_{name}", round(float(b.loc[f"t_{mdl}", n]), 2), "t",
                    f"Table 6 Panel {panel} (t from Table6.xls; printed as an a/b mark)")
                add("T6", f"{panel}:{n.lower()}", f"mean_abs_alpha_{name}", round(float(b.loc[f"{mdl}_absalpha", n]) * 100, 2),
                    "pct_return", f"Table 6 Panel {panel}")
                add("T6", f"{panel}:{n.lower()}", f"grs_p_{name}", round(float(b.loc[f"{mdl}_GRS_p", n]), 2), "pvalue", f"Table 6 Panel {panel}")
        add("T4", f"{panel}:count", "significant", float(len(names)), "count", f"Table 4 Panel {panel}: number of significant anomalies")
    # Spot-check Table 6 against the PDF: the first anomaly's FF5 alpha and mean |alpha| rows.
    t6a = [r for r in rows if r[0] == "T6" and r[1].startswith("A:")]
    assert t6a[0][3] == 1.11 and t6a[2][3] == 0.38, t6a[:3]


TEXT = [
    ("abstract:failure_rate_raw", "pct", 83.37, "share_pct", "Abstract: 83.37% insignificant raw spreads (Mainboard-VW, SHT)"),
    ("abstract:failure_rate_capm", "pct", 84.22, "share_pct", "Abstract: 84.22% insignificant CAPM alphas"),
    ("abstract:failure_rate_ff3", "pct", 86.99, "share_pct", "Abstract: 86.99% insignificant FF3 alphas"),
    ("S1:sig_full_sht", "n", 78, "count", "Introduction: 78 of 469 significant (16.63%), SHT"),
    ("S1:sig_full_mht", "n", 29, "count", "Introduction: 29 (6.18%) under MHT"),
    ("S1:sig_post2007_sht", "n", 61, "count", "Introduction: 61 of 469 (13.01%) post-2007, SHT"),
    ("S1:sig_post2007_mht", "n", 22, "count", "Introduction: 22 (4.69%) post-2007, MHT (the conclusion says 21; 22/469 = 4.69%)"),
    ("S1:explained_full_CH3", "pct", 53.85, "share_pct", "Introduction: CH3 explains 53.85% of significant anomalies"),
    ("S1:explained_full_CH4", "pct", 47.44, "share_pct", "Introduction: CH4 47.44%"),
    ("S1:explained_full_q", "pct", 25.64, "share_pct", "Introduction: q 25.64%"),
    ("S1:explained_post2007_q", "pct", 73.77, "share_pct", "Introduction: q explains 73.77% post-2007"),
    ("S2.1:soe_share_2003", "pct", 74.57, "share_pct", "Section 2.1: SOEs 74.57% of listed firms at the end of 2003"),
    ("S3.3:Roeq1_m", "pct", 0.48, "pct_return", "Section 3.3: Roeq1 earns 0.48% per month, insignificant"),
    ("S3.3:Roeq1_insignificant", "abs_t_below_1.96", 1.96, "upper_bound", "Section 3.3: Roeq1 insignificant (|t| < 1.96)"),
    ("S3.3:Roeq3_m", "pct", 0.37, "pct_return", "Section 3.3: Roeq3 0.37% per month, insignificant"),
    ("S3.3:Roeq3_insignificant", "abs_t_below_1.96", 1.96, "upper_bound", "Section 3.3: Roeq3 insignificant (|t| < 1.96)"),
]


def main(pdf_text: str) -> int:
    text = Path(pdf_text).read_text()
    table1(text)
    table2_3(text)
    tables4_6(text)
    table5(text)
    table7(text)
    for r, c, v, k, s in TEXT:
        add("TXT", r, c, v, k, s)
    df = pd.DataFrame(rows, columns=["table", "row", "col", "paper", "kind", "source"])
    assert not df.duplicated(["table", "row", "col"]).any()
    header = ("# Li, Liu, Liu & Wei (2024, Management Science 70(8)), published (accepted) version, lighthouse 2.\n"
              "# Generated by scripts/build_li_targets.py from references/Li_2023_MS_accepted.pdf (Tables 1-3, 5, 7)\n"
              "# and the authors' Table4.xls / Table6.xls (Tables 4, 6; every value checked against the PDF).\n"
              "# Tables 4 / 6 rows: the authors' variable names in lower case (as their g5_g1 files).\n"
              "# kind -> tolerance rule, see src/replication/common/compare.py.\n")
    OUT.write_text(header + df.to_csv(index=False))
    print(f"{len(df)} targets -> {OUT}")
    print(df.groupby("table").size().to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
