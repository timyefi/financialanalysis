#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量下载工具 - 配置文件驱动
只需修改配置文件即可使用
"""

import json
import os
import sys

# 获取脚本所在目录，确保导入路径正确
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

# 配置文件路径
CONFIG_FILE = "download-config.json"

def load_config(config_path):
    """加载配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def download_file_from_config(task):
    """下载单个文件"""
    url = task['url']
    output_path = task['output_path']
    name = task.get('name', os.path.basename(output_path))
    retries = task.get('retries', 3)

    print(f"\n下载: {name}")
    print("-" * 60)

    # 直接导入download模块，避免subprocess编码问题
    try:
        from download import download_file
        return download_file(url, output_path, retries)
    except Exception as e:
        print(f"执行失败: {e}")
        return False

def main():
    # 设置输出编码
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    # 支持命令行指定配置文件
    config_file = sys.argv[1] if len(sys.argv) > 1 else CONFIG_FILE

    # 检查配置文件
    if not os.path.exists(config_file):
        print(f"错误: 配置文件不存在: {config_file}")
        print("\n请先创建配置文件，格式如下：")
        print("""
{
    "output_dir": "C:/Users/Administrator/Downloads",
    "tasks": [
        {
            "name": "文件1",
            "url": "https://example.com/file1.pdf",
            "output_path": "文件1.pdf",
            "retries": 3
        },
        {
            "name": "文件2",
            "url": "https://example.com/file2.pdf",
            "output_path": "文件2.pdf",
            "retries": 3
        }
    ]
}
        """)
        sys.exit(1)

    # 加载配置
    try:
        config = load_config(config_file)
    except Exception as e:
        print(f"配置文件格式错误: {e}")
        sys.exit(1)

    # 获取输出目录
    output_dir = config.get('output_dir', '')
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    # 批量下载
    tasks = config.get('tasks', [])
    print("=" * 60)
    print(f"开始批量下载 ({len(tasks)} 个文件)")
    print("=" * 60)

    success_count = 0
    failed_count = 0

    for i, task in enumerate(tasks, 1):
        print(f"\n[{i}/{len(tasks)}]", end=" ")

        # 处理输出路径
        output_path = task.get('output_path', '')
        if output_dir and not os.path.isabs(output_path):
            output_path = os.path.join(output_dir, output_path)

        # 更新任务中的输出路径
        task['output_path'] = output_path

        if download_file_from_config(task):
            success_count += 1
            print("成功")
        else:
            failed_count += 1
            print("失败")

    # 统计结果
    print("\n" + "=" * 60)
    print("下载完成")
    print(f"成功: {success_count}, 失败: {failed_count}, 总计: {len(tasks)}")
    print("=" * 60)

    # 列出已下载的文件
    if output_dir and os.path.exists(output_dir):
        print("\n已下载的文件:")
        files = [f for f in os.listdir(output_dir)]
        for filename in files:
            filepath = os.path.join(output_dir, filename)
            if os.path.isfile(filepath):
                size_mb = os.path.getsize(filepath) / 1024 / 1024
                print(f"  {filename} - {size_mb:.2f} MB")

if __name__ == "__main__":
    main()
