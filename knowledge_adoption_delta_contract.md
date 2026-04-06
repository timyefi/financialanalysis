# Knowledge Adoption Delta Contract

## 1. 文档定位

这份文档定义章节级正式知识写入时必须提交的结构化 delta，以及与之绑定的审计外壳。

它解决的是“如何把复核结果稳定、可回滚、可审计地写入正式 `knowledge_base.json`”，不是知识内容本身，也不是 Soul 结构。

正式写入必须发生在 Codex 已经完成中间产物阅读、正式 Excel 工作底稿和正式报告写作之后；scaffold 只能作为复核输入，不能直接跳到 adoption。

本契约是后续 Codex 线程的 canonical 口径：

- 章节复核结论必须先落成 delta。
- 正式写入必须带审计外壳。
- 回滚必须能从同一份 adoption 记录恢复。
- `pending_updates.json` 不是主学习路径。

## 2. Canonical 记录形状

章节级正式写入使用一条 adoption 记录承载完整信息。canonical 形状按以下顶层分区组织：

- `identity`
- `source`
- `review`
- `operations`
- `evidence_refs`
- `hashes`
- `rollback`
- `audit`

其中 `identity`、`hashes`、`rollback`、`audit` 负责审计与控制面信息；`source`、`review`、`operations`、`evidence_refs` 负责业务证据与知识增量。当前脚本实现仍兼容扁平字段读写，但后续 Codex 线程必须把上面这组分区视为唯一 canonical 口径，不再各自发明变体。

```json
{
  "identity": {
    "adoption_id": "20260318_120000_henglong_chapter_10",
    "delta_version": "knowledge_adoption_delta_v1",
    "logged_at": "2026-03-18T12:00:00+08:00",
    "result": "applied"
  },
  "source": {
    "case_name": "恒隆地产",
    "chapter_no": "10",
    "chapter_title": "借款和融资成本",
    "run_dir": "/abs/path/to/run_dir",
    "chapter_record_path": "/abs/path/to/run_dir/chapter_records.jsonl",
    "review_ledger_path": "/abs/path/to/run_dir/chapter_review_ledger.jsonl",
    "scaffold_artifacts": {
      "analysis_report_scaffold": "/abs/path/to/run_dir/analysis_report_scaffold.md",
      "final_data_scaffold": "/abs/path/to/run_dir/final_data_scaffold.json",
      "soul_export_payload_scaffold": "/abs/path/to/run_dir/soul_export_payload_scaffold.json"
    }
  },
  "review": {
    "review_state": "adopted",
    "reviewer": "Codex",
    "reviewed_at": "2026-03-18T12:00:00+08:00",
    "summary": "将章节结论正式采纳为知识条目",
    "risk_level": "low",
    "confidence": "high",
    "decision": "adopt"
  },
  "operations": [
    {
      "op": "upsert_by_key",
      "path": "knowledge.indicators.solvency.long_term",
      "match_key": "title",
      "match_value": "长期借款结构",
      "value": {
        "title": "长期借款结构",
        "description": "新增章节复核结论"
      }
    }
  ],
  "evidence_refs": [
    {
      "type": "chapter_record",
      "path": "/abs/path/to/run_dir/chapter_records.jsonl",
      "chapter_no": "10"
    },
    {
      "type": "scaffold_artifact",
      "path": "/abs/path/to/run_dir/analysis_report_scaffold.md",
      "chapter_no": "10"
    }
  ],
  "hashes": {
    "before_hash": "md5:....",
    "after_hash": "md5:....",
    "knowledge_base_version_before": "2.4.0",
    "knowledge_base_version_after": "2.4.1"
  },
  "rollback": {
    "enabled": true,
    "backup_path": "/abs/path/to/adoption_logs/20260318_120000_henglong_chapter_10.before.json",
    "rollback_log_path": "",
    "strategy": "restore_full_knowledge_base_snapshot"
  },
  "audit": {
    "adoption_id": "20260318_120000_henglong_chapter_10",
    "logged_at": "2026-03-18T12:00:00+08:00",
    "result": "applied",
    "delta_path": "/abs/path/to/adoption_logs/20260318_120000_henglong_chapter_10.delta.json",
    "knowledge_base_path": "/abs/path/to/runtime/knowledge/knowledge_base.json",
    "backup_path": "/abs/path/to/adoption_logs/20260318_120000_henglong_chapter_10.before.json",
    "summary": "将长期借款结构与章节结论正式采纳为知识条目"
  }
}
```

## 3. 字段约束

### 3.1 `adoption_id`

- 必填。
- 必须能唯一标识一次章节级正式写入。
- 推荐与 adoption log 文件名保持同一 stem，格式为 `YYYYMMDD_HHMMSS_case_chapter_no`。
- 后续 rollback、摘要和人工排查都优先依赖该字段。

### 3.1.1 `identity` / 审计键

canonical 审计键由以下字段共同构成：

- `identity.adoption_id`
- `identity.delta_version`
- `identity.logged_at`
- `identity.result`

推荐字符串化审计键格式：

- `adoption_id|logged_at|result|delta_version`

含义如下：

- `adoption_id` 标识一次章节级写入实例。
- `delta_version` 标识这条 delta 的 schema 版本。
- `logged_at` 标识这条记录的生成时间。
- `result` 标识这条记录的控制面结果。

后续摘要、回滚、排障与去重都应优先使用这组字段，而不是依赖文件名猜测语义。

### 3.2 `delta_version`

- 必填。
- 当前固定为 `knowledge_adoption_delta_v1`。
- 后续如升级 schema，只允许新增版本，不允许悄悄改写 v1 语义。

### 3.3 `logged_at`

- 必填。
- 必须是带时区的 ISO 8601 时间。
- 表示这条正式采纳记录生成的时间，而不是章节原文时间。

### 3.4 `result`

- 必填。
- 推荐取值：
  - `applied`
  - `rejected`
  - `rolled_back`
  - `dry_run`
- `applied` 表示正式写入已生效。
- `rejected` 表示 review 通过但未进入正式写入，或者写入前被门禁阻断。
- `rolled_back` 只用于回滚后的审计记录。
- `dry_run` 只用于演练或校验，不得作为正式知识库变更结果。
- 只有 `applied` 允许进入 `write_knowledge_adoption.py` 的正式写入路径。

### 3.5 `source`

必须至少包含：

- `case_name`
- `chapter_no`
- `chapter_title`
- `run_dir`
- `chapter_record_path`
- `review_ledger_path`
- `scaffold_artifacts`

建议额外保留：

- `issuer`
- `report_period`
- `run_manifest_path`
- `analysis_report_path`
- `financial_output_path`

说明：

- `financial_output_path` 应指向最终正式工作簿；如果该工作簿采用隐藏原始输入层和公式派生指标，必须保留可审计的最终版本，不要把仅含静态结果的临时表当作正式产物。

约束：

- `run_dir`、`chapter_record_path`、`review_ledger_path` 必须指向当前案例运行目录内的真实路径。
- `scaffold_artifacts` 至少应包含 `analysis_report_scaffold`、`final_data_scaffold`、`soul_export_payload_scaffold`。
- 当正式 Excel 工作底稿和正式报告已生成时，建议同时保留 `financial_output_path` 和 `analysis_report_path`，用于证明 adoption 发生在最终成稿之后。
- `source` 只描述案例、章节和证据来源，不承载知识库内部治理字段。

### 3.6 `review`

必须至少包含：

- `review_state`
- `reviewer`
- `reviewed_at`
- `summary`
- `risk_level`
- `confidence`

推荐取值：

- `review_state`：
  - `proposed`
  - `reviewed`
  - `adopted`
  - `rejected`
  - `blocked`
- `risk_level`：
  - `low`
  - `medium`
  - `high`
- `confidence`：
  - `low`
  - `medium`
  - `high`

约束：

- `review_state` 不能空。
- `reviewed_at` 必须是 ISO 时间。
- `summary` 必须能解释为什么接受、拒绝或暂缓。
- `review` 只描述章节复核，不描述 Soul 导出结构。

### 3.7 `operations`

允许的操作类型只有三类：

- `set`
- `append`
- `upsert_by_key`

统一约束：

- `operations` 必须是非空列表。
- 每个 operation 都必须显式写出 `path`。
- `path` 只允许使用点号分隔的对象路径，不引入数组索引语义，例如不允许 `items[0]`。
- `path` 目标必须位于正式 `knowledge_base.json` 的知识域，不得写入运行态元数据。

各操作规则：

- `set`
  - `value` 必填。
  - 目标节点必须是对象路径。
  - 允许创建缺失的中间对象。
- `append`
  - `value` 必填。
  - 目标节点必须是列表。
  - 若列表不存在，可在正式知识域内创建空列表后再追加。
- `upsert_by_key`
  - `value` 必填，且必须是对象。
  - `match_key` 与 `match_value` 必填。
  - 若目标列表中已有对象满足 `match_key == match_value`，则用 `value` 与已有对象做浅合并，后写字段覆盖前写字段。
  - 若未命中，则把 `value` 追加到列表末尾。

### 3.8 `evidence_refs`

- 必填，且不能空。
- 每条 evidence 至少应能回指到章节复核证据。

推荐引用类型：

- `chapter_record`
- `scaffold_artifact`
- `locator`
- `raw_excerpt`
- `manual_note`

推荐字段：

- `type`
- `path`
- `chapter_no`
- `locator`
- `snippet`

约束：

- 至少一条 evidence 应指向 `chapter_records.jsonl`。
- 若结论依赖正文或附注定位，必须再补一条 `locator` 或 `raw_excerpt`。
- evidence 只负责可追溯，不负责承载正文全文。

### 3.9 `hashes`

- 必填。
- `before_hash` 与 `after_hash` 必须放在 `hashes` 对象内。
- 推荐使用 `md5:` 前缀，后接规范化 JSON 的摘要值。
- 计算对象是写入前后正式 `knowledge_base.json` 的完整内容。
- `before_hash` 与 `after_hash` 在正式 `applied` 写入中必须不同。

### 3.10 `knowledge_base_version_before` / `knowledge_base_version_after`

- 必填。
- 必须显式记录写入前后正式知识库版本。
- 版本来源以 `runtime/knowledge/knowledge_base.json` 的 `metadata.version` 为准。
- 版本升级算法不在本契约内规定，但写入方必须保证版本变化可解释、可审计。

### 3.11 `rollback`

必须至少包含：

- `enabled`
- `backup_path`
- `rollback_log_path`
- `strategy`

约束：

- `enabled=true` 时必须预先生成 `backup_path`。
- `backup_path` 必须指向写入前的完整正式知识库快照。
- `rollback_log_path` 用于回滚后的审计记录；未回滚前可以为空字符串。
- `strategy` 推荐固定为 `restore_full_knowledge_base_snapshot`。
- rollback 只恢复正式知识库，不回写 Soul、`chapter_records.jsonl` 或 review ledger。

### 3.12 `audit`

`audit` 是供摘要、排障和人工核查消费的控制面外壳，必须至少包含：

- `adoption_id`
- `logged_at`
- `result`
- `delta_path`
- `knowledge_base_path`
- `backup_path`
- `summary`

约束：

- `audit.adoption_id`、`audit.logged_at`、`audit.result` 应与 `identity` 中对应字段保持一致。
- `audit.backup_path` 应与 `rollback.backup_path` 保持一致。
- `audit.delta_path` 指向写入时落盘的 delta 文件，供回溯和排障使用。

如果后续 rollback 已发生，回滚日志应补充：

- `rolled_back_at`
- `source_log`
- `restored_hash`
- `rollback_log_path`

## 4. Validation 规则

正式写入前必须通过以下校验：

1. `identity.delta_version` 必须等于 `knowledge_adoption_delta_v1`。
2. `identity.adoption_id`、`identity.logged_at`、`identity.result` 不能为空。
3. `identity.result` 必须落在允许集合内，且只有 `applied` 可以进入正式写入入口。
4. `operations` 必须是非空列表。
5. `source.case_name`、`source.chapter_no`、`source.chapter_title`、`source.run_dir`、`source.chapter_record_path`、`source.review_ledger_path` 不能为空。
6. `review.review_state`、`review.reviewed_at`、`review.summary` 不能为空。
7. `review.review_state` 必须落在允许集合内。
8. `evidence_refs` 至少有 1 条，且必须能回指到章节证据。
9. `hashes.before_hash` 与 `hashes.after_hash` 在正式 `applied` 写入中不能相同。
10. `hashes.knowledge_base_version_before` 与 `hashes.knowledge_base_version_after` 必须显式记录。
11. `rollback.enabled=true` 时必须有 `rollback.backup_path`，且 backup 必须在写入前落盘。
12. 不能把内部治理元数据写回知识库的正式业务字段。
13. 不能把 `pending_updates`、review bundle 或 Soul 结构当成正式知识学习主路径。

## 5. 回滚约束

1. 每次正式写入必须对应一份写入前快照。
2. 每次正式写入必须对应一条 adoption log。
3. 回滚只能基于完整 adoption log 执行。
4. 回滚只恢复正式 `knowledge_base.json`，不修正 `chapter_records.jsonl`，不修改 Soul 产物。
5. 回滚动作必须留下独立 rollback log。
6. 同一条 adoption 记录不能被重复半回滚或部分回滚。
7. `result=rolled_back` 只能出现在回滚后生成的审计记录中，不能作为一次新的正式写入结果。
8. `result=rejected` 与 `result=dry_run` 不得产出正式知识库变更。

## 6. 与现有脚本的关系

- `financial-analyzer/scripts/write_knowledge_adoption.py` 是正式写入入口，应接收本契约定义的 delta 形状。
- `financial-analyzer/scripts/rollback_knowledge_adoption.py` 应按 adoption log + backup 恢复正式知识库。
- `financial-analyzer/scripts/show_knowledge_adoption.py` 应展示 source / review / hash / result 的摘要。

当前脚本实现仍保留最小兼容口径，后续 Codex 线程应以本契约为准，不应再把旧 `pending_updates` 或 review bundle 当主路径。

R3 live drill 已实际按 `knowledge.case_notes.<case_id>.chapters` 这一路径做了章节级直写与回滚验证；这只说明落地路径已被演练，不改变本契约的 canonical 口径。

## 7. 最小可执行示例

下面示例展示一条真实章节采纳记录的最小形状。字段可扩展，但核心约束不得缺失。

```json
{
  "identity": {
    "adoption_id": "20260318_120000_henglong_chapter_10",
    "delta_version": "knowledge_adoption_delta_v1",
    "logged_at": "2026-03-18T12:00:00+08:00",
    "result": "applied"
  },
  "source": {
    "case_name": "恒隆地产",
    "chapter_no": "10",
    "chapter_title": "借款和融资成本",
    "run_dir": "/abs/path/to/run_dir",
    "chapter_record_path": "/abs/path/to/run_dir/chapter_records.jsonl",
    "review_ledger_path": "/abs/path/to/run_dir/chapter_review_ledger.jsonl",
    "scaffold_artifacts": {
      "analysis_report_scaffold": "/abs/path/to/run_dir/analysis_report_scaffold.md",
      "final_data_scaffold": "/abs/path/to/run_dir/final_data_scaffold.json",
      "soul_export_payload_scaffold": "/abs/path/to/run_dir/soul_export_payload_scaffold.json"
    }
  },
  "review": {
    "review_state": "adopted",
    "reviewer": "Codex",
    "reviewed_at": "2026-03-18T12:00:00+08:00",
    "summary": "附注章节结论与原文证据一致，采纳为正式知识",
    "risk_level": "low",
    "confidence": "high",
    "decision": "adopt"
  },
  "operations": [
    {
      "op": "upsert_by_key",
      "path": "knowledge.indicators.solvency.long_term",
      "match_key": "title",
      "match_value": "长期借款结构",
      "value": {
        "title": "长期借款结构",
        "description": "长期借款主要为银行借款，关注到期结构与担保条款"
      }
    }
  ],
  "evidence_refs": [
    {
      "type": "chapter_record",
      "path": "/abs/path/to/run_dir/chapter_records.jsonl",
      "chapter_no": "10"
    }
  ],
  "hashes": {
    "before_hash": "md5:11111111111111111111111111111111",
    "after_hash": "md5:22222222222222222222222222222222",
    "knowledge_base_version_before": "2.4.0",
    "knowledge_base_version_after": "2.4.1"
  },
  "rollback": {
    "enabled": true,
    "backup_path": "/abs/path/to/adoption_logs/20260318_120000_henglong_chapter_10.before.json",
    "rollback_log_path": "",
    "strategy": "restore_full_knowledge_base_snapshot"
  },
  "audit": {
    "adoption_id": "20260318_120000_henglong_chapter_10",
    "logged_at": "2026-03-18T12:00:00+08:00",
    "result": "applied",
    "delta_path": "/abs/path/to/adoption_logs/20260318_120000_henglong_chapter_10.delta.json",
    "knowledge_base_path": "/abs/path/to/runtime/knowledge/knowledge_base.json",
    "backup_path": "/abs/path/to/adoption_logs/20260318_120000_henglong_chapter_10.before.json",
    "summary": "将长期借款结构与章节结论正式采纳为知识条目"
  }
}
```
