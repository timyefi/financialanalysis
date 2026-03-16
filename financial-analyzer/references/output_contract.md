# Output Contract

## 固定文件名

运行目录内固定保留以下文件名：

- `run_manifest.json`
- `chapter_records.jsonl`
- `focus_list.json`
- `final_data.json`
- `soul_export_payload.json`
- `pending_updates.json`
- `analysis_report.md`
- `financial_output.xlsx`

## 导出规则

- JSON 导出优先写稳定核心字段，再附加扩展字段。
- `soul_export_payload.json` 是 W3 -> W4 的正式导出契约；`final_data.json` 保留为分析聚合产物，不再直接作为 Soul 输入。
- Markdown 报告先给动态重点，再给章节速览与待固化更新。
- Excel 只消费稳定核心字段和已识别扩展字段。
- 遇到未知扩展字段时，允许忽略或降级展示，不能整体失败。
- 所有正常产物都只基于附注章节生成。

## 前向兼容

- 新版读取旧记录时，允许字段缺失。
- 旧版导出逻辑不应依赖新增扩展字段是否存在。
- 新主题第一次出现时，优先进入 `pending_updates.json`，而不是强制改历史数据。

## 失败契约

如果缺少 `notes_workfile`、附注目录为空或边界无效：

1. 脚本非零退出。
2. 仅生成失败态 `run_manifest.json`。
3. `run_manifest.json` 中必须带 `failure_reason`。
