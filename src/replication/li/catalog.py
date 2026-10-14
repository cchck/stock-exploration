"""The 177 base variables of Li et al. (DM Appendix A; paper Table 3 note): 104 sorted once
(annually at June-end, or monthly with a one-month holding period) and 73 sorted monthly
with five holding periods (1, 3, 6, 9, 12 months) = 469 anomaly variables.

Each entry: paper name, category, kind and the builder (module.function) that returns
the signal (stkcd, form, value); `author` is the stem of the authors' quintile series in the
replication package (only the significant anomalies have one), used for month-by-month
checks (lighthouse 3.3). `builder=None` marks a variable whose input is not available (the
reason is in `note`; lighthouse 5.3).

kind: "annual" = sorted at the end of June, held July..June; "monthly" = sorted every
month, five holding periods; "monthly1" = sorted every month, held one month.
"""

from __future__ import annotations

from dataclasses import dataclass

CATEGORIES = ("Momentum", "Value-versus-growth", "Investment", "Profitability", "Intangibles", "Trading frictions")
HOLDS = (1, 3, 6, 9, 12)


@dataclass(frozen=True)
class Var:
    name: str
    category: str
    kind: str
    builder: str | None
    author: str | None = None
    note: str = ""

    @property
    def anomalies(self) -> list[str]:
        """The anomaly variables this base variable contributes (e.g. Sue1..Sue12)."""
        return [f"{self.name}{h}" for h in HOLDS] if self.kind == "monthly" else [self.name]


M, V, I, P, N, F = CATEGORIES

VARS: list[Var] = [
    # A.1 Momentum (9 monthly x 5 = 45)
    Var("Sue", M, "monthly", "acct.sue", "sue_q"),
    Var("Abr", M, "monthly", "acct.abr", "abr_q"),
    Var("R6", M, "monthly", "market.r6"),
    Var("R11", M, "monthly", "market.r11"),
    Var("Rs", M, "monthly", "acct.rs"),
    Var("Tes", M, "monthly", "acct.tes"),
    Var("52w", M, "monthly", "market.w52"),
    Var("ϵ6", M, "monthly", "resid.eps6", "_6_res_mom"),
    Var("ϵ11", M, "monthly", "resid.eps11"),
    # A.2 Value versus growth (13 annual + 11 monthly x 5 = 68)
    Var("Bm", V, "annual", "acct.bm"),
    Var("Bmj", V, "annual", "acct.bmj"),
    Var("Bmq", V, "monthly", "acct.bmq"),
    Var("Dm", V, "annual", "acct.dm"),
    Var("Dmq", V, "monthly", "acct.dmq"),
    Var("Am", V, "annual", "acct.am"),
    Var("Amq", V, "monthly", "acct.amq"),
    Var("Rev", V, "monthly", "market.rev"),
    Var("Ep", V, "annual", "acct.ep"),
    Var("Epq", V, "monthly", "acct.epq", "ep_q"),
    Var("Cp", V, "annual", "acct.cp"),
    Var("Cpq", V, "monthly", "acct.cpq"),
    Var("Sr", V, "annual", "acct.sr", "sr"),
    Var("Sg", V, "annual", "acct.sg"),
    Var("Em", V, "annual", "acct.em"),
    Var("Emq", V, "monthly", "acct.emq"),
    Var("Sp", V, "annual", "acct.sp"),
    Var("Spq", V, "monthly", "acct.spq"),
    Var("Ocp", V, "annual", "acct.ocp"),
    Var("Ocpq", V, "monthly", "acct.ocpq"),
    Var("Ebp", V, "annual", "acct.ebp"),
    Var("Ndp", V, "annual", "acct.ndp", "ndp"),
    Var("Ebpq", V, "monthly", "acct.ebpq"),
    Var("Ndpq", V, "monthly", "acct.ndpq", "ndp_q"),
    # A.3 Investment (31 annual + 1 monthly x 5 = 36)
    Var("Aci", I, "annual", "acct.aci"),
    Var("I/A", I, "annual", "acct.ia", "i_a"),
    Var("Iaq", I, "monthly", "acct.iaq"),
    Var("dPia", I, "annual", "acct.dpia", "dpia"),
    Var("Noa", I, "annual", "acct.noa", "noa"),
    Var("dLno", I, "annual", "acct.dlno", "dlno"),
    Var("Ig", I, "annual", "acct.ig"),
    Var("2Ig", I, "annual", "acct.ig2"),
    Var("3Ig", I, "annual", "acct.ig3"),
    Var("Nsi", I, "annual", "acct.nsi"),
    Var("dIi", I, "annual", "acct.dii"),
    Var("Cei", I, "annual", "acct.cei", "cei"),
    Var("Cdi", I, "annual", "acct.cdi"),
    Var("Ivg", I, "annual", "acct.ivg"),
    Var("Ivc", I, "annual", "acct.ivchg"),
    Var("Oa", I, "annual", "acct.oa"),
    Var("Ta", I, "annual", "acct.ta_accr"),
    Var("dWc", I, "annual", "acct.dwc"),
    Var("dCoa", I, "annual", "acct.dcoa"),
    Var("dCol", I, "annual", "acct.dcol"),
    Var("dNco", I, "annual", "acct.dnco", "dnco"),
    Var("dNca", I, "annual", "acct.dnca", "dnca"),
    Var("dNcl", I, "annual", "acct.dncl"),
    Var("dFin", I, "annual", "acct.dfin", "dfin"),
    Var("dLti", I, "annual", "acct.dlti"),
    Var("dFnl", I, "annual", "acct.dfnl", "dfnl"),
    Var("dBe", I, "annual", "acct.dbe"),
    Var("Dac", I, "annual", "acct.dac"),
    Var("Poa", I, "annual", "acct.poa"),
    Var("Pta", I, "annual", "acct.pta"),
    Var("Pda", I, "annual", "acct.pda"),
    Var("Nxf", I, "annual", "acct.nxf"),
    # A.4 Profitability (19 annual + 15 monthly x 5 = 94)
    Var("Roe", P, "annual", "acct.roe"),
    Var("Roeq", P, "monthly", "acct.roeq"),
    Var("dRoe", P, "monthly", "acct.droe", "droe_q"),
    Var("Roa", P, "annual", "acct.roa"),
    Var("Roaq", P, "monthly", "acct.roaq"),
    Var("dRoa", P, "monthly", "acct.droa", "droa_q"),
    Var("Rna", P, "annual", "acct.rna"),
    Var("Pm", P, "annual", "acct.pm"),
    Var("Ato", P, "annual", "acct.ato"),
    Var("Cto", P, "annual", "acct.cto"),
    Var("Rnaq", P, "monthly", "acct.rnaq"),
    Var("Pmq", P, "monthly", "acct.pmq"),
    Var("Atoq", P, "monthly", "acct.atoq", "ato_q"),
    Var("Ctoq", P, "monthly", "acct.ctoq"),
    Var("Gpa", P, "annual", "acct.gpa"),
    Var("Gla", P, "annual", "acct.gla"),
    Var("Glaq", P, "monthly", "acct.glaq"),
    Var("Ope", P, "annual", "acct.ope"),
    Var("Ole", P, "annual", "acct.ole"),
    Var("Oleq", P, "monthly", "acct.oleq"),
    Var("Opa", P, "annual", "acct.opa"),
    Var("Ola", P, "annual", "acct.ola"),
    Var("Olaq", P, "monthly", "acct.olaq"),
    Var("Cop", P, "annual", "acct.cop"),
    Var("Cla", P, "annual", "acct.cla"),
    Var("Claq", P, "monthly", "acct.claq"),
    Var("Cbe", P, "annual", "acct.cbe"),
    Var("O", P, "annual", "acct.oscore"),
    Var("Z", P, "annual", "acct.zscore"),
    Var("Tbi", P, "annual", "acct.tbi"),
    Var("Tbiq", P, "monthly", "acct.tbiq"),
    Var("Bl", P, "annual", "acct.bl"),
    Var("Blq", P, "monthly", "acct.blq"),
    Var("Sgq", P, "monthly", "acct.sgq"),
    # A.5 Intangibles (38 single + 9 monthly x 5 = 83)
    Var("Adm", N, "annual", "acct.adm", "ad_m"),
    Var("gAd", N, "annual", "acct.gad"),
    Var("Rdm", N, "annual", "acct.rdm", note="R&D expenses: CSMAR RDSpendSum not subscribed; proxy, see deviation_log"),
    Var("Rdmq", N, "monthly", "acct.rdmq", "rdm_q", note="R&D proxy, see Rdm"),
    Var("Rds", N, "annual", "acct.rds", note="R&D proxy, see Rdm"),
    Var("Rdsq", N, "monthly", "acct.rdsq", note="R&D proxy, see Rdm"),
    Var("Ol", N, "annual", "acct.ol"),
    Var("Olq", N, "monthly", "acct.olq"),
    Var("Hn", N, "annual", "acct.hn"),
    Var("Rca", N, "annual", "acct.rca"),
    Var("Fop", N, "annual", "acct.fop"),
    Var("Parc", N, "annual", None, note="patent data (上市公司研发创新) not subscribed"),
    Var("Age", N, "monthly", "market.age"),
    Var("D1", N, "annual", "resid.d1"),
    Var("D2", N, "annual", "resid.d2"),
    Var("D3", N, "annual", "resid.d3"),
    Var("dSi", N, "annual", "acct.dsi"),
    Var("dSa", N, "annual", "acct.dsa"),
    Var("dGs", N, "annual", "acct.dgs"),
    Var("dSs", N, "annual", "acct.dss"),
    Var("Etr", N, "annual", "acct.etr"),
    Var("Lfe", N, "annual", "acct.lfe"),
    Var("Ana", N, "annual", "acct.ana"),
    Var("Rep", N, "annual", "acct.rep"),
    Var("Tan", N, "annual", "acct.tan"),
    Var("Tanq", N, "monthly", "acct.tanq", "tan_q"),
    Var("Kz", N, "annual", "acct.kz"),
    Var("Sa", N, "annual", "acct.sa"),
    Var("Vcf", N, "monthly", "acct.vcf"),
    Var("Cta", N, "monthly", "acct.cta", "cta_q"),
    Var("Gov", N, "annual", "acct.gov", note="institutional holdings (机构投资者) not subscribed: index from the other six inputs"),
    Var("Eper", N, "annual", "acct.eper"),
    Var("Eprd", N, "annual", "acct.eprd"),
    Var("Esm", N, "annual", "acct.esm"),
    Var("Evr", N, "annual", "acct.evr"),
    Var("Etl", N, "annual", "acct.etl"),
    Var("Ecs", N, "annual", "acct.ecs"),
    Var("Ala", N, "annual", "acct.ala"),
    Var("Alm", N, "annual", "acct.alm"),
    Var("Alaq", N, "monthly", "acct.alaq", "ala_q"),
    Var("Almq", N, "monthly", "acct.almq"),
    Var("R1a", N, "monthly1", "market.r1a", "ra_1_1"),
    Var("R1n", N, "monthly1", "market.r1n"),
    Var("R[2,5]a", N, "monthly1", "market.r25a"),
    Var("R[2,5]n", N, "monthly1", "market.r25n", "rn_2_5_1"),
    Var("R[6,10]a", N, "monthly1", "market.r610a"),
    Var("R[6,10]n", N, "monthly1", "market.r610n"),
    # A.6 Trading frictions (3 single + 28 monthly x 5 = 143)
    Var("Me", F, "annual", "market.me_june", "me"),
    Var("Iv", F, "annual", "resid.iv"),
    Var("Ivc", F, "monthly", "resid.ivc", "ivc"),
    Var("Ivff3", F, "monthly", "resid.ivff3", "ivff3"),
    Var("Ivff5", F, "monthly", "resid.ivff5", "ivff5"),
    Var("Ivq", F, "monthly", "resid.ivq", "ivq"),
    Var("Ivch3", F, "monthly", "resid.ivch3", "ivch3"),
    Var("Ivch4", F, "monthly", "resid.ivch4", "ivch4"),
    Var("Tv", F, "monthly", "market.tv"),
    Var("Svr", F, "monthly", "resid.svr", "svr", note="CBOE VXO from FRED (VXOCLS), ends 2021-09"),
    Var("β", F, "monthly", "resid.beta"),
    Var("βD", F, "monthly", "resid.beta_d", "beta_d"),
    Var("Tur", F, "monthly", "market.tur"),
    Var("Cvt", F, "monthly", "market.cvt", "cvt"),
    Var("Rtv", F, "monthly", "market.rtv", "rtv"),
    Var("Cvd", F, "monthly", "market.cvd"),
    Var("Pps", F, "monthly", "market.pps", "pps"),
    Var("Ami", F, "monthly", "market.ami", "amihud"),
    Var("Mdr", F, "monthly", "market.mdr", "mdr"),
    Var("Ts", F, "monthly", "market.ts", "ts"),
    Var("Isc", F, "monthly", "resid.isc", "isc"),
    Var("Isff3", F, "monthly", "resid.isff3", "isff3"),
    Var("Isff5", F, "monthly", "resid.isff5"),
    Var("Isq", F, "monthly", "resid.isq", "isq"),
    Var("Isch3", F, "monthly", "resid.isch3", "isch3"),
    Var("Isch4", F, "monthly", "resid.isch4", "isch4"),
    Var("Srev", F, "monthly1", "market.srev", "shorttermrev_1"),
    Var("Esba", F, "monthly", None, "esba", note="已实现指标 (effective spread) not subscribed"),
    Var("Qsba", F, "monthly", None, "qsba", note="已实现指标 (quoted spread) not subscribed"),
    Var("βPS", F, "monthly", "resid.beta_ps", "psbeta", note="liquidity innovations rebuilt from daily data (CSMAR 股票流动性 not subscribed)"),
    Var("Vpin", F, "monthly", None, "vpin", note="已实现指标 (VPIN) not subscribed"),
]

BY_NAME = {v.name: v for v in VARS}


def check() -> None:
    """The counts printed in the paper (Table 3 note): 45/68/36/94/83/143 = 469."""
    from collections import Counter
    n = Counter()
    for v in VARS:
        n[v.category] += len(v.anomalies)
    expected = dict(zip(CATEGORIES, (45, 68, 36, 94, 83, 143)))
    if dict(n) != expected:
        raise AssertionError(f"category counts {dict(n)} != paper {expected}")
    single = sum(v.kind != "monthly" for v in VARS)
    if (single, len(VARS) - single) != (104, 73):
        raise AssertionError(f"{single} single / {len(VARS) - single} monthly, paper 104 / 73")


def author_names() -> dict[str, str]:
    """Map the authors' variable names (lower case, as in Table4.xls / Table6.xls and the
    g5_g1 files) to our anomaly names (e.g. 'sue_q_1' -> 'Sue1', 'i_a' -> 'I/A')."""
    m = {}
    for v in VARS:
        if not v.author:
            continue
        if v.kind == "monthly":
            for h in HOLDS:
                m[f"{v.author}_{h}".lower()] = f"{v.name}{h}"
        else:
            m[v.author.lower()] = v.name
    return m
