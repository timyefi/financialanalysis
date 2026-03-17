---
name: financial-analyzer
description: 企业年报附注优先财务分析 skill。用于对 A 股、港股或交易商协会报告先识别财报附注，再通过关键词搜索、抽样阅读和主附注目录建立来驱动逐章分析，最终生成 chapter records、动态重点、待固化更新和统一导出产物。
---

# Financial Analyzer

本 skill 采用“经验式附注工作流 + 最小编排脚本”。

## 现状评估（当前版本）

### 优势

- 流程边界清晰：先定位附注，再做逐章分析，能显著降低正文噪声干扰。
- 失败契约明确：缺失可信附注边界时直接失败，避免“看起来完成但实际偏航”。
- 产物稳定：固定 7 个成功产物，便于后处理、回放和审计。

### 主要短板

- 缺少量化验收门槛：例如附注覆盖率、章节有效率、证据密度没有明确阈值。
- CLI 示例偏 Windows，跨平台可复制性不足。
- 缺少“最小自检清单”：运行后难以快速判断结果是否可用。
- 新增主题只说“先放 pending_updates”，但缺少优先级和升级标准。

### 优化优先级（建议按顺序落地）

1. 增加运行后验收清单（P0）。
2. 统一跨平台命令示例（P0）。
3. 增加待固化更新分级（P1）。
4. 增加常见失败原因与修复动作（P1）。

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
6. 将附注定位结果写成 `notes_workfile`。
7. 最后调用主脚本生成固定产物。

## 正文边界

- 正文只用于元信息识别和附注定位。
- 正文不得进入 `chapter_records.jsonl`。
- 正文不得参与 `focus_list.json`、`final_data.json` 和最终结论。
- 找不到可信附注区间时直接失败，不降级全文分析。

## 脚本入口

唯一入口：

- `scripts/financial_analyzer.py`

命令行接口（跨平台示例）：

```bash
python financial-analyzer/scripts/financial_analyzer.py \
  --md /path/to/report.md \
  --notes-workfile /path/to/notes_workfile.json \
  --run-dir /path/to/run_dir
```

生产/批处理入口：

- `scripts/run_batch_pipeline.py`
- `scripts/knowledge_manager.py`

推荐显式传入项目内 runtime 配置：

```bash
python financial-analyzer/scripts/run_batch_pipeline.py \
  --runtime-config /abs/path/to/repo/runtime/runtime_config.json \
  --task-list /path/to/task_list.json
```

```bash
python financial-analyzer/scripts/knowledge_manager.py \
  --runtime-config /abs/path/to/repo/runtime/runtime_config.json \
  build-review-bundle \
  --input /path/to/case_a/pending_updates.json /path/to/case_b/pending_updates.json /path/to/case_c/pending_updates.json \
  --output-dir /path/to/output_dir
```

只有在当前工作目录本身位于项目仓库内时，才可以省略 `--runtime-config`，依赖自动发现。

## 生产态 Runtime 绑定

已安装 skill 在生产态必须绑定项目内 runtime，而不是把动态状态写回 `~/.codex/skills`。

### `runtime_config` 发现顺序

1. CLI 参数 `--runtime-config`
2. 环境变量 `FINANCIAL_ANALYZER_RUNTIME_CONFIG`
3. 从当前工作目录向上逐级搜索 `runtime/runtime_config.json`

约束：

- 不扫描 skill 安装目录。
- 找不到配置时直接失败，不回退到 `financial-analyzer/test_runs/batches`。
- `runtime_config.json`、`project_root`、`runtime_root`、`paths.*` 必须满足项目内 runtime 契约。

### 找不到配置时的处理

- `run_batch_pipeline.py` 和读取正式知识基线的 `knowledge_manager.py` 属于 runtime-bound 入口。
- 找不到 `runtime_config.json`、配置非法、路径越界、或正式 `knowledge_base.json` 缺失时，命令必须直接失败并提示修复方式。
- 运行态目录不存在时允许自动创建，但不会自动改写 skill 文档或 skill 目录内容。

### 哪些内容必须走外部 runtime

- `runtime/runtime_config.json`
- `runtime/knowledge/knowledge_base.json`
- `runtime/state/registry/processed_reports/processed_reports.json`
- `runtime/state/batches/`
- `runtime/state/governance_review/`
- `runtime/state/logs/`
- `runtime/state/tmp/`
- 相关 lock、snapshot、batch 运行态文件

### 哪些内容可以保留在项目仓库

- `SKILL.md`、`references/`、模板、脚本源码
- 输入 PDF、Markdown、`notes_workfile`
- `financial-analyzer/test_runs/` 等开发/回归目录
- 单案 `financial_analyzer.py --run-dir <path>` 的显式输出目录

### 明确禁止

以下内容不得写入 `~/.codex/skills`：

- 任意 `runtime_config`
- 任意正式 `knowledge_base` 副本
- 任意 registry / batches / governance_review / logs / tmp 运行态目录
- 运行中对 `SKILL.md`、`references/*.md` 的自发改写

## notes_workfile 契约

顶层至少包含：

- `notes_start_line`
- `notes_end_line`
- `locator_evidence`
- `notes_catalog`

`notes_catalog` 每项至少包含：

- `note_no`
- `chapter_title`
- `start_line`
- `end_line`
- `evidence`

## 稳定产物

每次成功运行必须生成：

- `run_manifest.json`
- `chapter_records.jsonl`
- `focus_list.json`
- `final_data.json`
- `soul_export_payload.json`
- `pending_updates.json`
- `analysis_report.md`
- `financial_output.xlsx`

失败时只生成失败态 `run_manifest.json`。

## 运行后最小验收清单（新增）

成功态至少满足以下条件：

1. `run_manifest.json` 中 `status=success`，且存在 `notes_locator`、`notes_catalog_summary`。
2. `chapter_records.jsonl` 每条记录都包含核心字段：`chapter_no`、`chapter_title`、`status`、`summary`。
3. `focus_list.json` 不为空，且每个 focus 都有 `evidence_chapters`。
4. `final_data.json` 至少包含：`entity_profile`、`key_conclusions`、`topic_results`。
5. `soul_export_payload.json` 至少包含固定骨架模块、`module_manifest` 和 `evidence_index`。
5. `pending_updates.json` 中每条候选项都包含：
   `source`、`evidence`、`applicable_scope`、`status`、`introduced_in`、`confidence`。

失败态至少满足以下条件：

1. 脚本非零退出。
2. 仅存在失败态 `run_manifest.json`。
3. `run_manifest.json` 必须给出可执行的 `failure_reason`。

## pending_updates 分级（新增）

- `status=candidate`：首次出现，证据不足，仅观察。
- `status=validated`：跨 2 份以上报告复现，且不破坏现有产物契约。
- `status=promoted`：完成契约评估并已合入正式流程。

建议配合 `confidence` 使用：

- `0.0-0.49`：保留在 candidate。
- `0.50-0.79`：可升到 validated。
- `0.80-1.00`：可进入 promoted 评审。

## 常见失败原因与修复动作（新增）

- `failure_reason=notes_not_found`
  - 修复：补充关键词并重新抽样验证边界。
- `failure_reason=notes_boundary_invalid`
  - 修复：核对 `notes_start_line/end_line` 是否落在同一附注区间。
- `failure_reason=empty_notes_catalog`
  - 修复：确认只提取主附注编号，避免子附注误拆。

## 进化原则

- 新格式先记录到 `pending_updates.json`，不要直接写死到主脚本。
- 记录新的附注定位关键词、编号样式、标题变体、边界现象。
- 调整产物契约时读取 `references/open_record_protocol.md`、`references/output_contract.md` 和 `references/soul_export_contract.md`。
