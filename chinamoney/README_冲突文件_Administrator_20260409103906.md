# 批量下载与自动发现工具使用说明

## 工具组成

1. **discover_reports.py** - ChinaMoney 官方 JSON 接口发现工具
2. **download.py** - 通用文件下载工具（支持进度显示、自动重试）
3. **batch-download.py** - 批量下载工具（配置文件驱动）
4. **download-config.json** - 下载任务配置文件

## API-first 发现工作流

当前推荐优先走官方 JSON 接口，而不是先用浏览器手工点查。
pip install requests beautifulsoup4
### 1. 全市场发现 2024 年报

```bash
python chinamoney/scripts/discover_reports.py \
  --year 2024 \
  --report-type 4 \
  --max-pages 3 \
  --output /tmp/chinamoney-2024-market.json
```

说明：

- `discover_reports.py` 会先访问 `https://www.chinamoney.com.cn/chinese/zqcwbgcwgd/` 建立会话
- 再调用 `https://www.chinamoney.com.cn/ags/ms/cm-u-notice-issue/financeRepo`
- 支持 `orgName=''` 的全市场分页发现

### 2. 精确查询单个 issuer

```bash
python chinamoney/scripts/discover_reports.py \
  --year 2024 \
  --report-type 4 \
  --org-name "万科企业股份有限公司" \
  --max-pages 1 \
  --output /tmp/vanke-2024.json
```

### 3. 自动生成 P4 下载任务

```bash
python financial-analyzer/scripts/generate_p4_test_entry.py \
  --year 2024 \
  --sample-count 10 \
  --reserve-count 5 \
  --max-pages 20 \
  --max-head-checks 60
```

默认输出：

- `runtime/state/tmp/p4_auto_test_entry/<timestamp>/selection_manifest.json`
- `runtime/state/tmp/p4_auto_test_entry/<timestamp>/download_config.json`
- `runtime/state/tmp/p4_auto_test_entry/<timestamp>/task_seed_list.json`

其中 `download_config.json` 可直接喂给 `batch-download.py`。

## 使用方式

### 方式一：单个文件下载

直接使用 download.py：

```bash
python download.py <URL> <输出路径> [重试次数]
```

**示例：**
```bash
python download.py "https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3109042&priority=0&mode=save" "万科2024年报.pdf" 3
```

### 方式二：批量下载（推荐）

只需修改 `download-config.json` 配置文件，然后运行：

```bash
python batch-download.py
```

## 配置文件格式

编辑 `download-config.json`：

```json
{
    "output_dir": "C:/Users/XXX/Downloads",
    "tasks": [
        {
            "name": "文件名称",
            "url": "https://example.com/file1.pdf",
            "output_path": "file1.pdf",
            "retries": 3
        },
        {
            "name": "文件名称2",
            "url": "https://example.com/file2.pdf",
            "output_path": "file2.pdf",
            "retries": 3
        }
    ]
}
```

**配置说明：**
- `output_dir`: 下载文件的保存目录（可选）
- `tasks`: 下载任务列表
- `name`: 文件名称（仅用于显示）
- `url`: 下载链接
- `output_path`: 输出文件名或相对路径
- `retries`: 失败重试次数（默认3次）

## 优势

### 1. 无需重复编程
- 修改配置文件即可使用
- 不需要写新的Python脚本

### 2. 支持中文路径
- Python原生支持Unicode
- 完美处理中文文件名和路径

### 3. 实时进度显示
- 显示下载百分比
- 显示下载速度
- 显示已下载/总大小

### 4. 自动重试机制
- 下载失败自动重试
- 可配置重试次数
- 确保文件完整性

### 5. 断点续传支持
- 不完整文件自动保留
- 再次运行自动断点续传
- 大文件下载更可靠

### 6. 完善的错误处理
- URL安全验证
- 路径安全验证
- 写入权限检查
- 详细错误提示

### 7. 通用性强
- 适用于任何文件类型
- 适用于任何网站
- 配置灵活方便

## 中国货币网财报下载工作流

### 重要说明：当前下载网关约束

2026-03-19 更新，ChinaMoney 附件下载网关在当前环境仍会对部分请求返回 `421 Misdirected Request` 或 `There are too many connections from your internet address`。因此：

- `discover_reports.py` 负责官方来源发现
- 下载阶段会先尝试 ChinaMoney 官方附件
- 若官方附件仍被 421 拦截，会自动回退到 CNInfo 官方镜像并记录到 manifest

### 简报优先约束

- ChinaMoney 上经常只给出简报、摘要版或索引版 PDF，这类文件应先下载下来，再作为找到完整版的入口。
- 如果简报后半部分或财务信息章节里给出了深交所/上交所链接，优先沿这些官方交易所链接继续找完整版。
- 是否继续找完整版，不通过脚本判断，而是由 Skill 层结合浏览器页面、PDF 结构和交易所跳转链路来决定。
- 批量下载工具会把这类简报标记为 `followup_required`，表示“下载成功，但还要继续沿官方交易所链路找完整版”。
- 只有在简报里没有可用后续链接，或者链接失效时，才切回同主题的其他 ChinaMoney 搜索结果继续找。
- 这样做的目的是保留 ChinaMoney 作为入口，同时把完整版落到交易所官网的正式披露页。

这意味着当前版本可以稳定完成“发现、选样和真实下载”，同时保留官方附件作为主通路。

### 第一步：搜索获取下载链接

这是浏览器代理主路径，优先由 Playwright 直接操作网页，不要把下载接力给人工处理。

使用 playwright-cli 访问中国货币网，搜索财报：

```bash
playwright-cli open https://www.chinamoney.com.cn/chinese/cqcwbglm/ --browser=firefox
playwright-cli snapshot
# 查看搜索框和下载按钮的ref
# 填写搜索条件并点击查询
# 获取下载链接（fileDownLoad.do?contentId=XXX）
```

如果当前结果页只给出简报附件，先由浏览器直接点击下载，再检查后半部分或财务信息章节里的深交所/上交所链接；若没有可用后续链接，再切换到同一搜索词下的其他 ChinaMoney 结果继续找完整版。

如果页面是动态渲染或结构较复杂，优先用浏览器 snapshot 观察真实 DOM，再用 BeautifulSoup 解析已经拿到的 HTML；不要把直接 requests 抓网页当成主路径。

### 第二步：更新配置文件

将获取的下载链接添加到 `download-config.json`：

```json
{
    "output_dir": "C:/Users/XXX/Desktop/财报",
    "tasks": [
        {
            "name": "公司名+年度+报告类型",
            "url": "https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=XXX&priority=0&mode=save",
            "output_path": "文件名.pdf",
            "retries": 3
        }
    ]
}
```

### 第三步：执行下载

```bash
python batch-download.py
```

## 使用技巧

### 技巧1：多个公司财报下载
创建多个配置文件，分别对应不同公司：

```
download-vanke.json      # 万科配置
download-chinares.json   # 中海配置
download-crl.json        # 华润配置
```

运行时指定配置：
```bash
python batch-download.py download-vanke.json
```

### 技巧2：增量下载
在配置文件中只添加需要下载的新文件，旧的文件会自动跳过（如果有重名）。

### 技巧3：下载日志
批量下载工具会显示每个文件的成功/失败状态，便于记录。

## 常见问题

### Q1: 下载失败怎么办？
A: 工具会自动重试，如果仍失败，检查：
- 网络连接是否正常
- URL是否正确
- 下载权限是否足够

### Q2: 如何暂停下载？
A: 按 `Ctrl+C` 即可中断

### Q3: 文件已存在会覆盖吗？
A: 会覆盖同名文件。如需保留原文件，请修改配置中的 `output_path`

### Q4: 支持大文件吗？
A: 支持，使用流式下载，不占用过多内存

### Q5: 下载到一半网络断了怎么办？
A: 直接重新运行，会自动断点续传，不需要修改配置

### Q6: 如何查看详细的错误信息？
A: 错误信息会显示在控制台，包括：
   - 连接错误（网络问题）
   - HTTP错误（403、404、500等）
   - SSL错误（证书问题）
   - 权限错误（无法写入目录）

### Q7: 下载的文件安全吗？
A: 工具会进行安全验证：
   - 只允许HTTP/HTTPS协议
   - 检测路径遍历攻击（../）
   - 验证URL格式
   - 检查写入权限

## 文件说明

| 文件 | 说明 |
|------|------|
| discover_reports.py | 官方 JSON 接口发现工具 |
| download.py | 核心下载工具，可独立使用 |
| batch-download.py | 批量下载工具，读取配置文件 |
| download-config.json | 下载任务配置 |
| README.md | 本说明文档 |
