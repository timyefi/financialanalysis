---
name: financial-analyzer
description: 企业年报附注优先财务分析 skill。用于让 Codex 先保留中间产物，再像人工一样先做标准化 Excel 工作底稿、逐章阅读附注、写报告，最后做知识库净化。
---

# Financial Analyzer

本 skill 的核心不是“脚本自己完成分析”，而是“脚本先做通用模板抽取并保留中间产物，Codex 再按工作流像人工分析师一样逐章阅读、记录、写作和收口”。

## 工作定位

- `financial_analyzer.py` 是通用模板脚本，不是最终分析代理。
- `run_report_series.py` / `run_vanke_longitudinal_study.py` 默认只负责把中间产物跑出来；正式化必须显式执行，不能把 scaffold 自动收口当成最终分析。
- `finalize_scaffold_run.py` 和 `soul_exporter.py` 都是收口工具，不是分析本体。
- Codex 是实际执行分析与知识学习的主体。
- 脚本输出默认视为草稿或 scaffold，不能未经完整阅读直接当最终结论。
- 遇到特定案例时，允许在单案工作目录内修改脚本副本或辅助脚本；只有可复用改进才回写通用模板。

## 强制流程

1. 先识别报告类型、公司名、报告期、币种、审计意见。
2. 不直接进入全文分析，必须先定位财报附注。
3. 通过关键词搜索找附注候选：
   - `财务报表附注`
   - `合并财务报表项目注释`
   - `Notes to the Financial Statements`
4. 对命中点前后做抽样阅读，确认已经进入正式附注区间。
5. 在已确认的附注区间内建立主附注目录。
   - 只记录主附注，如 `1`、`10`、`17`、`18`
   - `(a)(b)` 等子附注并入父附注，不单独成章
6. 先运行模板脚本，生成 `run_manifest.json`、`chapter_records.jsonl` 和各类 scaffold，但不要把它们当成最终成稿。
7. Codex 先完整阅读中间产物，至少包括：
   - `run_manifest.json`
   - `notes_workfile.json`
   - `chapter_records.jsonl`
   - `analysis_report_scaffold.md`
   - `final_data_scaffold.json`
   - `soul_export_payload_scaffold.json`
   - 现有 `knowledge_base.json` 和最近的 adoption logs
8. 如果该案例已经存在正式产物，则把正式产物也当作主要阅读对象，按以下顺序二次阅读：
   - `financial_output.xlsx`
   - `analysis_report.md`
   - `final_data.json`
   - `soul_export_payload.json`
   这一步不是复跑模板，而是基于既有正式产物做第二轮独立阅读和 synthesis。
9. Codex 逐章阅读 `chapter_records` 中的章节原文与结构化要素，边读边写 `chapter_review_ledger.jsonl`，逐章提炼：
    - 章节结论
    - 证据摘录
    - 风险判断
    - 对正式知识库的增量或修正
10. 在完成逐章阅读之后，基于 `chapter_text` / `chapter_text_cleaned`、`chapter_review_ledger.jsonl` 和既有知识库，由 Codex 自己完成指标口径核对、数值整理与正式 `financial_output.xlsx` 工作底稿。这个 Excel 是客户可展示的第一层正式底稿，所有派生指标都要能回到章节证据和知识库口径。不要让模板脚本替代这一步。
11. 由已完成的标准化 `financial_output.xlsx`、`chapter_review_ledger.jsonl` 和既有知识库，完成正式 `analysis_report.md` 写作，再据此整理 `final_data.json` 和 `soul_export_payload.json`。不要让模板脚本替代这一步。
12. 最后才做知识库净化：先和现有知识库比对，再通过 adoption log 写入正式 `knowledge_base.json`。
13. 如果某一步还没读完、没写完、没比对完，就不要进入下一步的正式化。

## 复跑不变式

- 同一案例每次复跑都必须保持相同顺序：先脚本抽取并保留中间产物，再完整阅读中间产物，再读取正式 `financial_output.xlsx`，最后写正式 `analysis_report.md`、`final_data.json`、`soul_export_payload.json`。
- 如果正式产物已经存在，复跑时仍要先读 `financial_output.xlsx`，不能直接把 `analysis_report_scaffold.md` 作为写作底稿。
- 正式报告的事实来源只认同一运行目录内的 `financial_output.xlsx`、`chapter_records.jsonl` 和 `chapter_review_ledger.jsonl`；任何跨目录拷贝、缓存副本或脚本内联文本都不能替代这三类底座。
- 任何后续优化只允许改变模板脚本的初稿质量或工作簿内容，不允许改变“先读后写、先 workpaper 后报告”的执行顺序。

## 附注表格处理约束

- 附注中的原始表格不得通过脚本批量展开后一次性灌入工作簿。
- 每个表都必须先被单独识别，再单独审阅，再单独用 SQL 驱动抽取。
- SQL 只允许服务于单表的逐项分析与核对，不允许把章节表格处理封装成批量循环后直接落盘。
- 若同一章节含多个表，必须按表序逐个处理并记录差异，不得跳过中间表。
- 导出层只能消费已经逐表确认过的数据结果，不能直接消费“全章节批量解析结果”。

## Excel 单位与格式校验

- 生成 `financial_output.xlsx` 时，必须按“单位驱动格式”检查数值列：
  - `亿元`、`元`、`倍`、`年内` 一类口径默认按数值格式展示
  - `%` 才能使用百分数格式
  - `x`、`倍`、`亿元/x` 一类比率口径按倍数格式展示
- 每次重跑或正式化后，至少抽查 KPI Dashboard、Financial Summary、Debt Profile、Liquidity and Covenants 的关键行，确认单位标签和单元格格式一致
- 如果 Excel 里出现“单位是亿元但格式显示成百分数”的情况，视为导出层缺陷，必须回到脚本修正，不得用手工改表替代

## 报告写作标准

- 角色定位必须是资深固收/信用分析师，不是摘要器。
- 正式 `analysis_report.md` 必须体现“完整阅读后再写作”的结果，不得只是 scaffold 改写、主题拼接或模板填空。
- 正式 `analysis_report.md` 必须建立在标准化 `financial_output.xlsx` 工作底稿已经完成的前提上；先有 workpaper，后有报告。
- 正式报告必须以 `chapter_records.jsonl` 和 `chapter_review_ledger.jsonl` 为主阅读底座；`final_data.json`、`soul_export_payload.json` 只能作为摘要索引和交叉校验，不能单独承担写作来源。
- 逐章阅读时优先使用 `chapter_text` / `chapter_text_cleaned`，不要只依赖 `summary`。
- 指标核算必须优先调用知识库中的公式口径，尤其是：
  - 有息债务规模
  - 净债务与净负债率
  - 现金短债比
  - 利息支出含资本化后的融资成本
  - EBITDA、利息保障倍数和经营现金流/债务
- 债务分析页应同时给出“有息债务规模”和“年化融资成本率”
  - 融资成本分子优先使用财务费用附注中的贷款、债券及应付款项利息支出 + 租赁负债利息支出 - 资本化利息
  - 若仅有半年报期末债务余额，可用半年融资成本折年近似，但必须在表内注明是近似口径
- 如果 `evidence_index` 过于稀疏，说明中间产物还不够支撑客户级研报，必须回到章节级信息挖掘补强。
- 报告结构优先采用“总览 + 附注科目拆解 + 结论”骨架：
  1. 基本信息
  2. 结论先行
  3. 重大风险发现
  4. 按附注科目逐章分析
  5. 关键计算表与派生判断
  6. 学习点 / 信用判断 / 最终结论
- 逐章分析优先按财报科目和附注编号组织，尽量使用客户熟悉的章节名，而不是只用抽象主题词。
  - 优先章节示例：货币资金、受限资金、应收账款、其他应收款、存货、长期股权投资、短期借款、长期借款、应付债券、租赁负债、财务费用、资产减值、信用减值、担保、或有事项、现金流量表补充资料、外汇风险、税费
  - 必要时可以在科目章节上方加跨章节主题小结，但不能用主题小结替代科目拆解
- 每个核心判断都要同时给出：
  - 原文证据
  - 数字或计算
  - 信用含义
  - 学习点
- 报告正文中应显式写出关键派生指标的计算过程，不要只给结论值。
- 报告写法要像研究员手稿再提纯后的正式稿：
  - 允许较长段落
  - 允许表格
  - 允许派生比率和横向对比
  - 允许明确下判断
  - 不允许空泛套话
  - 不允许只有结论没有过程
- 对于数值密集、风险显著或需要深度阅读的案例，风格参考 `cases/碧桂园2024年年报分析.md` 与 `cases/中海地产2024年年报分析.md`：
  - 先给出风险结论
  - 再用表格和附注证据支撑
  - 再写信用含义与学习点
  - 结论要透明可追溯，读者能顺着证据回到原文
- 如果某项证据缺失，必须明确写“未抽取到/未识别”，不得补写或猜测。

## 正文边界

- 正文只用于元信息识别和附注定位。
- 正文不得直接进入 `chapter_records.jsonl`。
- 正文不得直接充当最终结论证据。
- 找不到可信附注区间时直接失败，不降级全文分析。

## 运行入口

模板脚本入口：

- `scripts/financial_analyzer.py`

批处理入口：

- `scripts/run_batch_pipeline.py`

知识写入/运维入口：

- `scripts/write_knowledge_adoption.py`
- `scripts/rollback_knowledge_adoption.py`
- `scripts/show_knowledge_adoption.py`

## 运行态 Runtime 绑定

已安装 skill 在生产态必须绑定项目内 runtime，而不是把动态状态写回 `~/.codex/skills`。

### `runtime_config` 发现顺序

1. CLI 参数 `--runtime-config`
2. 环境变量 `FINANCIAL_ANALYZER_RUNTIME_CONFIG`
3. 从当前工作目录向上逐级搜索 `runtime/runtime_config.json`

### 哪些内容必须走外部 runtime

- `runtime/runtime_config.json`
- `runtime/knowledge/knowledge_base.json`
- `runtime/knowledge/adoption_logs/`
- `runtime/state/registry/processed_reports/processed_reports.json`
- `runtime/state/batches/`
- `runtime/state/logs/`
- `runtime/state/tmp/`

### 明确禁止

以下内容不得写入 `~/.codex/skills`：

- 任意 `runtime_config`
- 任意正式 `knowledge_base` 副本
- 任意 registry / batches / logs / tmp 运行态目录
- 运行中对 `SKILL.md`、`references/*.md` 的自发改写

## 模板脚本成功态产物

模板脚本每次成功运行必须至少生成：

- `run_manifest.json`
- `chapter_records.jsonl`
- `analysis_report_scaffold.md`
- `focus_list_scaffold.json`
- `final_data_scaffold.json`
- `soul_export_payload_scaffold.json`

这些文件只代表“脚本初稿已生成”，不代表最终分析已完成。

## 最终交付产物

完成 Codex 逐章复核后，单案运行目录的正式交付产物为：

- `financial_output.xlsx`
- `analysis_report.md`
- `final_data.json`
- `soul_export_payload.json`

## 运行后最小验收清单

模板脚本成功态至少满足以下条件：

1. `run_manifest.json` 中 `status=success`。
2. `run_manifest.json` 中 `script_output_mode=scaffold_only`。
3. `run_manifest.json` 中 `codex_review_required=true`。
4. `chapter_records.jsonl` 每条记录都包含：`chapter_no`、`chapter_title`、`status`、`summary`。
5. scaffold 文件均存在且非空。

Codex 完整复核态至少满足以下条件：

1. 正式 `analysis_report.md` 已生成。
2. 正式 `final_data.json` 已生成。
3. 正式 `soul_export_payload.json` 已生成。
4. 正式 `financial_output.xlsx` 已生成。
5. `chapter_review_ledger.jsonl` 已记录逐章阅读与判断。
6. 若发生知识写入，则 `runtime/knowledge/adoption_logs/` 中存在对应日志。
8. 已完成 Excel 单位校验抽查，关键数值列未出现单位错配。

## 进化原则

- 不再把 `pending_updates.json` 作为知识学习主路径。
- 通用模板脚本只负责提高起点，不负责覆盖所有案例。
- 知识学习由 Codex 按章完成，脚本只提供结构化地基和持久化工具。
- 每次章节级正式写入都应遵循 `knowledge_adoption_delta_contract.md` 的 delta 口径，并保留 adoption log / rollback 线索。
- 某个 case 的临时修补，默认先留在该 case 工作目录；只有复用价值明确时才提升为通用能力。
