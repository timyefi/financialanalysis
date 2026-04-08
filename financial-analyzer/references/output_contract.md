# Output Contract

## 模板脚本固定文件名

模板脚本成功态在运行目录内固定保留以下文件名：

- `run_manifest.json`
- `chapter_records.jsonl`
- `analysis_report_scaffold.md`
- `focus_list_scaffold.json`
- `final_data_scaffold.json`
- `soul_export_payload_scaffold.json`

## Codex 复核后的正式文件名

完成逐章复核和最终汇总后，运行目录内正式交付文件名为：

- `financial_output.xlsx`
- `analysis_report.md`
- `final_data.json`
- `soul_export_payload.json`

## 导出规则

- 模板脚本输出的 scaffold 只能视为草稿，不能未经复核直接作为最终交付。
- 主链路默认停在 scaffold；正式 `financial_output.xlsx` 需要在 Codex 完成标准化 workpaper 后显式 formalize，正式 `analysis_report.md` 只能建立在该 workpaper 之上。
- `financial_output.xlsx` 是客户可展示的正式底稿，不是报告的附属摘要。
- `soul_export_payload.json` 仍是结构化中间契约，供底稿与报告共享稳定字段，但不替代 workpaper 本身。
- Excel 只消费稳定核心字段和已确认结构，不消费内部知识治理元数据。
- 如需版式收尾，可再用 `spreadsheet` 做格式微调，但不能改动底稿口径。
- 所有正常分析产物都只基于附注章节生成。

## 生成原则

- 正式输出必须由 Skill 驱动的逐章分析结果生成，而不是由固定脚本直接拼接成品。
- 每个主体的 `financial_output.xlsx`、`analysis_report.md`、`final_data.json` 和 `soul_export_payload.json` 都可以在结构上遵循同一套正式契约，但内容深度、专题模块和行项展开必须随本案章节覆盖与知识库覆盖动态变化。
- 任何只靠 scaffold、缓存副本或其他案例正式产物拼接出来的结果，都不能视为正式交付。
- 如果某主体只能覆盖部分章节或部分专题，应保持最小骨架并显式标注未识别与未抽取到的空位，不得用固定硬编码内容填充。

## 前向兼容

- 新版读取旧记录时，允许字段缺失。
- 旧版逻辑看到 scaffold 文件时，不应将其误认为正式分析完成。
- 不再要求主链路生成 `pending_updates.json`。
- 旧版或历史案例的输出结构只能作为参考，不得反向约束本案的章节覆盖或专题展开。

## 失败契约

如果缺少 `notes_workfile`、附注目录为空、边界无效：

1. 脚本非零退出。
2. `run_manifest.json` 中必须带 `failure_reason`。
3. 对于前置输入失败，可只生成失败态 `run_manifest.json`。
4. 失败时不得写成功态 scaffold 或正式交付文件。
