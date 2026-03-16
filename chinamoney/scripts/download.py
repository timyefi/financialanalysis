#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
通用文件下载工具
支持进度显示、自动重试、断点续传
"""

import sys
import os

# Windows下设置控制台编码 - 只在直接运行时设置，import时不设置
import requests
import time
from urllib.parse import urlparse

# 设置编码的函数
def setup_encoding():
    if sys.platform == 'win32':
        try:
            if sys.stdout.buffer is not None:
                import codecs
                sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
                sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
        except Exception:
            pass

def download_file(url, output_path, max_retries=3, timeout=120, resume=True):
    """
    下载文件到指定路径

    Args:
        url: 下载URL
        output_path: 输出文件路径
        max_retries: 最大重试次数
        timeout: 超时时间（秒）

    Returns:
        bool: 下载是否成功
    """
    retry_count = 0
    success = False

    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    # 检查写入权限
    if output_dir:
        try:
            test_file = os.path.join(output_dir, '.write_test')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
        except PermissionError:
            print(f"[FAIL] No write permission for directory: {output_dir}")
            return False
        except Exception as e:
            print(f"[FAIL] Cannot write to directory: {output_dir}")
            print(f"       Error: {e}")
            return False

    print("=" * 50)
    print(f"开始下载: {os.path.basename(output_path)}")
    print(f"URL: {url}")
    print("=" * 50)

    while retry_count < max_retries and not success:
        retry_count += 1

        if retry_count > 1:
            print(f"第 {retry_count} 次重试...")
            time.sleep(2)

        try:
            # 添加User-Agent
            req_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }

            # 获取文件大小（用于进度显示）
            head_response = requests.head(url, headers=req_headers, timeout=10, allow_redirects=True)
            head_response.raise_for_status()
            total_size = int(head_response.headers.get('content-length', 0))

            # 检查是否支持断点续传
            local_size = 0
            mode = 'wb'
            range_headers = {}

            if resume and os.path.exists(output_path):
                local_size = os.path.getsize(output_path)
                if local_size > 0 and local_size < total_size:
                    # 检查服务器是否支持Range请求
                    if 'accept-ranges' in head_response.headers.lower():
                        range_headers['Range'] = f'bytes={local_size}-'
                        mode = 'ab'
                        downloaded_size = local_size
                        print(f"[INFO] Resuming download from {local_size/1024/1024:.2f} MB")
                    else:
                        # 不支持断点续传，重新下载
                        print("[INFO] Server does not support resume, restarting download")

            # 下载文件（使用流式下载，支持大文件）
            chunk_size = 8192

            with requests.get(url, headers={**req_headers, **range_headers}, stream=True, timeout=(10, timeout)) as response:
                response.raise_for_status()

                # 检查断点续传是否成功
                if range_headers and response.status_code != 206:
                    # 服务器不支持Range，重新下载
                    mode = 'wb'
                    downloaded_size = 0
                    print("[INFO] Server does not support resume, restarting download")

                # 确保downloaded_size已初始化
                if 'downloaded_size' not in locals():
                    downloaded_size = 0

                with open(output_path, mode) as f:
                    start_time = time.time()

                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)

                            # 显示进度
                            if total_size > 0:
                                progress = (downloaded_size / total_size) * 100
                                elapsed = time.time() - start_time
                                if elapsed > 0:
                                    speed = downloaded_size / elapsed / 1024 / 1024  # MB/s
                                    print(f"\r下载进度: {progress:.1f}% ({downloaded_size/1024/1024:.2f} MB / {total_size/1024/1024:.2f} MB, 速度: {speed:.2f} MB/s)", end='', flush=True)

                    print()  # 换行

                # 验证文件
                if os.path.exists(output_path):
                    file_size = os.path.getsize(output_path)
                    if file_size > 0:
                        file_size_mb = file_size / 1024 / 1024

                        # 检查文件完整性
                        if total_size > 0 and file_size < total_size:
                            print(f"[WARN] File incomplete: {file_size_mb:.2f} MB / {total_size/1024/1024:.2f} MB")
                            # 不删除文件，下次可以断点续传
                            success = False
                        else:
                            print(f"[OK] Download success! File size: {file_size_mb:.2f} MB")
                            print(f"Save path: {output_path}")
                            success = True
                    else:
                        print("[FAIL] Downloaded file is empty")
                        os.remove(output_path)
                else:
                    print("[FAIL] File not created")

        except requests.exceptions.Timeout:
            print("\n[FAIL] Download timeout")
        except requests.exceptions.SSLError:
            print("\n[FAIL] SSL certificate verification failed")
        except requests.exceptions.ConnectionError:
            print("\n[FAIL] Connection failed")
            print("       Please check:")
            print("       1. Network connection")
            print("       2. URL correctness")
            print("       3. Proxy settings if needed")
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else 'Unknown'
            print(f"\n[FAIL] HTTP error: {status}")
            if status == 403:
                print("       Access forbidden, check permissions")
            elif status == 404:
                print("       Resource not found, check URL")
            elif status >= 500:
                print("       Server error, please retry later")
        except PermissionError:
            print("\n[FAIL] No write permission for the target directory")
        except Exception as e:
            print(f"\n[FAIL] Unknown error: {e}")

        # 清理失败的文件（保留不完整文件以便断点续传）
        if not success and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            if file_size == 0:
                # 空文件删除
                try:
                    os.remove(output_path)
                except:
                    pass
            else:
                # 不完整文件保留，提示可以断点续传
                print(f"[INFO] Incomplete file saved: {file_size/1024/1024:.2f} MB")
                print(f"[INFO] Run again to resume download")

    if not success:
        print(f"[FAIL] Download failed, max retries reached ({max_retries})")
        return False

    print("=" * 50)
    return True

def validate_url(url):
    """验证URL安全性"""
    parsed = urlparse(url)
    if parsed.scheme not in ['http', 'https']:
        print(f"[FAIL] Invalid URL scheme: {parsed.scheme}")
        print("       Only HTTP and HTTPS are supported")
        return False
    return True

def validate_path(output_path):
    """验证路径安全性"""
    # 检查路径遍历攻击
    if '..' in output_path.replace('\\', '/').split('/'):
        print("[FAIL] Invalid path: contains '..' (path traversal attempt)")
        return False
    return True

def main():
    setup_encoding()
    if len(sys.argv) < 3:
        print("使用方法: python download.py <URL> <输出路径> [最大重试次数]")
        print()
        print("示例:")
        print("  python download.py https://example.com/file.pdf C:/Downloads/file.pdf")
        print("  python download.py https://example.com/file.pdf C:/Downloads/file.pdf 5")
        sys.exit(1)

    url = sys.argv[1]
    output_path = sys.argv[2]
    max_retries = int(sys.argv[3]) if len(sys.argv) > 3 else 3

    # 验证URL和路径
    if not validate_url(url):
        sys.exit(1)
    if not validate_path(output_path):
        sys.exit(1)

    success = download_file(url, output_path, max_retries)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
