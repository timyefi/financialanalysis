import requests
import os

# 下载函数
def download_file(url, filepath):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()
        
        # 确保目录存在
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'wb') as f:
            f.write(response.content)
        
        print(f"下载成功: {filepath} - 大小: {len(response.content)} bytes")
        return True
    except Exception as e:
        print(f"下载失败: {filepath} - 错误: {e}")
        return False

# 所有下载任务
tasks = [
    ("https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3106435&priority=0&mode=save",
     "C:/Users/Administrator/Desktop/项目/信用工作流/余姚工业园区开发建设/年报/浙江余姚工业园区开发建设投资有限公司2024年年度报告.pdf"),
    ("https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=2867096&priority=0&mode=save",
     "C:/Users/Administrator/Desktop/项目/信用工作流/余姚工业园区开发建设/年报/浙江余姚工业园区开发建设投资有限公司2023年年度报告.pdf"),
    ("https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=2609125&priority=0&mode=save",
     "C:/Users/Administrator/Desktop/项目/信用工作流/余姚工业园区开发建设/年报/浙江余姚工业园区开发建设投资有限公司2022年年度报告.pdf"),
    ("https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=2950974&priority=0&mode=save",
     "C:/Users/Administrator/Desktop/项目/信用工作流/余姚工业园区开发建设/半年报/浙江余姚工业园区开发建设投资有限公司2024年半年度报告.pdf"),
    ("https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=2703784&priority=0&mode=save",
     "C:/Users/Administrator/Desktop/项目/信用工作流/余姚工业园区开发建设/半年报/浙江余姚工业园区开发建设投资有限公司2023年半年度报告.pdf"),
    ("https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=2450365&priority=0&mode=save",
     "C:/Users/Administrator/Desktop/项目/信用工作流/余姚工业园区开发建设/半年报/浙江余姚工业园区开发建设投资有限公司2022年半年度报告.pdf"),
    ("https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3175377&priority=0&mode=save",
     "C:/Users/Administrator/Desktop/项目/信用工作流/余姚工业园区开发建设/评级报告/2025年度浙江余姚工业园区开发建设投资有限公司信用评级报告(8月).pdf"),
    ("https://www.chinamoney.com.cn/dqs/cm-s-notice-query/fileDownLoad.do?contentId=3161829&priority=0&mode=save",
     "C:/Users/Administrator/Desktop/项目/信用工作流/余姚工业园区开发建设/评级报告/2025年度浙江余姚工业园区开发建设投资有限公司信用评级报告(7月).pdf"),
]

# 执行下载
success_count = 0
for url, filepath in tasks:
    print(f"\n正在下载: {os.path.basename(filepath)}")
    if download_file(url, filepath):
        success_count += 1

print(f"\n\n下载完成! 成功: {success_count}/{len(tasks)}")
