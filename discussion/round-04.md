> 存档元信息：第 4 轮｜2026-10-08｜解决：CPI 用 FRED/OECD（27a）、用户已下载 Allen 复现代码和互联网附录（28）、批准下载 Li et al. 附录与复现文件（29）、以发表版为准（30）、批准 HXZ 美国数据（31）｜遗留：第 26 题（确认完整复述）未答；CPI 2025-05 以后缺口；Li et al. 复现文件需 INFORMS 登录

# discussion — 第 4 轮（2026-10-08）

> lighthouse 三文件流程，阶段一：对齐到零歧义。本文件始终是最新一轮的完整内容；
> 历史轮次见 `discussion/round-01.md` 至 `round-03.md`。
>
> **完整设计复述在 `discussion/round-03.md` 的"完整设计复述"一节**（第 3 轮答案已全部吸收进去，
> 没有变化）。本轮只有两件事：① 请你确认那份复述无误；② 回答下载过程中暴露的 5 个新问题。
> 两件都完成，阶段一结束，开始写 `lighthouse.md`。

## 已明确（第 3 轮新增）

- 第 24 题：复现范围是**三篇论文正文里的所有表和图**（附录不算），拿不到数据的部分除外。具体清单见 round-03 复述第 3 节。
- 第 25 题：报告是一份中文 Markdown（`report/replication_report_zh.md`），每篇一节、每节一张"我们 vs 论文"对照表 + 偏差原因 + 图 + 延长到 2026 年的结果；notebook 每篇一个，只调用 `src/` 函数，保留运行输出。

## 数据进展（2026-10-08）

- 第二、三批 CSMAR 数据已下载完成（19 个文件），行数全部与网页核对一致，记录在 `docs/csmar_access.md`。
- 发现 CSMAR 的 CSV 导出有缺陷：长文本字段（备注、公告原文）里有未转义的引号和被截断的汉字，导致 3 张表整张无法解析。处理：原文件保留作记录，另外去掉这些文本字段重新下载了一次，新版本解析正常、行数一致。另有 6 行在短文本字段里有引号问题，清洗代码单独处理并记录。
- Stambaugh 官网的 CH-3/CH-4 因子已下载。注意：官网只更新到 **2021 年 12 月**，所以和官网序列逐月对照只能做到 2021 年；另外官网没有 CH-3 月度文件，只有日度，月度由日度复合得到。
- 十大股东和股权集中度数据从 **2003 年**才开始，所以 Allen 治理指数中的股权集中度在 2000–2002 年缺失。

## 待确认

26. **确认完整设计复述。** 请看 `discussion/round-03.md` 的"完整设计复述"一节（共 7 小节），确认无误，或指出要改的地方。

27. **中国 CPI 的来源。** 国家统计局网站（data.stats.gov.cn）对境外 IP 直接返回 403，我拿不到。两个选项：
    - (a) 用美联储 FRED 上的 OECD 中国 CPI 月度序列（数据原始来源就是国家统计局，免费公开）；
    - (b) 你在国内网络环境下从国家统计局网站手动下载，放进 `data/raw/external/`。
    我倾向 (a)，并在报告里注明来源。可以吗？
（a）
28. **Allen 的 JF 复现代码要请你下载。** Wiley 在我这边的浏览器里不认 NYU 的机构权限，NYU 的 OpenAthens 代理对 Wiley 也返回"Access denied"。请你用自己的浏览器（通过 NYU 图书馆登录）打开论文页面 https://onlinelibrary.wiley.com/doi/full/10.1111/jofi.13312 ，在 Supporting Information 里下载 `jofi13312-sup-0002-ReplicationCode.zip`，放进 `~/Desktop/stock-exploration/data/raw/external/allen_jf_code/`。同一处还有 `jofi13312-sup-0001-InternetAppendix.docx`（Allen 的互联网附录，里面有部分稳健性结果），要不要一起下？

29. **Li et al. 的 Online Appendix 找到了。** 这篇已在 Management Science 正式发表（DOI 10.1287/mnsc.2023.4904），INFORMS 网站上有：
    - Online Appendix PDF（`mnsc.2023.4904.sm1.pdf`，含表 A1：469 个变量的定义）；
    - 作者提供的复现文件（replication files）。
    批准我下载这两样吗？（都是期刊官网公开的补充材料。）
（可以）
30. **以哪个版本的 Li et al. 为准？** 我们手上的 PDF 是 SSRN 工作论文版（ssrn-4365416）。正式发表版的数字可能和 SSRN 版不同（审稿过程中常会改样本或方法）。我的提议：**以正式发表版为准**，因为那是同行评审后的最终结果；需要你提供或批准我下载发表版正文（通过 NYU 图书馆可以访问 Management Science）。如果拿不到发表版，就以 SSRN 版为准并注明。可以吗？
（可以）
31. **HXZ 美国异象数据（global-q.org）。** round-03 复述第 3 节里 Li et al. 第 4.2 节"和美国同期比较"需要它。免费公开，批准下载吗？
（可以）
## 已否决
- Li et al. 只做 32 个异象的子集（第 1 轮第 6 题曾同意，第 2 轮第 19 题改为全部 469 个）。
