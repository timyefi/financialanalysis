---
name: chinamoney
description: This skill helps credit analysts download rating reports and financial statements from China Money Network (中国货币网). Use this skill when users need to download bond rating reports, issuer financial reports, or disclosure information from China Money Network (https://www.chinamoney.com.cn).
license: MIT. LICENSE.txt has complete terms
---

# China Money Network Data Download Skill

## ⚠️ CRITICAL: Windows Environment Interaction Rules

**Before executing any commands, you MUST read and follow these rules:**

### 1. Process Call & Syntax Rules

- **DO NOT use `cmd.exe /c`** for complex commands - it has issues with special characters
- **Use PowerShell directly** with `-NoProfile -Command`
- **Wrap paths with single quotes** `' '`, NEVER double quotes
- **Use absolute paths** - NEVER relative paths like `.\` or `..\`

### 2. Correct Command Execution

```bash
# ✅ CORRECT - Use PowerShell directly
powershell.exe -NoProfile -Command python C:/path/to/script.py

# ✅ CORRECT - Python subprocess approach (recommended for complex URLs)
python -c "import subprocess; subprocess.run(['python', 'script.py', 'url', 'output'])"

# ❌ WRONG - cmd.exe has issues with & in URLs
cmd.exe /c python script.py https://example.com?a=1&b=2

# ❌ WRONG - Double quotes in paths
powershell.exe -NoProfile -Command "python \"C:\path\to\script.py\""
```

### 3. Python Encoding Setup

When running Python scripts in Windows:
- Set encoding in main() only, NOT at module level
- This prevents "I/O operation on closed file" errors when imported

```python
# ✅ CORRECT - Setup in main() only
def main():
    setup_encoding()  # Only call when running directly
    # ... rest of code

# ❌ WRONG - Module-level encoding breaks imports
sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)  # Breaks imports!
```

### 4. Variable Name Conflicts

Always use distinct variable names to avoid overwriting:
```python
# ✅ CORRECT - Distinct names
req_headers = {'User-Agent': '...'}
range_headers = {'Range': 'bytes=0-'}

# ❌ WRONG - Overwrites previous value
headers = {'User-Agent': '...'}
headers = {}  # User-Agent lost!
```

## Purpose

This skill provides workflows and tools for downloading financial data from China Money Network, including bond rating reports, financial statements (annual, semi-annual, quarterly), and disclosure announcements.

## When to Use This Skill

Use this skill when:
- Users need to download bond rating reports from China Money Network
- Users need to download financial statements for bond issuers
- Users need to access disclosure information from the platform
- Users mention "中国货币网" (China Money Network) or specific company financial report downloads

## Core Tools

This skill relies on the following tools located in the skill's `scripts/` directory:

### 1. discover_reports.py - API-first Discovery Tool
- Bootstraps a valid ChinaMoney session before calling official JSON APIs
- Supports market-wide discovery with `orgName=''`
- Supports exact issuer lookup
- Produces structured records with `contentId`, `draftPath`, `releaseDate`, and download URL

### 2. playwright-cli - Browser Automation
- Opens China Money Network web pages
- Fills search forms and navigates results
- Extracts download links (contentId values)

### 3. download.py - Single File Download Tool
- Downloads files with progress display
- Supports resume capability for large files
- Automatic retry mechanism (up to 3 retries by default)
- Validates file integrity

### 4. batch-download.py - Batch Download Tool
- Configuration-driven batch downloads
- Processes multiple files from JSON config
- Direct Python import (no subprocess encoding issues)

### 5. download-config.json - Configuration File Template
- Defines download tasks
- Specifies output directories
- Configures retry counts

## Installation

Ensure required dependencies are installed:

```bash
# Install playwright-cli
npm install -g @playwright/cli@latest
npx playwright install firefox

# Install Python dependencies
pip install requests beautifulsoup4
```

## Workflow

### Step 1: Prefer API-first Discovery

Use the official JSON endpoint through the discovery script:

```bash
python scripts/discover_reports.py --year 2024 --report-type 4 --max-pages 3 --output /tmp/chinamoney-market.json
```

Exact issuer lookup:

```bash
python scripts/discover_reports.py --year 2024 --report-type 4 --org-name "万科企业股份有限公司" --max-pages 1 --output /tmp/vanke.json
```

Current observed facts:
- call `https://www.chinamoney.com.cn/chinese/zqcwbgcwgd/` first to establish session
- then call `https://www.chinamoney.com.cn/ags/ms/cm-u-notice-issue/financeRepo`
- direct attachment GET may still hit `421 Misdirected Request` or `There are too many connections from your internet address` in the current environment, so download code now uses retry/backoff on the official attachment and falls back to CNInfo mirror when available
- if the ChinaMoney result is only a disclosure shell or brief and the parsed Markdown does not expose a real `财务报表附注` section, stop the automated notes extraction path and switch to the full financial report attachment from the exchange page or a manually downloaded local PDF in the current working directory

### Step 2: Open Financial Report Page

Use Firefox browser (headless mode works):

```bash
playwright-cli open https://www.chinamoney.com.cn/chinese/cqcwbglm/ --browser=firefox
```

For advanced pages, keep the browser open and inspect the live DOM instead of trying to infer everything from a raw request.

Recommended browser-first flow:
- open the page in Playwright
- take a snapshot
- inspect the rendered anchors / hidden sections
- use BeautifulSoup only to parse the captured HTML when the DOM is already available
- follow the official exchange links surfaced inside the brief
- if the page exposes a clickable download or disclosure link, click it in the browser first and let the browser navigate
- prefer browser events and page navigation over script-only extraction whenever the page is interactive or heavily scripted

### Step 3: Get Page Snapshot

Extract current page structure:

```bash
playwright-cli snapshot
```

The snapshot saves to `.playwright-cli/page-*.yml` with element references.

### Step 4: Fill Search Conditions

Extract element refs from snapshot:
- Search box: Find `textbox` followed by `[ref=exxx]`
- Year dropdown: Find `combobox` for year selection
- Report type dropdown: Find another `combobox` for report type
- Query button: Find `link "查询"` followed by `[ref=exxx]`

Execute form filling:

```bash
# Enter company name or bond code
playwright-cli fill <search-box-ref> 万科

# Select year
playwright-cli select <year-dropdown-ref> 2024

# Select report type
playwright-cli select <type-dropdown-ref> 年度报告

# Click query button
playwright-cli click <query-button-ref>
```

If click times out, use JavaScript:

```bash
playwright-cli eval "document.querySelector('a[onclick*=\"financeSearch\"]').click()"
```

### Step 5: Wait for Results and Extract Download Links

Query opens new tab. Switch to results tab:

```bash
playwright-cli tab-list
playwright-cli tab-select 1  # Switch to results tab
```

Get snapshot of results:

```bash
playwright-cli snapshot
```

In the snapshot file, find download links:
```
- /url: /dqs/cm-s-notice-query/fileDownLoad.do?contentId=3109042&priority=0&mode=save
```

If the result is a brief or index-style PDF, download it first and treat it as the starting point.

Extract the `contentId=XXXXXX` and construct full URL:
```
https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3109042&priority=0&mode=save
```

After downloading the brief, inspect the later pages or the financial information section for links to the full report. Those links usually jump to 深交所 or 上交所.

If the page is complex or lazy-loaded, prefer browser snapshot plus HTML parsing over direct script scraping. BeautifulSoup is the supported parser for extracted HTML, not a replacement for browser inspection.

### Step 6: Configure Batch Download

Edit `download-config.json` to add download tasks:

```json
{
    "output_dir": "C:/Users/Administrator/Desktop/项目/信用工作流/万科/历史财报",
    "tasks": [
        {
            "name": "万科企业股份有限公司2024年年度报告",
            "url": "https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3109042&priority=0&mode=save",
            "output_path": "万科企业股份有限公司2024年年度报告.pdf",
            "retries": 3
        }
    ]
}
```

### Step 7: Execute Batch Download

```bash
python scripts/batch-download.py
```

The download tool will:
- Display real-time progress (percentage, speed, size)
- Automatically retry on failure (default 3 times)
- Validate file integrity
- Report success/failure statistics

### 简报优先规则

- ChinaMoney 上经常只给出简报、摘要版或索引版 PDF，这类文件不是终点，而是进入完整版的入口。
- 先把简报下载下来，再沿着简报后半段的链接继续找完整版；这些链接通常会跳到深交所或上交所的网站。
- 是否继续找完整版，不通过脚本下结论，而是由 Skill 层结合浏览器页面、PDF 结构和交易所跳转链路来判断。
- 若简报里已经给出交易所的完整年报/财务报告链接，优先跟进这些链接，不要再把同一页当成最终结果。
- 只有在简报里没有可用的交易所链接，或者链接失效时，才回到 ChinaMoney 的同主题其他搜索结果继续找。
- 批量下载工具会把这类简报标记为 `followup_required`，表示“下载成功，但还要继续沿官方交易所链路找完整版”。
- 发现页面若只给出简报附件，也要先下载简报，再用 MinerU 或页面内链接定位正式报告，不要依赖 PDF 反向抽取下载地址作为主路径。
- 如果当前结果页确实没有任何可用后续链接，再切换到同一搜索词的其他 ChinaMoney 结果继续查找。

### Step 8: Close Browser

```bash
playwright-cli close
```

## Configuration File Format

### Basic Structure

```json
{
    "output_dir": "C:/Users/XXX/Downloads",
    "tasks": [
        {
            "name": "Display name for logging",
            "url": "https://xxx.com/download",
            "output_path": "filename.pdf",
            "retries": 3
        }
    ]
}
```

### Relative Path Handling

If `output_path` is not absolute, it's appended to `output_dir`:

```json
{
    "output_dir": "C:/Downloads",
    "tasks": [
        {
            "output_path": "2024/万科年报.pdf"
        }
    ]
}
# Saves to: C:/Downloads/2024/万科年报.pdf
```

## Single File Quick Download

For single files, use direct download:

```bash
python scripts/download.py "https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=XXX&priority=0&mode=save" "文件名.pdf"
```

## Batch Workflow Example

When downloading multiple reports for a company:

1. Collect all download links by switching years and types
2. Add all tasks to config file at once
3. Execute single batch download command

Example config for 3-year annual and semi-annual reports:

```json
{
    "output_dir": "C:/Users/Administrator/Desktop/财报/万科",
    "tasks": [
        {"name": "2024年报", "url": "...contentId=XXX...", "output_path": "2024年年报.pdf", "retries": 3},
        {"name": "2023年报", "url": "...contentId=XXX...", "output_path": "2023年年报.pdf", "retries": 3},
        {"name": "2022年报", "url": "...contentId=XXX...", "output_path": "2022年年报.pdf", "retries": 3},
        {"name": "2024半年报", "url": "...contentId=XXX...", "output_path": "2024年半年度报告.pdf", "retries": 3},
        {"name": "2023半年报", "url": "...contentId=XXX...", "output_path": "2023年半年度报告.pdf", "retries": 3}
    ]
}
```

## Error Handling

### Common Issues and Solutions

**Issue 1: Element click timeout**
- Cause: Element reference changed
- Solution: Re-run `snapshot` to get latest ref, or use JavaScript click:
  ```bash
  playwright-cli eval "document.querySelector('a[onclick*=\"financeSearch\"]').click()"
  ```

**Issue 2: Search results in new tab**
- Solution: Switch to new tab:
  ```bash
  playwright-cli tab-list
  playwright-cli tab-select 1
  ```

**Issue 3: Search keyword with quotes**
- Incorrect: `playwright-cli fill e109 "万科"`
- Correct: `playwright-cli fill e109 万科`
- Note: Do not add quotes around keywords

**Issue 4: PowerShell Chinese path issues**
- Avoid: PowerShell scripts with parameters
- Solution: Use Python scripts with direct import

**Issue 5: No download progress visibility**
- Solution: Python download tool displays real-time:
  - Download percentage
  - Download speed
  - Downloaded/total size

**Issue 6: Download failures without retry**
- Solution: Configure `retries` parameter for automatic retry

**Issue 7: Empty downloaded files**
- Solution: Download tool validates file size, retries on empty files

---

### 🚨 Critical Issues Encountered & Fixed

**Issue 8: Command line URL with `&` fails (2024-03-11)**
- Problem: URL contains `&` which gets interpreted as command separator in cmd.exe
- Failed attempts:
  - `cmd.exe /c python script.py https://...?a=1&b=2` - & splits command
  - Escaping with `^&` - doesn't work in cmd.exe /c
- Solution: Use Python subprocess instead:
  ```python
  import subprocess
  os.chdir(r"C:\path\to\scripts")
  subprocess.run([sys.executable, "download.py", url, output, "3"])
  ```

**Issue 9: Python "I/O operation on closed file" error (2024-03-11)**
- Problem: sys.stdout wrapped with codecs at module level breaks when imported
- Cause: batch-download.py imports download.py, which wraps stdout globally
- Solution: Move encoding setup to main() function only:
  ```python
  def setup_encoding():
      if sys.platform == 'win32':
          try:
              import codecs
              sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
              sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
          except Exception:
              pass

  def main():
      setup_encoding()  # Only called when running directly
      # ... rest of code
  ```

**Issue 10: Variable name conflict causing download failure (2024-03-11)**
- Problem: `headers` variable overwritten, losing User-Agent
- Code had:
  ```python
  headers = {'User-Agent': '...'}  # First assignment
  # ... later ...
  headers = {}  # OVERWRITES User-Agent!
  ```
- Solution: Use distinct variable names:
  ```python
  req_headers = {'User-Agent': '...'}
  range_headers = {}
  # Merge when making request:
  requests.get(url, headers={**req_headers, **range_headers}, ...)
  ```

**Issue 11: Import path error in batch-download.py (2024-03-11)**
- Problem: `from download import download_file` fails when run from different directory
- Solution: Add script directory to sys.path:
  ```python
  script_dir = os.path.dirname(os.path.abspath(__file__))
  if script_dir not in sys.path:
      sys.path.insert(0, script_dir)
  ```

**Issue 12: Missing User-Agent header (2024-03-11)**
- Problem: China Money Network may reject requests without User-Agent
- Solution: Always include User-Agent in requests:
  ```python
  req_headers = {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
  }
  ```

---

### ⚡ Best Practice: Test Scripts Before Production

Always test download scripts with a single file first:
```python
# test_runner.py
import subprocess
import os

os.chdir(r"C:\path\to\scripts")
result = subprocess.run(
    [sys.executable, "download.py", url, output, "3"],
    capture_output=True,
    text=True,
    encoding='utf-8',
    errors='replace'
)
print(result.stdout)
print(result.stderr)
```

## Best Practices

1. **Always execute snapshot before operations**
   - Element refs may change
   - Ensure using latest refs

2. **Use Firefox browser**
   - Best compatibility
   - No need for headed mode

3. **Batch download preferred over single downloads**
   - Collect all links first
   - Add all to config at once
   - Execute single download command

4. **Use Python instead of PowerShell**
   - Better Chinese support
   - Cross-platform compatibility
   - Powerful download capabilities

5. **Monitor download progress**
   - Real-time percentage display
   - Real-time speed display
   - Auto-retry on failure

6. **Validate download results**
   - Check file sizes
   - Check file counts
   - Confirm no duplicates
  - If a PDF is obviously a short bulletin/summary, treat it as incomplete and re-query ChinaMoney instead of mining PDF links.

## Download Link Extraction

### Download Link Pattern

In China Money Network search results, download links follow this pattern:
```
/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3109042&priority=0&mode=save
```

Extract `contentId` and construct full URL:
```
https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3109042&priority=0&mode=save
```

### Page Elements Reference

#### Financial Report Search Area

```
Company name: textbox (ref changes)
Report year: combobox (ref changes)
  - All, 2025, 2024, 2023, 2022, ...
Report type: combobox (ref changes)
  - All, 一季度报告, 半年度报告, 三季度报告, 四季度报告, 年度报告, 其他相关报告, 未审计年报, 审计年报
Query button: link "查询" (ref changes)
```

#### Search Results List

```
List items:
  - Date
  - Filename (link)
  - Download link (link) - Download URL here
  - /url: /dqs/cm-s-notice-query/fileDownLoad.do?contentId=XXX&priority=0&mode=save
```

## FAQ

**Q: Why does query button sometimes not respond?**
A: Possibly incorrect ref reference. Re-run `snapshot` to get latest ref, or use JavaScript click.

**Q: How to know when search is complete?**
A: Query automatically opens new tab. Use `playwright-cli tab-list` to check tab count.

**Q: What about very large download files?**
A: Python download tool uses streaming download, minimal memory usage, supports any file size.

**Q: How to verify download success?**
A: Download tool validates file size and displays statistics: success count, failure count, file list.

**Q: What happens on duplicate downloads?**
A: Overwrites files with same name. Modify `output_path` in config to preserve original files.

**Q: Can download multiple files simultaneously?**
A: `batch-download.py` downloads sequentially. For parallel downloads, modify script or run multiple instances.

## Key URLs

- Rating reports (issuer rating): https://www.chinamoney.com.cn/chinese/pjgg/
- Bond rating reports: https://www.chinamoney.com.cn/chinese/zxpjbgh/
- Financial statements: https://www.chinamoney.com.cn/chinese/cqcwbglm/

## Skill Structure

```
chinamoney-download/
├── SKILL.md                  # This file
├── README.md                 # Detailed user documentation (Chinese)
├── download-config.json       # Configuration file template
└── scripts/
    ├── download.py          # Single file download tool
    └── batch-download.py    # Batch download tool
```

## Additional Documentation

For detailed Chinese documentation, see `README.md` in this skill directory, which includes:
- Complete tool installation instructions
- Detailed workflow examples
- Configuration file templates
- Troubleshooting guide
- Usage tips and best practices
