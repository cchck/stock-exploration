"""Registry of the raw CSMAR tables used in this project.

Every table downloaded from CSMAR is listed here with the folder(s) holding its CSV parts
and the record count the CSMAR platform showed at download time (docs/csmar_access.md).
Readers use the expected count to fail loudly if a file is truncated or misparsed, which is
the only way to notice a partial download after the fact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_CSMAR = PROJECT_ROOT / "data" / "raw" / "csmar"
RAW_EXTERNAL = PROJECT_ROOT / "data" / "raw" / "external"
INTERIM = PROJECT_ROOT / "data" / "interim"
PROCESSED = PROJECT_ROOT / "data" / "processed"


@dataclass(frozen=True)
class RawTable:
    """One CSMAR table as downloaded.

    code: CSMAR physical table name (also the CSV file stem).
    subdirs: folders under data/raw/csmar/<code>/unzipped/ to read and concatenate. Tables
        downloaded in date chunks have one subdir per chunk.
    expected_rows: platform record count per subdir, from the download log.
    row_tolerance: allowed excess of parsed rows over the platform count per subdir. Only
        non-zero where a documented malformed row splits into two (see docs/csmar_access.md).
    tolerant_parse: read with the quote-aware splitter (readers.read_quote_delimited) because a
        few text fields carry unescaped quotes that break standard CSV parsers. CSMAR quotes
        every field, so records split on `"<newline>"` and fields on `","` recover the exact
        platform counts. Only used where needed: on tables whose long text fields contain
        legitimate line breaks inside proper quoting, the standard parser is the right one.
    """

    code: str
    description: str
    subdirs: tuple[str, ...]
    expected_rows: tuple[int, ...]
    row_tolerance: tuple[int, ...] = ()
    tolerant_parse: bool = False
    notes: str = ""

    def __post_init__(self) -> None:
        if len(self.subdirs) != len(self.expected_rows):
            raise ValueError(f"{self.code}: subdirs and expected_rows must align")
        if self.row_tolerance and len(self.row_tolerance) != len(self.subdirs):
            raise ValueError(f"{self.code}: row_tolerance must align with subdirs")

    def tolerance(self, i: int) -> int:
        return self.row_tolerance[i] if self.row_tolerance else 0

    def folder(self, subdir: str) -> Path:
        return RAW_CSMAR / self.code / "unzipped" / subdir


# _1999_12 was added on 2026-10-09 so that the year-end trading status exists for 1999
# (Li et al. Table 1 Panel A starts at the end of 1999; deviation_log D-002).
_DALYR_CHUNKS = ("_1999_12", "_2000_2004", "_2005_2009", "_2010_2014", "_2015_2019", "_2020_2024", "_2025_2026")
_MA_CHUNKS = ("_2007_2011", "_2012_2016", "_2017_2021", "_2022_2026")

TABLES: dict[str, RawTable] = {t.code: t for t in [
    RawTable("TRD_Mnth", "月个股回报率文件", ("_all",), (953_894,)),
    RawTable("TRD_Dalyr", "日个股回报率文件 (1999-12 and 2000-2026, seven chunks)", _DALYR_CHUNKS,
             (21_194, 1_494_737, 1_790_151, 2_764_592, 3_769_440, 5_852_287, 2_343_819)),
    RawTable("TRD_Co", "公司文件", ("_all",), (6_051,),
             notes="Platform header said 6,030; file has 6,051 unique codes (header stale)."),
    RawTable("TRD_Nrrate", "无风险利率文件", ("_all",), (13_072,)),
    RawTable("TRD_Cptl", "分配文件", ("_all",), (72_225,)),
    RawTable("TRD_Capchg", "股本变动文件", ("_all",), (143_696,)),
    RawTable("SPT_Trdchg", "特殊处理变动文件", ("_all",), (4_272,)),
    RawTable("SPT_LTDSTACHG", "上市状态变更表", ("_all",), (761,)),
    RawTable("TSR_Stkstat", "交易停复牌数据表", ("_all",), (113_721,), tolerant_parse=True),
    RawTable("IAR_Rept", "年、中、季报基本情况文件", ("_all",), (309_010,)),
    RawTable("FS_Combas", "资产负债表", ("_all",), (702_674,)),
    RawTable("FS_Comins", "利润表", ("_all",), (704_369,)),
    RawTable("FS_Comscfi", "现金流量表(间接法)", ("_all",), (331_220,)),
    RawTable("FS_Comscfd", "现金流量表(直接法)", ("_all",), (679_957,)),
    RawTable("HLD_Contrshr", "上市公司控制人文件 (free-text fields dropped)", ("_notext",), (188_022,),
             notes="The full-field download (_all) cannot be parsed; never read it."),
    RawTable("HLD_Shareholders", "十大股东文件", ("_all",), (2_497_859,)),
    RawTable("HLD_CR", "十大股东股权集中文件", ("_all",), (248_528,)),
    RawTable("CG_Ybasic", "治理综合信息文件 (free-text fields dropped)", ("_notext",), (74_458,),
             notes="The full-field download (_all) cannot be parsed; never read it."),
    RawTable("CG_ManagerShareSalary", "高管人数、持股及薪酬情况表", ("_all",), (148_912,)),
    RawTable("RPT_Transfer", "关联交易中资金往来情况文件 (free-text fields dropped)", ("_notext",), (1_401_718,),
             notes="The full-field download (_all) cannot be parsed; never read it."),
    RawTable("STK_MA_TRADINGMAIN", "并购重组交易信息总表 (2007-2026, four chunks)", _MA_CHUNKS,
             (21_072, 36_235, 47_957, 41_251), tolerant_parse=True,
             notes="Unescaped quotes in buyer/seller/valuation-method text; the quote-aware "
                   "reader recovers the exact platform counts."),
]}


def get(code: str) -> RawTable:
    try:
        return TABLES[code]
    except KeyError:
        raise KeyError(f"Unknown CSMAR table {code!r}; known: {sorted(TABLES)}") from None
