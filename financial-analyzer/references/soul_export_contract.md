# Soul Export Contract

## 定位

`soul_export_payload.json` 是 Financial Analysis 到 Soul Excel 导出层之间的正式稳定契约。

- `final_data.json` 继续承担分析聚合产物角色。
- `soul_export_payload.json` 负责固定骨架、可选模块、证据索引与导出顺序。
- `pending_updates.json`、知识候选、内部治理元数据不得进入该契约。

## 顶层字段

```json
{
  "contract_version": "soul_export_v1",
  "template_version": "soul_v1_1_alpha",
  "generated_at": "",
  "entity_profile": {},
  "source_artifacts": {},
  "module_manifest": [],
  "overview": {},
  "kpi_dashboard": {},
  "financial_summary": {},
  "debt_profile": {},
  "liquidity_and_covenants": {},
  "optional_modules": [],
  "evidence_index": []
}
```

## 固定骨架

- `overview`
  - `executive_summary[]`
  - `key_risks[]`
  - `rating_snapshot[]`
  - `report_highlights[]`
- `kpi_dashboard`
  - `periods[]`
  - `sections[{category, metrics[]}]`
- `financial_summary`
  - `unit_label`
  - `statements{balance_sheet[], income_statement[], cash_flow[]}`
  - `coverage_note`
- `debt_profile`
  - `totals[]`
  - `maturity_buckets[]`
  - `financing_mix[]`
  - `rate_profile[]`
  - `debt_comments[]`
- `liquidity_and_covenants`
  - `cash_metrics[]`
  - `credit_lines[]`
  - `restricted_assets[]`
  - `covenants[]`
  - `liquidity_observations[]`
- `evidence_index`
  - 所有模块字段的 `evidence_refs` 必须能回溯到这里

固定骨架必须始终输出。值缺失时保留结构，并用 `null`、空数组或 `source_status=manual_needed` 表示。

## 可选模块

- `05_bond_detail`
- `06_rating_view`
- `07_peer_comparison`
- `08_topic_<name>`
- `90_full_statements`

可选模块只在 `module_manifest.enabled=true` 时输出。

## 通用类型

- `MetricFact`
  - `metric_code`, `label`, `value`, `unit`, `period`, `comparison`, `benchmark`, `risk_level`, `source_status`, `evidence_refs`
- `TableRow`
  - `row_code`, `label`, `values`, `commentary`, `source_status`, `evidence_refs`
- `EvidenceEntry`
  - `evidence_id`, `field_path`, `sheet_name`, `excerpt`, `source_document`, `chapter_no`, `chapter_title`, `note_no`, `line_span`, `confidence`
- `ModuleManifestItem`
  - `sheet_name`, `module_key`, `module_type`, `required`, `enabled`, `title`, `empty_state`

## 当前实现边界

- `entity_profile` 直接来自 `final_data.json.entity_profile`
- `overview`、`debt_profile`、`liquidity_and_covenants`、部分 `kpi_dashboard` 可由当前 notes-only 输出供数
- `financial_summary` 当前保留空骨架，等待标准化报表抽取
- `rating_view`、`peer_comparison` 当前默认禁用
- 证据定位当前使用 `note_no + line_span`，页码暂非必填
