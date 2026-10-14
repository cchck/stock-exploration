# CSMAR access (checked 2026-10-07)

## How to get in

- NYU Libraries subscription, through the OpenAthens proxy:
  `https://global-csmar-com.us1.proxy.openathens.net/` (CSMAR global platform).
- The library page also says CSMAR is available via WRDS. Not yet checked whether the WRDS
  copy has the same tables.
- The Chrome profile that is signed in is **"Rami · nyu.edu"**. Agents must never enter
  credentials; if the proxy asks for a login, stop and ask the user.
- Do not click "保存" in the "单表查询个性化设置" pop-up: it changes account settings.

## Permission check

Method: "单表查询" page, display filter "有权限". Each table node in a database's left tree
carries the CSS class `tree-noauth` when not subscribed; this matched the "已购买" /
"无权限" label on every table opened. Five series are subscribed: 股票市场系列, 因子研究系列,
公司研究系列, 银行研究系列, 历史数据.

### Tables needed for the replications

| Need | Database -> table | Access | Coverage seen |
|---|---|---|---|
| Monthly returns, market cap | 股票市场交易 -> 月个股回报率文件 | yes | 1990-12 to 2026-09 |
| Daily trading (turnover, volatility, trading-day filters, limit status) | 股票市场交易 -> 日个股回报率文件 | yes | 1990-12-19 to 2026-09-30, **max 5 years per download** |
| Risk-free rate | 股票市场交易 -> 无风险利率文件 | yes | 1990-04-15 to 2026-09-30 |
| Listing date, industry, board, company info | 股票市场交易 -> 公司文件 | yes | to 2026-09-30 |
| Market returns | 股票市场交易 -> 月/综合月市场回报率文件 | yes | |
| Adjusted prices | 股票市场交易 -> 复权行情 tables | yes | |
| ST / delisting status | 特殊处理与特别转让 -> 特殊处理变动文件, 上市状态变更表 | yes | |
| Suspensions | 停复牌 -> 交易停复牌数据表 | yes | |
| Financial statements (annual + quarterly) | 财务报表 -> 资产负债表, 利润表, 现金流量表 (直接法/间接法), 所有者权益变动表 | yes | |
| Actual report disclosure date | 年、中、季报公布日期 -> 年、中、季报基本情况文件 (field 报告公布日期) | yes | 1990-12-31 to 2026-06-30 |
| CSMAR-built FF factors | Fama-French因子 -> 三因子/五因子 (日/周/月) | yes | |
| Governance (board, duality, executive holdings) | 治理结构 | yes | |
| Ownership concentration, ultimate controller | 股东 -> 十大股东文件, 上市公司控制人文件 | yes | |
| Tunneling proxy (Allen et al.) | 关联交易 -> 关联交易中资金往来情况文件 | yes | |
| Split-share reform | 股权分置改革 (历史数据) | yes | |
| Private firms | 民营上市公司 -> 民企上市公司文件 | yes | |
| **SOE flag used by Li et al.** | 股权性质 -> 中国上市公司股权性质文件 | **no** | |
| Momentum / Carhart factors | 动量因子 | no (compute ourselves) | |

### Fields seen

- 月个股回报率文件: 月开盘/收盘日期与价格, 月个股交易股数/金额, **月个股流通市值**, **月个股总市值**,
  月交易天数, **考虑现金红利再投资的月个股回报率**, 不考虑现金红利再投资的月个股回报率, 市场类型,
  最新股本变动日期, 盘后成交量/额.
- 日个股回报率文件: 开高低收, 交易股数/金额, 流通/总市值, 考虑/不考虑现金红利的日回报率, 可比价格,
  市场类型, 交易状态, 涨跌幅, 涨停价, 跌停价, **涨跌停状态**.
- 无风险利率文件: 无风险利率基准, 统计日期, 无风险利率(%), 日/周/月度化无风险利率(%).
- 年、中、季报基本情况文件: 证券代码, 报告类型, 统计截止日期, **报告公布日期**, 调整前/后净利润,
  每股净资产, 每股收益.

## Implications

- Both market-cap conventions exist (total: LSY weights; circulating: Li et al. weights).
- SOE status can be rebuilt from 上市公司控制人文件 using Allen et al.'s definition (ultimate
  controller is SASAC, the Ministry of Finance, a local SASAC, or another government agency).
  Only needed for SOE splits, not for the main results.
- Data run to 2026, so the replications can be extended past the papers' sample ends.

## Download log

Every download is recorded here. Downloads use the user's licensed account and need the user's
go-ahead (batch 1 approved by the user on 2026-10-07).

Conventions for all rows below unless noted: platform = CSMAR global via NYU proxy; code
setting = 全部代码 (all codes); fields = 全选 (all fields of the table); format = CSV（*.csv）;
file renamed to `<TABLE_CODE>[_chunk]_20261007.zip` and extracted with `ditto -x -k` (zip
entry names are GBK; `unzip` fails on them) into `unzipped/<_chunk or _all>/`. Tables over
1,000,000 rows arrive split into `<CODE>.csv`, `<CODE>1.csv`, `<CODE>2.csv`, ... ;
"rows" sums all parts. "Platform count" is the figure CSMAR showed on the download page.

### Batch 1 (2026-10-07)

| Table (database) | Code | Date filter | Fields | Rows | Platform count | Zip bytes | SHA-256 |
|---|---|---|---|---|---|---|---|
| 年、中、季报基本情况文件 (年、中、季报公布日期) | IAR_Rept | 1990-12-31 – 2026-06-30 (full) | 14 | 309,010 | 309,010 | 9,166,307 | `8bc6e215c64158df0a33d9b6a5e49a2c48c88e0337c61dd98741c60e9fc74087` |
| 无风险利率文件 (股票市场交易) | TRD_Nrrate | 时间不限 | 6 | 13,072 | 13,072 | 251,719 | `cbb319aa7bc9b6b4c8be7cffee1634d185cd8b5f37d6b40b418a0b91fbd81168` |
| 月个股回报率文件 (股票市场交易) | TRD_Mnth | 时间不限 | 17 | 953,894 | 953,894 | 41,672,575 | `ebf600a33e46ddfc742de36321b6b2782bb48c93977e1cf459b0a057e7f8fad2` |
| 公司文件 (股票市场交易) | TRD_Co | 时间不限 | 37 | 6,051 | 6,030 (header) | 685,205 | `b45a5d86d0cc3b76a6655b7f9caf4cf0b7b36161b436cf412eae08fd616b3461` |
| 特殊处理变动文件 (特殊处理与特别转让) | SPT_Trdchg | 时间不限 | 9 | 4,272 | 4,272 | 1,524,998 | `56f212838690477de99cfb2b8a463a85a1cbd553547751ac44e933e1a2f70bdd` |
| 资产负债表 (财务报表) | FS_Combas | 时间不限 | 154 | 702,674 | 702,674 | 155,552,554 | `49b9c26d094b47650f021697993689ee0f5077eff909514ddc1ec11d84a7478a` |
| 利润表 (财务报表) | FS_Comins | 时间不限 | 81 | 704,369 | 704,369 | 90,347,536 | `e8990a059dcb4147688b2aca6d948f2f65ce4a042f989587fe3e50cf373376e0` |
| 日个股回报率文件 (股票市场交易) | TRD_Dalyr_2000_2004 | 2000-01-01 – 2004-12-31 | 24 | 1,494,737 | 1,494,737 | 77,324,737 | `4cc55a07b0a1c670b4fa7527fe148f5e47cf97a885dcf4fde161df8c618b6873` |
| 日个股回报率文件 | TRD_Dalyr_2005_2009 | 2005-01-01 – 2009-12-31 | 24 | 1,790,151 | 1,790,151 | 99,580,030 | `4eb118aa5f494f48d0c61c9c52075d58a599a0ee39b4e3577b36d1420fa6b101` |
| 日个股回报率文件 | TRD_Dalyr_2010_2014 | 2010-01-01 – 2014-12-31 | 24 | 2,764,592 | 2,764,592 | 155,437,826 | `282c2c52682f0ca6af41210426355ea6647ecaaadcb2b2caab85e01acff1fa82` |
| 日个股回报率文件 | TRD_Dalyr_2015_2019 | 2015-01-01 – 2019-12-31 | 24 | 3,769,440 | 3,769,440 | 220,640,275 | `aa17b47ad1fa76725885ccea3b56320f05b983344a77318ddd8a8e54f6f51d3a` |
| 日个股回报率文件 | TRD_Dalyr_2020_2024 | 2020-01-01 – 2024-12-31 | 24 | 5,852,287 | 5,852,287 | 340,147,343 | `12a100ad537b4a1fbc0028df87464ca8ca9bfe0af0d30b355cc0609ca14397e2` |
| 日个股回报率文件 | TRD_Dalyr_2025_2026 | 2025-01-01 – 2026-09-30 | 24 | 2,343,819 | 2,343,819 | 142,471,521 | `eda53e943a1702e1b82f541156f1ffa2b01bd1648ed5e554fcddb38b94705af7` |

Daily chunk boundaries checked: first/last trading dates are 2000-01-04/2004-12-31,
2005-01-04/2009-12-31, 2010-01-04/2014-12-31, 2015-01-05/2019-12-31, 2020-01-02/2024-12-31,
2025-01-02/2026-09-30. Contiguous, no overlap. Daily total 2000-2026: 18,015,026 rows (corrected 2026-10-08; an earlier version of this line said 17,815,026, an addition error).

Notes:
- TRD_Co: the table header on the query page said 6,030 records; the file has 6,051 rows with
  6,051 unique `Stkcd`. We treat the file as authoritative (header count is likely stale).
- The date-filter fields: IAR_Rept filters on 统计截止日期; TRD_Dalyr on 交易日期; the other
  tables were downloaded with no date filter.
- The query page pre-fills the previous download's date range ("填充最近一次下载的时间设置");
  every download's date range was read back from the page before clicking download, and
  re-checked on the download summary page.
- **Restatements (look-ahead risk).** FS_Combas has one row per (Stkcd, Accper, Typrep), no
  duplicates, and 54,585 of 702,674 rows (7.8%) carry `IfCorrect = 1` with a `DeclareDate` for
  the correction (e.g. 000001 FY2008-2010 corrected on 2011-08-18). Because only one version is
  kept, we must establish whether values are as originally reported or as corrected. If
  corrected, using them at the original disclosure date is look-ahead. **Resolved
  2026-10-08:** period-end rows hold the originally reported values; restated comparatives
  appear only in the YYYY-01-01 opening rows. Evidence and handling: `docs/data_layer.md`
  section 2.4.
- **Opening-balance rows.** 149,275 balance-sheet rows have `Accper` = YYYY-01-01. These are
  opening balances (期初数), e.g. restated under the 2007 accounting standards, not a reporting
  period. Cleaning code must separate them from period-end rows.
- Financial statements include all report types (annual, semi-annual, quarterly) and both
  consolidated and parent-company statements (field `Typrep`); filtering happens in code.

### Batches 2 and 3 (2026-10-08)

Same conventions as batch 1 unless noted. "Parsed rows" = rows read by a CSV parser
(pandas, or Python `csv` when a few rows are malformed); `wc -l` over-counts tables whose text
fields contain line breaks, so it is not used for verification here.

| Table (database) | Code / file suffix | Date filter | Fields | Parsed rows | Platform count | Zip bytes | SHA-256 |
|---|---|---|---|---|---|---|---|
| 现金流量表(间接法) (财务报表) | FS_Comscfi | 时间不限 | 35 | 331,220 | 331,220 | 27,887,606 | `f9095e2dbeb42192bc27f7bf875cc70d9c8bc3cbdeca38285cfe2db89ce50200` |
| 现金流量表(直接法) (财务报表) | FS_Comscfd | 时间不限 | 72 | 679,957 | 679,957 | 97,054,055 | `09987a75b7fa58abb98ec8d4a236bba713868e62757d0784c05b2a74b2a7e6bd` |
| 分配文件 (股票市场交易) | TRD_Cptl | 时间不限 | 8 | 72,225 | 72,225 | 992,015 | `e9b4fb8b604e579fef1a0bdf21606c1f36e7bc5b2174b9f46c2cf0b8bc89c097` |
| 股本变动文件 (股票市场交易) | TRD_Capchg | 时间不限 | 21 | 143,696 | 143,696 | 3,185,785 | `5b22041cf9f3e992ce3fc552d2f89f7504e55c05a94251439bae4ca2900dfe10` |
| 上市公司控制人文件 (股东) | HLD_Contrshr | 时间不限 | 15 | **unparseable** | 188,022 | 9,474,033 | `48d9200e5649c6128f07fc844ea969f69f5811bba1a44a225cf0af4c8856a54f` |
| 上市公司控制人文件, text fields dropped | HLD_Contrshr _notext | 时间不限 | 13 (no 备注, 实际控制人背景) | 188,022 | 188,022 | 3,110,340 | `f559de0b3604d7c915329e878f51149fb9ddd8970864b7ec6205458f80077be0` |
| 十大股东文件 (股东) | HLD_Shareholders | 时间不限 | 18 | 2,497,859 | 2,497,859 | 48,900,249 | `c96cc25adb59790500b610192f1974d21ceb34a499164acc71554ed4075af224` |
| 十大股东股权集中文件 (股东) | HLD_CR | 时间不限 | 12 | 248,528 | 248,528 | 7,657,045 | `c91bd65c4d4dbd341292a7b47d251ff2f2e63b75b37ea9af0ee05940ac3e6167` |
| 治理综合信息文件 (治理结构) | CG_Ybasic | 时间不限 | 23 | **unparseable** | 74,458 | 22,517,096 | `854daffecf0b625f8818a115a456c348c5b98e30491210a5db63846c472f4c9d` |
| 治理综合信息文件, text fields dropped | CG_Ybasic _notext | 时间不限 | 21 (no 备注, 独立董事与上市公司工作地点一致性统计) | 74,458 | 74,458 | 2,022,135 | `1428223d07226dddd1cc776bedcc5030fe04730dcb265f62f00e0b5fb0496de0` |
| 高管人数、持股及薪酬情况表 (治理结构) | CG_ManagerShareSalary | 时间不限 | 34 | 148,912 | 148,912 | 5,815,402 | `506c310381594a290692f01d51a44a69c64cb73c548adc53758269c8c7491525` |
| 关联交易中资金往来情况文件 (关联交易) | RPT_Transfer | 时间不限 | 13 | **unparseable** | 1,401,718 | 20,228,775 | `33eb719f396f6a12f6613ed06916e2b22763cd1150fb237952feb6af9fb0e633` |
| 关联交易中资金往来情况文件, text fields dropped | RPT_Transfer _notext | 时间不限 | 10 (no 备注, 资金往来科目性质, 关联关系1; 关联方 is mandatory) | 1,401,718 | 1,401,718 | 17,291,890 | `bb8470e11ab10e9f3022303f23fe55fd266a5679b50b2493b5dd38ddcb1d49fd` |
| 上市状态变更表 (特殊处理与特别转让) | SPT_LTDSTACHG | 时间不限 | 8 (no 变动公告内容) | 761 | 761 | 224,021 | `a6a352b6276f233a5aa0fb7e916029c5046e2462619ff01e8f9d666fc44c650b` |
| 交易停复牌数据表 (停复牌) | TSR_Stkstat | 时间不限 | 10 | 113,721 (1 malformed) | 113,721 | 2,095,899 | `471443bdf7538dcd560eeb4779409326ea3b4c20e50b59ac68a18268903fbe93` |
| 交易信息总表 (并购重组) | STK_MA_TRADINGMAIN_2007_2011 | 首次公告日期 2007-01-01 – 2011-12-31 | 32 (no 交易概述) | 21,072 | 21,072 | 1,280,574 | `4b960c9928c9abca103d0755e1d8fea7eb0521ca3b204460d876a3e8ffdd0a36` |
| 交易信息总表 | STK_MA_TRADINGMAIN_2012_2016 | 2012-01-01 – 2016-12-31 | 32 | 36,235 (2 malformed) | 36,235 | 2,290,285 | `8fcf170b52f7e2b3d5a071d46c85294db44ebb0bebc3272703223044917f4c94` |
| 交易信息总表 | STK_MA_TRADINGMAIN_2017_2021 | 2017-01-01 – 2021-12-31 | 32 | 47,958 (2 malformed) | 47,957 | 3,151,647 | `01bfe9952e8193f5322a915d07de213e646ba2f378ebba93eda2578b8c11b5ce` |
| 交易信息总表 | STK_MA_TRADINGMAIN_2022_2026 | 2022-01-01 – 2026-10-08 | 32 | 41,251 (1 malformed) | 41,251 | 2,866,251 | `9a015ef1e2c11ccddbb49730b84cb2f593d709dfbdc7295799be0c1dd16d6594` |

Notes:
- **Free-text fields break CSMAR's CSV export.** Long text fields (备注, 公告内容, 原文说明)
  contain unescaped quotes and truncated multi-byte characters, so three tables could not be
  parsed at all. The originals are kept (`unzipped/_all`) for the record, and each was
  re-downloaded without those fields (`unzipped/_notext`), which parse cleanly with counts
  matching the platform. Cleaning code must read the `_notext` versions.
- A handful of rows in TSR_Stkstat and STK_MA_TRADINGMAIN have an unescaped quote in a short
  text field (停牌原因, 买方/卖方 names). Python's `csv` module mis-parses them: the 2017-2021
  M&A chunk comes out as 47,958 rows against 47,957 on the platform, which is the "47,958"
  in the table above. The cleaning code instead uses a quote-aware splitter
  (`csmar.readers.read_quote_delimited`, deviation_log D-009). It gives exactly the platform
  count for every chunk, keeps all 21 affected records verbatim (TSR 16, of which 1 breaks a
  standard parser; STK_MA 5), and logs them on every read.
- HLD_Shareholders and HLD_CR start in 2003 (CSMAR coverage), so ownership-concentration
  measures for Allen et al. are unavailable for 2000-2002.
- Reverse-merger identification will use 重组类型编码 in STK_MA_TRADINGMAIN; the code book is
  in the CSMAR manual (to be checked when writing the rule).

### External data (2026-10-08)

All under `data/raw/external/`. Approved by the user in discussion rounds 2-4.

| File | Bytes | SHA-256 |
|---|---|---|
| `external/allen_jf_code/jofi13312-sup-0001-internetappendix.docx` | 334635 | `b11c7159eb61ac402da5938e22c379a735a9db7fa7a9e6ed8c48ae8b198efe64` |
| `external/allen_jf_code/jofi13312-sup-0002-replicationcode.zip` | 183411 | `fbb8bd6501c13354b1c08a2c85b1e21c9879efd92a5b56b3e5ed3a1d56e53320` |
| `external/fred/CHNCPIALLMINMEI.csv` (OECD China CPI index, 2015=100) | 11791 | `d619f4f86bf59edb16f3b2f345fd604b7bb361a32e6d2adc2c065e51008b1376` |
| `external/fred/CPALTT01CNM659N.csv` (OECD China CPI, YoY %) | 7508 | `c73c9d37fdd7aa452954d053ef2d13bf9b5734abc35025e9bf8248d0302b45b3` |
| `external/fred/CPALTT01CNM657N.csv` (OECD China CPI, MoM %) | 12514 | `a7d153425b71adc6065ff6af755a961d2af9519061f293042894f8d492833b19` |
| `external/fred/CHNCPALTT01IXNBM.csv` (OECD China CPI index, alt.) | 10461 | `9533796427fc3524d6d2214c3f5b4188349b11438cf650e50164da4294391a0e` |
| `external/hxz/{mom,vvg,inv,prof,intan,fric}_monthly_2025.zip` (HXZ US anomaly decile portfolios, VW, NYSE breakpoints) | see below | see below |
| `external/hxz/fric_monthly_2025.zip` | 574536 | `23ccdb002f23e8dd3119fbc18fff95d3e3e6b0abc6fd732a2697b250cb70aeb1` |
| `external/hxz/intan_monthly_2025.zip` | 1539418 | `492b1d28f6a850661ae55222f5f1312324443a15e04493fc14a11f75235113b5` |
| `external/hxz/inv_monthly_2025.zip` | 1660818 | `b17242f741c2edf1df12084c6c040adbd2df2fa1012a92a162144cac49af0c82` |
| `external/hxz/mom_monthly_2025.zip` | 2154782 | `05b20fec2cc7c8087d30208dd76e07c82fab506314708b2f3cb154d72ca4ec66` |
| `external/hxz/prof_monthly_2025.zip` | 2453360 | `18dfced977d9412e2e6ec0582646f0c61b596db3a4ac88dbcdd9dae53fef963c` |
| `external/hxz/vvg_monthly_2025.zip` | 1642662 | `d5f7fb88c401195d9b31f0bd8853d6087a47b77ac3642e2fd9217b67ccb6a2ba` |
| `external/hxz/q5_factors_monthly_2025.csv` (US q5 factors) | 37117 | `8b2e2f1364890f8f5876da20e6bfad0acd8d272425de3b65c725f54b51128f6a` |
| `external/hxz/portfoliostd_2026jul.pdf` (HXZ testing-portfolio technical document) | 701404 | `626b6f496c960c963728486703e111257d4430a96ce76ad98ccd1cd4d56c748a` |
| `external/li_et_al/Li_Replicating_Digesting_Anomalies_polyu.pdf` (accepted manuscript of Management Science 70(8):5066-5090, PolyU repository) | 1655382 | `a60746f2d8baa7fcd123ba03aa6ecf88124c6785e62fc1a36734cb2dcaf2562d` |
| `external/li_et_al/mnsc.2023.4904.sm1.pdf` (Online Appendix, 119 pp., Table A1 = variable definitions) | 3879985 | `912928667b75f5fa810e87f253cf1ecec397cdd86a39a7f5800bace7e6f690e1` |
| `external/stambaugh/CH_4_fac_update_20211231.csv` (monthly CH-4) | 9932 | `b12853ce209bc717b42b0eb4778d80e492315c5e25037cb06f4f1f4c7061d14f` |
| `external/stambaugh/CH_4_fac_daily_update_20211231.csv` | 204345 | `3fd8d9b3bf380683c085237efdc44d2c5546730ba1ac96496864e9c653962928` |
| `external/stambaugh/CH_3_fac_daily_update_20211231.csv` (no monthly CH-3 file is published) | 175740 | `0a53339a4f8677d48517abaed0abd9114252a06f9c0e86b5e8f9a8e2f216f1f3` |
| `external/stambaugh/size_value_china_appendix_2_rev.pdf` (LSY appendix) | 251046 | `7e612f3688f809e411888a6550bfebf0383e416e19acaccd38f639cb51c78820` |

Notes:
- Stambaugh series end 2021-12, so the >= 0.95 correlation check covers 2000-01 to 2021-12.
- FRED/OECD China CPI series all end by 2025-04 (CHNCPIALLMINMEI: 1993-01 to 2025-04). The
  NBS site (data.stats.gov.cn) returns HTTP 403 to non-mainland IPs from this machine's default
  network, but loads in the user's Chrome profile "Chenkai" (see NBS rows below).
- Allen et al. JF replication code (SAS) contains analysis scripts only; the input datasets
  (`Asharew21`, `globalw22`, `monthly_ret_china_9018_3`, ...) are not included, so it documents
  conventions but cannot be run. Downloaded by the user (Wiley access works in the user's
  browser, not via the NYU OpenAthens proxy).
- Li et al.: the accepted manuscript replaces the SSRN version as the replication target
  (round 4, Q30). Its abstract figures match SSRN; table-level differences to be checked in
  milestone 1.4. The authors' replication files (services.informs.org) need an INFORMS login and
  were not obtained.

### Later additions (2026-10-08)

| File | Bytes / count | SHA-256 | How obtained |
|---|---|---|---|
| `external/nbs/nbs_cpi_mom_table_2021_2025.csv` | 351 records (13 indicators x 2023-10..2025-12) | `db17b104789887765df5496fdf07c48291e4e9f5b1ef852c1321edca74f6ff28` | NBS 国家数据 → 月度数据 → 价格指数 → 全国居民消费价格分类指数 (上月=100) (2021-2025), view "最近36个月" |
| `external/nbs/nbs_cpi_mom_table_2026.csv` | 104 records (13 indicators x 2026-01..2026-08) | `48b2d936fcd673013b800595b42752b93ec7470799012ff9e92f12be04fd234b` | same tree, (2026-) node |
| `external/li_et_al/replication_package_MS-FIN-21-02398/` | 608 files, 204 MB | per-file hashes in `external/li_et_al/replication_package_SHA256SUMS.txt` | downloaded by the user from INFORMS (account login) |

NBS notes:
- The NBS "下载" button requires a personal login with captcha, which the agent must not do.
  The values were read from the public table rendered on the page (browser profile "Chenkai",
  which reaches data.stats.gov.cn) and saved as CSV (`indicator,month,value`, UTF-8 BOM).
  Column alignment was verified against the on-screen values (2025-12 = 100.2, 2025-11 = 99.9).
- 2026-09 was not yet published on 2026-10-08.
- Splice check against OECD (FRED CHNCPIALLMINMEI): month-on-month changes implied by the
  OECD index match the NBS headline (居民消费价格指数(上月=100)) on the 19 overlapping months
  2023-10..2025-04 within 0.2 index points (both rounded to one decimal).

Li et al. replication package (`replication_package_MS-FIN-21-02398/`):
- SAS code and logs per table (Tables 1, 3, 4&6, 5, 7), the Data Manual PDF, and readme.docx.
- `allfactors.sas7bdat`: the authors' monthly factor series, 2000-07..2019-06 (228 months):
  mkt, me, ia, roe, smbff5, hml, rmw, cma, mktch, smbch3, smbch4, vmg, pmo, smbff3, mom,
  monthlyrf, hmlff3.
- `g5_g1_2000_2019/` (157 files) and `g5_g1_2008_2019/` (122 files): monthly quintile returns
  g1..g5 and g5_g1 for the significant anomalies (`*_lsvw` = Mainboard-VW versions).
- `reg_results_*`, `merge_results_*`: factor-regression outputs.
- No raw CSMAR data (licence), so it cannot be run end to end, but the monthly series allow
  month-by-month comparison with our replication.

### Batch 4 (2026-10-09)

Approved by the user on 2026-10-09 ("下吧，1999年12月的日度数据"), to resolve deviation_log
D-002 (Li Table 1A end-of-1999 sample). Same conventions as batch 1: 全部代码, all 24 fields,
CSV. The date range was read back from the query page (1999-12-01 / 1999-12-31) before
download and confirmed on the download summary page.

| Table | Code / chunk | Date filter | Fields | Rows | Platform count | Zip bytes | SHA-256 |
|---|---|---|---|---|---|---|---|
| 日个股回报率文件 (股票市场交易) | TRD_Dalyr_1999_12 | 1999-12-01 – 1999-12-31 | 24 | 21,194 | 21,194 | 1,382,100 | `179b1d3b4eb038c1adc3177275ec3adc17c66a6237eb854d40fc33d7bbc1ca12` |

The daily table now spans 1999-12-01..2026-09-30 in seven contiguous chunks (the 1999-12
chunk's last trading day is 1999-12-30; 1999-12-31 was a market holiday), 18,036,220 rows
in total.

### Batch 5 (2026-10-09): Allen et al. inputs

Approved by the user on 2026-10-09 (both items: RPT_Operation and the FRED exchange rate).

| Table | Code / chunk | Date filter (统计截止日期) | Fields | Rows | Platform count | Zip bytes | SHA-256 |
|---|---|---|---|---|---|---|---|
| 关联交易情况文件 (关联交易) | RPT_Operation_1997_2008 | 1997-12-31 – 2008-12-31 | 21 of 28 | 190,112 | 190,112 | 3,463,617 | `b5ab81cf9ee3a23d0faef8c0898b31f0600606c24d79a5c7fb813ce40c621794` |
| 关联交易情况文件 | RPT_Operation_2009_2014 | 2009-01-01 – 2014-12-31 | 21 | 346,860 | 346,860 | 6,519,509 | `9bdb29f9e1bd1737696d61a072c9ed65721caa338d3576cfa13b18902cd11537` |
| 关联交易情况文件 | RPT_Operation_2015_2019 | 2015-01-01 – 2019-12-31 | 21 | 622,435 | 622,435 | 10,990,651 | `5de185d7d5fc03e8367bab9b4279f6bb4ef77098030c28f5a205d1648d8281ba` |
| 关联交易情况文件 | RPT_Operation_2020_2026 | 2020-01-01 – 2026-12-31 | 21 | 1,167,342 | 1,167,342 | 20,129,851 | `f68d36755d40eb88033e255d2952e032da0a53caeb946c01ec802d1e3c0537c1` |

- Total 2,326,749 rows = the table's platform total. An all-years request returned
  "请求异常" on the platform, hence the four chunks.
- Dropped free-text fields (they break CSV exports, as with batches 2-3): 关联关系1, 关联交易事项,
  交易涉及的银行, 交易内容, 交易定价原则, 交易事项对公司利润的影响, 备注. 关联方 (party name)
  cannot be deselected on the platform and is kept.
- Codes used: Repat 05 = 资金交易 (funds transactions); Direction 1 = listed firm on the
  providing side, 2 = receiving side; Trasub 1 = transaction between the listed firm and a
  related party.

External: FRED `EXCHUS` (CNY per USD, monthly, 1981-01..2026-09, 550 lines, SHA-256
`f1a7e13b5c01c51b22fb5d4e3beefc756d1d4d83b14a69417af9130ae46e0510`) and `AEXCHUS` (annual,
1981..2025, SHA-256 `31bf7b23b3075842e37ea16d25b4b392e253b2e092f828f1472a4d54e23801ac`),
in `data/raw/external/fred/`, downloaded 2026-10-09 with curl from fredgraph.csv.

Access checks (2026-10-09, no download): 港股市场交易 (incl. AH股比价表) and 外汇市场 show
"无权限" (not subscribed). Allen's AH premium therefore cannot be built (lighthouse 5.2: then
only turnover).

### Batch 6 (2026-10-13): Li et al. analyst inputs

Approved by the user on 2026-10-13 (three tables; the third was not downloaded, see below).
Conventions as above; file names `<CODE>_20261013.zip`.

| Table (database) | Code | Date filter | Fields | Rows | Platform count | Zip bytes | SHA-256 |
|---|---|---|---|---|---|---|---|
| 上市公司基本信息特色指标表 (分析师预测) | AF_CFEATUREPROFILE | 2001-12-31 – 2025-12-31 (会计年度, full) | 10 | 71,922 | 71,922 | 1,507,560 | `8d98865d20abd2e5c359cfdc31571f0514a0122a7c5ce2eb79bd1d8bb674ca59` |
| 分析师预测特色指标 (分析师预测) | AF_ANAFOREFEATURE | 2001-01-01 – 2026-10-13 (报告日期, full) | 16 | 795,246 | 795,246 | 29,520,351 | `11549ff4aee478c5dd549d758f9023a94b2c040809ba63ac6a2800fb8ffeedcf` |

- AF_CFEATUREPROFILE carries AnaAttention / ReportAttention (Li et al. Ana, Rep);
  AF_ANAFOREFEATURE carries RelativeOptimism per analyst report (Li et al. Fop).
- **Not downloaded:** 财务报表附注 -> 研发费用 (approved). Its coverage starts at 2018-12-31,
  the same start as the income-statement R&D line we already hold (FS_Comins B001216000), so
  it adds nothing for 2007-2017.

Access checks (2026-10-13, no download), relevant to Li et al.:
- 无权限: 上市公司研发创新 (研发投入情况表 = RDSpendSum, 专利明细 / 专利申请获得情况),
  已实现指标 (个股买卖价差表(日) = effective / quoted spreads, 个股知情交易概率指标表(日) = VPIN),
  机构投资者 (机构持股明细 / 分类统计), 经营困境.
- 有权限: 分析师预测 (all tables), 财务报表附注, 治理结构, 股东 (incl. 基金持股文件).

External (2026-10-13, approved by the user): FRED `VXOCLS` (CBOE S&P 100 volatility index,
daily, 1986-01-02..2021-09-23, 9,322 lines, SHA-256
`3ab3e522630a6b404fda6cd2d7ef33834139218bf00f5a290aa089361dd334e8`), in
`data/raw/external/fred/`, downloaded with curl from fredgraph.csv. Used for Li et al.'s Svr.
