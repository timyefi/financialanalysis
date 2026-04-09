# Repository Guidelines

## Project Structure & Module Organization
根目录主要存放年报 PDF、分析产出 `.md/.xlsx`，以及辅助脚本 `run_mineru.py`。核心分析逻辑位于 `financial-analyzer/`：`scripts/` 放主程序，`templates/` 放行业模板，`references/` 放产物契约与流程说明，`testdata/` 放手工测试输入，`test_runs/` 保存回归运行结果。

## Planning & Canonical Docs
本项目的整体性设计、阶段计划、workstream 拆解、跨对话协作约定，统一以根目录 `automation_blueprint.md` 为主入口和最高优先级项目文档。后续新对话或新 agent 开始工作时，如任务不是纯局部修复，应先阅读该文件，再阅读当前任务对应的专项文档。

与 Soul Excel 相关的专项文档按以下关系使用：
- `automation_blueprint.md`：总目标、总架构、总计划、状态看板
- `codex_execution_runbook.md`：Codex 对话/agent 的执行顺序与启动方式
- `production_execution_runbook.md`：项目进入正式投入使用阶段后的生产化对话启动包
- `codex_review_and_finalization_runbook.md`：scaffold-only 之后的复核/直写/收尾 prompt pack
- `knowledge_adoption_delta_contract.md`：章节级知识直写的 delta 契约与字段口径
- `soul_excel_spec_v1.md`：Soul 结构规范
- `soul_excel_case_analysis.md`：案例归纳依据
- `excel_skill_adoption_plan.md`：Excel 生成技术路线与工具选择

原则上不要在 `AGENTS.md` 重复蓝图内容；如项目方向、workstream 边界、阶段状态发生变化，应优先更新上述文档，而不是只在对话中说明。

## Cross-Session Workflow
如果一次工作涉及结构性决策、模块边界变化、优先级变化或阶段推进，结束前应同步更新 `automation_blueprint.md` 中的相关部分，至少保证“当前状态看板”和“下一步”可供下一个对话直接接手。

如任务只涉及某个局部模块，也应在开始时先明确当前属于哪个 workstream，避免在同一对话中同时重构采集、解析、分析、导出等多个层次。

如果一次工作涉及章节复核、知识直写、rollback 或正式成稿收尾，结束前还应同步更新 `codex_review_and_finalization_runbook.md` 与 `knowledge_adoption_delta_contract.md`。

## Git Branch Policy
本项目当前采用单分支策略：本地与远程默认只保留 `main`，不维护长期存在的功能分支、`codex/*` 分支或并行发布分支。除非用户明确要求或遇到高风险隔离性改动，否则所有 Codex 对话都应直接基于 `main` 工作。

开始新对话时，应先确认当前分支为 `main`，并默认在 `main` 上完成修改、验证、提交和推送；完成后不要额外创建或保留分支。

## Build, Test, and Development Commands
本仓库没有统一构建系统，日常开发直接运行 Python 脚本。

```powershell
py ".\run_mineru.py"
py ".\financial-analyzer\scripts\financial_analyzer.py" --md "C:\path\report.md" --notes-workfile "C:\path\notes_workfile.json" --run-dir "C:\path\run_dir"
```

前两个命令分别生成 Markdown 解析结果和示例财务分析 Excel；第三个命令是附注优先分析的正式入口。运行命令时统一使用 PowerShell，并确保文件读写为 UTF-8。

## Coding Style & Naming Conventions
Python 采用 4 空格缩进，保持小函数、直接逻辑、少做跨文件改动。模块与脚本名使用 `snake_case`，JSON 字段名保持小写下划线风格，如 `notes_start_line`。时间处理统一 `import datetime`，禁止 `from datetime import ...`。涉及中文路径、日志或 Markdown/JSON 读写时，必须显式指定 `encoding="utf-8"`。

## Testing Guidelines
当前没有独立测试框架，使用样例文件做脚本级回归。优先复用 `financial-analyzer\testdata\henglong_notes_workfile.json` 和 `financial-analyzer\test_runs\` 中的既有产物做比对。提交前至少验证：脚本可运行、`run_manifest.json` 正常生成、`analysis_report.md` 与 `financial_output.xlsx` 路径正确。

## Commit & Pull Request Guidelines
现有 Git 历史较少，且最近提交信息不规范；后续请统一使用简短祈使句，建议采用 `feat:`, `fix:`, `docs:` 前缀，例如 `fix: tighten notes range validation`。PR 需说明变更目的、影响文件、验证命令，以及是否更新了示例产物；若修改报告模板或输出格式，请附关键截图或产物路径。

## Data & Output Handling
不要批量提交无关的大型 PDF、日志或临时运行目录。新增案例时，优先把输入放在根目录或 `testdata/`，把可复现输出放在 `test_runs/<case_name>/`，避免覆盖既有样本。
