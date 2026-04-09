---
name: financial-analyzer
description: 企业年报附注优先财务分析 skill。用于驱动你先保留最小中间产物，再像人工一样逐章阅读附注，随后由 Skill 在当前 run_dir 内编写一次性临时脚本先生成公式版 Excel 工作底稿，再在其基础上固化最终版，最后写报告并净化知识库。
---

# Financial Analyzer

本 skill 的核心不是“仓库里的固定脚本直接生成最终成品”，而是“模板脚本只产出最小分析材料，你逐章阅读并判断，再由 Skill 在当前 run_dir 内现写一次性临时脚本先生成本案专用的公式版 Excel 工作底稿，再从公式版派生最终版，然后基于底稿写报告并净化知识库”。

## 工作定位

- `financial_analyzer.py` 是通用模板脚本，不是最终分析代理。
- `run_report_series.py` / `run_vanke_longitudinal_study.py` 默认只负责把中间产物跑出来；正式化必须显式执行，不能把 scaffold 自动收口当成最终分析。
- 仓库内固定脚本不得直接生成正式 `financial_output.xlsx`；正式 Excel 必须由 Skill 在当前 `run_dir` 内根据本案材料编写一次性临时脚本生成。
- 只要生成 Excel，就必须先生成保留公式关系的 `financial_output_formula.xlsx`，再由公式版派生最终 `financial_output.xlsx`；不允许跳过公式版直接产出最终版。
- Excel 生成过程是非标准化的：sheet 结构、字段组织和格式收口可因案例而变，但所有结果都必须能回到章节证据与知识库口径。
- 脚本输出默认视为草稿或 scaffold，不能未经完整阅读直接当最终结论。
- 遇到特定案例时，允许在单案工作目录内修改脚本副本或辅助脚本；只有可复用改进才回写通用模板。

## 强制流程

原先流程里的“逐章阅读并形成章节判断”其实是主线核心，这里前移成强制主步骤；其余产物都只能服务这条主线，不能反过来主导分析。

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
6. 先运行模板脚本，只要求生成最小中间产物，不要把它们当成最终成稿。
7. 先完整阅读最小中间产物，至少包括：
   - `run_manifest.json`
   - `notes_workfile.json`
   - `chapter_records.jsonl`
   - 现有 `knowledge_base.json` 和最近的 adoption logs
   补充说明：`analysis_report_scaffold.md`、`final_data_scaffold.json`、`soul_export_payload_scaffold.json` 只在调试或兼容下游时按需阅读。
8. 如果该案例已经存在正式产物，则把正式产物也当作主要阅读对象，优先二次阅读：
  - `financial_output_formula.xlsx`
  - `financial_output.xlsx`
  - `analysis_report.md`
  补充说明：`final_data.json` 和 `soul_export_payload.json` 只在下游真的依赖时才再看。
  这一步不是复跑模板，而是基于既有正式产物做第二轮独立阅读和 synthesis。
9. 这是整个流程中最关键的一步：逐章阅读 `chapter_records` 中的章节原文与结构化要素，边读边写 `chapter_review_ledger.jsonl`，逐章提炼：
    - 章节结论
    - 证据摘录
    - 风险判断
    - 对正式知识库的增量或修正
10. 在完成逐章阅读之后，由 Skill 基于 `chapter_text` / `chapter_text_cleaned`、`chapter_review_ledger.jsonl` 和既有知识库，在当前 `run_dir` 内编写一次性临时生成脚本，先生成保留公式关系的 `financial_output_formula.xlsx`。这个公式版是 workpaper 的计算层，关键派生指标、勾稽关系和汇总逻辑应优先留在这一层完成。
11. 在核对公式版口径、公式关系和展示效果之后，再由 `financial_output_formula.xlsx` 派生最终 `financial_output.xlsx`。
12. 由已完成的 `financial_output.xlsx`、`chapter_review_ledger.jsonl` 和既有知识库，完成正式 `analysis_report.md` 写作。`final_data.json` 和 `soul_export_payload.json` 只有在下游显式需要时才作为兼容产物生成，不属于主线完成标准。
13. 最后才做知识库净化：先和现有知识库比对，再通过 adoption log 写入正式 `knowledge_base.json`。
14. 如果某一步还没读完、没写完、没比对完，就不要进入下一步的正式化。

## 报告写作标准

- 角色定位必须是资深固收/信用分析师，不是摘要器。
- 正式 `analysis_report.md` 必须体现“完整阅读后再写作”的结果，不得只是 scaffold 改写、主题拼接或模板填空。
- 正式 `analysis_report.md` 必须建立在“公式版已核对、最终版已固化”的 `financial_output.xlsx` 工作底稿基础上；先有 workpaper，后有报告。
- 正式报告必须以 `chapter_records.jsonl` 和 `chapter_review_ledger.jsonl` 为主阅读底座；`final_data.json`、`soul_export_payload.json` 只能作为可选兼容索引和交叉校验，不能单独承担写作来源。
- 逐章阅读时优先使用 `chapter_text` / `chapter_text_cleaned`，不要只依赖 `summary`。
- 正式 `financial_output.xlsx` 不是“标准模板实例化结果”，而是本案临时生成脚本从公式版派生出的结果；关键在于证据闭环、公式关系和口径正确，而不是套统一导出器。
- 指标核算必须优先调用知识库中的公式口径，尤其是：
  - 有息债务规模
  - 净债务与净负债率
  - 现金短债比
  - 利息支出含资本化后的融资成本
  - EBITDA、利息保障倍数和经营现金流/债务
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
- 正式 `financial_output.xlsx` 中的金额型汇总值必须先统一到一致口径再落表，默认使用“亿元”作为对外分析口径；原始“元”值只能留在证据层或中间数据层，不得直接进入正式汇总区。
- `99_evidence_index`、`00_overview` 这类正式化概览页必须优先输出标签化摘要、科目名、风险点和必要的最短证据片段，不得用整段章节原文充当摘要。
- 概览页的来源说明要保留关键链路：发现来源、回退下载、MinerU 解析、正式化路径与人工复核，不要压缩成笼统的“已生成”。
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

这一章有必要保留，但只需要保留与主线执行直接相关的最小约束：

- 已安装 skill 在运行时必须绑定项目内 runtime，不得把动态状态写回 skills。
- 正式知识库、adoption log 和批次运行状态都应落在项目 `runtime/` 下，而不是落在 skill 安装目录里。
- 如果需要显式指定 runtime，优先使用 `--runtime-config` 或 `FINANCIAL_ANALYZER_RUNTIME_CONFIG`；其余发现顺序、目录契约和部署细节不在本 skill 展开。
- 运行中不得自发改写 `SKILL.md`、`references/*.md` 或复制正式 `knowledge_base.json` 到 skill 安装目录。

更细的 runtime 绑定规则、目录结构和生产化约束，统一参考 `production_execution_runbook.md` 与 `runtime_external_data_layer_spec.md`。

## 模板脚本最小成功态产物

模板脚本每次成功运行只要求保留主线必需材料：

- `run_manifest.json`
- `notes_workfile.json`
- `chapter_records.jsonl`

以下 scaffold 只在调试、兼容或排障时按需保留，不属于主线完成条件：

- `analysis_report_scaffold.md`
- `focus_list_scaffold.json`
- `final_data_scaffold.json`
- `soul_export_payload_scaffold.json`

这些文件只代表“脚本初稿已生成”，不代表最终分析已完成。

## 主线关键输出

完成逐章复核后，主线只看三项结果：

- `financial_output.xlsx`
- `analysis_report.md`
- 对 `knowledge_base.json` 的优化（通过 adoption log 落地）

其中 Excel 主线的强制中间层为：

- `financial_output_formula.xlsx`

以下只是可选兼容输出，不属于主线完成标准：

- `final_data.json`
- `soul_export_payload.json`
- `financial_output_formula_view.xlsx`
- `financial_output_formula_fit.xlsx`
- `financial_output_fit.xlsx`

## 运行后最小验收清单

模板脚本成功态至少满足以下条件：

1. `run_manifest.json` 中 `status=success`。
2. `run_manifest.json` 中 `script_output_mode=scaffold_only`。
3. `run_manifest.json` 中 `codex_review_required=true`。
4. `notes_workfile.json` 存在且附注边界有效。
5. `chapter_records.jsonl` 每条记录都包含：`chapter_no`、`chapter_title`、`status`、`summary`。

完整复核态至少满足以下条件：

1. `financial_output_formula.xlsx` 已生成，且由当前 `run_dir` 内的一次性临时脚本落表。
2. 正式 `financial_output.xlsx` 已基于公式版派生完成。
3. 正式 `analysis_report.md` 已生成。
4. `chapter_review_ledger.jsonl` 已记录逐章阅读与判断。
5. 若发生知识写入，则 `runtime/knowledge/adoption_logs/` 中存在对应日志。
6. `final_data.json`、`soul_export_payload.json` 只有在下游显式需要时才要求存在。

## 进化原则

- 不再把 `pending_updates.json` 作为知识学习主路径。
- 通用模板脚本只负责提高起点，不负责覆盖所有案例。
- 知识学习由 Codex 按章完成，脚本只提供结构化地基和持久化工具。
- 工作簿正式化本身也是知识学习的一部分：数值单位归一、证据标签化和来源链路保全都应沉淀为稳定规则，而不是只在单个案例脚本里临时处理。
- 主线完成标准始终只有三项：`financial_output.xlsx`、`analysis_report.md`、知识库优化；其他文件默认都是可选兼容层。
- Excel 正式化必须遵循“先公式版、后最终版”：先保留公式关系做核对，再固化纯值最终版，不要反过来从最终版补公式。
- 每次章节级正式写入都应遵循 `knowledge_adoption_delta_contract.md` 的 delta 口径，并保留 adoption log / rollback 线索。
- 某个 case 的临时修补，默认先留在该 case 工作目录；只有复用价值明确时才提升为通用能力。
