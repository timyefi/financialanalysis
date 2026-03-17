# P4 自动找 10 份财报测试入口规范

## 1. 目标

P4 的目标不是手工列一张 10 份名单，而是提供一条可重复执行的“自动发现 -> 自动筛样 -> 生成任务种子”入口，为后续 P5 冷启动仿真准备：

- `selection_manifest.json`
- `download_config.json`
- `task_seed_list.json`

当前实现入口：

- [chinamoney/scripts/discover_reports.py](/Users/yetim/project/financialanalysis/chinamoney/scripts/discover_reports.py)
- [financial-analyzer/scripts/generate_p4_test_entry.py](/Users/yetim/project/financialanalysis/financial-analyzer/scripts/generate_p4_test_entry.py)

## 2. 官方来源与请求方式

### 2.1 来源池

主来源池固定为 ChinaMoney 2024 年 `type=4` 年度报告接口：

- 列表页：`https://www.chinamoney.com.cn/chinese/zqcwbgcwgd/`
- 年度/类型接口：`https://www.chinamoney.com.cn/ags/ms/cm-u-notice-an/staYearAndType`
- 财报列表接口：`https://www.chinamoney.com.cn/ags/ms/cm-u-notice-issue/financeRepo`

### 2.2 会话要求

直接 POST 到 `financeRepo` 时，若没有先访问列表页建立 cookie，会遇到 403 或不稳定响应。

当前脚本固定流程：

1. 先 GET `https://www.chinamoney.com.cn/chinese/zqcwbgcwgd/`
2. 再以同一个 `requests.Session` 调用 JSON 接口
3. JSON 接口请求头包含：
   - `Referer`
   - `User-Agent`
   - `X-Requested-With: XMLHttpRequest`

### 2.3 全市场池

`orgName=''` 时可以直接拉全市场分页结果。2026-03-17 实测：

- `year=2024`
- `type=4`
- `orgName=''`

返回 `total=3910`，因此可以作为 P4 的官方主池，不依赖手工 issuer 名单。

## 3. 选样规则

### 3.1 快速过滤

固定排除：

- 非 `pdf`
- 多年度打包标题，如 `2022-2024`、`2023-2024`
- 公告/更正噪声，如 `公告`、`更正`、`变更`、`前期会计差错`
- 当前分析范围外的金融机构：`银行|保险|证券|信托|基金|创业投资|融资租赁|担保|资产管理`

### 3.2 大小粗筛

目标门槛：`>= 10MB`

优先顺序：

1. 优先尝试附件下载 URL 的 `HEAD`
2. 若 `HEAD` 成功，直接使用 `Content-Length`
3. 若 `HEAD` 失败，则进入保守降级

### 3.2.1 官方镜像优先

当前环境下，ChinaMoney 附件下载网关对真实 PDF 下载经常返回：

- `421 Misdirected Request`
- `There are too many connections from your internet address ...`

因此 P4 现已补充“官方镜像解析”步骤：

1. 先继续以 ChinaMoney 作为**发现源**
2. 对 dedupe 后的高质量候选，额外探测 CNInfo 官方年报 PDF
3. 若存在可用官方镜像，则：
   - 在 `selection_manifest.json` 中写入 `official_source`、`official_download_url`
   - 在 `download_config.json` 中优先使用官方镜像 URL
   - 在 `task_seed_list.json` 中保留原始 ChinaMoney `download_url`，同时写入 `effective_download_url`

这意味着：

- ChinaMoney 继续负责“选谁”
- 官方镜像负责“怎么下”
- 当前 P5 下载 gate 的目标是“至少 8 份成功下载”，不要求 8 份都来自 ChinaMoney 附件网关

### 3.3 当前站点约束与降级

2026-03-17 实测，ChinaMoney 附件下载网关对当前环境大量返回：

- `421 Misdirected Request`

因此当前实现采用两级降级：

1. **本地案例尺寸校准**
   - 从 `cases/*.pdf` 自动建立已知 issuer 的文件大小映射
   - 例如：
     - 保利约 `0.5MB`
     - 招商蛇口约 `3.3MB`
     - 万科约 `5.2MB`
     - 碧桂园约 `11.1MB`
     - 杭海约 `15.3MB`
2. **标题语义估算**
   - 若标题包含 `附注`、`合并及母公司财务报告`、`财务报告及母公司会计报表`、`审计报告及财务报表`、`经审计的财务报告`
   - 则估算为完整财报候选，按 `12MB` 进入粗筛

说明：

- 这是为了解决当前下载网关的 live `HEAD` 不稳定问题
- 该降级逻辑必须在 `selection_manifest.json` 中写明 `content_length_source`
- P5 前仍应优先验证真实下载链路是否恢复正常

### 3.4 去重规则

去重键：

- `normalized_issuer_name + year`

若同一 issuer/year 出现多条记录：

1. 优先保留更大 `content_length`
2. 如大小相同，保留更晚 `release_date`

### 3.5 多样性规则

目标 bucket：

- `real_estate`
- `lgfv_platform`
- `industrial_energy_manufacturing`
- `consumer_services_logistics`
- `general_holding_other_nonfinancial`

策略：

- 尽量每类取 2 份
- 若不足则由其他 bucket 回填
- 任一 bucket 上限 3 份

## 4. 仓库内 issuer 补查

为避免全市场前若干页样本偏科，当前实现会自动扫描 `cases/*.md` 中已出现过的 issuer，并对这些 issuer 发起一次 ChinaMoney 精确查询。

这是自动补查，不是手工指定 10 份名单。

用途：

- 把仓库已有校准案例纳入候选集
- 保持 P4 结果与现有回归知识连续
- 为保利/万科/碧桂园/杭海等已知样本提供尺寸校准

## 5. 输出契约

### 5.1 `selection_manifest.json`

必须包含：

- `policy`
- `candidate_pool_summary`
- `dedupe_events`
- `excluded_candidates`
- `selected_candidates`
- `reserve_candidates`
- `coverage_summary`

`selected_candidates` 每项至少包含：

- `task_id`
- `issuer_name`
- `bucket`
- `content_id`
- `title`
- `release_date`
- `draft_page_url`
- `download_url`
- `effective_download_url`
- `content_length`
- `selection_reason`

### 5.2 `download_config.json`

兼容：

- [chinamoney/scripts/batch-download.py](/Users/yetim/project/financialanalysis/chinamoney/scripts/batch-download.py)

顶层包含：

- `output_dir`
- `tasks`

每个任务至少包含：

- `name`
- `url`
- `output_path`
- `retries`

如果存在官方镜像，则 `url` 应优先写官方镜像下载地址。

### 5.3 `task_seed_list.json`

这是 P5 的前置种子，不是当前 `run_batch_pipeline.py` 的直接输入。

每项至少包含：

- `task_id`
- `issuer`
- `year`
- `source_pdf`
- `md_path`
- `notes_workfile`
- `run_dir`
- `selection_bucket`
- `selection_reason`

`source` 中应同时保留：

- 原始 ChinaMoney `download_url`
- 当前实际执行的 `effective_download_url`
- `official_source`（若存在）

## 6. 当前默认输出目录

默认写入：

- `runtime/state/tmp/p4_auto_test_entry/<timestamp>/`

因此一次成功运行下会得到：

- `runtime/state/tmp/p4_auto_test_entry/<timestamp>/selection_manifest.json`
- `runtime/state/tmp/p4_auto_test_entry/<timestamp>/download_config.json`
- `runtime/state/tmp/p4_auto_test_entry/<timestamp>/task_seed_list.json`

## 7. P5 接口关系

P4 到此为止不做：

- 实际批量下载
- MinerU 解析
- `notes_workfile` 生产
- `run_batch_pipeline.py` 批跑

P5 应基于 P4 输出继续：

1. 执行下载
2. 解析 PDF
3. 补齐 `notes_workfile`
4. 把 `task_seed_list.json` 转成真正可运行的 batch task list
