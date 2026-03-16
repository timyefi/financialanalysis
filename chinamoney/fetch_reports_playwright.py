import asyncio
from playwright.async_api import async_playwright
import json
import os

async def fetch_reports():
    company_name = "余姚工业园区开发建设"
    queries = [
        {"year": "2024", "type": "4", "type_name": "年度报告"},
        {"year": "2023", "type": "4", "type_name": "年度报告"},
        {"year": "2022", "type": "4", "type_name": "年度报告"},
        {"year": "2024", "type": "2", "type_name": "半年度报告"},
        {"year": "2023", "type": "2", "type_name": "半年度报告"},
        {"year": "2022", "type": "2", "type_name": "半年度报告"},
    ]

    all_reports = []

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # 访问查询页面
        await page.goto('https://www.chinamoney.com.cn/chinese/cqcwbglm/')

        # 等待页面加载
        await page.wait_for_selector('#bond-finance-org')

        for query in queries:
            print(f"\n正在查询 {query['year']}年 {query['type_name']}...")

            try:
                # 填写机构名称
                await page.fill('#bond-finance-org', company_name)

                # 选择年份
                await page.select_option('#bond-finance-select-year', query['year'])

                # 选择报表类型
                await page.select_option('#bond-finance-select-type', query['type_name'])

                # 点击查询按钮
                query_button = page.get_by_role('link', name='查询')
                await query_button.click()

                # 等待新标签页打开
                await asyncio.sleep(2)

                # 获取所有页面
                pages = context.pages
                if len(pages) > 1:
                    # 切换到结果页面
                    result_page = pages[-1]
                    await result_page.wait_for_load_state('networkidle')

                    # 等待结果加载
                    await asyncio.sleep(3)

                    # 获取页面内容
                    content = await result_page.content()

                    # 解析结果
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(content, 'html.parser')

                    # 查找结果项
                    results = soup.find_all('li', class_='clearfix')

                    if results:
                        print(f"找到 {len(results)} 条记录")
                        for item in results:
                            try:
                                # 获取日期
                                date_div = item.find('div', class_='san-fl san-date')
                                date = date_div.text.strip() if date_div else ""

                                # 获取文件名
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
                    else:
                        print(f"未找到 {query['year']}年 {query['type_name']}")

                    # 关闭结果页面
                    await result_page.close()
                else:
                    print(f"未打开新标签页")

                # 返回查询页面
                await page.bring_to_front()

                # 等待一小段时间
                await asyncio.sleep(1)

            except Exception as e:
                print(f"查询 {query['year']}年 {query['type_name']} 时出错: {e}")
                # 继续下一个查询
                continue

        await browser.close()

    # 保存结果到JSON文件
    output_dir = "C:/Users/Administrator/Desktop/项目/信用工作流/余姚工业园区开发建设"
    config = {
        "output_dir": output_dir,
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
    with open("download-config.json", 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"\n\n共找到 {len(all_reports)} 份报告")
    print(f"配置已保存到 download-config.json")
    print(f"输出目录: {config['output_dir']}")

if __name__ == "__main__":
    asyncio.run(fetch_reports())
