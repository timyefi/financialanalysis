# 数据契约与运行态

这份文档只说明最重要的文件、目录和产物关系，让开发者知道什么该看、什么该改、什么不能碰。

## 关键产物

- `run_manifest.json`：一次运行的状态和来源记录。
- `chapter_records.jsonl`：章节级抽取与摘要记录。
- `notes_workfile.json`：附注定位和处理工作文件。
- `analysis_report_scaffold.md`：草稿报告。
- `final_data_scaffold.json`：草稿结构化结果。
- `soul_export_payload_scaffold.json`：对外交付草稿。

## 正式产物

- `financial_output.xlsx`
- `analysis_report.md`
- `final_data.json`
- `soul_export_payload.json`

## 运行态边界

- 运行态目录只放动态数据。
- skill 目录只放能力定义和参考文档。
- 不把 runtime 数据写回 skill 自身。

## BondClaw 资产骨架

以下目录是 BondClaw V1 的可开发骨架，后续新功能优先往这些地方补：

- `contracts/`
- `provider-registry/`
- `prompt-library/`
- `research-brain/`
- `research-brain/case-library/`
- `desktop-shell/research_brain/`
- `desktop-shell/lead_capture/`
- `lead-capture/`
- `lead-capture/manifest.json`
- `lead-capture/queue.example.json`
- `research-writing/`

推荐先运行 `contracts/validate_bondclaw_assets.py`，它会检查这几类骨架是否仍然可读。

如果你想看完整目录，可以运行：

- `python3 financial-analyzer/scripts/bondclaw_assets.py --catalog`
- `python3 financial-analyzer/scripts/bondclaw_assets.py --providers`
- `python3 financial-analyzer/scripts/bondclaw_assets.py --roles`

如果你只想看某个角色或某个 prompt，也可以用 `--role` / `--prompt` 直接定位。

对应的适配层脚本位于：

- `financial-analyzer/scripts/bondclaw_shell.py`
- `financial-analyzer/scripts/bondclaw_providers.py`
- `financial-analyzer/scripts/bondclaw_runtime.py`

如果 UI 只想认一个入口，优先用 `bondclaw_runtime.py`。

桌面壳的配套骨架位于：

- `desktop-shell/bridge/settings_store.py`
- `desktop-shell/bridge/runtime_client.py`
- `desktop-shell/home/home_model.py`
- `desktop-shell/launch_bondclaw.py`

## 你在开发时最需要记住的事

- 草稿不是最终结论。
- 产物名称本身就是契约的一部分。
- 路径和命名尽量稳定，不要随手改。
