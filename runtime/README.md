# Runtime 目录说明

本目录是项目内可携带的 production runtime 根目录。

当前阶段结论：

- `runtime_config + knowledge_base + adoption_logs` 目录骨架进入 Git。
- `registry / batches / governance_review / logs / tmp` 属于运行态状态目录，不应作为日常版本化资产管理。
- 运行中的动态数据不得写入 `~/.codex/skills`。
- 逐份报告独立闭环入口由 `financial-analyzer/scripts/run_report_series.py` 承担；它复用同一套下载、解析、单案分析和 registry 更新逻辑，但每份报告独立产出正式报告与 Excel，不在同一结果里合并多份报告。

当前 P1 只落规范与静态基线：

- 不修改脚本默认路径
- 不实现 registry 逻辑
- 不启动 10 案测试

正式规范见：

- [runtime_external_data_layer_spec.md](/Users/yetim/project/financialanalysis/runtime_external_data_layer_spec.md)
