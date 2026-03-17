#!/usr/bin/env python3
"""
W7 批处理入口：基于现有稳定的 Markdown + notes_workfile 链路执行批量分析。
"""

import argparse
import datetime
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


ROOT_DIR = Path(__file__).resolve().parents[2]
ANALYZER_SCRIPT = ROOT_DIR / "financial-analyzer" / "scripts" / "financial_analyzer.py"
KNOWLEDGE_MANAGER_SCRIPT = ROOT_DIR / "financial-analyzer" / "scripts" / "knowledge_manager.py"
DEFAULT_BATCH_ROOT = ROOT_DIR / "financial-analyzer" / "test_runs" / "batches"
TASK_RESULT_LOG = "task_results.jsonl"
FAILED_TASKS_FILE = "failed_tasks.json"
PENDING_UPDATES_INDEX_FILE = "pending_updates_index.json"
BATCH_MANIFEST_FILE = "batch_manifest.json"
GOVERNANCE_REVIEW_DIRNAME = "governance_review"
TASKS_DIRNAME = "tasks"
TASK_LOG_NAME = "task.log"
KNOWN_TASK_OUTPUTS = [
    "run_manifest.json",
    "chapter_records.jsonl",
    "focus_list.json",
    "final_data.json",
    "soul_export_payload.json",
    "pending_updates.json",
    "analysis_report.md",
    "financial_output.xlsx",
    "preview.pdf",
    TASK_LOG_NAME,
]
REQUIRED_TASK_FIELDS = ["task_id", "issuer", "year", "md_path", "notes_workfile"]
OPTIONAL_TASK_FIELDS = {"run_dir", "tags", "source_pdf", "retry_group"}


def now_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def append_jsonl(path: Path, row: Dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def parse_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            rows.append(json.loads(text))
    return rows


def slugify(value: str) -> str:
    normalized = re.sub(r"[^\w.-]+", "_", value.strip(), flags=re.UNICODE)
    normalized = normalized.strip("._")
    return normalized or "batch_run"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="W7 Markdown-first 批处理入口")
    parser.add_argument("--task-list", required=True, help="任务清单 JSON 路径")
    parser.add_argument("--batch-run-dir", help="批次运行目录；默认写入 financial-analyzer/test_runs/batches/<batch_name>")
    parser.add_argument("--resume", action="store_true", help="跳过已有成功结果的任务")
    parser.add_argument("--only-failed", action="store_true", help="仅复跑 failed_tasks.json 中记录的任务")
    parser.add_argument("--build-review-bundle", action="store_true", help="对成功任务的 pending_updates 构建 W5 审核包")
    return parser.parse_args()


def ensure_valid_task_id(task_id: str):
    if not re.fullmatch(r"[A-Za-z0-9._-]+", task_id):
        raise SystemExit(f"非法 task_id: {task_id!r}；仅允许字母、数字、点、下划线和中划线")


def resolve_path(raw_value: str, base_dir: Path) -> Path:
    path = Path(raw_value)
    if path.is_absolute():
        return path.resolve()
    return (base_dir / path).resolve()


def normalize_task(
    raw_task: Dict[str, Any],
    defaults: Dict[str, Any],
    task_list_dir: Path,
    batch_run_dir: Path,
) -> Dict[str, Any]:
    if not isinstance(raw_task, dict):
        raise SystemExit("tasks 列表中的每项必须是对象")

    missing_fields = [field for field in REQUIRED_TASK_FIELDS if raw_task.get(field) in (None, "", [])]
    if missing_fields:
        raise SystemExit(f"任务缺少必填字段: {', '.join(missing_fields)}")

    task_id = str(raw_task["task_id"]).strip()
    ensure_valid_task_id(task_id)

    task = {
        "task_id": task_id,
        "issuer": str(raw_task["issuer"]).strip(),
        "year": raw_task["year"],
    }
    task["md_path"] = resolve_path(str(raw_task["md_path"]), task_list_dir)
    task["notes_workfile"] = resolve_path(str(raw_task["notes_workfile"]), task_list_dir)

    for field in OPTIONAL_TASK_FIELDS:
        value = raw_task.get(field, defaults.get(field))
        if value in (None, "", []):
            continue
        if field == "run_dir":
            task[field] = resolve_path(str(value), task_list_dir)
        elif field == "tags":
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise SystemExit(f"{task_id}: tags 必须是字符串列表")
            task[field] = value
        else:
            task[field] = value

    task["run_dir"] = task.get("run_dir", batch_run_dir / TASKS_DIRNAME / task_id)
    return task


def load_task_list(task_list_path: Path, batch_run_dir: Path) -> Dict[str, Any]:
    payload = read_json(task_list_path)
    if not isinstance(payload, dict):
        raise SystemExit("任务清单顶层必须是对象")

    batch_name = payload.get("batch_name")
    defaults = payload.get("defaults", {})
    tasks = payload.get("tasks")

    if not isinstance(batch_name, str) or not batch_name.strip():
        raise SystemExit("任务清单缺少合法的 batch_name")
    if not isinstance(defaults, dict):
        raise SystemExit("defaults 必须是对象")
    if not isinstance(tasks, list) or not tasks:
        raise SystemExit("tasks 必须是非空列表")

    normalized_tasks: List[Dict[str, Any]] = []
    task_ids = set()
    for raw_task in tasks:
        task = normalize_task(raw_task, defaults, task_list_path.parent, batch_run_dir)
        if task["task_id"] in task_ids:
            raise SystemExit(f"task_id 重复: {task['task_id']}")
        task_ids.add(task["task_id"])
        normalized_tasks.append(task)

    return {
        "batch_name": batch_name.strip(),
        "defaults": defaults,
        "tasks": normalized_tasks,
    }


def load_latest_results(results_path: Path) -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for row in parse_jsonl(results_path):
        task_id = row.get("task_id")
        if task_id:
            latest[task_id] = row
    return latest


def load_failed_task_ids(failed_tasks_path: Path) -> List[str]:
    if not failed_tasks_path.exists():
        raise SystemExit(f"--only-failed 需要已有 {FAILED_TASKS_FILE}: {failed_tasks_path}")
    payload = read_json(failed_tasks_path)
    return [item["task_id"] for item in payload.get("tasks", []) if item.get("task_id")]


def determine_selected_tasks(
    tasks: List[Dict[str, Any]],
    latest_results: Dict[str, Dict[str, Any]],
    failed_task_ids: List[str],
    resume: bool,
    only_failed: bool,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    selected_tasks: List[Dict[str, Any]] = []
    skipped_success_task_ids: List[str] = []
    failed_id_set = set(failed_task_ids)

    for task in tasks:
        task_id = task["task_id"]
        previous = latest_results.get(task_id)
        if only_failed and task_id not in failed_id_set:
            continue
        if resume and previous and previous.get("status") == "success":
            skipped_success_task_ids.append(task_id)
            continue
        selected_tasks.append(task)
    return selected_tasks, skipped_success_task_ids


def clear_task_run_dir(run_dir: Path):
    run_dir.mkdir(parents=True, exist_ok=True)

    # 每次显式复跑前清理已知稳定产物，避免失败态残留旧成功文件。
    for filename in KNOWN_TASK_OUTPUTS:
        path = run_dir / filename
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

    for png_path in run_dir.glob("preview-*.png"):
        png_path.unlink()


def build_command(task: Dict[str, Any]) -> List[str]:
    return [
        sys.executable,
        str(ANALYZER_SCRIPT),
        "--md",
        str(task["md_path"]),
        "--notes-workfile",
        str(task["notes_workfile"]),
        "--run-dir",
        str(task["run_dir"]),
    ]


def summarize_pending_updates(path: Path) -> int:
    if not path.exists():
        return 0
    payload = read_json(path)
    items = payload.get("items")
    if not isinstance(items, list):
        return 0
    return len(items)


def run_single_task(task: Dict[str, Any]) -> Dict[str, Any]:
    started_at = now_iso()
    run_dir = Path(task["run_dir"])
    run_dir.mkdir(parents=True, exist_ok=True)

    if not task["md_path"].exists():
        completed_at = now_iso()
        return {
            "task_id": task["task_id"],
            "issuer": task["issuer"],
            "year": task["year"],
            "status": "failed",
            "attempt": 1,
            "returncode": None,
            "failure_reason": "md_path_not_found",
            "run_dir": str(run_dir),
            "manifest_path": "",
            "manifest_status": "",
            "notes_locator_status": "",
            "engine_version": "",
            "pending_updates_path": "",
            "pending_updates_count": 0,
            "started_at": started_at,
            "completed_at": completed_at,
            "task_log_path": "",
        }

    if not str(task["notes_workfile"]).strip():
        completed_at = now_iso()
        return {
            "task_id": task["task_id"],
            "issuer": task["issuer"],
            "year": task["year"],
            "status": "failed",
            "attempt": 1,
            "returncode": None,
            "failure_reason": "notes_workfile_path_missing",
            "run_dir": str(run_dir),
            "manifest_path": "",
            "manifest_status": "",
            "notes_locator_status": "",
            "engine_version": "",
            "pending_updates_path": "",
            "pending_updates_count": 0,
            "started_at": started_at,
            "completed_at": completed_at,
            "task_log_path": "",
        }

    clear_task_run_dir(run_dir)
    log_path = run_dir / TASK_LOG_NAME
    command = build_command(task)
    with open(log_path, "w", encoding="utf-8") as handle:
        completed = subprocess.run(
            command,
            cwd=str(ROOT_DIR),
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
        )
    completed_at = now_iso()

    manifest_path = run_dir / "run_manifest.json"
    manifest = read_json(manifest_path) if manifest_path.exists() else None
    pending_updates_path = run_dir / "pending_updates.json"
    pending_updates_count = summarize_pending_updates(pending_updates_path)

    status = "failed"
    failure_reason = "manifest_missing_after_process_exit"
    manifest_status = ""
    notes_locator_status = ""
    engine_version = ""

    if manifest:
        manifest_status = str(manifest.get("status", ""))
        failure_reason = str(manifest.get("failure_reason", "")) or failure_reason
        notes_locator_status = str((manifest.get("notes_locator") or {}).get("status", ""))
        engine_version = str(manifest.get("engine_version", ""))
        if manifest_status == "success" and completed.returncode == 0:
            status = "success"
            failure_reason = ""
        elif manifest_status == "success" and completed.returncode != 0:
            failure_reason = "nonzero_returncode_with_success_manifest"
        elif manifest_status == "failed":
            status = "failed"

    return {
        "task_id": task["task_id"],
        "issuer": task["issuer"],
        "year": task["year"],
        "status": status,
        "attempt": 1,
        "returncode": completed.returncode,
        "failure_reason": failure_reason,
        "run_dir": str(run_dir),
        "manifest_path": str(manifest_path) if manifest_path.exists() else "",
        "manifest_status": manifest_status,
        "notes_locator_status": notes_locator_status,
        "engine_version": engine_version,
        "pending_updates_path": str(pending_updates_path) if pending_updates_path.exists() else "",
        "pending_updates_count": pending_updates_count,
        "started_at": started_at,
        "completed_at": completed_at,
        "task_log_path": str(log_path),
        "command": command,
        "tags": task.get("tags", []),
        "retry_group": task.get("retry_group", ""),
        "source_pdf": str(task.get("source_pdf", "")),
    }


def build_failed_tasks_payload(
    batch_name: str,
    batch_run_dir: Path,
    latest_results: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    failed_tasks = [
        {
            key: item.get(key)
            for key in [
                "task_id",
                "issuer",
                "year",
                "attempt",
                "returncode",
                "failure_reason",
                "run_dir",
                "manifest_path",
                "task_log_path",
            ]
        }
        for item in latest_results.values()
        if item.get("status") == "failed"
    ]
    failed_tasks.sort(key=lambda item: item["task_id"])
    return {
        "generated_at": now_iso(),
        "batch_name": batch_name,
        "batch_run_dir": str(batch_run_dir),
        "failed_count": len(failed_tasks),
        "tasks": failed_tasks,
    }


def build_pending_updates_index_payload(
    batch_name: str,
    batch_run_dir: Path,
    latest_results: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    items = []
    for item in latest_results.values():
        if item.get("status") != "success" or not item.get("pending_updates_path"):
            continue
        items.append(
            {
                "task_id": item["task_id"],
                "issuer": item["issuer"],
                "year": item["year"],
                "case_name": item["task_id"],
                "run_dir": item["run_dir"],
                "pending_updates_path": item["pending_updates_path"],
                "item_count": item["pending_updates_count"],
                "engine_version": item["engine_version"],
            }
        )
    items.sort(key=lambda item: item["task_id"])
    return {
        "generated_at": now_iso(),
        "batch_name": batch_name,
        "batch_run_dir": str(batch_run_dir),
        "success_task_count": len(items),
        "items": items,
    }


def run_governance_review(
    batch_name: str,
    batch_run_dir: Path,
    build_review_bundle: bool,
    latest_results: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    success_items = [
        item
        for item in latest_results.values()
        if item.get("status") == "success" and item.get("pending_updates_path")
    ]
    success_items.sort(key=lambda item: item["task_id"])
    governance_review_dir = batch_run_dir / GOVERNANCE_REVIEW_DIRNAME
    governance_review_dir.mkdir(parents=True, exist_ok=True)

    base_payload = {
        "batch_name": batch_name,
        "success_task_count": len(success_items),
        "manual_review_required": False,
        "governance_status": "not_built",
        "governance_note": "",
        "review_bundle_path": "",
        "review_report_path": "",
        "build_log_path": "",
    }

    if not success_items:
        return base_payload

    if not build_review_bundle:
        base_payload["governance_status"] = "collected"
        return base_payload

    if len(success_items) < 3:
        base_payload["governance_note"] = "insufficient_successful_cases_for_review_bundle"
        return base_payload

    build_log_path = governance_review_dir / "build_review_bundle.log"
    command = [
        sys.executable,
        str(KNOWLEDGE_MANAGER_SCRIPT),
        "build-review-bundle",
        "--input",
    ]
    command.extend(item["pending_updates_path"] for item in success_items)
    command.extend(["--output-dir", str(governance_review_dir)])

    with open(build_log_path, "w", encoding="utf-8") as handle:
        completed = subprocess.run(
            command,
            cwd=str(ROOT_DIR),
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
        )

    bundle_path = governance_review_dir / "knowledge_review_bundle.json"
    report_path = governance_review_dir / "knowledge_review_report.md"
    if completed.returncode == 0 and bundle_path.exists() and report_path.exists():
        base_payload.update(
            {
                "manual_review_required": True,
                "governance_status": "review_bundle_built",
                "review_bundle_path": str(bundle_path),
                "review_report_path": str(report_path),
                "build_log_path": str(build_log_path),
            }
        )
        return base_payload

    base_payload.update(
        {
            "manual_review_required": True,
            "governance_status": "manual_review_required",
            "governance_note": "review_bundle_build_failed",
            "build_log_path": str(build_log_path),
        }
    )
    return base_payload


def build_task_index(
    tasks: List[Dict[str, Any]],
    latest_results: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    task_index = []
    for task in tasks:
        latest = latest_results.get(task["task_id"], {})
        task_index.append(
            {
                "task_id": task["task_id"],
                "issuer": task["issuer"],
                "year": task["year"],
                "run_dir": str(task["run_dir"]),
                "status": latest.get("status", "pending"),
                "failure_reason": latest.get("failure_reason", ""),
                "manifest_path": latest.get("manifest_path", ""),
                "pending_updates_path": latest.get("pending_updates_path", ""),
                "pending_updates_count": latest.get("pending_updates_count", 0),
            }
        )
    return task_index


def build_batch_manifest(
    *,
    batch_name: str,
    task_list_path: Path,
    batch_run_dir: Path,
    tasks: List[Dict[str, Any]],
    latest_results: Dict[str, Dict[str, Any]],
    created_at: str,
    run_started_at: str,
    run_completed_at: str,
    selected_task_count: int,
    executed_task_count: int,
    skipped_success_task_ids: List[str],
    resume: bool,
    only_failed: bool,
    build_review_bundle: bool,
    governance_payload: Dict[str, Any],
) -> Dict[str, Any]:
    success_count = sum(1 for item in latest_results.values() if item.get("status") == "success")
    failed_count = sum(1 for item in latest_results.values() if item.get("status") == "failed")
    pending_count = max(len(tasks) - success_count - failed_count, 0)
    return {
        "batch_name": batch_name,
        "batch_run_dir": str(batch_run_dir),
        "task_list_path": str(task_list_path),
        "created_at": created_at,
        "generated_at": now_iso(),
        "summary": {
            "task_count": len(tasks),
            "success_count": success_count,
            "failed_count": failed_count,
            "pending_count": pending_count,
        },
        "latest_run": {
            "started_at": run_started_at,
            "completed_at": run_completed_at,
            "resume": resume,
            "only_failed": only_failed,
            "build_review_bundle": build_review_bundle,
            "selected_task_count": selected_task_count,
            "executed_task_count": executed_task_count,
            "skipped_existing_success_count": len(skipped_success_task_ids),
            "skipped_existing_success_task_ids": skipped_success_task_ids,
        },
        "governance": governance_payload,
        "task_index": build_task_index(tasks, latest_results),
    }


def main():
    args = parse_args()
    task_list_path = Path(args.task_list).resolve()
    if not task_list_path.exists():
        raise SystemExit(f"任务清单不存在: {task_list_path}")

    preliminary_payload = read_json(task_list_path)
    batch_name = preliminary_payload.get("batch_name") if isinstance(preliminary_payload, dict) else None
    if not isinstance(batch_name, str) or not batch_name.strip():
        raise SystemExit("任务清单缺少合法的 batch_name")

    batch_run_dir = (
        Path(args.batch_run_dir).resolve()
        if args.batch_run_dir
        else (DEFAULT_BATCH_ROOT / slugify(batch_name))
    )
    batch_run_dir.mkdir(parents=True, exist_ok=True)

    task_list = load_task_list(task_list_path, batch_run_dir)
    task_result_log_path = batch_run_dir / TASK_RESULT_LOG
    failed_tasks_path = batch_run_dir / FAILED_TASKS_FILE
    pending_updates_index_path = batch_run_dir / PENDING_UPDATES_INDEX_FILE
    batch_manifest_path = batch_run_dir / BATCH_MANIFEST_FILE

    previous_manifest = read_json(batch_manifest_path) if batch_manifest_path.exists() else {}
    created_at = previous_manifest.get("created_at", now_iso())
    latest_results = load_latest_results(task_result_log_path)
    failed_task_ids = load_failed_task_ids(failed_tasks_path) if args.only_failed else []
    selected_tasks, skipped_success_task_ids = determine_selected_tasks(
        task_list["tasks"],
        latest_results,
        failed_task_ids,
        args.resume,
        args.only_failed,
    )

    run_started_at = now_iso()
    for task in selected_tasks:
        result = run_single_task(task)
        append_jsonl(task_result_log_path, result)
        latest_results[result["task_id"]] = result

    pending_updates_index = build_pending_updates_index_payload(
        task_list["batch_name"],
        batch_run_dir,
        latest_results,
    )
    write_json(pending_updates_index_path, pending_updates_index)

    failed_tasks_payload = build_failed_tasks_payload(
        task_list["batch_name"],
        batch_run_dir,
        latest_results,
    )
    write_json(failed_tasks_path, failed_tasks_payload)

    governance_payload = run_governance_review(
        task_list["batch_name"],
        batch_run_dir,
        args.build_review_bundle,
        latest_results,
    )
    run_completed_at = now_iso()

    batch_manifest = build_batch_manifest(
        batch_name=task_list["batch_name"],
        task_list_path=task_list_path,
        batch_run_dir=batch_run_dir,
        tasks=task_list["tasks"],
        latest_results=latest_results,
        created_at=created_at,
        run_started_at=run_started_at,
        run_completed_at=run_completed_at,
        selected_task_count=len(selected_tasks),
        executed_task_count=len(selected_tasks),
        skipped_success_task_ids=skipped_success_task_ids,
        resume=args.resume,
        only_failed=args.only_failed,
        build_review_bundle=args.build_review_bundle,
        governance_payload=governance_payload,
    )
    write_json(batch_manifest_path, batch_manifest)

    print(f"[OK] 批次目录: {batch_run_dir}")
    print(
        "[OK] 结果汇总: "
        f"success={batch_manifest['summary']['success_count']}, "
        f"failed={batch_manifest['summary']['failed_count']}, "
        f"pending={batch_manifest['summary']['pending_count']}"
    )
    print(f"[OK] failed_tasks: {failed_tasks_path}")
    print(f"[OK] pending_updates_index: {pending_updates_index_path}")
    if governance_payload["governance_status"] in {"review_bundle_built", "manual_review_required"}:
        print(f"[OK] governance_status: {governance_payload['governance_status']}")
    elif governance_payload["governance_note"]:
        print(f"[INFO] governance_note: {governance_payload['governance_note']}")


if __name__ == "__main__":
    main()
