# Codex 复核与直写手册（Prompt Pack）

## 1. 文档定位

这份文档只解决一件事：

- 当项目已经完成 scaffold-only 抽取、runtime 绑定和 batch 回归后，如何把“章节复核 -> 直写知识 -> 正式成稿”变成稳定、可交接、可回滚的主线。

它不是总蓝图的替代品，也不是 `codex_execution_runbook.md` 的重复版。它只承接后 W5 的新主线：`Codex Review & Direct Adopt`。

## 2. 当前口径

1. `financial_analyzer.py` 只负责抽取与 scaffold，不再直接生成正式分析结论。
2. `pending_updates.json` 不是主学习路径，只保留兼容痕迹。
3. 正式知识学习由 Codex 按章复核后，通过 adoption log 直写 `runtime/knowledge/knowledge_base.json`。
4. `knowledge_manager.py` 只负责正式知识库审计、摘要与兼容入口，不再承担候选治理主路径。
5. 任何章节级知识写入都必须能回滚，并且能被摘要工具看见。
6. `chapter_records.jsonl` 的 `status=completed` 只表示模板抽取完成，不代表已复核、已采纳或已正式成稿。
7. `knowledge_adoption_delta_contract.md` 定义正式 delta payload、审计外壳和 rollback 规则，canonical 形状固定为 `identity / source / review / operations / evidence_refs / hashes / rollback / audit`，后续线程不得各自发明变体口径。

## 2.1 R1 控制面边界

1. `chapter_records.jsonl` 继续作为抽取层记录，只承载已确认附注主章节的结构化初稿。
2. 章节复核的主记录改为独立的 `chapter_review_ledger.jsonl`，不写入 Soul 契约，不写回 `chapter_records.jsonl`。
3. `chapter_review_ledger.jsonl` 采用章节级状态机，最新一条有效记录代表该章节当前复核状态。
4. adoption gate 只控制“是否允许写入正式 `knowledge_base.json`”，finalization gate 只控制“是否允许把整案收口为正式交付”。
5. rollback boundary 以单个 adoption log 为原子单元；回滚只恢复正式知识库，不回写 Soul 结构，也不重写 `chapter_records.jsonl`。

## 3. 推荐执行顺序

R1 与 R2 已收口到文档与规范，当前剩余主线是 R3 和 P6。

| 顺序 | 类型 | 主目标 | 核心交付物 |
|------|------|--------|------------|
| 0 | 总控线程 | 维护复核状态、排序任务 | 状态更新、下一步安排 |
| 1 | 执行线程 | 做 1-2 个完整案例的 scaffold -> adopt 演练 | 正式 knowledge_base、adoption logs、正式成稿 |
| 2 | 执行线程 | 形成 go-live checklist | 上线门禁、人工复核点、回滚策略 |

说明：

- 第 1 步只选少量完整案例演练，不要一上来跑 10 案。
- 第 2 步只在复核闭环跑通后推进。

## 4. 新线程 Prompt

### 4.1 线程 R1：Codex Review & Direct Adopt Control Plane

### 目标

- 把“模板脚本输出 scaffold -> Codex 逐章复核 -> 直写正式 knowledge_base -> 生成正式交付”的控制面标准化，替代旧的 `pending_updates / review bundle` 主路径。
- 明确章节状态机、adoption gate、finalization gate、rollback boundary 和 direct adopt 交接规则。

### 开始前阅读

- `AGENTS.md`
- `automation_blueprint.md`
- `codex_execution_runbook.md`
- `production_execution_runbook.md`
- `financial-analyzer/SKILL.md`
- `financial-analyzer/references/open_record_protocol.md`
- `financial-analyzer/references/output_contract.md`

### 交付物

- 复核状态机
- adoption gate
- finalization gate
- 章节级 review ledger 口径
- rollback boundary
- 与 direct adopt 的交接规则

### 本线程不做

- 不做 10 案测试
- 不再推进 `pending_updates` 主路径
- 不直接改 Soul 模板结构

### R1 交接规则

1. `chapter_records.jsonl` 只负责“抽取已完成”的事实，不承载 review 判定。
2. `chapter_review_ledger.jsonl` 只负责 review 过程和决策，不承载 Soul 输出。
3. `write_knowledge_adoption.py` 只接受已通过 adoption gate 的章节级 delta。
4. `rollback_knowledge_adoption.py` 只回滚已写入的正式知识，不修正抽取层记录。
5. `show_knowledge_adoption.py` 和 `knowledge_manager.py` 只做正式知识库与 adoption log 的摘要/审计，不作为 review 主路径。

### 可直接复制的 Prompt

```text
先阅读 AGENTS.md、automation_blueprint.md、codex_execution_runbook.md、production_execution_runbook.md、financial-analyzer/SKILL.md、financial-analyzer/references/open_record_protocol.md、financial-analyzer/references/output_contract.md。当前聚焦 R1：Codex Review & Direct Adopt Control Plane。请把“模板脚本输出 scaffold -> Codex 逐章复核 -> 直写正式 knowledge_base -> 生成正式交付”的控制面标准化，明确 review 状态机、adoption gate、finalization gate、章节级 review ledger 口径、rollback boundary 以及与 direct adopt 的交接规则，并把结果落成仓库文档。不要继续按 `pending_updates / review bundle` 主路径推进，也不要开始 10 案测试。
```

### 4.2 线程 R2：Knowledge Adoption Delta Contract

### 目标

- 固化每次章节级知识写入的 delta 契约、审计外壳与 rollback 约束，使 `write_knowledge_adoption.py` 的输入可审计、可回滚、可摘要。

### 开始前阅读

- `AGENTS.md`
- `automation_blueprint.md`
- `codex_execution_runbook.md`
- `financial-analyzer/references/open_record_protocol.md`
- `production_execution_runbook.md`
- `knowledge_adoption_delta_contract.md`
- `financial-analyzer/scripts/write_knowledge_adoption.py`
- `financial-analyzer/scripts/rollback_knowledge_adoption.py`
- `financial-analyzer/scripts/show_knowledge_adoption.py`

### 交付物

- delta 契约文档
- adoption log 审计键与摘要口径
- 允许的操作类型与字段说明
- 验证规则
- 最小示例 payload

### 本线程不做

- 不直接做 10 案测试
- 不把契约写成模糊自然语言
- 不修改知识库主结构

### 可直接复制的 Prompt

```text
先阅读 AGENTS.md、automation_blueprint.md、codex_execution_runbook.md、financial-analyzer/references/open_record_protocol.md、knowledge_adoption_delta_contract.md，以及 financial-analyzer/scripts/write_knowledge_adoption.py、financial-analyzer/scripts/rollback_knowledge_adoption.py、financial-analyzer/scripts/show_knowledge_adoption.py。当前聚焦 R2：Knowledge Adoption Delta Contract。请把章节级正式写入所需的 canonical delta schema 落成仓库文档，明确 `identity / source / review / operations / evidence_refs / hashes / rollback / audit` 八个分区，以及 `adoption_id`、`logged_at`、`result`、审计键、`before_hash`、`after_hash`、`knowledge_base_version_before/after`、rollback 约束和 validation 规则；同时明确 adoption log 的摘要口径，并说明当前 flat 字段别名仅作兼容，不要改 Soul 结构，也不要重新引入 pending_updates 作为主学习路径。
```

### 4.3 线程 R3：1-2 个完整案例的 Scaffold -> Adopt 演练

### 目标

- 用少量完整案例验证“scaffold -> 逐章复核 -> adoption log -> 正式知识库 -> 正式成稿”的闭环。

### 开始前阅读

- `AGENTS.md`
- `automation_blueprint.md`
- `production_execution_runbook.md`
- `codex_review_and_finalization_runbook.md`
- `knowledge_adoption_delta_contract.md`
- 最新的 W6 / W7 回归结果

### 交付物

- 1-2 个完整案例的正式成稿
- 对应的 adoption logs
- 回滚验证结论
- 单案复核耗时与摩擦点记录

### 本线程不做

- 不扩到 10 案
- 不在这个线程里继续改生产结构
- 不绕过 review gate 直接写正式产物

### 可直接复制的 Prompt

```text
先阅读 AGENTS.md、automation_blueprint.md、production_execution_runbook.md、codex_review_and_finalization_runbook.md、knowledge_adoption_delta_contract.md，以及最新的 W6 / W7 回归结果。当前聚焦 R3：1-2 个完整案例的 Scaffold -> Adopt 演练。请选取 1 到 2 个完整案例，按“先 scaffold、再逐章复核、再通过 adoption log 直写正式 knowledge_base、最后生成正式 analysis_report/final_data/soul_export_payload/financial_output”的顺序跑通全流程，并记录 adoption logs、回滚验证和单案复核摩擦点。不要扩成 10 案，也不要回到 pending_updates/review bundle 口径。
```

### 4.4 线程 P6：Go-Live Checklist

### 目标

- 在复核与直写闭环稳定后，形成正式投入使用前的门禁、人工抽检点与回滚策略。

### 开始前阅读

- `AGENTS.md`
- `automation_blueprint.md`
- `production_execution_runbook.md`
- `codex_review_and_finalization_runbook.md`
- 最近一次 R3 演练结果

### 交付物

- go-live checklist
- 人工复核清单
- 回滚和停机策略
- 上线判定标准

### 可直接复制的 Prompt

```text
先阅读 AGENTS.md、automation_blueprint.md、production_execution_runbook.md、codex_review_and_finalization_runbook.md，以及最近一次 R3 演练结果。当前聚焦 P6：Go-Live Checklist。请基于已经跑通的 scaffold -> adopt -> formal 流程，整理一份正式投入使用前的 go-live checklist，至少覆盖 skill 安装校验、runtime 配置校验、registry 状态、复核状态机、adoption log 完整性、失败重跑策略、回滚策略、人工抽检点和“哪些问题出现时必须停止上线”。请把结果落成仓库文档。
```

## 5. 使用方式

如果你现在只想开一个新线程，优先开 `R1`。

如果你已经确定控制面无需再争论，直接开 `R2`。

如果你想验证整个闭环是否真正可用，开 `R3`。

`P6` 只在 `R3` 跑通之后再开。
