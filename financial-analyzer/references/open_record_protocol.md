# Open Record Protocol

## 目标

用稳定外壳承载每次运行的核心产物，同时明确区分：

- 模板脚本生成的结构化初稿
- Codex 复核后的正式分析与知识沉淀

## 章节记录

`chapter_records.jsonl` 每行一条记录，固定核心字段如下：

- `chapter_no`
- `chapter_title`
- `status`
- `summary`

扩展载荷如下：

- `attributes`
- `numeric_data`
- `findings`
- `anomalies`
- `evidence`
- `extensions`

记录范围仅限“已确认附注主章节”，正文不进入 `chapter_records.jsonl`。
其中 `status=completed` 只表示模板抽取完成，不代表已复核、已采纳或已正式成稿。
`attributes` 至少补充：

- `note_no`
- `note_scope`
- `locator_evidence`

读取旧记录时，只依赖固定核心字段；扩展字段缺失不能导致失败。

## 章节复核 ledger

`chapter_review_ledger.jsonl` 是复核与直写控制面的主记录，建议落在 `runtime/state/governance_review/<case_name>/<run_id>/chapter_review_ledger.jsonl`。
它是 append-only 的章节级状态日志，最新一条有效记录代表该章节当前复核状态。

### 固定核心字段

- `ledger_version`
- `record_type`
- `case_name`
- `run_dir`
- `run_manifest_path`
- `chapter_no`
- `chapter_title`
- `chapter_record_path`
- `state`
- `previous_state`
- `adoption_gate`
- `finalization_gate`
- `review`
- `evidence_refs`
- `updated_at`
- `actor`
- `decision`

### 建议状态机

- `scaffold_ready`：模板抽取完成，等待人工或 Codex 开始复核。
- `reviewing`：正在核对章节边界、证据和增量结论。
- `reviewed`：复核已完成，但尚未满足直写条件。
- `adopt_ready`：review 已通过，delta 与证据已齐备，可以进入正式写入。
- `adopted`：已通过 `write_knowledge_adoption.py` 写入正式 `knowledge_base.json`，且对应 adoption log 已生成。
- `finalized`：该章节已进入正式成稿收口状态，且不再存在未闭环的 ledger 项。
- `blocked`：因证据、边界、delta 或运行态条件不足而暂停。
- `rejected`：章节不应进入正式采纳。
- `rolled_back`：此前已采纳，但随后被 `rollback_knowledge_adoption.py` 回滚。

### 门禁口径

- adoption gate 只在以下条件都满足时为 `true`：
  - 章节已确认属于正式附注主章节
  - 证据已挂接到 `evidence_refs`
  - delta 结构完整，且可被正式写入工具稳定消费
  - review 结论明确通过
  - 不存在跨章混写或未决冲突
- finalization gate 只在以下条件都满足时为 `true`：
  - 目标章节全部处于 `adopted` 或 `finalized`
  - 正式 `knowledge_base.json` 处于稳定可读状态
  - 运行目录中不存在未结案的 review ledger 项
  - 正式输出已基于采纳后的知识重新生成

### 交接边界

- `chapter_records.jsonl` 只记录抽取层事实，不承载复核决策。
- `chapter_review_ledger.jsonl` 只记录复核决策，不承载 Soul 结构。
- adoption log 只记录正式知识写入的 before/after snapshot 与 delta，不替代 review ledger。
- 回滚只撤销正式知识写入，不修正 `chapter_records.jsonl`，也不改 Soul 输出契约。

## 模板脚本 scaffold

模板脚本允许输出以下 scaffold：

- `analysis_report_scaffold.md`
- `focus_list_scaffold.json`
- `final_data_scaffold.json`
- `soul_export_payload_scaffold.json`

这些 scaffold 只代表“脚本初稿”，必须经过 Codex 复核后才能升级为正式交付。

## 最终数据

正式 `final_data.json` 固定核心字段如下：

- `entity_profile`
- `key_conclusions`
- `topic_results`

各主题节点允许通过 `attributes` 和 `extensions` 自由增长。

## Soul 导出契约

正式 `soul_export_payload.json` 是面向 Soul Excel 导出层的稳定接口，固定核心字段如下：

- `contract_version`
- `template_version`
- `generated_at`
- `entity_profile`
- `source_artifacts`
- `module_manifest`
- `overview`
- `kpi_dashboard`
- `financial_summary`
- `debt_profile`
- `liquidity_and_covenants`
- `optional_modules`
- `evidence_index`

要求：

- 固定骨架模块必须始终存在，即使字段值为空。
- 所有可追溯字段只能通过 `evidence_refs` 关联 `evidence_index`。
- 内部知识写入日志、adoption log、运行态审计信息不得进入该契约。

## 运行清单

`run_manifest.json` 需要显式记录模板脚本结果：

- `status`
- `failure_reason`
- `notes_locator`
- `notes_catalog_summary`
- `script_output_mode`
- `codex_review_required`

成功态默认要求：

- `script_output_mode=scaffold_only`
- `codex_review_required=true`

## 正式知识写入

正式知识写入不再通过 `pending_updates.json` 主导，而是通过：

- `runtime/knowledge/knowledge_base.json`
- `runtime/knowledge/adoption_logs/`

章节级复核、写入前后的结构化 delta，以及回滚约束的正式口径见 [knowledge_adoption_delta_contract.md](/Users/yetim/project/financialanalysis/knowledge_adoption_delta_contract.md)。

每次章节级知识写入至少需要：

- 写入来源 case / chapter
- before/after hash
- 结构化 delta
- 时间戳

缺少 adoption log 的知识写入视为非法实现。
