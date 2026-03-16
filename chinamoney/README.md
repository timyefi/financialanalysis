# 批量下载工具使用说明

## 工具组成

1. **download.py** - 通用文件下载工具（支持进度显示、自动重试）
2. **batch-download.py** - 批量下载工具（配置文件驱动）
3. **download-config.json** - 下载任务配置文件

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

### 第一步：搜索获取下载链接

使用 playwright-cli 访问中国货币网，搜索财报：

```bash
playwright-cli open https://www.chinamoney.com.cn/chinese/cqcwbglm/ --browser=firefox
playwright-cli snapshot
# 查看搜索框和下载按钮的ref
# 填写搜索条件并点击查询
# 获取下载链接（fileDownLoad.do?contentId=XXX）
```

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
| download.py | 核心下载工具，可独立使用 |
| batch-download.py | 批量下载工具，读取配置文件 |
| download-config.json | 下载任务配置 |
| README.md | 本说明文档 |
