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
- `chapter_text`
- `summary`

扩展载荷如下：

- `chapter_text_cleaned`
- `attributes`
- `numeric_data`
- `findings`
- `anomalies`
- `evidence`
- `extensions`

记录范围仅限“已确认附注主章节”，正文不进入 `chapter_records.jsonl`。
其中 `chapter_text` 保存该章对应的原文切片，供 Codex 逐章阅读与指标核算；`summary` 只作为速览，不可替代原文。
其中 `status=completed` 只表示模板抽取完成，不代表已复核、已采纳或已正式成稿。
`attributes` 至少补充：

- `note_no`
- `note_scope`
- `locator_evidence`

读取旧记录时，只依赖固定核心字段；扩展字段缺失不能导致失败。

## 章节覆盖门禁

- `chapter_records.jsonl` 只应包含已确认的附注主章节，不得混入正文或未确认章节。
- 章节拆解完成后，所有已抽取主章节都必须在 `chapter_records.jsonl` 中出现，不能只保留一部分章节作为正式分析入口。
- `status=completed` 只表示模板抽取完成，不表示该章节已经完成阅读、分析、计算或采纳。
- 任何章节在进入正式 workpaper 之前，都必须先完成原文阅读、证据定位、知识库比对和本章分析。

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

### 章节完成口径

- `scaffold_ready`：仅代表模板脚本已产出章节初稿，不代表已经开始正式分析。
- `reviewing`：该章正在回看原文、定位证据并对照知识库。
- `reviewed`：该章原文、证据和关键口径已完成核对，可以进入本章结论整理。
- `adopt_ready`：该章可以正式写入知识库，或已明确不写入但可作为正式冻结结果。
- 如果某章尚未到 `reviewed`，不得把该章当成可复用知识，也不得把该章视为已完成。

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
- `chapter_count`
- `focus_count`
- `extensions`

正式 `final_data.json` 只承担运行元信息与章节数量摘要，不承载脚本式分析结论。

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

章节级复核、写入前后的结构化 delta、审计外壳和回滚约束的正式口径见 [knowledge_adoption_delta_contract.md](/Users/yetim/project/financialanalysis/knowledge_adoption_delta_contract.md)。该契约是 canonical 口径；当前脚本实现仍兼容 flat 字段别名，但后续线程不得再以别名发明新形状。

### 正式 adoption 记录的最小核心字段

一条正式 adoption 记录应同时覆盖 delta payload 和 audit envelope，canonical 最小形状至少包含：

- `identity`
- `source`
- `review`
- `operations`
- `evidence_refs`
- `hashes`
- `rollback`
- `audit`

其中 `identity` 至少包含 `adoption_id`、`delta_version`、`logged_at`、`result`；`hashes` 至少包含 `before_hash`、`after_hash`、`knowledge_base_version_before`、`knowledge_base_version_after`；`audit` 至少包含 `adoption_id`、`logged_at`、`result`、`delta_path`、`knowledge_base_path`、`backup_path`、`summary`。

### 回滚记录的最小核心字段

当发生回滚时，rollback log 至少应记录：

- `rolled_back_at`
- `source_log`
- `knowledge_base_path`
- `backup_path`
- `restored_hash`
- `rollback_log_path`

### 兼容与摘要

- 当前脚本实现已经稳定写出 canonical nested adoption record，并额外保留 flat 字段别名供兼容读取。
- canonical 口径以 `knowledge_adoption_delta_contract.md` 为准；后续 Codex 线程应按正式字段补齐，不再把旧 `pending_updates` 或 review bundle 当主路径。
- `show_knowledge_adoption.py` 的摘要目标已经直接展示 `identity.adoption_id / identity.result / source / review / hashes`，对缺失字段保持兼容。
- 旧 adoption log 如果还没有 `review`、`result` 或 `hashes`，摘要工具应显示 `unknown` 或空值，而不是报错中断。

缺少 adoption log 的知识写入视为非法实现。
