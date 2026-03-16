import requests
from bs4 import BeautifulSoup
import json
import time
from urllib.parse import quote

# 定义查询参数
base_url = "https://www.chinamoney.com.cn/chinese/zqcwbgcwgd/"
company_name = "余姚工业园区开发建设"

# 需要查询的年份和类型组合
queries = [
    {"year": "2024", "type": "4", "type_name": "年度报告"},
    {"year": "2023", "type": "4", "type_name": "年度报告"},
    {"year": "2022", "type": "4", "type_name": "年度报告"},
    {"year": "2024", "type": "2", "type_name": "半年度报告"},
    {"year": "2023", "type": "2", "type_name": "半年度报告"},
    {"year": "2022", "type": "2", "type_name": "半年度报告"},
]

all_reports = []

for query in queries:
    print(f"\n正在查询 {query['year']}年 {query['type_name']}...")

    # 构建完整URL
    url = f"{base_url}?tabid=0&inextp=3,5&org={quote(company_name)}&year={query['year']}&repoType={query['type']}"
    print(f"请求URL: {url}")

    try:
        response = requests.get(url, timeout=30)
        response.encoding = 'utf-8'

        print(f"响应状态码: {response.status_code}")
        print(f"响应长度: {len(response.text)}")

        # 调试:保存HTML到文件
        with open(f"debug_{query['year']}_{query['type']}.html", 'w', encoding='utf-8') as f:
            f.write(response.text)

        soup = BeautifulSoup(response.text, 'html.parser')

        # 查找结果列表
        results = soup.find_all('li', class_='clearfix')

        if not results:
            print(f"未找到 {query['year']}年 {query['type_name']}")
            continue

        print(f"找到 {len(results)} 条记录")

        for item in results:
            try:
                # 获取日期
                date_div = item.find('div', class_='san-fl san-date')
                date = date_div.text.strip() if date_div else ""

                # 获取文件名和链接
                link_div = item.find('div', class_='san-fl san-title')
                if link_div:
                    file_link = link_div.find('a')
                    if file_link:
                        filename = file_link.text.strip()

                # 获取下载链接
                download_div = item.find('div', class_='san-fr')
                if download_div:
                    download_link = download_div.find('a')
                    if download_link and 'href' in download_link.attrs:
                        download_url = "https://www.chinamoney.com.cn" + download_link['href']

                        all_reports.append({
                            "year": query["year"],
                            "type": query["type_name"],
                            "date": date,
                            "filename": filename,
                            "download_url": download_url,
                            "content_id": download_url.split('contentId=')[1].split('&')[0]
                        })

                        print(f"  - {filename}")

            except Exception as e:
                print(f"解析条目时出错: {e}")
                continue

        # 添加延迟避免请求过快
        time.sleep(2)

    except Exception as e:
        print(f"查询 {query['year']}年 {query['type_name']} 时出错: {e}")
        continue

# 保存结果到JSON文件
output_file = "download-config.json"
config = {
    "output_dir": "C:/Users/Administrator/Desktop/项目/信用工作流/余姚工业园区开发建设",
    "tasks": []
}

for report in all_reports:
    # 生成输出文件名
    safe_filename = report['filename'].replace('/', '_').replace('\\', '_').replace(':', '_')
    task = {
        "name": f"{report['year']}年{report['type']} - {report['filename']}",
        "url": report['download_url'],
        "output_path": f"{report['year']}年/{report['type']}/{safe_filename}",
        "retries": 3
    }
    config["tasks"].append(task)

# 保存配置文件
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(config, f, ensure_ascii=False, indent=2)

print(f"\n\n共找到 {len(all_reports)} 份报告")
print(f"配置已保存到 {output_file}")
print(f"输出目录: {config['output_dir']}")
