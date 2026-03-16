# 自动化训练项目总蓝图（ChinaMoney + MinerU + Financial Analysis + Soul）

## 1. 文档定位

本文档是本项目的总蓝图与总计划，作用不是记录某一次实现细节，而是作为后续多个 Codex 对话、多个 agent、多个实现阶段共享的总设计基线。

目标是解决两个问题：

1. 后续切换对话后，新的 agent 可以快速理解项目整体目标、边界、当前决策和下一步任务。
2. 庞大工程可以被拆成多个相对独立的 workstream，由不同进程逐步实现，而不至于失去整体一致性。

## 2. 项目愿景

构建一个面向中国债券发行主体的自动化研究生产线，实现：

1. 自动采集完整财报与评级报告。
2. 自动解析 PDF 并定位关键章节，尤其是附注。
3. 自动生成研究分析结果。
4. 自动生成对外交付级 Excel 成品 `Soul`。
5. 自动沉淀内部知识候选，但与对外交付严格解耦。

最终目标不是做一个“能跑一次的脚本集合”，而是形成一个可持续迭代、可批量运维、可审计、可交接的研究自动化系统。

## 3. 核心原则

1. **对外与对内双轨制**：Soul 是对外成品；知识进化文件只服务内部。
2. **附注优先**：债务、受限资金、担保、契约等关键判断必须以下游附注为核心证据。
3. **证据可追溯**：关键字段、关键结论必须回溯到页码、章节、段落或行号。
4. **结构先于美化**：先固化数据契约和模块边界，再追求复杂模板和视觉效果。
5. **模块化设计**：采集、解析、标准化、分析、Excel、知识治理、调度运维应尽量解耦。
6. **面向多 agent 协作**：每个模块都要有清晰输入、输出、边界、状态与交接方式。

## 4. 总体架构

```text
任务定义(issuer-year)
  -> 数据采集层（ChinaMoney）
  -> 文档理解层（MinerU）
  -> 文档标准化层（Normalizer / Locator）
  -> 分析引擎层（Financial Analysis）
  -> 成品导出层（Soul Excel）
  -> 运行治理层（Manifest / QA / Retry）
  -> 知识进化层（Pending -> Review -> Adopt）
```

## 5. 目标产物

### 5.1 对外交付产物

- `analysis_report.md`
- `financial_output.xlsx` 或后续正式命名的 `soul_output.xlsx`

### 5.2 内部运行产物

- `run_manifest.json`
- `chapter_records.jsonl`
- `focus_list.json`
- `final_data.json`
- `soul_export_payload.json`
- `pending_updates.json`

### 5.3 原始与中间数据

- 原始 PDF
- `doc_profile.json`
- `chapter_index.json`
- `notes_workfile.json`

## 6. 模块分层设计

### 6.1 数据采集层

职责：

- 从 ChinaMoney 或其他官方来源检索并下载目标主体的年报、半年报、评级报告。
- 优先下载完整版本，必须尽量覆盖附注。
- 保存下载元数据，保证可回放和可审计。

输入：

- `issuer`
- `year`
- `doc_type`

输出：

- 原始 PDF
- 下载元数据

### 6.2 文档理解层

职责：

- 调用 MinerU 对 PDF 进行解析。
- 输出 Markdown 或结构化文本。
- 为后续定位附注、章节和关键信息提供可读中间层。

输入：

- PDF

输出：

- Markdown
- 原始解析结果

### 6.3 文档标准化层

职责：

- 识别文档类型、主体、期间、币种。
- 定位附注起止范围。
- 生成统一的章节索引和附注工作文件。

输入：

- Markdown
- MinerU 解析结果

输出：

- `doc_profile.json`
- `chapter_index.json`
- `notes_workfile.json`

### 6.4 分析引擎层

职责：

- 基于附注优先原则提取财务与信用关键信息。
- 生成分析报告、焦点主题、章节记录和候选知识。
- 输出 Soul 所需的稳定数据契约。

输入：

- Markdown
- `notes_workfile.json`
- 评级报告文本或结构化内容

输出：

- `analysis_report.md`
- `final_data.json`
- `focus_list.json`
- `chapter_records.jsonl`
- `pending_updates.json`
- Soul 导出数据契约

### 6.5 Soul Excel 导出层

职责：

- 将稳定数据契约转换为对外交付级工作簿。
- 负责版式、公式、批注、颜色系统和多 Sheet 模板。
- 严禁把内部知识进化信息混入对外交付。

当前设计要点：

- Soul 采用“固定骨架 + 可选模块 + 行业专题模块”。
- 当前固定骨架参考 `soul_excel_spec_v1.md`。
- 生成层建议使用已安装的 `spreadsheet` skill 思路推进。

### 6.6 运行治理层

职责：

- 保证一次运行可审计、可失败定位、可重试、可比较。
- 统一记录输入文件、哈希、时间、状态、产物路径。

核心文件：

- `run_manifest.json`

### 6.7 知识进化层

职责：

- 把一次案例里新发现的字段、规则、专题候选沉淀为待审核项。
- 审核后再进入正式知识库。

约束：

- `pending_updates.json` 不得直接影响对外交付结构。
- 知识迭代与 Soul 稳定版本必须解耦。

## 7. Soul 当前设计结论

截至 2026-03-16，Soul 的当前结论是：

1. 不再继续坚持“固定 8 张表”的硬编码思路。
2. 应采用“固定骨架 + 标准可选模块 + 行业专题模块”。
3. 当前最稳定的骨架是：
   - `00_overview`
   - `01_kpi_dashboard`
   - `02_financial_summary`
   - `03_debt_profile`
   - `04_liquidity_and_covenants`
   - `99_evidence_index`
4. 专题模块是后续演进重点，而不是继续膨胀主表。

对应文档：

- `soul_excel_spec_v1.md`
- `soul_excel_case_analysis.md`
- `excel_skill_adoption_plan.md`
- `codex_execution_runbook.md`

## 8. 当前仓库内的事实基线

### 8.1 已有组件

- `run_mineru.py`
- `generate_henglong_report.py`
- `financial-analyzer/scripts/financial_analyzer.py`
- 多个案例 PDF / Markdown / Excel

### 8.2 已确认事实

1. `financial_analyzer.py` 当前生成的 Excel 更偏内部分析产物，不等于最终 Soul 成品。
2. 现有 4 个案例 Excel 可作为结构归纳样本，但尚未达到统一成品标准。
3. 当前案例全部缺少公式层、批注溯源、冻结窗格和标准证据索引。
4. curated `spreadsheet` skill 已安装，可作为 Excel 生成层参考。

### 8.3 当前主要缺口

1. 缺统一任务编排与批处理机制。
2. 缺稳定的 Soul 导出数据契约。
3. 缺案例驱动的模板打样机制。
4. 缺知识审核与采纳流程。
5. 缺跨对话可持续推进的项目状态管理。

## 9. 项目拆解方式（适合多对话、多 agent）

建议将项目拆为 7 个 workstream，每次对话只聚焦 1 个主 workstream，避免上下文污染。

### W1 采集与原始数据治理

目标：

- 下载逻辑、原始文件命名、元数据管理、重复下载判断。

典型任务：

- ChinaMoney 下载器封装
- URL / content_id / hash 记录
- 原始文件目录规范

### W2 MinerU 接入与文档标准化

目标：

- 让 PDF -> Markdown -> 结构化文档的链路稳定。

典型任务：

- MinerU 调用适配
- 章节索引生成
- 附注边界识别

### W3 Financial Analysis 核心引擎

目标：

- 提升附注抽取、主题识别、动态重点和报告生成质量。

典型任务：

- `notes_workfile` 校验
- 章节记录提炼
- 报告生成逻辑

### W4 Soul Excel 生成系统

目标：

- 实现稳定 JSON 契约到对外交付 Excel 的转换。

典型任务：

- Soul 数据契约
- 模板打样
- `spreadsheet` skill 工作流接入

### W5 知识进化与治理

目标：

- 建立 `pending -> review -> adopt` 流程。

典型任务：

- 候选项分类
- 审核标准
- 版本化变更日志

### W6 QA、回归与可运维性

目标：

- 保证批量运行时可定位、可回放、可复核。

典型任务：

- `run_manifest.json` 完整性
- 回归案例目录
- 数据质量校验

### W7 编排、自动化与项目运营

目标：

- 让多个步骤能被系统化串起来执行。

典型任务：

- 任务队列设计
- 失败重试
- 运行状态看板
- 批处理入口

## 10. 每个 workstream 的交接规则

为了支持多个 agent 在不同对话里逐步推进，每个 workstream 必须满足以下约束：

1. 明确输入文件和输出文件。
2. 明确“本模块不负责什么”。
3. 改动尽量局限在对应目录或文档。
4. 结束时更新总蓝图中的“当前状态”和“下一步”。
5. 如果做出结构性决策，必须写入相关规范文档，而不是只留在对话里。

## 11. 推荐的跨对话协作协议

后续新的 Codex 对话开始时，建议默认执行以下顺序：

1. 先阅读：
   - `automation_blueprint.md`
   - 与当前任务直接相关的规范文档
2. 确认当前要处理的是哪一个 workstream。
3. 明确只推进一个主要目标，不在同一对话里同时重构多个层。
4. 完成后：
   - 更新对应规范文档
   - 更新本蓝图中的状态区
   - 写明下一步建议，方便下一个 agent 接手

Git 协作约束：

- 当前项目采用单分支策略，默认只保留 `main`
- 多个 Codex 对话对应多个执行线程，不对应多个长期 Git 分支
- 除非用户明确要求，否则不要为每个线程新建 `codex/*` 分支

## 12. 当前阶段规划

### Phase 0：蓝图与规范收敛

目标：

- 先把总设计、Soul 结构、案例基线和 Excel 技术路线写清楚。

当前状态：

- 已完成。

### Phase 1：单案例稳定跑通

目标：

- 让单个案例能稳定完成下载、解析、分析、导出。

验收：

- 成功生成 `analysis_report.md`
- 成功生成初版 Soul Excel
- 成功生成 `run_manifest.json`

### Phase 2：多案例模板打样

目标：

- 用差异较大的案例检验 Soul 模块化结构。

建议样本：

- 恒隆地产
- 杭海新城控股
- 碧桂园

### Phase 3：导出层正式分离

目标：

- 让 Financial Analysis 不再直接硬编码最终 Excel 结构，而是输出稳定契约，由 Soul 导出层生成成品。

### Phase 4：批处理与治理

目标：

- 支持任务清单批跑、失败重试、质量检查、人工复核。

### Phase 5：知识进化闭环

目标：

- 建立待审核知识池、审核机制和版本化沉淀。

## 13. 当前优先级排序

截至 2026-03-16，建议优先级如下：

1. 固化 Soul 数据契约和导出分层。
2. 选三个差异化案例做 Excel 模板打样。
3. 将 `financial_analyzer.py` 与 Soul 导出层拆开。
4. 建立回归案例目录和运行校验。
5. 再推进批处理和知识治理。

## 14. 当前状态看板

### 已完成

- 总蓝图初版建立
- Soul 从固定 8 Sheet 改为模块化设计
- 4 个历史 Excel 案例完成结构复盘
- `spreadsheet` skill 已调研并安装
- Excel 案例盘点脚本已补充
- Git 已收敛为单分支策略：本地与远程默认只保留 `main`
- `financial_analyzer.py` 已新增 `soul_export_payload.json`，用于承接 Soul 固定骨架与可选模块导出契约
- 已补充碧桂园、杭海新城控股的 `notes_workfile` 测试输入，可复现生成 3 个案例的 Soul 契约样本
- 已新增独立 `soul_exporter.py`，可从 `soul_export_payload.json` 生成 Soul v1.1-alpha 工作簿
- 已完成恒隆地产、碧桂园、杭海新城控股三案例的 Soul v1.1-alpha 样稿与 PDF/PNG 预览产物
- 已验证首轮专题模块：`investment_property`、`restricted_assets`、`lgfv_features`、`external_guarantees`

### 进行中

- Financial Analysis -> Soul 导出层正式拆分

### 待启动

- 将 `financial_analyzer.py` 的最终 Excel 导出切换为独立 Soul exporter
- 批处理与任务编排
- 知识审核与采纳流程

## 15. 与其他文档的关系

- 本文档负责：总目标、总架构、总计划、模块拆分、跨对话协作约定。
- `soul_excel_spec_v1.md` 负责：Soul 的结构规范。
- `soul_excel_case_analysis.md` 负责：基于案例的结构归纳依据。
- `excel_skill_adoption_plan.md` 负责：Excel 生成技术路线与工具选择。
- `financial-analyzer/references/soul_export_contract.md` 负责：Soul 导出 JSON 契约。
- `codex_execution_runbook.md` 负责：如何实际开启和组织多个 Codex 执行线程。

## 16. 后续维护要求

以后凡是出现以下情况，都应同步更新本蓝图：

1. 项目目标发生变化。
2. Soul 结构发生重大调整。
3. workstream 边界发生变化。
4. 当前优先级发生变化。
5. 某个阶段完成，进入下一个阶段。

如果只是局部实现细节变化，则更新对应模块文档，不必污染总蓝图。
