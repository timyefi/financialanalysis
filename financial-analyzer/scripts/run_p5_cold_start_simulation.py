#!/usr/bin/env python3
"""
P5 冷启动全真生产仿真入口。

阶段 A：
- 读取 P4 输出目录中的 selection_manifest / download_config / task_seed_list
- 执行 ChinaMoney 真实下载
- 生成 download_phase_manifest.json，并按成功数判断 gate

阶段 B：
- 仅对下载成功的样本调用 MinerU 生成 Markdown
- 生成最小 notes_workfile
- 适配为 run_batch_pipeline.py 可消费的 batch task list
- 满足 gate 后继续执行批处理与 governance review
"""

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from runtime_support import (
    RuntimeConfigError,
    load_runtime_config,
    resolve_runtime_path,
    runtime_project_root,
)


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
CHINAMONEY_SCRIPT_DIR = REPO_ROOT / "chinamoney" / "scripts"
if str(CHINAMONEY_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(CHINAMONEY_SCRIPT_DIR))

from discover_reports import BASE_PAGE_URL, bootstrap_session, default_headers  # type: ignore


DOWNLOAD_PHASE_MANIFEST = "download_phase_manifest.json"
PREPARATION_MANIFEST = "preparation_manifest.json"
P5_MANIFEST = "p5_run_manifest.json"
BATCH_TASK_LIST = "batch_task_list.json"
DEFAULT_DOWNLOAD_THRESHOLD = 8
DEFAULT_DOWNLOAD_TIMEOUT = 120
DEFAULT_MINERU_MAX_ATTEMPTS = 2
NOTE_SECTION_KEYWORDS = [
    "财务报表附注",
    "合并财务报表附注",
    "合并财务报表项目注释",
    "notes to the financial statements",
    "附注逐章分析",
    "附注关键发现",
]
NOTE_SECTION_END_KEYWORDS = [
    "十年财务概要",
    "五年财务概要",
    "财务报表补充资料",
    "补充资料",
    "词汇",
    "glossary",
]
MIN_NOTE_HEADING_COUNT = 2
NOTE_HEADING_RE = re.compile(
    r"^\s{0,3}#{1,6}\s*(?:附注\s*)?(?P<note_no>\(?\d{1,3}(?:\.\d+)?\)?)\s*[-.、）)]?\s*(?P<title>.+?)\s*$"
)
P4_CONTENT_ID_RE = re.compile(r"contentId=(\d+)")


def now_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def timestamp_slug() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def read_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="P5 cold-start production simulation runner")
    parser.add_argument("--p4-dir", required=True, help="P4 输出目录")
    parser.add_argument("--runtime-config", help="显式指定 runtime/runtime_config.json")
    parser.add_argument("--output-dir", help="P5 输出目录；默认写入 runtime/state/tmp/p5_cold_start/<timestamp>")
    parser.add_argument(
        "--download-threshold",
        type=int,
        default=DEFAULT_DOWNLOAD_THRESHOLD,
        help="阶段 A 真实下载成功门槛，默认 8",
    )
    parser.add_argument(
        "--download-timeout",
        type=int,
        default=DEFAULT_DOWNLOAD_TIMEOUT,
        help="单次下载超时秒数，默认 120",
    )
    parser.add_argument(
        "--no-build-review-bundle",
        action="store_true",
        help="阶段 B 不调用 run_batch_pipeline.py 的 review bundle 构建",
    )
    parser.add_argument(
        "--mineru-max-attempts",
        type=int,
        default=DEFAULT_MINERU_MAX_ATTEMPTS,
        help="单份 PDF 的 MinerU 最大尝试次数，默认 2",
    )
    parser.add_argument(
        "--resume-output-dir",
        action="store_true",
        help="若 output_dir 已存在，则复用已下载/已解析产物而不是删除重跑",
    )
    return parser.parse_args()


def load_p4_inputs(p4_dir: Path) -> Dict[str, Any]:
    selection_manifest = p4_dir / "selection_manifest.json"
    download_config = p4_dir / "download_config.json"
    task_seed_list = p4_dir / "task_seed_list.json"
    required_paths = [selection_manifest, download_config, task_seed_list]
    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        raise SystemExit(f"P4 输入不完整，缺失: {', '.join(missing)}")
    return {
        "selection_manifest_path": selection_manifest,
        "download_config_path": download_config,
        "task_seed_list_path": task_seed_list,
        "selection_manifest": read_json(selection_manifest),
        "download_config": read_json(download_config),
        "task_seed_list": read_json(task_seed_list),
    }


def discover_mineru_token() -> bool:
    return bool(load_mineru_token_value())


def load_mineru_token_value() -> str:
    env_token = os.environ.get("MINERU_TOKEN", "").strip()
    if env_token:
        return env_token
    config_path = REPO_ROOT / "mineru" / "config.json"
    if not config_path.exists():
        return ""
    try:
        payload = read_json(config_path)
    except Exception:
        return ""
    return str(payload.get("token", "")).strip()


def check_skill_status(runtime_config: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "financial_analyzer": {
            "status": "available",
            "runtime_config_path": str(Path(str(runtime_config["_config_path"])).resolve()),
            "run_batch_pipeline_exists": (SCRIPT_DIR / "run_batch_pipeline.py").exists(),
        },
        "chinamoney": {
            "status": "available",
            "discover_reports_exists": (CHINAMONEY_SCRIPT_DIR / "discover_reports.py").exists(),
            "download_script_exists": (CHINAMONEY_SCRIPT_DIR / "download.py").exists(),
            "batch_download_script_exists": (CHINAMONEY_SCRIPT_DIR / "batch-download.py").exists(),
        },
        "mineru": {
            "status": "available" if (REPO_ROOT / "mineru" / "scripts" / "mineru_stable.py").exists() else "missing",
            "script_path": str((REPO_ROOT / "mineru" / "scripts" / "mineru_stable.py").resolve()),
            "token_present": discover_mineru_token(),
        },
    }


def extract_content_id_from_url(url: str) -> str:
    match = P4_CONTENT_ID_RE.search(url)
    return match.group(1) if match else ""


def build_seed_index(task_seed_list: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}
    for task in task_seed_list.get("tasks", []):
        source = task.get("source") or {}
        content_id = str(source.get("content_id", "")).strip()
        if content_id:
            index[content_id] = task
    return index


def status_or_error_label(status_code: Optional[int], error_text: str) -> str:
    if status_code is not None:
        return f"HTTP {status_code}"
    return error_text or "unknown_error"


def download_one_task(
    *,
    task_id: str,
    task: Dict[str, Any],
    output_root: Path,
    timeout: int,
    resume_existing: bool,
) -> Dict[str, Any]:
    output_path = output_root / str(task.get("output_path", "")).strip()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".part")
    url = str(task.get("url", "")).strip()
    retries = int(task.get("retries", 3) or 3)
    source = task.get("source") or {}
    referer = str(source.get("draft_page_url", "")).strip() or BASE_PAGE_URL

    attempt_logs: List[Dict[str, Any]] = []
    if resume_existing and output_path.exists() and output_path.stat().st_size > 0:
        return {
            "task_id": task_id,
            "name": str(task.get("name", "")).strip(),
            "download_status": "success",
            "http_status_or_error": "reused_existing_file",
            "status_code": None,
            "output_pdf": str(output_path.resolve()),
            "file_size_bytes": output_path.stat().st_size,
            "attempted_retries": 0,
            "attempt_logs": [],
            "draft_page_url": str(source.get("draft_page_url", "")).strip(),
            "content_id": str(source.get("content_id", "")).strip() or extract_content_id_from_url(url),
            "release_date": str(source.get("release_date", "")).strip(),
            "url": url,
        }

    final_status = "failed"
    final_error = ""
    final_status_code: Optional[int] = None
    for attempt in range(1, retries + 1):
        started = time.monotonic()
        status_code: Optional[int] = None
        error_text = ""
        try:
            session = bootstrap_session()
            with session.get(
                url,
                headers=default_headers(referer=referer),
                stream=True,
                allow_redirects=True,
                timeout=(15, timeout),
            ) as response:
                status_code = response.status_code
                response.raise_for_status()
                with open(tmp_path, "wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            handle.write(chunk)

            if not tmp_path.exists() or tmp_path.stat().st_size == 0:
                raise RuntimeError("downloaded_file_empty")

            tmp_path.replace(output_path)
            final_status = "success"
            final_status_code = status_code
            attempt_logs.append(
                {
                    "attempt": attempt,
                    "status": "success",
                    "status_code": status_code,
                    "error": "",
                    "duration_seconds": round(time.monotonic() - started, 3),
                }
            )
            break
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            error_text = f"http_error:{status_code}" if status_code is not None else "http_error"
        except requests.Timeout:
            error_text = "timeout"
        except requests.ConnectionError:
            error_text = "connection_error"
        except Exception as exc:
            error_text = str(exc)
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

        final_error = error_text
        final_status_code = status_code
        attempt_logs.append(
            {
                "attempt": attempt,
                "status": "failed",
                "status_code": status_code,
                "error": error_text,
                "duration_seconds": round(time.monotonic() - started, 3),
            }
        )
        if attempt < retries:
            time.sleep(float(attempt))

    file_size_bytes = output_path.stat().st_size if output_path.exists() else 0
    return {
        "task_id": task_id,
        "name": str(task.get("name", "")).strip(),
        "download_status": final_status,
        "http_status_or_error": status_or_error_label(final_status_code, final_error),
        "status_code": final_status_code,
        "output_pdf": str(output_path.resolve()),
        "file_size_bytes": file_size_bytes,
        "attempted_retries": retries,
        "attempt_logs": attempt_logs,
        "draft_page_url": str(source.get("draft_page_url", "")).strip(),
        "content_id": str(source.get("content_id", "")).strip() or extract_content_id_from_url(url),
        "release_date": str(source.get("release_date", "")).strip(),
        "url": url,
    }


def run_download_phase(
    *,
    download_config: Dict[str, Any],
    seed_index: Dict[str, Dict[str, Any]],
    output_dir: Path,
    threshold: int,
    timeout: int,
    resume_existing: bool,
) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    for task in download_config.get("tasks", []):
        source = task.get("source") or {}
        content_id = str(source.get("content_id", "")).strip() or extract_content_id_from_url(str(task.get("url", "")))
        seed_task = seed_index.get(content_id)
        task_id = str(seed_task.get("task_id", "")).strip() if seed_task else ""
        if not task_id:
            task_id = re.sub(r"[^\w.-]+", "_", str(task.get("name", "")).strip()) or f"content_{content_id}"
        results.append(
            download_one_task(
                task_id=task_id,
                task=task,
                output_root=output_dir,
                timeout=timeout,
                resume_existing=resume_existing,
            )
        )

    success_count = sum(1 for item in results if item["download_status"] == "success")
    failed_count = len(results) - success_count
    return {
        "generated_at": now_iso(),
        "download_attempted_count": len(results),
        "download_success_count": success_count,
        "download_failed_count": failed_count,
        "download_threshold": threshold,
        "gate_passed": success_count >= threshold,
        "results": results,
    }


def find_markdown_path(output_dir: Path, pdf_path: Path) -> Path:
    matches = sorted(output_dir.rglob("*.md"))
    if not matches:
        raise FileNotFoundError(f"MinerU 未生成 Markdown: {output_dir}")
    preferred_name = pdf_path.stem + ".md"
    for path in matches:
        if path.name == preferred_name:
            return path.resolve()
    return matches[0].resolve()


def normalize_note_no(raw_value: str) -> str:
    note_no = raw_value.strip()
    if note_no.startswith("(") and note_no.endswith(")"):
        note_no = note_no[1:-1]
    return note_no.strip()


def find_notes_start(lines: List[str]) -> Tuple[int, Dict[str, Any]]:
    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        lowered = stripped.lower()
        for keyword in NOTE_SECTION_KEYWORDS:
            if keyword.lower() in lowered:
                return index, {
                    "step": "keyword_search",
                    "keyword": keyword,
                    "excerpt": stripped[:200],
                }
    raise ValueError("notes_section_keyword_not_found")


def find_note_headings(lines: List[str], start_line: int) -> List[Dict[str, Any]]:
    headings: List[Dict[str, Any]] = []
    for index in range(start_line - 1, len(lines)):
        stripped = lines[index].strip()
        if not stripped:
            continue
        match = NOTE_HEADING_RE.match(stripped)
        if not match:
            continue
        note_no = normalize_note_no(match.group("note_no"))
        title = match.group("title").strip()
        if not note_no or not title:
            continue
        headings.append(
            {
                "note_no": note_no,
                "chapter_title": title,
                "start_line": index + 1,
                "evidence": [stripped[:200]],
            }
        )
    return headings


def determine_notes_end(lines: List[str], heading_starts: List[int]) -> int:
    if not heading_starts:
        return len(lines)
    last_heading_line = heading_starts[-1]
    for index in range(last_heading_line, len(lines)):
        lowered = lines[index].strip().lower()
        if not lowered:
            continue
        if any(keyword.lower() in lowered for keyword in NOTE_SECTION_END_KEYWORDS):
            return index
    return len(lines)


def build_notes_workfile_from_markdown(md_path: Path, notes_workfile_path: Path) -> Dict[str, Any]:
    text = md_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines:
        raise ValueError("markdown_empty")

    notes_start_line, locator_evidence = find_notes_start(lines)
    headings = find_note_headings(lines, notes_start_line)
    if len(headings) < MIN_NOTE_HEADING_COUNT:
        raise ValueError(f"notes_heading_count_below_minimum:{len(headings)}")

    notes_end_line = determine_notes_end(lines, [item["start_line"] for item in headings])
    notes_catalog: List[Dict[str, Any]] = []
    for index, item in enumerate(headings):
        next_start = headings[index + 1]["start_line"] if index + 1 < len(headings) else notes_end_line + 1
        end_line = max(item["start_line"], next_start - 1)
        if end_line > notes_end_line:
            end_line = notes_end_line
        if end_line < item["start_line"]:
            continue
        notes_catalog.append(
            {
                "note_no": item["note_no"],
                "chapter_title": item["chapter_title"],
                "start_line": item["start_line"],
                "end_line": end_line,
                "evidence": item["evidence"],
            }
        )

    if len(notes_catalog) < MIN_NOTE_HEADING_COUNT:
        raise ValueError("notes_catalog_too_small")

    payload = {
        "notes_start_line": notes_start_line,
        "notes_end_line": notes_end_line,
        "locator_evidence": [
            locator_evidence,
            {
                "step": "sample_read",
                "keyword": notes_catalog[0]["chapter_title"],
                "excerpt": notes_catalog[0]["evidence"][0],
            },
        ],
        "notes_catalog": notes_catalog,
    }
    write_json(notes_workfile_path, payload)
    return {
        "notes_start_line": notes_start_line,
        "notes_end_line": notes_end_line,
        "note_count": len(notes_catalog),
        "first_note": notes_catalog[0]["note_no"],
        "last_note": notes_catalog[-1]["note_no"],
    }


def run_mineru_for_pdf(
    pdf_path: Path,
    output_dir: Path,
    *,
    mineru_token: str,
    max_attempts: int,
    resume_existing: bool,
) -> Dict[str, Any]:
    mineru_script = REPO_ROOT / "mineru" / "scripts" / "mineru_stable.py"
    log_path = output_dir / "mineru.log"
    output_dir.mkdir(parents=True, exist_ok=True)

    if resume_existing:
        try:
            existing_md = find_markdown_path(output_dir, pdf_path)
            return {
                "returncode": 0,
                "log_path": log_path,
                "duration_seconds": 0.0,
                "attempt_count": 0,
                "reused_existing_output": True,
                "md_path": existing_md,
            }
        except Exception:
            pass

    env = os.environ.copy()
    if mineru_token:
        env["MINERU_TOKEN"] = mineru_token
    started = time.monotonic()
    command = [
        sys.executable,
        str(mineru_script),
        "--file",
        str(pdf_path),
        "--output",
        str(output_dir),
        "--language",
        "ch",
    ]
    if resume_existing:
        command.append("--resume")

    completed: Optional[subprocess.CompletedProcess[str]] = None
    attempt_count = max(1, max_attempts)
    with open(log_path, "w", encoding="utf-8") as handle:
        for attempt in range(1, attempt_count + 1):
            if attempt > 1:
                handle.write(f"\n\n===== RETRY {attempt}/{attempt_count} =====\n")
                handle.flush()
                time.sleep(float(attempt - 1))
            completed = subprocess.run(
                command,
                cwd=str(mineru_script.parent),
                stdout=handle,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
            if completed.returncode == 0:
                break

    return {
        "returncode": completed.returncode if completed is not None else 1,
        "log_path": log_path,
        "duration_seconds": round(time.monotonic() - started, 3),
        "attempt_count": attempt_count,
        "reused_existing_output": False,
        "md_path": None,
    }


def build_batch_task_entry(
    *,
    seed_task: Dict[str, Any],
    md_path: Path,
    notes_workfile_path: Path,
    analysis_run_dir: Path,
    pdf_path: Path,
) -> Dict[str, Any]:
    tags = list(seed_task.get("tags", []))
    if "p5" not in tags:
        tags.append("p5")
    if "cold_start" not in tags:
        tags.append("cold_start")
    return {
        "task_id": seed_task["task_id"],
        "issuer": seed_task["issuer"],
        "year": seed_task["year"],
        "md_path": str(md_path),
        "notes_workfile": str(notes_workfile_path),
        "run_dir": str(analysis_run_dir),
        "source_pdf": str(pdf_path),
        "tags": tags,
        "retry_group": "p5_cold_start",
    }


def run_preparation_phase(
    *,
    download_manifest: Dict[str, Any],
    seed_index: Dict[str, Dict[str, Any]],
    output_dir: Path,
    skill_status: Dict[str, Any],
    mineru_max_attempts: int,
    resume_existing_output: bool,
) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    batch_tasks: List[Dict[str, Any]] = []
    mineru_available = skill_status.get("mineru", {}).get("status") == "available"
    mineru_token_present = bool(skill_status.get("mineru", {}).get("token_present"))
    mineru_token = load_mineru_token_value()

    for item in download_manifest.get("results", []):
        if item.get("download_status") != "success":
            continue
        task_id = str(item["task_id"])
        seed_task = None
        content_id = str(item.get("content_id", "")).strip()
        if content_id:
            seed_task = seed_index.get(content_id)
        if seed_task is None:
            continue

        pdf_path = Path(str(item["output_pdf"])).resolve()
        prep_result = {
            "task_id": task_id,
            "issuer": seed_task["issuer"],
            "download_status": item["download_status"],
            "output_pdf": str(pdf_path),
            "preparation_status": "failed",
            "failure_stage": "",
            "failure_reason": "",
            "mineru_log_path": "",
            "mineru_duration_seconds": 0.0,
            "mineru_attempt_count": 0,
            "reused_existing_output": False,
            "md_path": "",
            "notes_workfile": "",
        }

        if not mineru_available:
            prep_result["failure_stage"] = "mineru"
            prep_result["failure_reason"] = "mineru_script_missing"
            results.append(prep_result)
            continue
        if not mineru_token_present:
            prep_result["failure_stage"] = "mineru"
            prep_result["failure_reason"] = "mineru_token_missing"
            results.append(prep_result)
            continue

        mineru_output_dir = output_dir / "mineru" / task_id
        mineru_result = run_mineru_for_pdf(
            pdf_path,
            mineru_output_dir,
            mineru_token=mineru_token,
            max_attempts=mineru_max_attempts,
            resume_existing=resume_existing_output,
        )
        prep_result["mineru_log_path"] = str(mineru_result["log_path"])
        prep_result["mineru_duration_seconds"] = mineru_result["duration_seconds"]
        prep_result["mineru_attempt_count"] = mineru_result["attempt_count"]
        prep_result["reused_existing_output"] = mineru_result["reused_existing_output"]
        if mineru_result["returncode"] != 0:
            prep_result["failure_stage"] = "mineru"
            prep_result["failure_reason"] = f"mineru_failed_returncode_{mineru_result['returncode']}"
            results.append(prep_result)
            continue

        try:
            md_path = (
                Path(str(mineru_result["md_path"])).resolve()
                if mineru_result.get("md_path")
                else find_markdown_path(mineru_output_dir, pdf_path)
            )
        except Exception as exc:
            prep_result["failure_stage"] = "mineru"
            prep_result["failure_reason"] = str(exc)
            results.append(prep_result)
            continue

        notes_workfile_path = output_dir / "notes_workfiles" / f"{task_id}.json"
        try:
            notes_summary = build_notes_workfile_from_markdown(md_path, notes_workfile_path)
        except Exception as exc:
            prep_result["failure_stage"] = "notes_workfile"
            prep_result["failure_reason"] = str(exc)
            prep_result["md_path"] = str(md_path)
            results.append(prep_result)
            continue

        analysis_run_dir = output_dir / "analysis_runs" / task_id
        batch_tasks.append(
            build_batch_task_entry(
                seed_task=seed_task,
                md_path=md_path,
                notes_workfile_path=notes_workfile_path,
                analysis_run_dir=analysis_run_dir,
                pdf_path=pdf_path,
            )
        )
        prep_result.update(
            {
                "preparation_status": "success",
                "failure_stage": "",
                "failure_reason": "",
                "md_path": str(md_path),
                "notes_workfile": str(notes_workfile_path),
                "notes_summary": notes_summary,
            }
        )
        results.append(prep_result)

    success_count = sum(1 for item in results if item["preparation_status"] == "success")
    failed_count = len(results) - success_count
    return {
        "generated_at": now_iso(),
        "download_qualified_count": len(results),
        "preparation_success_count": success_count,
        "preparation_failed_count": failed_count,
        "mineru_max_attempts": max(1, mineru_max_attempts),
        "resume_existing_output": bool(resume_existing_output),
        "results": results,
        "batch_tasks": batch_tasks,
    }


def run_batch_pipeline(
    *,
    runtime_config_path: Path,
    batch_task_list_path: Path,
    batch_run_dir: Path,
    build_review_bundle: bool,
) -> Dict[str, Any]:
    batch_script = SCRIPT_DIR / "run_batch_pipeline.py"
    log_path = batch_run_dir.parent / "run_batch_pipeline.log"
    command = [
        sys.executable,
        str(batch_script),
        "--runtime-config",
        str(runtime_config_path),
        "--task-list",
        str(batch_task_list_path),
        "--batch-run-dir",
        str(batch_run_dir),
    ]
    if build_review_bundle:
        command.append("--build-review-bundle")

    with open(log_path, "w", encoding="utf-8") as handle:
        completed = subprocess.run(
            command,
            cwd=str(REPO_ROOT),
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
        )

    batch_manifest_path = batch_run_dir / "batch_manifest.json"
    failed_tasks_path = batch_run_dir / "failed_tasks.json"
    pending_updates_index_path = batch_run_dir / "pending_updates_index.json"
    return {
        "command": command,
        "returncode": completed.returncode,
        "log_path": str(log_path),
        "batch_manifest_path": str(batch_manifest_path) if batch_manifest_path.exists() else "",
        "failed_tasks_path": str(failed_tasks_path) if failed_tasks_path.exists() else "",
        "pending_updates_index_path": str(pending_updates_index_path) if pending_updates_index_path.exists() else "",
    }


def build_batch_task_list_payload(batch_name: str, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "batch_name": batch_name,
        "defaults": {},
        "tasks": tasks,
    }


def main():
    args = parse_args()
    p4_dir = Path(args.p4_dir).resolve()
    if not p4_dir.exists():
        raise SystemExit(f"P4 输出目录不存在: {p4_dir}")

    try:
        runtime_config = load_runtime_config(
            config_path=Path(args.runtime_config) if args.runtime_config else None,
            cwd=Path.cwd(),
            require_knowledge_base=True,
            ensure_state_dirs=True,
        )
    except RuntimeConfigError as exc:
        raise SystemExit(str(exc)) from exc

    project_root = runtime_project_root(runtime_config)
    runtime_config_path = Path(str(runtime_config["_config_path"])).resolve()
    tmp_root = resolve_runtime_path(runtime_config, "tmp_root")
    if args.output_dir:
        output_dir = Path(args.output_dir).resolve()
    else:
        output_dir = (tmp_root / "p5_cold_start" / timestamp_slug()).resolve()

    try:
        output_dir.relative_to(project_root)
    except ValueError as exc:
        raise SystemExit(f"--output-dir 必须位于 project_root 内: {output_dir}") from exc

    if output_dir.exists() and not args.resume_output_dir:
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    p4_inputs = load_p4_inputs(p4_dir)
    seed_index = build_seed_index(p4_inputs["task_seed_list"])
    skill_status = check_skill_status(runtime_config)

    download_manifest = run_download_phase(
        download_config=p4_inputs["download_config"],
        seed_index=seed_index,
        output_dir=output_dir,
        threshold=args.download_threshold,
        timeout=args.download_timeout,
        resume_existing=args.resume_output_dir,
    )
    write_json(output_dir / DOWNLOAD_PHASE_MANIFEST, download_manifest)

    p5_manifest: Dict[str, Any] = {
        "generated_at": now_iso(),
        "p4_dir": str(p4_dir),
        "output_dir": str(output_dir),
        "download_threshold": args.download_threshold,
        "skill_status": skill_status,
        "runtime_config_path": str(runtime_config_path),
        "stages": {
            "download": {
                "status": "success" if download_manifest["gate_passed"] else "blocked",
                "manifest_path": str((output_dir / DOWNLOAD_PHASE_MANIFEST).resolve()),
                "download_success_count": download_manifest["download_success_count"],
                "download_failed_count": download_manifest["download_failed_count"],
                "gate_passed": download_manifest["gate_passed"],
            },
            "preparation": {
                "status": "not_started",
                "manifest_path": "",
                "prepared_task_count": 0,
            },
            "batch": {
                "status": "not_started",
                "task_list_path": "",
                "batch_run_dir": "",
                "batch_manifest_path": "",
                "failed_tasks_path": "",
                "pending_updates_index_path": "",
                "log_path": "",
            },
        },
        "go_live_blocker": "",
        "next_step": "",
    }

    if not download_manifest["gate_passed"]:
        p5_manifest["go_live_blocker"] = "chinamoney_download_gate_blocked"
        p5_manifest["next_step"] = "retry_p5_after_download_gateway_revalidation"
        write_json(output_dir / P5_MANIFEST, p5_manifest)
        return

    preparation_manifest = run_preparation_phase(
        download_manifest=download_manifest,
        seed_index=seed_index,
        output_dir=output_dir,
        skill_status=skill_status,
        mineru_max_attempts=args.mineru_max_attempts,
        resume_existing_output=args.resume_output_dir,
    )
    write_json(output_dir / PREPARATION_MANIFEST, preparation_manifest)
    prepared_task_count = len(preparation_manifest["batch_tasks"])
    p5_manifest["stages"]["preparation"] = {
        "status": "success" if prepared_task_count > 0 else "failed",
        "manifest_path": str((output_dir / PREPARATION_MANIFEST).resolve()),
        "prepared_task_count": prepared_task_count,
        "preparation_failed_count": preparation_manifest["preparation_failed_count"],
    }

    if prepared_task_count == 0:
        p5_manifest["go_live_blocker"] = "stage_b_preparation_failed"
        p5_manifest["next_step"] = "fix_mineru_or_notes_workfile_preparation"
        write_json(output_dir / P5_MANIFEST, p5_manifest)
        return

    batch_name = f"p5_cold_start_{p4_dir.name}"
    batch_task_list_payload = build_batch_task_list_payload(batch_name, preparation_manifest["batch_tasks"])
    batch_task_list_path = output_dir / BATCH_TASK_LIST
    write_json(batch_task_list_path, batch_task_list_payload)

    batch_run_dir = output_dir / "batch_run"
    batch_result = run_batch_pipeline(
        runtime_config_path=runtime_config_path,
        batch_task_list_path=batch_task_list_path,
        batch_run_dir=batch_run_dir,
        build_review_bundle=not args.no_build_review_bundle,
    )

    p5_manifest["stages"]["batch"] = {
        "status": "success" if batch_result["returncode"] == 0 else "failed",
        "task_list_path": str(batch_task_list_path),
        "batch_run_dir": str(batch_run_dir),
        "batch_manifest_path": batch_result["batch_manifest_path"],
        "failed_tasks_path": batch_result["failed_tasks_path"],
        "pending_updates_index_path": batch_result["pending_updates_index_path"],
        "log_path": batch_result["log_path"],
    }
    if batch_result["returncode"] != 0:
        p5_manifest["go_live_blocker"] = "batch_pipeline_failed"
        p5_manifest["next_step"] = "inspect_batch_pipeline_log_and_failed_tasks"
    else:
        p5_manifest["next_step"] = "review_batch_manifest_and_prepare_p6_go_live_checklist"

    write_json(output_dir / P5_MANIFEST, p5_manifest)


if __name__ == "__main__":
    main()
