# -*- coding: utf-8 -*-
import requests
import sys

url = 'https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3106435&priority=0&mode=save'
output = 'C:/Users/Administrator/Desktop/项目/信用工作流/余姚工业园区开发建设/测试目录/test_2024.pdf'

print("测试开始...")
print(f"URL: {url}")
print(f"Output: {output}")

try:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    r = requests.get(url, headers=headers, timeout=60)
    print(f"Status: {r.status_code}")
    print(f"Content-Length: {len(r.content)}")
    print(f"Content-Type: {r.headers.get('Content-Type', 'unknown')}")
    
    if r.status_code == 200:
        import os
        os.makedirs(os.path.dirname(output), exist_ok=True)
        with open(output, 'wb') as f:
            f.write(r.content)
        print(f"保存成功: {output}")
    else:
        print("下载失败")
        sys.exit(1)
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
