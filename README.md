# financialanalysis

本项目聚焦于债券发行主体研究的资料采集、文档解析、附注优先分析、对外交付产物生成和运行治理。

这个仓库的目标不是做一个单脚本工具，而是把一条可复用、可交接、可扩展的研究工作流整理成标准工程结构，让新加入的开发者能够快速理解项目，并在此基础上继续开发。

## 概览

仓库按常见开源项目方式组织：根目录放项目首页、贡献说明和关键入口，`docs/` 放技术文档索引与主题文档，`financial-analyzer/`、`chinamoney/`、`mineru/` 放三个核心能力模块。

## 这个项目解决什么问题

债券研究通常需要同时处理三类材料：

- 从官方来源获取财报、公告和披露文件。
- 把 PDF、Word、PPT、图片等材料转换成可读、可检索的中间文本。
- 在大量非结构化内容中定位附注、提取证据、形成结论，并输出标准化底稿和报告。

这个项目把上述流程拆成独立模块，避免把采集、解析、分析和导出混成一个难以维护的大脚本。

## 业务逻辑

这个项目的业务目标，是围绕债券发行主体的财务与信用信息，形成一条可复用的研究链路。核心不是做摘要，而是把“主体是谁、财务结构怎样、债务压力在哪里、现金是否够用、条款是否有保护、风险是否已经显性化”这些问题，放到同一套流程里去看。

项目中的财务分析主要做以下几件事：

1. 识别主体和报告类型，确认是哪一家主体、哪一年、哪类披露材料。
2. 优先定位财报附注，提取债务结构、受限资金、担保、或有事项、现金流、资本化利息等关键证据。
3. 把报表正文与附注信息合并成可核对的工作底稿，而不是只看汇总表。
4. 基于工作底稿生成分析结论、风险判断和结构化输出。
5. 继续把稳定口径沉淀为知识输入，供后续案例复用和回滚。

换句话说，这个仓库里的分析不是泛化的财务报表阅读，而是面向债券研究的主体信用分析。

## 核心能力

1. 数据采集：从中国货币网等官方来源下载财报和披露材料。
2. 文档解析：将 PDF、Word、PPT 和图片转成 Markdown 或结构化中间文本。
3. 标准化处理：识别主体、期间、报告类型、附注范围和章节结构。
4. 分析工作流：按附注优先原则生成分析底稿、报告草稿和结构化结果。
5. 运行治理：记录 manifest、状态、失败原因、重跑信息和正式产物。
6. 知识治理：把案例中的稳定口径整理成可审阅、可回滚的知识输入。

## 关键文档与执行顺序

这几个文档是理解和使用本仓库的主入口，建议按下面顺序阅读：

1. [automation_blueprint.md](automation_blueprint.md)：项目总蓝图，定义仓库的总体目标、模块分层和长期协作口径。
2. [codex_execution_runbook.md](codex_execution_runbook.md)：把总蓝图转成可执行的对话流程，说明每个线程应该怎么推进。
3. [run_mineru.py](run_mineru.py)：文档解析的实际执行入口，用于把 PDF 转成后续分析可消费的中间文本。
4. [knowledge_adoption_delta_contract.md](knowledge_adoption_delta_contract.md)：定义正式知识写入时需要提交的 delta 和审计外壳。
5. [soul_excel_spec_v1.md](soul_excel_spec_v1.md)：定义对外交付 Excel 成品的结构骨架、可选模块和证据索引。

如果你是第一次接触这个仓库，建议先读 [automation_blueprint.md](automation_blueprint.md)，再读 [codex_execution_runbook.md](codex_execution_runbook.md)，最后看 [run_mineru.py](run_mineru.py) 的执行入口和后两份契约文档。

## 工作流总览

```text
任务定义(issuer-year)
	-> 数据采集层（ChinaMoney）
	-> 文档理解层（MinerU）
	-> 文档标准化层（定位主体、期间、附注范围）
	-> 分析引擎层（financial-analyzer）
	-> 运行治理层（manifest / 状态 / 重跑）
	-> 正式产物层（工作底稿、报告、结构化输出）
	-> 知识治理层（review / adopt / rollback）
```

## 仓库结构

- `README.md`：项目首页。
- `CONTRIBUTING.md`：贡献与协作说明。
- `docs/`：技术文档索引与主题文档。
- `financial-analyzer/`：分析工作流与参考实现。
- `chinamoney/`：数据下载能力。
- `mineru/`：文档解析能力。
- `cases/`：示例案例与产物。
- `runtime/`：运行态目录。

## 三个能力模块

### `financial-analyzer`

财务分析技能主模块，负责围绕债券发行主体做结构化分析：先识别报告类型和主体，再定位附注与核心证据，接着抽取债务、现金、受限资金、担保、或有事项和现金流等信息，最后形成可复核的工作底稿、分析报告和结构化结果。

- 入口：`financial-analyzer/scripts/`
- 参考说明：`financial-analyzer/references/`
- 核心约束：附注优先、先草稿后正式、先复核后采纳。

### `chinamoney`

数据采集模块，负责从中国货币网获取财报、评级报告和披露材料。

- 入口：`chinamoney/`
- 重点：先建立会话，再访问接口或下载链接。
- 适用场景：发行主体年报、评级文件、存续期披露材料。

### `mineru`

文档解析模块，负责把非结构化文档转换为可读中间文本。

- 入口：`mineru/`
- 重点：处理 PDF、Word、PPT、图片等文档。
- 适用场景：年报解析、附注定位、图片或扫描件 OCR。
- 配置模板：先复制 `mineru/config.example.json` 为 `mineru/config.json`，再填写自己的 `MINERU_TOKEN`。

## 主要产物

### 草稿产物

- `run_manifest.json`
- `chapter_records.jsonl`
- `notes_workfile.json`
- `analysis_report_scaffold.md`
- `final_data_scaffold.json`
- `soul_export_payload_scaffold.json`

### 正式产物

- `financial_output.xlsx`
- `analysis_report.md`
- `final_data.json`
- `soul_export_payload.json`

### 运行态产物

- `runtime/knowledge/knowledge_base.json`
- `runtime/knowledge/adoption_logs/`
- `runtime/state/registry/processed_reports/processed_reports.json`
- `runtime/state/batches/`
- `runtime/state/logs/`

## 文档入口

1. [docs/README.md](docs/README.md)
2. [docs/quickstart.md](docs/quickstart.md)
3. [docs/architecture.md](docs/architecture.md)
4. [docs/contracts.md](docs/contracts.md)
5. [docs/troubleshooting.md](docs/troubleshooting.md)
6. [docs/projects.md](docs/projects.md)

## 快速上手 issues

下面这几条 issue 已经把常见的启动、案例复盘、调试经验和思路沉淀好了，适合新同事直接打开照着看：

1. [Codex 快速上手包：新同事协作与启动指南](issues/8)
2. [案例复盘：万科 2024 年报分析与调试经验](issues/9)
3. [案例复盘：恒隆地产与 Soul 模块化设计](issues/10)
4. [调试与排障：常见故障和运行坑](issues/11)

如果你要开始开发，建议先看 [docs/quickstart.md](docs/quickstart.md)，再看 [docs/architecture.md](docs/architecture.md) 和 [docs/contracts.md](docs/contracts.md)。

## 开发协作

如果你要参与修改、添加或重构，先阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。如果你要理解仓库级工作方式，再看 [AGENTS.md](AGENTS.md) 和 [automation_blueprint.md](automation_blueprint.md)。

## 运行约束

- 不要把运行态数据写回 skill 目录。
- 不要把草稿产物当作正式结论。
- 不要把采集、解析、分析和导出混成一个不可拆分的脚本。

## 许可

Author and rights holder: 叶青 YEQING.

This repository is for non-commercial use only. Commercial use, resale,
sublicensing, paid hosting, and commercial integration are prohibited. See
[LICENSE](LICENSE) for the full terms.
