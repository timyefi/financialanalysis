# Go-Live Checklist

## 1. 目的

这份清单用于判断项目是否可以从 `R3 scaffold -> adopt -> rollback -> formal` 的验证阶段，进入正式投入使用阶段。

它不是新的实现规范，也不是运行日志模板，而是上线前的门禁。任何一项失败，只要触发停机条件，就不能继续放行。

## 2. 适用范围

适用对象：

- 已安装的 `financial-analyzer`、`chinamoney`、`mineru` 相关 skill
- 项目内 runtime：`runtime/runtime_config.json`
- 全局 processed reports registry：`runtime/state/registry/processed_reports/processed_reports.json`
- 复核与直写控制面：`runtime/state/governance_review/<case_name>/<run_id>/chapter_review_ledger.jsonl`
- 正式知识库与 adoption logs：`runtime/knowledge/knowledge_base.json`、`runtime/knowledge/adoption_logs/`
- 最近一次 R3 实际产物：
  - [runtime/state/batches/r3_scaffold_adopt_20260318_211902/](/Users/yetim/project/financialanalysis/runtime/state/batches/r3_scaffold_adopt_20260318_211902/)
  - [runtime/state/governance_review/henglong_2024/20260318_211902/](/Users/yetim/project/financialanalysis/runtime/state/governance_review/henglong_2024/20260318_211902/)
  - [runtime/state/governance_review/country_garden_2024/20260318_211902/](/Users/yetim/project/financialanalysis/runtime/state/governance_review/country_garden_2024/20260318_211902/)
  - [runtime/knowledge/adoption_logs/](/Users/yetim/project/financialanalysis/runtime/knowledge/adoption_logs/)

## 3. 放行原则

1. 先看门禁，再看产能。
2. 先看可回滚，再看可扩展。
3. 先看证据闭环，再看输出外观。
4. 只要出现下面的停机条件之一，就必须停止上线。

## 4. 检查清单

### 4.1 Skill 安装校验

检查项：

- `financial-analyzer` 已安装，并能读取当前仓库内 `SKILL.md`。
- `chinamoney` 已安装，并可使用官方来源发现/下载逻辑。
- `mineru` 已安装，并可在当前环境完成 PDF 解析入口调用。
- `spreadsheet` 已安装，或其职责已被替代为可用的等价实现。
- skill 目录中没有 runtime 状态文件、registry 文件或批次产物。

通过标准：

- skill 目录只包含能力定义、模板或参考文档，不包含 `runtime/state/**` 之类的动态数据。
- 生产化入口能明确找到外部 runtime，而不是回退到 skill 内部写路径。

失败动作：

- 先修复安装或绑定，再继续。
- 如果发现 skill 目录内已经出现动态状态写入，立即停止上线。

### 4.2 Runtime 配置校验

检查项：

- `runtime/runtime_config.json` 存在，且 `contract_version=runtime_config_v1`。
- `project_root` 与 `runtime_root` 都是绝对路径，且指向当前仓库。
- `paths.knowledge_base`、`paths.knowledge_adoption_log_dir`、`paths.processed_reports_registry`、`paths.batch_root`、`paths.governance_review_root`、`paths.logs_root`、`paths.tmp_root` 均存在或可创建。
- `policies.require_paths_under_project_root=true`。
- `policies.forbid_skill_dir_writes=true`。
- runtime-bound 入口遇到缺配置、非法配置、越界路径、缺失正式知识库时会直接失败，不 silent fallback。

通过标准：

- `runtime_config` 能稳定定位正式 runtime，且与最近一次 R3 的路径口径一致。
- 运行时不会自动写入 `~/.codex/skills`。

失败动作：

- 先修复 `runtime_config` 或 runtime 目录结构，再继续。
- 如果入口存在 silent fallback，立即停止上线。

### 4.3 Registry 状态校验

检查项：

- `runtime/state/registry/processed_reports/processed_reports.json` 存在。
- registry 里可区分已处理、待处理、重跑、失败、被跳过的状态。
- registry 与 batch manifest、task results 的关系已经定型，不再靠人工口头解释。
- 最近一次 R3 不依赖临时目录中的隐式状态。

通过标准：

- 已处理财报的去重、重跑和版本追踪都能通过 registry 解释。
- 生产化入口读取 registry 时不会把历史演练目录误判成正式状态。

失败动作：

- 先修复 registry schema 或更新流程，再继续。
- 如果 registry 状态不完整但仍被用于放行，立即停止上线。

### 4.4 复核状态机校验

检查项：

- `chapter_review_ledger.jsonl` 采用 append-only 记录。
- 状态链至少能表达：`scaffold_ready -> reviewing -> reviewed -> adopt_ready -> adopted -> finalized`。
- 退化分支至少能表达：`blocked`、`rejected`、`rolled_back`。
- `adoption_gate` 只在证据闭环、delta 完整、review 通过时为 `true`。
- `finalization_gate` 只在整案收口条件满足时为 `true`。
- 最新一条有效 ledger 记录能代表该章节当前状态。

通过标准：

- 最近一次 R3 的 review ledger 能明确看出章节从 scaffold 到 adopted，再到回滚验证和最终收口的轨迹。
- `finalized` 只代表正式收口，不再混用为抽取完成。

失败动作：

- 先修复状态机定义或写入逻辑，再继续。
- 如果 ledger 不能解释当前章节状态，立即停止上线。

### 4.5 Adoption Log 完整性校验

检查项：

- adoption log 采用 canonical 八分区：
  - `identity`
  - `source`
  - `review`
  - `operations`
  - `evidence_refs`
  - `hashes`
  - `rollback`
  - `audit`
- `identity` 至少包含 `adoption_id`、`delta_version`、`logged_at`、`result`。
- `hashes` 至少包含 `before_hash`、`after_hash`、`knowledge_base_version_before`、`knowledge_base_version_after`。
- `rollback` 至少包含 `enabled`、`backup_path`、`rollback_log_path`、`strategy`。
- `audit` 至少包含 `adoption_id`、`logged_at`、`result`、`delta_path`、`knowledge_base_path`、`backup_path`、`summary`。
- `source`、`review`、`evidence_refs`、`audit` 之间能互相对上同一条章节采纳事件。
- 兼容用 flat 字段别名可以存在，但不能代替 canonical 结构。

通过标准：

- 最近一次 R3 的 adoption log 能被 `show_knowledge_adoption.py` 直接摘要，并能追到对应 `backup_path` 与 `delta_path`。
- 回滚日志存在时，能证明知识库恢复到写入前快照。

失败动作：

- 先补齐缺失字段，再继续。
- 如果 adoption log 缺少 canonical 分区、hash、rollback 轨迹或 audit 轨迹，立即停止上线。

### 4.6 失败重跑策略

检查项：

- 模板抽取失败时，只重跑单案 scaffold，不把失败的章节写入正式知识库。
- 复核或写入失败时，先修复证据、delta 或状态机，再重跑 adoption。
- 回滚验证失败时，不允许直接进入正式放行。
- 失败产物、日志和 manifest 能区分“输入失败”“复核失败”“写入失败”“回滚失败”。

通过标准：

- 每一种失败都能被定位到具体层级，而不是笼统归因。
- 重新运行不会污染 registry、knowledge_base 或 review ledger 的正式状态。

失败动作：

- 先修复失败原因，再重跑。
- 如果重跑会覆盖尚未审计的正式状态，立即停止上线。

### 4.7 回滚策略

检查项：

- 每条 adoption log 都对应一个独立备份快照。
- 回滚以单条 adoption log 为原子单元。
- 回滚后必须记录 `rollback_log_path`。
- 回滚动作只恢复正式知识库，不回写 `chapter_records.jsonl`，不重写 Soul 结构。
- 最近一次 R3 已验证至少一条正常采纳和一条回滚恢复。

通过标准：

- 能从 `backup_path` 恢复知识库快照。
- 能在 ledger 里把对应章节标记为 `rolled_back`。
- 回滚后可以再采纳，但必须重新生成对应 adoption log。

失败动作：

- 回滚失败时停止上线。
- 如果不能确认恢复结果与回滚前一致，立即停机。

### 4.8 人工抽检点

检查项：

- 抽查一条 `adopted` adoption log。
- 抽查一条 `rolled_back` adoption log 或 rollback log。
- 抽查一条 `finalized` review ledger 记录。
- 抽查一份 `run_manifest.json`，确认 `status=success`、`script_output_mode=scaffold_only`、`codex_review_required=true`。
- 抽查一份正式 `analysis_report.md`。
- 抽查一份正式 `financial_output.xlsx`。
- 抽查一份 `chapter_review_ledger.jsonl`，确认状态流转正常。
- 抽查最近一次 R3 的 `case_summary.md` 和 `case_results.json`。

通过标准：

- 抽检样本能互相解释：ledger 能指向 adoption log，adoption log 能指向 delta 和 backup，正式输出能回指证据。
- 抽检结果与自动校验结果一致。

失败动作：

- 只要抽检发现一处证据链断裂，就暂停上线。

## 5. 必须停止上线的情况

出现以下任一问题，必须停止上线：

1. `runtime_config` 缺失、非法、越界，或 runtime-bound 入口仍存在 silent fallback。
2. `skill` 目录中出现运行态数据、registry、批次产物或自我改写痕迹。
3. `processed_reports` registry 无法解释去重、重跑、历史状态或当前批次关系。
4. `chapter_review_ledger.jsonl` 的状态机不完整，或 `adoption_gate` / `finalization_gate` 语义不一致。
5. adoption log 缺少 canonical 八分区，或缺少 `hashes`、`rollback`、`audit` 关键字段。
6. 回滚不能从 `backup_path` 恢复，或恢复后状态无法验证。
7. 正式 `knowledge_base.json`、`analysis_report.md`、`financial_output.xlsx` 之间证据链断裂。
8. 抽检发现 `adopted`、`rolled_back`、`finalized` 三类状态被混用或误标。
9. `run_manifest.json` 不满足 `status=success`、`script_output_mode=scaffold_only`、`codex_review_required=true`。
10. 发现任何未审计的正式知识写入。
11. 最近一次验证结果与当前产物不一致，且无法解释差异来源。

## 6. 推荐放行顺序

1. 先通过 skill 安装与 runtime 配置校验。
2. 再确认 registry 和 review ledger 的状态可解释。
3. 再抽查 adoption log、回滚日志和正式输出。
4. 最后做一次“必须停止上线”的反向模拟，确认门禁能拦住错误状态。

## 7. 证据锚点

最近一次 R3 可作为 go-live 的基线证据，重点看：

- [runtime/state/batches/r3_scaffold_adopt_20260318_211902/batch_manifest.json](/Users/yetim/project/financialanalysis/runtime/state/batches/r3_scaffold_adopt_20260318_211902/batch_manifest.json)
- [runtime/state/batches/r3_scaffold_adopt_20260318_211902/case_results.json](/Users/yetim/project/financialanalysis/runtime/state/batches/r3_scaffold_adopt_20260318_211902/case_results.json)
- [runtime/state/governance_review/henglong_2024/20260318_211902/case_summary.md](/Users/yetim/project/financialanalysis/runtime/state/governance_review/henglong_2024/20260318_211902/case_summary.md)
- [runtime/state/governance_review/country_garden_2024/20260318_211902/case_summary.md](/Users/yetim/project/financialanalysis/runtime/state/governance_review/country_garden_2024/20260318_211902/case_summary.md)
- [runtime/knowledge/adoption_logs/](/Users/yetim/project/financialanalysis/runtime/knowledge/adoption_logs/)

## 8. 结论

只有当上面的检查项都通过，且没有任何停机条件被触发时，项目才算进入正式投入使用状态。
