# -*- coding: utf-8 -*-
import sys
import os
import subprocess

# 获取脚本路径
script_path = r"C:\Users\Administrator\.workbuddy\plugins\marketplaces\tim\plugins\chinamoney\scripts\download.py"
url = r"https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3106435&priority=0&mode=save"
output = r"C:\Users\Administrator\Desktop\项目\信用工作流\余姚工业园区开发建设\测试目录\test_2024.pdf"

print(f"Running: python {script_path}")
print(f"URL: {url}")
print(f"Output: {output}")

# 切换到脚本目录执行
os.chdir(r"C:\Users\Administrator\.workbuddy\plugins\marketplaces\tim\plugins\chinamoney\scripts")
result = subprocess.run(
    [sys.executable, "download.py", url, output, "3"],
    capture_output=True,
    text=True,
    encoding='utf-8',
    errors='replace'
)

print(f"\nReturn code: {result.returncode}")
print(f"\nStdout:\n{result.stdout}")
print(f"\nStderr:\n{result.stderr}")
