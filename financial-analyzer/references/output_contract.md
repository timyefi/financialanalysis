# Output Contract

## 模板脚本最小固定文件名

模板脚本成功态在运行目录内固定保留以下主线必需文件名：

- `run_manifest.json`
- `notes_workfile.json`
- `chapter_records.jsonl`

以下 scaffold 仅作调试或兼容用途，不属于主线必需文件：

- `analysis_report_scaffold.md`
- `focus_list_scaffold.json`
- `final_data_scaffold.json`
- `soul_export_payload_scaffold.json`

## Codex 复核后的主线正式文件名

完成逐章复核和最终汇总后，运行目录内主线正式交付文件名为：

- `financial_output.xlsx`
- `analysis_report.md`

知识库优化不以单案文件名体现，而是通过 `runtime/knowledge/adoption_logs/` 和正式 `knowledge_base.json` 落地。

Excel 主线必须先生成以下强制中间产物：

- `financial_output_formula.xlsx`

以下仅为可选兼容输出，不属于主线完成标准：

- `final_data.json`
- `soul_export_payload.json`
- `financial_output_formula_view.xlsx`
- `financial_output_formula_fit.xlsx`
- `financial_output_fit.xlsx`

## 导出规则

- 模板脚本输出的 scaffold 只能视为草稿，不能未经复核直接作为最终交付。
- 主链路默认停在最小中间产物；正式 `financial_output.xlsx` 必须由 Skill 在当前 `run_dir` 内编写一次性临时脚本显式生成，不能由仓库级固定脚本直接导出。
- Excel 正式化顺序固定为：先生成 `financial_output_formula.xlsx`，再由公式版固化出 `financial_output.xlsx`。
- `financial_output_formula.xlsx` 是审计层 workpaper，要求尽量保留公式关系、派生逻辑和勾稽链路；`financial_output.xlsx` 是对外最终版，默认固化为稳定展示结果。
- Excel 生成过程是非标准化的，允许按案例调整 sheet 结构和字段组织，但必须保证证据闭环与口径一致。
- 整条主线以 `chapter_review_ledger.jsonl` 为核心；没有逐章阅读与判断，就不能进入正式 Excel 与正式报告。
- 正式 `analysis_report.md` 只能建立在“公式版已核对、最终版已固化”的 `financial_output.xlsx` workpaper 之上。
- `financial_output.xlsx` 是客户可展示的正式底稿，不是报告的附属摘要。
- `soul_export_payload.json` 仍是可选结构化中间契约，供需要下游兼容时共享稳定字段，但不替代 workpaper 本身。
- Excel 只消费稳定核心字段和已确认结构，不消费内部知识治理元数据。
- 如需版式收尾，可再用 `spreadsheet` 做格式微调，但不能改动底稿口径。
- 所有正常分析产物都只基于附注章节生成。

## 前向兼容

- 新版读取旧记录时，允许字段缺失。
- 旧版逻辑看到 scaffold 文件时，不应将其误认为正式分析完成。
- 不再要求主链路生成 `pending_updates.json`。
- `final_data.json` 和 `soul_export_payload.json` 缺失时，不应被视为主线失败，除非该运行明确声明需要兼容下游。
- `financial_output_formula_view.xlsx`、`financial_output_formula_fit.xlsx`、`financial_output_fit.xlsx` 缺失时，不应被视为主线失败，除非该运行显式要求预览、截图或排版校验。

## 失败契约

如果缺少 `notes_workfile`、附注目录为空、边界无效：

1. 脚本非零退出。
2. `run_manifest.json` 中必须带 `failure_reason`。
3. 对于前置输入失败，可只生成失败态 `run_manifest.json`。
4. 失败时不得写成功态 scaffold 或正式交付文件。
