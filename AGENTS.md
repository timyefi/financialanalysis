# Repository Guidelines

## Project Structure & Module Organization
根目录主要存放年报 PDF、分析产出 `.md/.xlsx`，以及两个辅助脚本：`run_mineru.py` 用于触发 PDF 转 Markdown，`generate_henglong_report.py` 用于生成示例 Excel 报告。核心分析逻辑位于 `financial-analyzer/`：`scripts/` 放主程序，`templates/` 放行业模板，`references/` 放产物契约与流程说明，`testdata/` 放手工测试输入，`test_runs/` 保存回归运行结果。

## Build, Test, and Development Commands
本仓库没有统一构建系统，日常开发直接运行 Python 脚本。

```powershell
py ".\run_mineru.py"
py ".\generate_henglong_report.py"
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
