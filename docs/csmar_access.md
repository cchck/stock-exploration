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

No data downloaded yet. Record every download here: date, table, fields, date range, file
name under `data/raw/csmar/`. Downloads use the user's licensed account and need the user's
go-ahead.
