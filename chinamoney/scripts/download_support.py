#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChinaMoney 下载核心能力。

这个模块统一承载：
- ChinaMoney 官方附件下载
- 421 / 429 / 5xx 的退避重试
- CNInfo 官方镜像回退
- 下载结果元数据

`download.py`、`batch-download.py` 和 P5 冷启动下载阶段都共用这里的实现。
"""

from __future__ import annotations

import datetime
import json
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests


BASE_PAGE_URL = "https://www.chinamoney.com.cn/chinese/zqcwbgcwgd/"
DOWNLOAD_BASE_URL = "https://www.chinamoney.com.cn/dqs/cm-s-notice-query/"
CNINFO_SEARCH_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_STATIC_BASE_URL = "https://static.cninfo.com.cn/"

DEFAULT_TIMEOUT = 120
DEFAULT_MAIN_RETRIES = 3
DEFAULT_FALLBACK_RETRIES = 2
DEFAULT_MAIN_BACKOFF_SECONDS = 12.0
DEFAULT_FALLBACK_BACKOFF_SECONDS = 4.0
DEFAULT_INTER_TASK_COOLDOWN_SECONDS = 1.5
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


def now_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def setup_encoding() -> None:
    if sys.platform == "win32":
        try:
            if sys.stdout.buffer is not None:
                import codecs

                sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
                sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")
        except Exception:
            pass


def default_headers(referer: str = BASE_PAGE_URL) -> Dict[str, str]:
    return {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "application/pdf,application/octet-stream,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Upgrade-Insecure-Requests": "1",
        "Referer": referer,
        "Origin": "https://www.chinamoney.com.cn",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
    }


def build_download_url(content_id: str, mode: str = "save", priority: int = 0) -> str:
    return (
        f"{DOWNLOAD_BASE_URL}fileDownLoad.do?"
        f"contentId={content_id}&priority={priority}&mode={mode}"
    )


def sanitize_filename(name: str) -> str:
    value = re.sub(r'[\\/:*?"<>|]+', "_", name.strip())
    return value or "report"


def validate_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"}


def validate_path(output_path: str) -> bool:
    if ".." in output_path.replace("\\", "/").split("/"):
        return False
    return True


def bootstrap_session(session: Optional[requests.Session] = None) -> requests.Session:
    client = session or requests.Session()
    response = client.get(
        BASE_PAGE_URL,
        headers=default_headers(referer=BASE_PAGE_URL),
        timeout=30,
    )
    response.raise_for_status()
    client.headers.update(
        {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/pdf,application/octet-stream,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
    )
    return client


def _normalize_report_type_text(report_type: str) -> str:
    value = str(report_type or "").strip()
    if value in {"4", "年度报告", "年报"}:
        return "年度报告"
    if value in {"2", "半年度报告", "半年报", "半年度"}:
        return "半年度报告"
    return value


def _cninfo_category_for_report_type(report_type: str) -> str:
    normalized = _normalize_report_type_text(report_type)
    if normalized == "半年度报告":
        return "category_bndbg_szsh;"
    if normalized == "三季度报告":
        return "category_sjdbg_szsh;"
    return "category_ndbg_szsh;"


def _candidate_source_match(title: str, year: Optional[int], report_type: str) -> bool:
    normalized_title = title.strip()
    normalized_report_type = _normalize_report_type_text(report_type)
    if year is not None and str(year) not in normalized_title:
        return False
    if normalized_report_type and normalized_report_type not in normalized_title:
        return False
    if "摘要" in normalized_title or "简要" in normalized_title:
        return False
    return True


def resolve_cninfo_mirror(
    issuer_name: str,
    *,
    year: Optional[int] = None,
    report_type: str = "年度报告",
    timeout: int = 30,
) -> Dict[str, Any]:
    issuer_name = str(issuer_name or "").strip()
    if not issuer_name:
        return {}

    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Origin": "https://www.cninfo.com.cn",
    }
    category = _cninfo_category_for_report_type(report_type)
    session = requests.Session()

    for column, plate in (("szse", "sz"), ("sse", "sh")):
        payload = {
            "pageNum": "1",
            "pageSize": "10",
            "column": column,
            "tabName": "fulltext",
            "plate": plate,
            "searchkey": issuer_name,
            "secid": "",
            "category": category,
        }
        response = session.post(CNINFO_SEARCH_URL, headers=headers, data=payload, timeout=timeout)
        response.raise_for_status()
        payload_json = response.json()
        announcements = payload_json.get("announcements") or []
        for item in announcements:
            title = str(item.get("announcementTitle", ""))
            adjunct_url = str(item.get("adjunctUrl", "")).strip()
            if not adjunct_url:
                continue
            if not _candidate_source_match(title, year, report_type):
                continue

            pdf_url = CNINFO_STATIC_BASE_URL + adjunct_url.lstrip("/")
            head_response = requests.head(
                pdf_url,
                headers={"User-Agent": DEFAULT_USER_AGENT},
                timeout=timeout,
                allow_redirects=True,
            )
            head_response.raise_for_status()
            return {
                "official_source": "cninfo_static_pdf",
                "official_download_url": pdf_url,
                "official_content_length": int(head_response.headers.get("Content-Length") or 0),
                "official_announcement_title": title,
                "official_announcement_id": str(item.get("announcementId", "")),
                "official_adjunct_url": adjunct_url,
                "official_sec_code": str(item.get("secCode", "")),
                "official_sec_name": str(item.get("secName", "")),
            }

    return {}


def _response_body_preview(response: requests.Response, limit: int = 200) -> str:
    try:
        body = response.text
    except Exception:
        return ""
    body = body.replace("\r", " ").replace("\n", " ")
    return body[:limit]


def _looks_like_pdf(path: Path) -> bool:
    try:
        with open(path, "rb") as handle:
            return handle.read(5) == b"%PDF-"
    except Exception:
        return False


def _is_probably_simplified_pdf(output_path: Path, *, fallback_lookup: Optional[Dict[str, Any]] = None) -> bool:
    if not output_path.exists() or not _looks_like_pdf(output_path):
        return False

    report_type = str((fallback_lookup or {}).get("report_type", "")).strip()
    if report_type and report_type not in {"年度报告", "半年度报告", "三季度报告", "四季度报告"}:
        return False

    try:
        from pypdf import PdfReader
    except Exception:
        return False

    try:
        reader = PdfReader(str(output_path))
    except Exception:
        return False

    page_count = len(reader.pages)
    if page_count >= 20:
        return False

    keywords = (
        "财务报表及审阅报告",
        "财务报表及审计报告",
        "审阅报告",
        "审计报告",
        "合并资产负债表",
        "母公司资产负债表",
        "合并利润表",
        "母公司利润表",
        "合并现金流量表",
        "母公司现金流量表",
        "合并股东权益变动表",
        "母公司股东权益变动表",
        "附注",
    )
    combined_text = []
    for page in reader.pages[: min(5, page_count)]:
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        if page_text:
            combined_text.append(page_text)

    try:
        outlines = reader.outline  # type: ignore[attr-defined]
    except Exception:
        outlines = []

    outline_titles: List[str] = []

    def _collect_titles(items: Any) -> None:
        if isinstance(items, list):
            for item in items:
                _collect_titles(item)
        elif isinstance(items, dict):
            title = str(items.get("/Title", "")).strip()
            if title:
                outline_titles.append(title)

    _collect_titles(outlines)

    text_blob = "\n".join(combined_text + ["\n".join(outline_titles)])
    if any(keyword in text_blob for keyword in keywords):
        return False

    return page_count < 20


def _attempt_download(
    *,
    session: requests.Session,
    source_label: str,
    url: str,
    output_path: Path,
    referer: str,
    max_retries: int,
    timeout: int,
    retry_backoff_seconds: float,
    resume: bool,
    cooldown_seconds: float,
) -> Dict[str, Any]:
    attempt_logs: List[Dict[str, Any]] = []
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".part")

    if resume and output_path.exists() and output_path.stat().st_size > 0:
        return {
            "download_status": "success",
            "download_source": "reused_existing_file",
            "download_url": url,
            "final_url": url,
            "status_code": None,
            "failure_reason": "",
            "http_status_or_error": "reused_existing_file",
            "file_size_bytes": output_path.stat().st_size,
            "attempt_count": 0,
            "attempt_logs": [],
            "fallback_used": False,
            "source_label": source_label,
        }

    last_status_code: Optional[int] = None
    last_error = ""
    last_body_preview = ""

    for attempt in range(1, max_retries + 1):
        started = time.monotonic()
        if attempt > 1:
            time.sleep(retry_backoff_seconds * (attempt - 1) + random.uniform(0.2, 0.8))
        elif cooldown_seconds > 0:
            time.sleep(cooldown_seconds)

        try:
            with session.get(
                url,
                headers=default_headers(referer=referer),
                stream=True,
                allow_redirects=True,
                timeout=(15, timeout),
            ) as response:
                last_status_code = response.status_code
                if response.status_code >= 400:
                    last_body_preview = _response_body_preview(response)
                    raise requests.HTTPError(
                        f"HTTP {response.status_code}: {last_body_preview}",
                        response=response,
                    )

                with open(tmp_path, "wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            handle.write(chunk)

            if not tmp_path.exists() or tmp_path.stat().st_size <= 0:
                raise RuntimeError("downloaded_file_empty")
            if not _looks_like_pdf(tmp_path):
                raise RuntimeError("downloaded_file_not_pdf")

            tmp_path.replace(output_path)
            file_size_bytes = output_path.stat().st_size
            attempt_logs.append(
                {
                    "attempt": attempt,
                    "source_label": source_label,
                    "status": "success",
                    "status_code": last_status_code,
                    "error": "",
                    "duration_seconds": round(time.monotonic() - started, 3),
                }
            )
            return {
                "download_status": "success",
                "download_source": source_label,
                "download_url": url,
                "final_url": response.url,
                "status_code": last_status_code,
                "failure_reason": "",
                "http_status_or_error": f"HTTP {last_status_code} ({source_label})",
                "file_size_bytes": file_size_bytes,
                "attempt_count": attempt,
                "attempt_logs": attempt_logs,
                "fallback_used": source_label != "chinamoney_official",
                "source_label": source_label,
            }
        except requests.HTTPError as exc:
            last_status_code = exc.response.status_code if exc.response is not None else None
            last_body_preview = (
                _response_body_preview(exc.response) if exc.response is not None else ""
            )
            if last_status_code in {421, 429, 500, 502, 503, 504}:
                last_error = f"http_error:{last_status_code}"
            else:
                last_error = f"http_error:{last_status_code}" if last_status_code is not None else "http_error"
        except requests.Timeout:
            last_error = "timeout"
        except requests.ConnectionError:
            last_error = "connection_error"
        except Exception as exc:
            last_error = str(exc)
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

        attempt_logs.append(
            {
                "attempt": attempt,
                "source_label": source_label,
                "status": "failed",
                "status_code": last_status_code,
                "error": last_error,
                "body_preview": last_body_preview,
                "duration_seconds": round(time.monotonic() - started, 3),
            }
        )

    return {
        "download_status": "failed",
        "download_source": source_label,
        "download_url": url,
        "final_url": "",
        "status_code": last_status_code,
        "failure_reason": last_error or "download_failed",
        "http_status_or_error": (
            f"HTTP {last_status_code}"
            if last_status_code is not None
            else (last_error or "download_failed")
        ),
        "file_size_bytes": output_path.stat().st_size if output_path.exists() else 0,
        "attempt_count": max_retries,
        "attempt_logs": attempt_logs,
        "fallback_used": source_label != "chinamoney_official",
        "source_label": source_label,
    }


def download_file_with_metadata(
    url: str,
    output_path: str,
    *,
    max_retries: int = DEFAULT_MAIN_RETRIES,
    timeout: int = DEFAULT_TIMEOUT,
    resume: bool = True,
    referer: Optional[str] = None,
    fallback_url: str = "",
    fallback_retries: int = DEFAULT_FALLBACK_RETRIES,
    main_backoff_seconds: float = DEFAULT_MAIN_BACKOFF_SECONDS,
    fallback_backoff_seconds: float = DEFAULT_FALLBACK_BACKOFF_SECONDS,
    cooldown_seconds: float = DEFAULT_INTER_TASK_COOLDOWN_SECONDS,
    fallback_lookup: Optional[Dict[str, Any]] = None,
    session: Optional[requests.Session] = None,
) -> Dict[str, Any]:
    output = Path(output_path)
    referer_value = referer or BASE_PAGE_URL
    client = bootstrap_session(session)

    result: Dict[str, Any] = {
        "generated_at": now_iso(),
        "download_status": "failed",
        "download_source": "",
        "download_url": url,
        "final_url": "",
        "fallback_url": fallback_url,
        "status_code": None,
        "failure_reason": "",
        "http_status_or_error": "",
        "file_size_bytes": 0,
        "attempt_count": 0,
        "attempt_logs": [],
        "fallback_used": False,
        "resolved_fallback": False,
        "output_path": str(output.resolve()),
    }

    simplified_requery_hint = fallback_lookup or {}

    primary = _attempt_download(
        session=client,
        source_label="chinamoney_official",
        url=url,
        output_path=output,
        referer=referer_value,
        max_retries=max(1, max_retries),
        timeout=timeout,
        retry_backoff_seconds=main_backoff_seconds,
        resume=resume,
        cooldown_seconds=cooldown_seconds,
    )
    result["attempt_count"] += int(primary.get("attempt_count") or 0)
    primary_logs = list(primary.get("attempt_logs") or [])
    result["attempt_logs"].extend(primary_logs)
    if primary.get("download_status") == "success":
        result.update(primary)
        result["attempt_logs"] = primary_logs
        result["resolved_fallback"] = False
        if _is_probably_simplified_pdf(output, fallback_lookup=simplified_requery_hint):
            result["followup_required"] = True
            result["followup_reason"] = "brief_pdf_should_be_used_as_index_for_official_exchange_links"
            result["followup_action"] = "extract_official_exchange_links_from_brief_pdf"
            result["followup_targets"] = ["szse", "sse"]
            result["brief_pdf_detected"] = True
            result["brief_pdf_message"] = (
                "downloaded_pdf_looks_like_brief_index_follow_official_exchange_links"
            )
            result["file_size_bytes"] = output.stat().st_size if output.exists() else 0
            result["followup_hint"] = {
                "issuer_name": simplified_requery_hint.get("issuer_name", ""),
                "year": simplified_requery_hint.get("year"),
                "report_type": simplified_requery_hint.get("report_type", ""),
                "message": "downloaded_index_style_pdf_follow_szse_or_sse_links_for_full_report",
                "action": "follow_official_exchange_links",
            }
            return result
        return result

    resolved_fallback_url = fallback_url.strip()
    fallback_metadata: Dict[str, Any] = {}
    if not resolved_fallback_url and fallback_lookup:
        try:
            fallback_metadata = resolve_cninfo_mirror(
                str(fallback_lookup.get("issuer_name", "")),
                year=fallback_lookup.get("year"),
                report_type=str(fallback_lookup.get("report_type", "年度报告")),
                timeout=min(timeout, 30),
            )
            resolved_fallback_url = str(fallback_metadata.get("official_download_url", "")).strip()
        except Exception as exc:
            fallback_metadata = {"fallback_resolution_error": str(exc)}

    result["resolved_fallback"] = bool(resolved_fallback_url)
    if resolved_fallback_url:
        result["fallback_url"] = resolved_fallback_url
        fallback = _attempt_download(
            session=client,
            source_label="cninfo_mirror",
            url=resolved_fallback_url,
            output_path=output,
            referer=referer_value,
            max_retries=max(1, fallback_retries),
            timeout=timeout,
            retry_backoff_seconds=fallback_backoff_seconds,
            resume=resume,
            cooldown_seconds=cooldown_seconds,
        )
        fallback_logs = list(fallback.get("attempt_logs") or [])
        result["attempt_logs"].extend(fallback_logs)
        if fallback.get("download_status") == "success":
            total_attempt_count = int(result.get("attempt_count") or 0) + int(fallback.get("attempt_count") or 0)
            result.update(fallback)
            result["attempt_logs"] = primary_logs + fallback_logs
            result["download_source"] = "cninfo_mirror"
            result["download_url"] = url
            result["fallback_url"] = resolved_fallback_url
            result["fallback_used"] = True
            result["attempt_count"] = total_attempt_count
            if fallback_metadata:
                result["fallback_metadata"] = fallback_metadata
            if _is_probably_simplified_pdf(output, fallback_lookup=simplified_requery_hint):
                result["followup_required"] = True
                result["followup_reason"] = "brief_pdf_should_be_used_as_index_for_official_exchange_links"
                result["followup_action"] = "extract_official_exchange_links_from_brief_pdf"
                result["followup_targets"] = ["szse", "sse"]
                result["brief_pdf_detected"] = True
                result["brief_pdf_message"] = (
                    "downloaded_pdf_looks_like_brief_index_follow_official_exchange_links"
                )
                result["file_size_bytes"] = output.stat().st_size if output.exists() else 0
                result["followup_hint"] = {
                    "issuer_name": simplified_requery_hint.get("issuer_name", ""),
                    "year": simplified_requery_hint.get("year"),
                    "report_type": simplified_requery_hint.get("report_type", ""),
                    "message": "downloaded_index_style_pdf_follow_szse_or_sse_links_for_full_report",
                    "action": "follow_official_exchange_links",
                }
                return result
            return result
        result["fallback_used"] = True
        if fallback_metadata:
            result["fallback_metadata"] = fallback_metadata
        total_attempt_count = int(result.get("attempt_count") or 0) + int(fallback.get("attempt_count") or 0)
        result["failure_reason"] = fallback.get("failure_reason") or primary.get("failure_reason") or "download_failed"
        result["status_code"] = fallback.get("status_code") or primary.get("status_code")
        result["http_status_or_error"] = fallback.get("http_status_or_error") or primary.get("http_status_or_error") or "download_failed"
        result["file_size_bytes"] = output.stat().st_size if output.exists() else 0
        result["attempt_logs"] = primary_logs + fallback_logs
        result["attempt_count"] = total_attempt_count
        return result

    result["failure_reason"] = primary.get("failure_reason") or "download_failed"
    result["status_code"] = primary.get("status_code")
    result["http_status_or_error"] = primary.get("http_status_or_error") or "download_failed"
    result["file_size_bytes"] = output.stat().st_size if output.exists() else 0
    if fallback_metadata:
        result["fallback_metadata"] = fallback_metadata
    return result


def download_file(url: str, output_path: str, max_retries: int = DEFAULT_MAIN_RETRIES, timeout: int = DEFAULT_TIMEOUT, resume: bool = True, **kwargs: Any) -> bool:
    result = download_file_with_metadata(
        url,
        output_path,
        max_retries=max_retries,
        timeout=timeout,
        resume=resume,
        **kwargs,
    )
    return result.get("download_status") == "success"


def _print_result(result: Dict[str, Any]) -> None:
    print("=" * 50)
    print(f"下载状态: {result.get('download_status')}")
    print(f"下载来源: {result.get('download_source') or result.get('source_label')}")
    print(f"URL: {result.get('download_url')}")
    if result.get("final_url"):
        print(f"最终URL: {result.get('final_url')}")
    if result.get("status_code") is not None:
        print(f"HTTP状态: {result.get('status_code')}")
    if result.get("failure_reason"):
        print(f"失败原因: {result.get('failure_reason')}")
    if result.get("file_size_bytes"):
        print(f"文件大小: {result.get('file_size_bytes') / 1024 / 1024:.2f} MB")
    print(f"保存路径: {result.get('output_path')}")
    if result.get("fallback_used"):
        print("[INFO] 使用了官方镜像回退")
    print("=" * 50)


def cli_main() -> int:
    setup_encoding()
    if len(sys.argv) < 3:
        print("使用方法: python download.py <URL> <输出路径> [最大重试次数]")
        print()
        print("示例:")
        print("  python download.py https://example.com/file.pdf C:/Downloads/file.pdf")
        print("  python download.py https://example.com/file.pdf C:/Downloads/file.pdf 5")
        return 1

    url = sys.argv[1]
    output_path = sys.argv[2]
    max_retries = int(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_MAIN_RETRIES

    if not validate_url(url):
        print(f"[FAIL] Invalid URL: {url}")
        return 1
    if not validate_path(output_path):
        print(f"[FAIL] Invalid path: {output_path}")
        return 1

    result = download_file_with_metadata(url, output_path, max_retries=max_retries)
    _print_result(result)
    return 0 if result.get("download_status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(cli_main())
