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
2025-01-02/2026-09-30. Contiguous, no overlap. Daily total 2000-2026: 17,815,026 rows.

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
  corrected, using them at the original disclosure date is look-ahead. Open question; check
  CSMAR documentation and whether an "original report" table exists.
- **Opening-balance rows.** 149,275 balance-sheet rows have `Accper` = YYYY-01-01. These are
  opening balances (期初数), e.g. restated under the 2007 accounting standards, not a reporting
  period. Cleaning code must separate them from period-end rows.
- Financial statements include all report types (annual, semi-annual, quarterly) and both
  consolidated and parent-company statements (field `Typrep`); filtering happens in code.
