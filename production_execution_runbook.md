# 生产化执行手册（Prompt Pack）

## 1. 这份文档解决什么问题

这份文档只解决一件事：

- 当 W1-W7 已基本完成后，如何把项目推进到“可正式投入使用”的生产化阶段。

它不是蓝图的替代品，而是生产化阶段的对话启动包。整体目标仍以 `automation_blueprint.md` 为准；日常线程组织仍以 `codex_execution_runbook.md` 为准。

## 2. 生产化阶段的核心原则

1. 不把运行时数据塞进已安装的 `skill` 目录。
2. `skill` 负责能力定义，不负责批内自我改写。
3. 项目文档负责治理口径，不负责运行时即时生效。
4. 真正需要批内动态生效的内容，统一放在外部 `runtime` 数据层。
5. 在补齐全局 registry 前，不把“10 案全真测试”视为最终投产验收。

## 3. 推荐执行顺序

| 顺序 | 类型 | 主目标 | 核心交付物 |
|------|------|--------|------------|
| 0 | 总控线程 | 维护生产化状态、排序任务 | 状态更新、下一步安排 |
| 1 | 执行线程 | 定义 runtime 外部数据层 | 目录结构、配置契约、读写边界 |
| 2 | 执行线程 | 建立全局已处理财报 registry | registry schema、去重规则、更新流程 |
| 3 | 执行线程 | 让已安装 skill 绑定外部 runtime | skill/runtime 绑定方案与代码落地 |
| 4 | 执行线程 | 定义“自动找 10 份财报”的测试入口 | 选样规则、来源记录、任务清单生成方式 |
| 5 | 执行线程 | 做冷启动全真生产仿真 | 一次完整批次运行与结果汇总 |
| 6 | 执行线程 | 形成 go-live checklist | 上线门禁、人工复核点、回滚方案 |

说明：

- 第 1 到第 3 步决定系统是否可持续运行，优先级高于全真测试。
- 第 4 步不是人工挑报告，而是让 Codex 按目标和规则生成测试样本集。
- 第 5 步要求尽量接近真实生产，而不是复用当前会话里的隐式上下文。

## 3.1 当前建议的 Skill 安装基线

基于当前仓库结构，生产化阶段建议区分三类 skill：

1. 已安装的通用 skill：例如 `spreadsheet`
2. 项目内自定义 skill：`financial-analyzer`、`chinamoney`、`mineru`
3. P5 冷启动仿真前才需要冻结版本的 skill 包

当前建议：

- 在进入 P3 前，至少安装 `financial-analyzer`
- 如果 P3 准备覆盖完整链路，建议同时安装 `chinamoney` 和 `mineru`
- `spreadsheet` 已是通用依赖，如果当前机器已安装，则无需重复处理

## 3.2 安装方式建议

在当前阶段，建议分两种安装方式：

### 开发态安装

适用于 P3 前后反复调整 `SKILL.md` 或脚本。

- 优先使用软链接，把仓库内 skill 目录链接到 `~/.codex/skills/`
- 好处是仓库内修改可以直接体现在已安装 skill 上
- 每次调整后重启 Codex 即可重新拾取

### 冷启动仿真安装

适用于 P5 的正式仿真。

- 使用复制后的冻结版本，而不是继续用开发态软链接
- 这样更接近未来正式投入使用时的真实安装状态
- 安装后重启 Codex，再开始冷启动测试

## 4. 对话启动模板

每个新对话都建议先用下面这句开场：

```text
先阅读 AGENTS.md、automation_blueprint.md、codex_execution_runbook.md、production_execution_runbook.md。确认当前在 main 分支。请先用一句话确认本线程属于生产化阶段的哪一个任务，再开始执行。
```

如果你只是要先处理 skill 安装本身，再开下面这个对话：

```text
先阅读 AGENTS.md、automation_blueprint.md、production_execution_runbook.md。当前聚焦生产化安装基线。请先核对当前 ~/.codex/skills 中已经安装了哪些 skill，再判断项目内自定义 skill（financial-analyzer、chinamoney、mineru）是否应在 P3 前安装，并给出推荐安装顺序、开发态安装方式、冷启动仿真安装方式和重启要求；如有必要，再实际完成安装。
```

## 5. 线程卡片与可复制 Prompt

## 5.1 线程 P1：Runtime 外部数据层设计

### 目标

- 明确哪些数据留在项目仓库、哪些数据放在外部 runtime、哪些绝不能放进 `~/.codex/skills`。

当前 P1 默认口径：

- 正式 runtime 根目录放在项目内 `runtime/`
- `runtime_config + knowledge_base + adoption_logs` 目录骨架进入 Git
- `registry / batches / governance_review / logs / tmp` 作为运行态状态目录，不进入 Git

### 开始前阅读

- `automation_blueprint.md`
- `runtime_external_data_layer_spec.md`

### 交付物

- `runtime` 目录结构方案
- `runtime_config` 配置契约
- 读写边界说明
- 推荐的默认路径策略
- 项目内 `runtime/` 默认落点说明

### 完成标准

1. 明确 `runtime/knowledge/knowledge_base.json` 为正式知识基线落点。
2. 明确 `runtime/state/registry/processed_reports/processed_reports.json` 为 registry 正式落点。
3. 明确 `runtime/state/batches/` 为正式批次产物根目录。
4. 明确 `runtime/runtime_config.json` 为项目内正式配置入口。
5. 明确哪些内容允许进入 Git，哪些内容绝不能写进 `~/.codex/skills`。

### 本线程不做

- 不直接实现批量分析
- 不修改 Soul 结构
- 不开始 10 案测试

### 可直接复制的 Prompt

```text
先阅读 AGENTS.md、automation_blueprint.md、codex_execution_runbook.md、production_execution_runbook.md，以及 financial-analyzer 目录下现有 scripts/references。当前聚焦生产化 P1：Runtime 外部数据层设计。请基于“skill 负责能力定义、runtime 负责动态数据、文档负责治理说明”的原则，设计正式投入使用所需的 runtime 外部数据层，至少明确目录结构、runtime_config 配置契约、knowledge_base 的推荐落点、批次产物落点、全局 registry 落点，以及哪些内容绝不能写进 ~/.codex/skills。请把方案落成仓库文档，不要只停留在回答里；不要开始实现 10 案测试。
```

## 5.2 线程 P2：全局已处理财报 Registry

### 目标

- 建立跨批次、跨历史的“已处理财报”注册表，解决去重、重跑判定和版本追踪。

### 开始前阅读

- `automation_blueprint.md`
- `runtime_external_data_layer_spec.md`
- `financial-analyzer/scripts/run_batch_pipeline.py`
- `financial-analyzer/scripts/knowledge_manager.py`

### 交付物

- registry schema
- 主键/指纹策略
- 去重与重跑规则
- 推荐存储格式与更新流程

### 本线程不做

- 不直接修改已安装 skill
- 不做最终上线验收
- 不人工指定 10 份报告名单

### 可直接复制的 Prompt

```text
先阅读 AGENTS.md、automation_blueprint.md、production_execution_runbook.md、runtime_external_data_layer_spec.md，以及 financial-analyzer/scripts/run_batch_pipeline.py、financial-analyzer/scripts/knowledge_manager.py。当前聚焦生产化 P2：全局已处理财报 registry。请基于项目内 runtime 方案，设计并实现一个跨批次、跨历史的 processed_reports registry，用于记录哪些财报已经处理过、用什么版本处理、是否需要重跑。要求给出 schema、唯一标识/文档指纹策略、去重规则、重跑规则、与 batch_manifest/task_results 的关系，并把设计写入文档；如果实现代码，要求优先保持与现有 batch runner 兼容，并将正式落点固定在 runtime/state/registry/processed_reports/processed_reports.json。不要把 registry 放进 ~/.codex/skills。
```

## 5.3 线程 P3：Skill 与 Runtime 绑定

### 目标

- 让“安装后的 skill”明确知道去哪里读写外部 runtime，而不是默认写回 skill 目录。

### 开始前阅读

- `automation_blueprint.md`
- `runtime_external_data_layer_spec.md`
- `runtime/runtime_config.json`
- `financial-analyzer/SKILL.md`
- 与运行入口相关的 scripts

### 交付物

- skill/runtime 绑定机制
- 配置读取优先级
- 缺省路径与报错策略
- 必要代码改造或文档说明

### 当前已定口径（2026-03-17）

- `runtime_config` 发现顺序固定为：
  1. CLI 参数 `--runtime-config`
  2. 环境变量 `FINANCIAL_ANALYZER_RUNTIME_CONFIG`
  3. 从当前工作目录向上逐级搜索 `runtime/runtime_config.json`
- 找不到 `runtime_config.json`、配置非法、路径越界、或正式 `runtime/knowledge/knowledge_base.json` 缺失时，runtime-bound 入口直接失败，不再 silent fallback。
- `run_batch_pipeline.py`、`processed_reports_registry.py`、读取正式知识基线的 `knowledge_manager.py` 都属于 runtime-bound 入口。
- `financial_analyzer.py` 保持单案独立，只继续依赖 `--run-dir`，不强制要求 runtime。
- 正式读写统一落到项目内 runtime：
  - `runtime/runtime_config.json`
  - `runtime/knowledge/knowledge_base.json`
  - `runtime/state/registry/processed_reports/processed_reports.json`
  - `runtime/state/batches/`
  - `runtime/state/governance_review/`
  - `runtime/state/logs/`
  - `runtime/state/tmp/`
- `SKILL.md`、`references/`、源码、模板、输入文件、`financial-analyzer/test_runs/` 仍留在项目仓库，不视为正式 production runtime。
- 运行态目录允许按需创建，但不得写入 `~/.codex/skills`，也不得在运行中自发改写 `SKILL.md` 或 reference 文档。

### 本线程不做

- 不在批内自动升级分析规则
- 不让 skill 自发改写自己的 `SKILL.md`
- 不开始找 10 份报告

### 可直接复制的 Prompt

```text
先阅读 AGENTS.md、automation_blueprint.md、production_execution_runbook.md、runtime_external_data_layer_spec.md、runtime/runtime_config.json、financial-analyzer/SKILL.md，以及与运行入口相关的 scripts。当前聚焦生产化 P3：Skill 与 Runtime 绑定。请设计并实现“安装后的 skill 如何稳定找到项目内 runtime”的机制，要求至少明确 runtime_config 的发现方式、路径覆盖优先级、找不到配置时的失败策略、哪些读写必须走外部 runtime、哪些仍可保留在项目仓库；必要时修改 skill 文档或脚本，但不要让 skill 在运行中自发改写自身文件。
```

## 5.4 线程 P4：自动找 10 份财报的测试入口

### 目标

- 不由用户手工点名 10 份报告，而是由 Codex 按测试目标自动选样、记录来源并生成可执行任务清单。

### 交付物

- 选样规则
- 来源记录规范
- 任务清单生成器或任务清单文档
- “为什么是这 10 份”的说明

### 本线程不做

- 不直接跑完整批次
- 不绕过来源记录
- 不让用户先手工指定 10 份完整名单

### 可直接复制的 Prompt

```text
先阅读 AGENTS.md、automation_blueprint.md、production_execution_runbook.md，以及现有批处理和上游入口相关代码/文档。当前聚焦生产化 P4：自动找 10 份财报的测试入口。测试目标不是手工指定 10 份名单，而是请你根据“真实生产仿真”目标，自己定义合理的选样规则，自动寻找并确定 10 份可用于全真测试的财报，并把来源、筛选理由、去重逻辑、预期覆盖面和最终 task list 落成文档或任务清单文件。要求优先保证样本多样性、来源可追溯、后续可批跑；不要直接开始完整批次执行。
```

## 5.5 线程 P5：冷启动全真生产仿真

### 目标

- 用尽量接近真实生产的方式，从干净环境和已安装 skill 出发，完整跑通一次全流程。

### 开始前阅读

- `automation_blueprint.md`
- `runtime_external_data_layer_spec.md`
- 已落地的 runtime/registry/skill 绑定方案

### 交付物

- 冷启动测试方案
- 实际批次目录
- 运行结果汇总
- 失败与风险清单
- 下载阶段 manifest、P5 总 manifest、batch task list

### 当前实现约定

- 统一入口：`financial-analyzer/scripts/run_p5_cold_start_simulation.py`
- 上游输入固定为某次 P4 输出目录中的：
  - `selection_manifest.json`
  - `download_config.json`
  - `task_seed_list.json`
- 阶段 A 先做真实下载验证，并输出 `download_phase_manifest.json`
- 只有当真实下载成功数 `>= 8/10` 时，才进入 MinerU、`notes_workfile`、batch task list 和 `run_batch_pipeline.py`
- 若下载 gate 未通过，P5 必须在阶段 A 停止，并在 `p5_run_manifest.json` 中明确标记下载链路阻塞

### 本线程不做

- 不把临时修补直接当正式上线
- 不跳过来源记录、registry、runtime 配置检查
- 不依赖当前对话里的隐式上下文

### 可直接复制的 Prompt

```text
先阅读 AGENTS.md、automation_blueprint.md、codex_execution_runbook.md、production_execution_runbook.md、runtime_external_data_layer_spec.md，以及已落地的 runtime/registry/skill 绑定方案。当前聚焦生产化 P5：冷启动全真生产仿真。请按“尽量接近真实生产”的原则，从已安装 skill 和项目内 runtime 出发，完成一次完整仿真：检查 skill 安装状态、检查 runtime 配置、使用自动选样得到的 10 份财报任务清单、执行批处理、输出 batch_manifest/failed_tasks/pending_updates_index/governance review，并给出最终成功率、主要失败点和是否达到 go-live 前门槛。不要只做静态审查。
```

## 5.6 线程 P6：Go-Live Checklist

### 目标

- 把上线前必须检查的门禁、人工复核点和回滚动作写成清单，供后续反复使用。

### 交付物

- go-live checklist 文档
- 人工复核清单
- 回滚与停机策略
- 上线判定标准

### 本线程不做

- 不继续发散做新功能
- 不重新设计 Soul 结构
- 不省略失败场景

### 可直接复制的 Prompt

```text
先阅读 AGENTS.md、automation_blueprint.md、production_execution_runbook.md，以及最近一次冷启动全真生产仿真的结果。当前聚焦生产化 P6：Go-Live Checklist。请基于现有系统的真实能力边界，整理一份正式投入使用前的 go-live checklist，至少覆盖 skill 安装校验、runtime 配置校验、registry 状态、批处理成功率门槛、人工抽检点、pending_updates 审核边界、失败重跑策略、回滚策略和“哪些问题出现时必须停止上线”。请把结果落成仓库文档。
```

## 6. 你接下来怎么开对话

推荐顺序：

1. 先开 P1
2. 再开 P2
3. 然后开 P3
4. 再开 P4
5. 之后开 P5
6. 最后开 P6

如果你只想先开一个最关键的新对话，就先开 P1。

如果你已经完成 P1-P3，想直接进入生产仿真，就先开 P4。

## 7. 总控线程怎么用

当前这个主线程建议继续只做三件事：

1. 判断上一线程是否真的完成
2. 决定下一线程开哪一个
3. 要求执行线程把结构性结论回写到蓝图或专项文档

不要在总控线程里顺手实现一半代码、一半方案、一半测试。
