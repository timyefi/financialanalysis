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
3. 在 Skill 驱动下生成研究分析结果。
4. 自动生成对外交付级 Excel 工作底稿 `Soul`，并在底稿基础上形成正式报告。
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
  -> 分析引擎层（Skill 驱动的 Financial Analysis）
  -> 成品导出层（Soul Excel）
  -> 运行治理层（Manifest / QA / Retry）
  -> 知识进化层（Scaffold -> Codex Review -> Direct Adopt）
```

## 5. 目标产物

### 5.1 对外交付产物

- `financial_output.xlsx`
- `analysis_report.md`

### 5.2 内部运行产物

- `run_manifest.json`
- `chapter_records.jsonl`
- `focus_list.json`
- `final_data.json`
- `soul_export_payload.json`
- `analysis_report_scaffold.md`
- `focus_list_scaffold.json`
- `final_data_scaffold.json`
- `soul_export_payload_scaffold.json`
- `runtime/knowledge/adoption_logs/`

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
- 先让 Codex 完整阅读中间产物，再生成分析报告、焦点主题、章节记录和候选知识。
- 输出 Soul 所需的稳定数据契约。

输入：

- Markdown
- `notes_workfile.json`
- 评级报告文本或结构化内容

输出：

- `financial_output.xlsx`
- `analysis_report.md`
- `final_data.json`
- `focus_list.json`
- `chapter_records.jsonl`
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

- 把一次案例里新发现的字段、规则、专题候选经 Codex 逐章阅读、写作、比对后沉淀为正式知识库。
- 通过 adoption log 和 rollback 工具维持可审计、可回滚。

约束：

- scaffold 只能作为 Codex 复核起点，不能直接视为最终知识。
- adoption log 缺失的写入视为非法实现。
- 知识迭代与 Soul 稳定版本必须解耦。

## 7. Soul 当前设计结论

截至 2026-03-16，Soul 的当前结论是：

1. 不再继续坚持“固定 8 张表”的硬编码思路。
2. 应采用“固定骨架 + 标准可选模块 + 行业专题模块”。
3. 当前最稳定的骨架是：
   - `00_overview`
   - `01_input_ledger`
   - `02_calculations`
   - `03_debt_profile`
   - `04_liquidity_and_covenants`
   - `05_operating_profile`
   - `06_risk_matrix`
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

1. `financial_analyzer.py` 当前仍以 scaffold-only 为默认输出，正式 Excel 工作底稿和正式报告需要在 Codex 完整阅读中间产物后显式收口。
2. 历史 `test_runs` 目录仍混有旧内部分析 workbook、旧路径口径和分层改造前样本，不能直接等同于当前 W6 回归基线。
3. 现有历史 Excel 与 3 个固定案例可继续作为结构归纳和回归样本，但需要区分“历史样本”和“当前主线重跑产物”。
4. curated `spreadsheet` skill 已安装，可作为 Excel 生成层参考。

### 8.3 当前主要缺口

1. 缺统一任务编排与批处理机制。
2. 历史 `test_runs` 目录存在旧产物和旧路径遗留，缺统一的回归基线口径。
3. 缺更细粒度的 QA：视觉预览检查、内容级 golden diff、失败路径回归尚未纳入最小基线。
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

- 建立 `scaffold -> Codex review -> direct adopt` 流程。

典型任务：

- adoption delta 规范
- 审计日志
- 回滚与摘要工具

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

Subagents 协作约束：

- `subagents` 适合做边界清晰、可并行汇总的子任务，不适合多人同时改同一个主入口脚本或同一个最终规范文档
- 主线程负责最终决策、核心入口整合和蓝图更新
- 当前阶段优先把 `subagents` 用在 W6.1 的失败路径回归、预览检查和 golden diff 设计，以及 W5 的跨案例候选项归纳
- W7 可以用 `subagents` 做方案探索，但不建议把同一个批处理入口拆给多个子线程同时实现

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

- 成功生成标准化 `financial_output.xlsx`
- 成功生成 `analysis_report.md`
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

### Phase 6：生产化与正式投入使用

目标：

- 把项目从“已能跑通”推进到“已具备正式投入使用所需的 runtime、registry、冷启动仿真和上线门禁”。

### Phase 7：复核与直写控制面

目标：

- 把 scaffold-only 之后的章节复核、knowledge adopt、回滚与正式成稿收敛成可持续执行的控制面。

## 13. 当前优先级排序

截至 2026-03-18，在 W1-W7 主线和 P1-P6 基础设施已基本落地后，R1、R2、R3 与 P6 已完成收口，当前优先级如下：

1. 维护 [go_live_checklist.md](/Users/yetim/project/financialanalysis/go_live_checklist.md) 与其交叉引用，按实际运行反馈微调门禁。
2. 后续若出现新的风险模式或运行口径变化，优先回写到 go-live 门禁和 runtime 治理文档，而不是另起一套上线标准。
3. 远端协作层将按 P0 / P1 / P2 / P3 四档拆分 GitHub Projects，其中 P0 对应阻塞与上线门禁，P1 对应信息收集，P2 对应文档理解与分析主链，P3 对应导出、QA 与知识治理收口。

排序原因：

- scaffold-only 已切换为当前主线；正式知识学习不再依赖 `pending_updates`，而是依赖逐章复核后的 direct adopt。
- 当前最关键的缺口已经从“闭环是否可验证、回滚是否可审计”转为“如何持续维护上线门禁与抽检标准”。
- go-live 门禁已经落地，后续工作重心是按真实运行反馈做小步校正，而不是重新设计上线标准。

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
- 已将 `financial_output.xlsx` 的正式定位切换为客户可展示的 Excel 工作底稿，workpaper 由 Skill 驱动的分析阶段先行生成，`spreadsheet` 仅负责版式收尾
- W5 路线已调整：不再把“知识学习”压在规则脚本和 `pending_updates` 上，而是改为“模板脚本先产 scaffold，Codex 再逐章复核、逐章写入正式知识库，并通过 adoption log 保持可审计和可回滚”
- `financial-analyzer/SKILL.md` 已切换为 Codex-driven workflow：脚本只负责通用模板抽取，知识学习与最终分析由 Codex 按章完成，正式写入必须带 adoption log
- 已新增 `financial-analyzer/scripts/run_w6_regression.py`，将 W6 最小回归收敛为固定 3 案例重跑 + 结构校验
- 已生成 `financial-analyzer/test_runs/w6_henglong`、`w6_country_garden`、`w6_hanghai` 三个专用回归目录
- 已生成 `financial-analyzer/test_runs/w6_regression_results.json` 与 `financial-analyzer/test_runs/w6_regression_report.md`
- 已确认 W6 当前基线只认“当前主线重跑产物”，不以历史 `*_soul_contract`、`*_v1_1_alpha`、`henglong_v3` 等目录判定通过
- W6.1 已将 `notes_workfile_missing`、`notes_workfile_invalid` 纳入失败路径回归，并新增 `w6_missing_notes_workfile`、`w6_invalid_notes_workfile` 专用目录
- W6.1 已把 scaffold-only 结构校验纳入硬门禁：要求成功态生成 `chapter_records.jsonl`、`analysis_report_scaffold.md`、`focus_list_scaffold.json`、`final_data_scaffold.json`、`soul_export_payload_scaffold.json`，并要求正式 `analysis_report.md`、`final_data.json`、`soul_export_payload.json`、`financial_output.xlsx`、`preview.*` 不再出现在模板脚本成功态
- W6.1 已新增按案例维护的 golden 基线 JSON，并对成功态 payload 子集、失败态 manifest 子集执行非门禁 diff 评估
- W7 已调整为“抽取层 batch”：`financial-analyzer/scripts/run_batch_pipeline.py` 仍支持 Markdown-first 任务清单批跑、失败记录、`--resume`、`--only-failed`，但主成功产物已改为 `chapter_records + scaffold`，不再把 `pending_updates/review bundle` 作为默认主链
- W7 已补充 `financial-analyzer/testdata/w7_batch_tasks/` 样例任务清单，以及 `financial-analyzer/scripts/run_w7_batch_regression.py` 回归脚本，覆盖混合批次、全成功批次、`--resume`、`--only-failed` 和 deprecated governance 门槛
- 生产化 P2 已完成第一版：新增项目内 processed reports registry 规范文档、runtime helper、registry helper，并把 [runtime/state/registry/processed_reports/processed_reports.json](/Users/yetim/project/financialanalysis/runtime/state/registry/processed_reports/processed_reports.json) 接入 `run_batch_pipeline.py`
- P2 已实现 W6 历史单案回填、W7 batch 回填告警口径、全局去重/重跑判定，以及 `financial-analyzer/scripts/run_p2_registry_regression.py` 专项回归脚本
- 生产化 P3 已完成第一版：已安装 `financial-analyzer` skill 现通过 `--runtime-config` / `FINANCIAL_ANALYZER_RUNTIME_CONFIG` / `cwd` 向上搜索三层优先级稳定绑定项目内 [runtime/runtime_config.json](/Users/yetim/project/financialanalysis/runtime/runtime_config.json)
- P3 已把 `run_batch_pipeline.py`、`processed_reports_registry.py` 和正式知识基线入口绑定到外部 runtime，并明确单案 `financial_analyzer.py` 继续保持 `--run-dir` 独立模式
- P3 已把“找不到 runtime 配置或正式 knowledge_base 时直接失败、不再回退 skill 目录或 `financial-analyzer/test_runs/batches`”写入代码与 `financial-analyzer/SKILL.md`
- 生产化 P4 已完成第一版：新增 [chinamoney/scripts/discover_reports.py](/Users/yetim/project/financialanalysis/chinamoney/scripts/discover_reports.py) 与 [financial-analyzer/scripts/generate_p4_test_entry.py](/Users/yetim/project/financialanalysis/financial-analyzer/scripts/generate_p4_test_entry.py)，可基于 ChinaMoney 官方 JSON 接口自动发现 2024 年报候选并生成 `selection_manifest.json`、`download_config.json`、`task_seed_list.json`
- `chinamoney` 已完成第一版 API-first 升级：正式记录 `financeRepo` / `staYearAndType` 接口、会话预热要求、官方来源字段和与批量下载配置的映射
- P4/P5 已把 ChinaMoney 附件网关约束收敛为可恢复门禁：当前环境下官方附件常见 `421 Misdirected Request` / `too many connections from your internet address`，下载阶段现先尝试官方附件，再在失败时按任务元数据回退到 CNInfo 官方镜像，并在 `download_phase_manifest.json` 中记录 `download_main_success_count` / `download_fallback_success_count`
- 生产化 P5 已完成第一版入口：新增 [financial-analyzer/scripts/run_p5_cold_start_simulation.py](/Users/yetim/project/financialanalysis/financial-analyzer/scripts/run_p5_cold_start_simulation.py)，按“两阶段”执行冷启动仿真，阶段 A 的下载门禁现在是 recovery-aware，而不是简单把 421 视为全局死锁
- P5 第一版已把下载成功样本到 MinerU / `notes_workfile` / batch task list / [financial-analyzer/scripts/run_batch_pipeline.py](/Users/yetim/project/financialanalysis/financial-analyzer/scripts/run_batch_pipeline.py) 的适配链路落地，并为 P5 输出独立 `p5_run_manifest.json`
- P4 已新增官方镜像回退能力：`generate_p4_test_entry.py` 会为候选探测 CNInfo 官方 PDF 镜像，并将可用镜像直接写入 `download_config.json` / `task_seed_list.json`，从而提高 ChinaMoney 附件网关的可恢复性
- 已验证新一轮 P4/P5：基于 [runtime/state/tmp/chinamoney_fix_validation_20260319/p5_run_v3](/Users/yetim/project/financialanalysis/runtime/state/tmp/chinamoney_fix_validation_20260319/p5_run_v3) 的真实样本，P5 下载阶段已实现 `1/1` 下载成功、`1/1` 通过 gate，且 attempt log 同时记录了 ChinaMoney 官方附件 `421` 退避与 CNInfo 镜像回退成功
- P5 准备阶段已补一轮韧性增强：`run_p5_cold_start_simulation.py` 现支持 `--resume-output-dir` 复用已下载 / 已解析产物、为单份 MinerU 增加最大尝试次数与耗时记录，并把“批量准备失败后必须全量重跑”的成本降下来
- `mineru/scripts/mineru_stable.py` 已补 `mineru/config.json` token fallback；即使调用方未显式注入 `MINERU_TOKEN`，脚本自身也会先尝试读取本地配置，避免再次出现“manifest 记录 token_present=true、实际子进程却报未设置 token”的割裂状态
- 2026-03-17 新一轮 P5 已在 [runtime/state/tmp/p5_cold_start/20260317_171925](/Users/yetim/project/financialanalysis/runtime/state/tmp/p5_cold_start/20260317_171925) 完成 `10/10` 下载、`10/10` 准备和 `10/10` batch 成功；P5 主目录保留编排与中间产物，而正式 batch 产物已对齐写入 `runtime/state/batches/`
- `financial_analyzer.py` 已切换为 scaffold-only 模式：脚本主线只生成 `chapter_records.jsonl`、`analysis_report_scaffold.md`、`focus_list_scaffold.json`、`final_data_scaffold.json`、`soul_export_payload_scaffold.json` 和标记 `codex_review_required=true` 的 `run_manifest.json`
- 已新增 `write_knowledge_adoption.py`、`rollback_knowledge_adoption.py`、`show_knowledge_adoption.py`，用于支撑 Codex 逐章直写正式 `runtime/knowledge/knowledge_base.json` 并保留 adoption log / rollback 能力
- 生产化 R1 第一版已落地：已明确章节复核状态机、adoption gate、finalization gate、rollback boundary 与 `chapter_review_ledger` 控制面口径
- 生产化 R2 已完成文档收口：知识 adoption delta contract、审计外壳、rollback 约束与校验规则已统一到仓库文档
- 生产化 R2 已进一步收口为 canonical contract：后续 Codex 线程必须直接消费 `identity / source / review / operations / evidence_refs / hashes / rollback / audit` 口径，不再自造 flat 变体
- 生产化 R3 已完成双案例演练：`henglong_2024` 与 `country_garden_2024` 已跑通 scaffold -> adopt -> rollback -> formal closed loop，`P6` 现在可以直接接手 go-live checklist
- `go_live_checklist.md` 已落地，作为正式投入使用前的单一 go-live 门禁清单
- GitHub Projects 的优先级拆分方案已定为 P0 / P1 / P2 / P3 四档，后续会以此作为远端项目板的默认分层

### 进行中

- 当前主阻塞已从“闭环是否跑通”转为“按 go-live checklist 执行上线前抽检与放行”
- 当前已确认完整链路可按两层运行：`PDF -> MinerU Markdown -> notes_workfile -> batch 抽取层 -> Codex/skill 逐章分析与知识写入`
- 后续如果要调整上线门禁，只修改 `go_live_checklist.md` 及其交叉引用

### 下一步

- `R3` 已完成：`henglong_2024` 与 `country_garden_2024` 都已完成 scaffold -> adopt -> rollback -> formal 闭环。
- 复核与直写线程继续直接消费 `knowledge_adoption_delta_contract.md` 的 canonical 口径，不再沿旧 flat 变体分叉。
- `P6` 已收口为 `go_live_checklist.md`，后续只按运行反馈维护门禁和交叉引用。

## 15. 与其他文档的关系

- 本文档负责：总目标、总架构、总计划、模块拆分、跨对话协作约定。
- `soul_excel_spec_v1.md` 负责：Soul 的结构规范。
- `soul_excel_case_analysis.md` 负责：基于案例的结构归纳依据。
- `excel_skill_adoption_plan.md` 负责：Excel 生成技术路线与工具选择。
- `financial-analyzer/references/soul_export_contract.md` 负责：Soul 导出 JSON 契约。
- `codex_execution_runbook.md` 负责：如何实际开启和组织多个 Codex 执行线程。
- `runtime_external_data_layer_spec.md` 负责：项目内 production runtime 的目录结构、`runtime_config` 契约、Git 边界与 skill/runtime 读写边界。
- `production_execution_runbook.md` 负责：生产化阶段如何逐个开启 Codex 对话并执行 runtime/registry/go-live 相关任务。
- `codex_review_and_finalization_runbook.md` 负责：scaffold-only 之后的复核/直写/收尾 prompt pack。
- `knowledge_adoption_delta_contract.md` 负责：章节级知识直写的 delta 契约与字段口径。
- `go_live_checklist.md` 负责：正式投入使用前的上线门禁、人工抽检点、回滚与停机条件。

## 16. 后续维护要求

以后凡是出现以下情况，都应同步更新本蓝图：

1. 项目目标发生变化。
2. Soul 结构发生重大调整。
3. workstream 边界发生变化。
4. 当前优先级发生变化。
5. 某个阶段完成，进入下一个阶段。

如果只是局部实现细节变化，则更新对应模块文档，不必污染总蓝图。

## 17. 业务研究规划补充（信用组 2026）

仓库内另有一套面向信用组业务建设的研究规划，核心是“大数据信用研究 + 财务分析”的双子项目结构。

该规划的基本原则是：

1. 先做子项目 1 的大数据分析，再做子项目 2 的财务分析。
2. 子项目 1 负责全市场定价重构与比价，子项目 2 负责财报附注深挖与基本面补强。
3. 实习生优先参与子项目 1，随后逐步进入子项目 2。
4. 相关成果以研究文档、Excel 数据库和案例材料为主，不涉及代码实现细节。

该业务规划的正式文本分别见：

- `大数据信用研究与财务分析项目总体规划.md`
- `大数据信用研究项目1详细规划.md`
- `大数据信用研究实习生介绍.md`
