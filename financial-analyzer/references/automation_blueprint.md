# 自动化训练项目蓝图（ChinaMoney + Financial Analysis）

## 1. 目标定义（按最新口径）

本项目的目标是通过两个技能协同，形成一个可持续训练的自动化分析闭环：

1. **ChinaMoney 数据采集技能**：批量获取中国债券发行主体的完整财报（必须含附注）与评级报告。
2. **Financial Analysis 分析技能**：对财报与评级报告进行深度分析，输出研究报告与结构化主表 Excel（Soul）。

> 说明：Soul 是对外输出成品，不是内部进化的中间产物。

## 2. 端到端流程（Pipeline）

```text
任务清单(issuer-year)
  -> ChinaMoney 检索与下载
  -> PDF 解析（MinerU）
  -> 文档标准化（年报/评级报告）
  -> Financial Analysis（附注优先 + 评级交叉验证）
  -> 输出：analysis_report.md + Soul Excel + run_manifest.json
  -> 候选知识沉淀：pending_updates.json（内部）
  -> 人工审核后更新知识库（内部）
```

## 3. 模块职责边界

### 3.1 下载层（Downloader）
- 输入：`issuer`、`year`、`doc_type`（年报/评级）
- 输出：原始 PDF、下载元数据（url/content_id/hash）
- 要求：优先完整版本（含附注）

### 3.2 文档理解层（MinerU + Normalizer）
- 统一使用 MinerU 解析 PDF。
- 解析后生成规范化中间数据：
  - `doc_profile.json`（文档类型、期间、主体）
  - `chapter_index.json`（关键章节定位）
  - `notes_workfile.json`（附注边界）

### 3.3 分析层（Financial Analysis）
- 仅消费已确认的附注范围与评级文本。
- 输出内容分为：
  - 面向阅读：`analysis_report.md`
  - 面向比较：`financial_output.xlsx`（Soul）

### 3.4 学习进化层（Knowledge Loop）
- 运行中识别到的新规则先进入 `pending_updates.json`。
- 经人工轻审后写回知识库并版本化。
- 与对外 Soul 解耦，避免内部演化影响对外交付稳定性。

## 4. 核心设计原则

1. **双轨制**：对外产物（Soul）稳定优先；对内知识（pending/knowledge_base）迭代优先。
2. **证据可追溯**：关键字段需保留来源段落/页码/章节引用。
3. **标准化+开放性并存**：
   - 标准化：固定核心字段与命名
   - 开放性：允许扩展字段和行业特化字段
4. **批量可运维**：失败重试、断点续跑、可回放、可审计。

## 5. 里程碑建议

### M1（MVP，2周）
- 跑通 3-5 个发行人、单年度（建议 2024）。
- 稳定生成：`run_manifest.json`、`analysis_report.md`、`financial_output.xlsx`。

### M2（标准化，2-4周）
- 固化 Soul v1 字段字典。
- 增加跨主体对比页。
- 建立数据质量检查（单位、缺失、异常波动）。

### M3（进化闭环，4-8周）
- 完成 pending -> review -> adopt 流程。
- 增加知识版本 changelog。
- 形成月度增量更新机制。

## 6. 风险与缓解

1. **来源异构风险**：不同主体公告格式差异大。
   - 缓解：模板分层 + 异常回退。
2. **误提取风险**：OCR/表格切分误差。
   - 缓解：关键字段证据索引与规则校验。
3. **输出失稳风险**：内部规则变更影响对外 Excel。
   - 缓解：Soul 核心字段版本锁定，扩展字段向后兼容。

