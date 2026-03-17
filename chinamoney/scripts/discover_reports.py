#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChinaMoney 财报发现脚本。

支持：
- 通过官方 JSON 接口按 issuer 或全市场发现财报
- 自动建立会话，规避直接调用接口时的 403
- 可选用 HEAD 获取附件元数据（如 Content-Length）
"""

import argparse
import datetime
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


BASE_PAGE_URL = "https://www.chinamoney.com.cn/chinese/zqcwbgcwgd/"
API_BASE_URL = "https://www.chinamoney.com.cn/ags/ms"
YEAR_AND_TYPE_ENDPOINT = "/cm-u-notice-an/staYearAndType"
FINANCE_REPO_ENDPOINT = "/cm-u-notice-issue/financeRepo"
DOWNLOAD_BASE_URL = "https://www.chinamoney.com.cn/dqs/cm-s-notice-query/"
SITE_ROOT = "https://www.chinamoney.com.cn"
DEFAULT_TIMEOUT = 30
DEFAULT_PAGE_SIZE = 30
DEFAULT_MAX_ATTEMPTS = 4


def now_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def default_headers(referer: str = BASE_PAGE_URL) -> Dict[str, str]:
    return {
        "Referer": referer,
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "X-Requested-With": "XMLHttpRequest",
    }


def build_draft_page_url(draft_path: str) -> str:
    if draft_path.startswith("http://") or draft_path.startswith("https://"):
        return draft_path
    return SITE_ROOT + draft_path


def build_download_url(content_id: str, mode: str = "save", priority: int = 0) -> str:
    return (
        f"{DOWNLOAD_BASE_URL}fileDownLoad.do?"
        f"contentId={content_id}&priority={priority}&mode={mode}"
    )


def sanitize_filename(name: str) -> str:
    value = re.sub(r'[\\/:*?"<>|]+', "_", name.strip())
    return value or "report"


def request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    backoff_seconds: float = 1.0,
    timeout: int = DEFAULT_TIMEOUT,
    **kwargs: Any,
) -> Dict[str, Any]:
    last_error: Optional[str] = None
    merged_headers = default_headers()
    if headers:
        merged_headers.update(headers)

    for attempt in range(1, max_attempts + 1):
        try:
            response = session.request(
                method=method,
                url=url,
                headers=merged_headers,
                timeout=timeout,
                **kwargs,
            )
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, json.JSONDecodeError) as exc:
            last_error = str(exc)
            if attempt == max_attempts:
                break
            time.sleep(backoff_seconds * attempt)

    raise RuntimeError(f"请求 JSON 失败: {url}; last_error={last_error}")


def bootstrap_session(session: Optional[requests.Session] = None) -> requests.Session:
    client = session or requests.Session()
    response = client.get(
        BASE_PAGE_URL,
        headers=default_headers(referer=BASE_PAGE_URL),
        timeout=DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    return client


def fetch_year_and_types(session: requests.Session) -> Dict[str, Any]:
    return request_json(
        session,
        "post",
        API_BASE_URL + YEAR_AND_TYPE_ENDPOINT,
        headers=default_headers(),
    )


def fetch_finance_repo_page(
    session: requests.Session,
    *,
    year: int,
    report_type: str,
    org_name: str = "",
    page_no: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    inextp: str = "3,5",
    limit: int = 1,
) -> Dict[str, Any]:
    payload = {
        "year": str(year),
        "type": str(report_type),
        "orgName": org_name,
        "pageSize": str(page_size),
        "pageNo": str(page_no),
        "inextp": inextp,
        "limit": str(limit),
    }
    result = request_json(
        session,
        "post",
        API_BASE_URL + FINANCE_REPO_ENDPOINT,
        headers=default_headers(),
        data=payload,
    )
    data = result.get("data") or {}
    records = result.get("records") or []
    return {
        "page_no": page_no,
        "page_size": page_size,
        "total": int(data.get("total") or 0),
        "page_total_size": int(data.get("pageTotalSize") or 0),
        "records": records,
    }


def head_attachment_metadata(
    session: requests.Session,
    *,
    content_id: str,
    draft_page_url: str,
    timeout: int = DEFAULT_TIMEOUT,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> Dict[str, Any]:
    url = build_download_url(content_id)
    last_error: Optional[str] = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = session.head(
                url,
                allow_redirects=True,
                headers=default_headers(referer=draft_page_url),
                timeout=timeout,
            )
            response.raise_for_status()
            return {
                "url": url,
                "status_code": response.status_code,
                "content_length": int(response.headers.get("Content-Length") or 0),
                "content_type": response.headers.get("Content-Type", ""),
                "content_disposition": response.headers.get("content-disposition", ""),
            }
        except requests.RequestException as exc:
            last_error = str(exc)
            if attempt == max_attempts:
                break
            time.sleep(float(attempt))
    raise RuntimeError(f"HEAD 附件失败: content_id={content_id}; last_error={last_error}")


def enrich_record(
    session: requests.Session,
    record: Dict[str, Any],
    *,
    include_head: bool = False,
) -> Dict[str, Any]:
    content_id = str(record.get("contentId", ""))
    draft_path = str(record.get("draftPath", ""))
    draft_page_url = build_draft_page_url(draft_path) if draft_path else ""
    enriched = {
        "content_id": content_id,
        "title": str(record.get("title", "")),
        "release_date": str(record.get("releaseDate", "")),
        "draft_path": draft_path,
        "draft_page_url": draft_page_url,
        "download_url": build_download_url(content_id) if content_id else "",
        "channel_path": str(record.get("channelPath", "")),
        "suffix": str(record.get("suffix", "")),
        "attachment_count": int(record.get("attSize") or 0),
        "raw_record": record,
    }
    if include_head and content_id and draft_page_url:
        try:
            enriched["attachment_head"] = head_attachment_metadata(
                session,
                content_id=content_id,
                draft_page_url=draft_page_url,
            )
        except RuntimeError as exc:
            enriched["attachment_head_error"] = str(exc)
    return enriched


def discover_reports(
    *,
    year: int,
    report_type: str,
    org_name: str = "",
    page_size: int = DEFAULT_PAGE_SIZE,
    max_pages: int = 1,
    include_head: bool = False,
    sleep_seconds: float = 0.0,
) -> Dict[str, Any]:
    session = bootstrap_session()
    year_and_type = fetch_year_and_types(session)

    pages: List[Dict[str, Any]] = []
    enriched_records: List[Dict[str, Any]] = []
    total_records = 0
    page_total_size = 0

    for page_no in range(1, max_pages + 1):
        page = fetch_finance_repo_page(
            session,
            year=year,
            report_type=report_type,
            org_name=org_name,
            page_no=page_no,
            page_size=page_size,
        )
        pages.append(
            {
                "page_no": page_no,
                "record_count": len(page["records"]),
            }
        )
        total_records = page["total"]
        page_total_size = page["page_total_size"]

        for record in page["records"]:
            enriched_records.append(
                enrich_record(
                    session,
                    record,
                    include_head=include_head,
                )
            )

        if page_no >= page_total_size or not page["records"]:
            break
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    return {
        "generated_at": now_iso(),
        "query": {
            "year": year,
            "report_type": str(report_type),
            "org_name": org_name,
            "page_size": page_size,
            "max_pages": max_pages,
            "include_head": include_head,
        },
        "year_and_type_head": year_and_type.get("head", {}),
        "year_and_type_data": year_and_type.get("data", {}),
        "page_summary": {
            "fetched_page_count": len(pages),
            "reported_total_records": total_records,
            "reported_total_pages": page_total_size,
        },
        "pages": pages,
        "records": enriched_records,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover ChinaMoney finance reports")
    parser.add_argument("--year", type=int, required=True, help="报告年度，例如 2024")
    parser.add_argument("--report-type", default="4", help="ChinaMoney report type，默认 4=年度报告")
    parser.add_argument("--org-name", default="", help="机构名称；为空时拉全市场分页结果")
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE, help="每页条数")
    parser.add_argument("--max-pages", type=int, default=1, help="最大抓取页数")
    parser.add_argument("--include-head", action="store_true", help="对每条记录执行附件 HEAD 获取元数据")
    parser.add_argument("--sleep-seconds", type=float, default=0.0, help="分页请求间隔")
    parser.add_argument("--output", help="输出 JSON 文件路径")
    return parser.parse_args()


def write_json(path: Path, payload: Dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def main():
    args = parse_args()
    payload = discover_reports(
        year=args.year,
        report_type=str(args.report_type),
        org_name=args.org_name,
        page_size=args.page_size,
        max_pages=args.max_pages,
        include_head=args.include_head,
        sleep_seconds=args.sleep_seconds,
    )

    if args.output:
        write_json(Path(args.output), payload)
        print(f"[OK] 输出: {args.output}")
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    print(
        "[OK] 发现完成: "
        f"records={len(payload['records'])}, "
        f"reported_total={payload['page_summary']['reported_total_records']}"
    )


if __name__ == "__main__":
    main()
