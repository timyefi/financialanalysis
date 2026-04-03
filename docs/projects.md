# GitHub Projects 分层方案

这个仓库采用按优先级拆分的 GitHub Projects，而不是把所有任务放进一个大看板。这样做的目的，是让阻塞项、上游采集、分析主链和治理收口彼此分离，避免状态混杂。

## 项目划分

已创建的远端 Projects：

- [P0 - 阻塞与上线门禁](https://github.com/users/timyefi/projects/14)
- [P1 - 信息收集与原始数据](https://github.com/users/timyefi/projects/15)
- [P2 - 文档理解与分析主链](https://github.com/users/timyefi/projects/16)
- [P3 - 导出 QA 与知识治理](https://github.com/users/timyefi/projects/17)

### P0 - 阻塞与上线门禁

职责：只放会阻塞发布、回归、正式运行的任务。

典型内容：

- `go_live_checklist.md` 的补充和修订。
- runtime、registry、失败路径、回滚边界相关问题。
- 影响正式投入使用的门禁项。

### P1 - 信息收集与原始数据治理

职责：只放采集、下载、原始材料治理、元数据管理相关任务。

典型内容：

- ChinaMoney 下载器与接口适配。
- 新数据源补充。
- 原始 PDF、附件、哈希、命名规则治理。

### P2 - 文档理解与分析主链

职责：只放 MinerU、章节定位、附注优先分析、报告生成相关任务。

典型内容：

- PDF -> Markdown -> notes_workfile 的链路稳定化。
- 章节索引、附注定位、证据提炼。
- `analysis_report.md`、`final_data.json`、`chapter_records.jsonl` 的主链质量改进。

### P3 - 导出、QA 与知识治理收口

职责：只放 Soul 导出、回归、知识采纳、回滚和治理任务。

典型内容：

- Soul Excel 导出层。
- 批处理、回归、golden diff、预览检查。
- knowledge adopt / rollback / audit。

## 优先级映射

仓库内的工作流优先级与 GitHub Projects 的对应关系如下：

- P0：阻塞与上线门禁。
- P1：信息收集与原始数据治理。
- P2：文档理解与分析主链。
- P3：导出、QA 与知识治理收口。

这四档不是一般意义上的“高/中/低”，而是按工作流边界切分的主项目。

## 建议字段

每个 Project 的 issue 卡片建议统一以下字段：

- Priority
- Workstream
- Status
- Owner
- Target Case
- Blocking Reason
- Acceptance Criteria

## 维护规则

1. 新任务先定优先级，再进入对应 Project。
2. 跨优先级任务只挂一个主 Project，不重复分流。
3. 阻塞上线的事项优先进入 P0，而不是临时塞进其他板。
4. issue 标题尽量使用动词开头，便于项目视图排序。

## 建议的入口 issue

- [P0 项目总纲：阻塞与上线门禁](https://github.com/timyefi/financialanalysis/issues/3)
- [P1 项目总纲：信息收集与原始数据](https://github.com/timyefi/financialanalysis/issues/4)
- [P2 项目总纲：文档理解与分析主链](https://github.com/timyefi/financialanalysis/issues/5)
- [P3 项目总纲：导出 QA 与知识治理](https://github.com/timyefi/financialanalysis/issues/6)

## 与蓝图的关系

这个文件只定义 GitHub Projects 的分层和维护方式。项目总蓝图仍然以 [automation_blueprint.md](../automation_blueprint.md) 为准。