# -*- coding: utf-8 -*-
import sys
import os
import subprocess

# 获取脚本路径
script_path = r"C:\Users\Administrator\.workbuddy\plugins\marketplaces\tim\plugins\chinamoney\scripts\batch-download.py"
config_path = r"C:\Users\Administrator\.workbuddy\plugins\marketplaces\tim\plugins\chinamoney\download-config.json"

print(f"Running: python {script_path}")
print(f"Config: {config_path}")

# 切换到脚本目录执行
os.chdir(r"C:\Users\Administrator\.workbuddy\plugins\marketplaces\tim\plugins\chinamoney")
result = subprocess.run(
    [sys.executable, "scripts/batch-download.py", config_path],
    capture_output=True,
    text=True,
    encoding='utf-8',
    errors='replace'
)

print(f"\nReturn code: {result.returncode}")
print(f"\nStdout:\n{result.stdout}")
print(f"\nStderr:\n{result.stderr}")
