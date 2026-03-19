#!/usr/bin/env python3
"""
逐份报告独立闭环的系列驱动入口。

目标：
- 复用 ChinaMoney 发现 / 下载
- 复用 MinerU 解析
- 复用 financial_analyzer.py + run_batch_pipeline.py 的单案正式输出
- 每份报告独立完成后再进入下一份，不在同一个分析结果里合并多份报告
"""

import argparse
import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from runtime_support import (
    RuntimeConfigError,
    load_runtime_config,
    resolve_runtime_path,
    runtime_project_root,
)

from run_p5_cold_start_simulation import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_MINERU_MAX_ATTEMPTS,
    DOWNLOAD_PHASE_MANIFEST,
    P5_BATCH_NAME_PREFIX,
    PREPARATION_MANIFEST,
    build_batch_task_list_payload,
    build_seed_index,
    check_skill_status,
    load_p4_inputs,
    now_iso,
    run_batch_pipeline,
    run_download_phase,
    run_preparation_phase,
    timestamp_slug,
    write_json,
)


SCRIPT_DIR = Path(__file__).resolve().parent
SERIES_MANIFEST = "series_manifest.json"
SERIES_RESULTS_JSONL = "series_task_results.jsonl"
SERIES_TASK_LISTS_DIR = "series_task_lists"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="逐份报告独立闭环驱动")
    parser.add_argument("--p4-dir", required=True, help="P4 输出目录")
    parser.add_argument("--runtime-config", help="显式指定 runtime/runtime_config.json")
    parser.add_argument("--output-dir", help="系列输出目录；默认写入 runtime/state/tmp/report_series/<timestamp>")
    parser.add_argument(
        "--task-ids",
        nargs="*",
        default=None,
        help="仅处理指定 task_id；默认处理 P4 中的全部任务",
    )
    parser.add_argument(
        "--download-timeout",
        type=int,
        default=DEFAULT_DOWNLOAD_TIMEOUT,
        help="单次下载超时秒数，默认 120",
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
        help="若 output_dir 已存在，则复用既有产物而不是删除重跑",
    )
    parser.add_argument(
        "--download-only",
        action="store_true",
        help="仅执行下载与解析，不进入单案正式分析",
    )
    parser.add_argument(
        "--no-build-review-bundle",
        action="store_true",
        help="批处理阶段不构建 review bundle",
    )
    parser.add_argument(
        "--stop-on-failure",
        action="store_true",
        help="遇到单份报告失败时立即停止；默认继续处理后续报告并记录缺口",
    )
    return parser.parse_args()


def read_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def slugify(value: str) -> str:
    import re

    normalized = re.sub(r"[^\w.-]+", "_", value.strip(), flags=re.UNICODE)
    normalized = normalized.strip("._")
    return normalized or "series_run"


def write_jsonl(path: Path, rows: List[Dict[str, Any]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def ensure_under_project_root(path: Path, project_root: Path, label: str):
    try:
        path.relative_to(project_root)
    except ValueError as exc:
        raise SystemExit(f"{label} 必须位于 project_root 内: {path}") from exc


def filter_p4_inputs(
    p4_inputs: Dict[str, Any],
    task_ids: Optional[List[str]],
) -> Tuple[Dict[str, Any], List[str]]:
    if not task_ids:
        return p4_inputs, []

    wanted_ids: Set[str] = {str(item).strip() for item in task_ids if str(item).strip()}
    original_seeds = p4_inputs["task_seed_list"].get("tasks", [])
    selected_seeds = [task for task in original_seeds if str(task.get("task_id", "")).strip() in wanted_ids]
    selected_seed_ids = {str(task.get("task_id", "")).strip() for task in selected_seeds}

    if selected_seed_ids != wanted_ids:
        missing = sorted(wanted_ids - selected_seed_ids)
        raise SystemExit(f"指定 task_id 不存在于 P4 任务清单: {', '.join(missing)}")

    selected_content_ids = {
        str(task.get("source", {}).get("content_id", "")).strip()
        for task in selected_seeds
        if str(task.get("source", {}).get("content_id", "")).strip()
    }
    selected_download_tasks = []
    for task in p4_inputs["download_config"].get("tasks", []):
        source = task.get("source") or {}
        content_id = str(source.get("content_id", "")).strip()
        if content_id in selected_content_ids:
            selected_download_tasks.append(task)

    filtered_inputs = {
        "selection_manifest_path": p4_inputs["selection_manifest_path"],
        "download_config_path": p4_inputs["download_config_path"],
        "task_seed_list_path": p4_inputs["task_seed_list_path"],
        "selection_manifest": p4_inputs["selection_manifest"],
        "download_config": {
            **p4_inputs["download_config"],
            "tasks": selected_download_tasks,
        },
        "task_seed_list": {
            **p4_inputs["task_seed_list"],
            "tasks": selected_seeds,
        },
    }
    return filtered_inputs, sorted(wanted_ids)


def build_series_batch_name(series_name: str, task_id: str) -> str:
    return f"{P5_BATCH_NAME_PREFIX}_{slugify(series_name)}_{slugify(task_id)}"


def run_single_task_batch(
    *,
    runtime_config_path: Path,
    task: Dict[str, Any],
    batch_root: Path,
    series_name: str,
    review_bundle: bool,
) -> Dict[str, Any]:
    batch_name = build_series_batch_name(series_name, task["task_id"])
    batch_run_dir = batch_root / batch_name
    task_list_dir = batch_run_dir / "task_list"
    task_list_dir.mkdir(parents=True, exist_ok=True)
    task_list_path = task_list_dir / f"{task['task_id']}.json"
    payload = build_batch_task_list_payload(batch_name, [task])
    write_json(task_list_path, payload)

    batch_result = run_batch_pipeline(
        runtime_config_path=runtime_config_path,
        batch_task_list_path=task_list_path,
        batch_run_dir=batch_run_dir,
        build_review_bundle=review_bundle,
    )

    if batch_result["returncode"] != 0:
        return {
            "task_id": task["task_id"],
            "issuer": task["issuer"],
            "year": task["year"],
            "status": "failed",
            "batch_name": batch_name,
            "batch_run_dir": str(batch_run_dir),
            "batch_task_list_path": str(task_list_path),
            "batch_returncode": batch_result["returncode"],
            "batch_log_path": batch_result["log_path"],
            "batch_manifest_path": batch_result["batch_manifest_path"],
            "batch_failed_tasks_path": batch_result["failed_tasks_path"],
            "batch_scaffold_index_path": batch_result["scaffold_index_path"],
            "task_run_dir": str(task_run_dir),
            "task_manifest_path": str(task_run_dir / "run_manifest.json") if (task_run_dir / "run_manifest.json").exists() else "",
            "task_manifest_status": "",
            "task_failure_reason": "analysis_batch_failed",
            "analysis_report": "",
            "analysis_report_scaffold": "",
            "final_data": "",
            "final_data_scaffold": "",
            "soul_export_payload": "",
            "soul_export_payload_scaffold": "",
            "financial_output": "",
            "chapter_records": "",
            "run_manifest": "",
            "formalization_manifest": "",
        }

    manifest_path = Path(batch_result["batch_manifest_path"]) if batch_result["batch_manifest_path"] else batch_run_dir / "batch_manifest.json"
    manifest: Dict[str, Any] = {}
    if manifest_path.exists():
        manifest = read_json(manifest_path)

    task_run_dir = Path(task["run_dir"])
    task_manifest_path = task_run_dir / "run_manifest.json"
    task_manifest: Dict[str, Any] = {}
    if task_manifest_path.exists():
        task_manifest = read_json(task_manifest_path)

    artifacts = (task_manifest.get("artifacts") or {}) if task_manifest else {}
    finalizer_result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_DIR / "finalize_scaffold_run.py"),
            "--run-dir",
            str(task_run_dir),
        ],
        cwd=str(ROOT_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if finalizer_result.returncode != 0:
        return {
            "task_id": task["task_id"],
            "issuer": task["issuer"],
            "year": task["year"],
            "status": "failed",
            "batch_name": batch_name,
            "batch_run_dir": str(batch_run_dir),
            "batch_task_list_path": str(task_list_path),
            "batch_returncode": batch_result["returncode"],
            "batch_log_path": batch_result["log_path"],
            "batch_manifest_path": batch_result["batch_manifest_path"],
            "batch_failed_tasks_path": batch_result["failed_tasks_path"],
            "batch_scaffold_index_path": batch_result["scaffold_index_path"],
            "task_run_dir": str(task_run_dir),
            "task_manifest_path": str(task_manifest_path) if task_manifest_path.exists() else "",
            "task_manifest_status": str(task_manifest.get("status", "")),
            "task_failure_reason": f"finalization_failed: {finalizer_result.stdout.strip()}",
            "analysis_report": str(task_run_dir / "analysis_report.md"),
            "analysis_report_scaffold": str(artifacts.get("analysis_report_scaffold", "")),
            "final_data": str(task_run_dir / "final_data.json"),
            "final_data_scaffold": str(artifacts.get("final_data_scaffold", "")),
            "soul_export_payload": str(task_run_dir / "soul_export_payload.json"),
            "soul_export_payload_scaffold": str(artifacts.get("soul_export_payload_scaffold", "")),
            "financial_output": str(task_run_dir / "financial_output.xlsx"),
            "chapter_records": str(artifacts.get("chapter_records", "")),
            "run_manifest": str(artifacts.get("run_manifest", "")),
            "formalization_manifest": "",
        }
    return {
        "task_id": task["task_id"],
        "issuer": task["issuer"],
        "year": task["year"],
        "status": "success" if batch_result["returncode"] == 0 else "failed",
        "batch_name": batch_name,
        "batch_run_dir": str(batch_run_dir),
        "batch_task_list_path": str(task_list_path),
        "batch_returncode": batch_result["returncode"],
        "batch_log_path": batch_result["log_path"],
        "batch_manifest_path": batch_result["batch_manifest_path"],
        "batch_failed_tasks_path": batch_result["failed_tasks_path"],
        "batch_scaffold_index_path": batch_result["scaffold_index_path"],
        "task_run_dir": str(task_run_dir),
        "task_manifest_path": str(task_manifest_path) if task_manifest_path.exists() else "",
        "task_manifest_status": str(task_manifest.get("status", "")),
        "task_failure_reason": str(task_manifest.get("failure_reason", "")),
        "analysis_report": str(task_run_dir / "analysis_report.md"),
        "analysis_report_scaffold": str(artifacts.get("analysis_report_scaffold", "")),
        "final_data": str(task_run_dir / "final_data.json"),
        "final_data_scaffold": str(artifacts.get("final_data_scaffold", "")),
        "soul_export_payload": str(task_run_dir / "soul_export_payload.json"),
        "soul_export_payload_scaffold": str(artifacts.get("soul_export_payload_scaffold", "")),
        "financial_output": str(task_run_dir / "financial_output.xlsx"),
        "chapter_records": str(artifacts.get("chapter_records", "")),
        "run_manifest": str(artifacts.get("run_manifest", "")),
        "formalization_manifest": str(task_run_dir / "formalization_manifest.json"),
    }


def build_series_manifest(
    *,
    p4_dir: Path,
    output_dir: Path,
    runtime_config_path: Path,
    skill_status: Dict[str, Any],
    download_manifest: Dict[str, Any],
    preparation_manifest: Dict[str, Any],
    task_results: List[Dict[str, Any]],
    download_only: bool,
) -> Dict[str, Any]:
    success_count = sum(1 for item in task_results if item["status"] == "success")
    failed_count = sum(1 for item in task_results if item["status"] != "success")
    complete_count = sum(1 for item in task_results if item.get("task_manifest_status") == "success" and item.get("status") == "success")
    return {
        "generated_at": now_iso(),
        "p4_dir": str(p4_dir),
        "output_dir": str(output_dir),
        "runtime_config_path": str(runtime_config_path),
        "download_only": bool(download_only),
        "skill_status": skill_status,
        "download_phase_manifest_path": str(output_dir / DOWNLOAD_PHASE_MANIFEST),
        "preparation_manifest_path": str(output_dir / PREPARATION_MANIFEST),
        "summary": {
            "total_tasks": len(task_results),
            "success_count": success_count,
            "failed_count": failed_count,
            "complete_task_count": complete_count,
            "download_success_count": int(download_manifest.get("download_success_count", 0)),
            "download_failed_count": int(download_manifest.get("download_failed_count", 0)),
            "preparation_success_count": int(preparation_manifest.get("preparation_success_count", 0)),
            "preparation_failed_count": int(preparation_manifest.get("preparation_failed_count", 0)),
        },
        "task_results_path": str(output_dir / SERIES_RESULTS_JSONL),
        "tasks": task_results,
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
    batch_root = resolve_runtime_path(runtime_config, "batch_root")
    if args.output_dir:
        output_dir = Path(args.output_dir).resolve()
    else:
        output_dir = (tmp_root / "report_series" / timestamp_slug()).resolve()

    ensure_under_project_root(output_dir, project_root, "--output-dir")

    if output_dir.exists() and not args.resume_output_dir:
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / SERIES_TASK_LISTS_DIR).mkdir(parents=True, exist_ok=True)

    p4_inputs = load_p4_inputs(p4_dir)
    p4_inputs, selected_task_ids = filter_p4_inputs(p4_inputs, args.task_ids)
    seed_index = build_seed_index(p4_inputs["task_seed_list"])
    skill_status = check_skill_status(runtime_config)

    download_manifest = run_download_phase(
        download_config=p4_inputs["download_config"],
        seed_index=seed_index,
        output_dir=output_dir,
        threshold=1,
        timeout=args.download_timeout,
        resume_existing=args.resume_output_dir,
    )
    write_json(output_dir / DOWNLOAD_PHASE_MANIFEST, download_manifest)

    series_manifest: Dict[str, Any] = {
        "generated_at": now_iso(),
        "p4_dir": str(p4_dir),
        "output_dir": str(output_dir),
        "runtime_config_path": str(runtime_config_path),
        "skill_status": skill_status,
        "selected_task_ids": selected_task_ids,
        "download_only": bool(args.download_only),
        "stages": {
            "download": {
                "manifest_path": str(output_dir / DOWNLOAD_PHASE_MANIFEST),
                "download_success_count": download_manifest.get("download_success_count", 0),
                "download_failed_count": download_manifest.get("download_failed_count", 0),
                "gate_passed": download_manifest.get("gate_passed", False),
            },
            "preparation": {
                "status": "not_started",
                "manifest_path": "",
                "prepared_task_count": 0,
            },
            "per_report": {
                "status": "not_started",
                "processed_count": 0,
                "failed_count": 0,
                "task_results_path": "",
            },
        },
        "tasks": [],
    }

    if args.download_only:
        series_manifest["download_only"] = True
        write_json(output_dir / SERIES_MANIFEST, series_manifest)
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
    series_manifest["stages"]["preparation"] = {
        "status": "success" if preparation_manifest.get("preparation_success_count", 0) > 0 else "failed",
        "manifest_path": str(output_dir / PREPARATION_MANIFEST),
        "prepared_task_count": len(preparation_manifest.get("batch_tasks", [])),
    }

    prep_map = {item["task_id"]: item for item in preparation_manifest.get("results", [])}
    batch_task_map = {item["task_id"]: item for item in preparation_manifest.get("batch_tasks", [])}
    task_results: List[Dict[str, Any]] = []

    for download_item in download_manifest.get("results", []):
        task_id = str(download_item.get("task_id", "")).strip()
        content_id = str(download_item.get("content_id", "")).strip()
        seed_task = seed_index.get(content_id) or {}
        issuer_name = str(seed_task.get("issuer", download_item.get("seed_issuer", ""))).strip()
        task_year = seed_task.get("year", "")
        prep_item = prep_map.get(task_id)
        if download_item.get("download_status") != "success":
            task_results.append(
                {
                    "task_id": task_id,
                    "issuer": issuer_name,
                    "year": task_year,
                    "status": "failed",
                    "failure_stage": "download",
                    "failure_reason": str(download_item.get("failure_reason", download_item.get("http_status_or_error", ""))),
                    "download_status": download_item.get("download_status", ""),
                    "analysis_status": "",
                    "batch_name": "",
                    "task_run_dir": "",
                    "analysis_report": "",
                    "financial_output": "",
                }
            )
            if args.stop_on_failure:
                break
            continue

        if not prep_item or prep_item.get("preparation_status") != "success":
            task_results.append(
                {
                    "task_id": task_id,
                    "issuer": issuer_name,
                    "year": task_year,
                    "status": "failed",
                    "failure_stage": "preparation",
                    "failure_reason": str((prep_item or {}).get("failure_reason", "preparation_failed")),
                    "download_status": download_item.get("download_status", ""),
                    "analysis_status": "",
                    "batch_name": "",
                    "task_run_dir": "",
                    "analysis_report": "",
                    "financial_output": "",
                }
            )
            if args.stop_on_failure:
                break
            continue

        batch_task = batch_task_map.get(task_id)
        if not batch_task:
            task_results.append(
                {
                    "task_id": task_id,
                    "issuer": issuer_name,
                    "year": task_year,
                    "status": "failed",
                    "failure_stage": "analysis",
                    "failure_reason": "batch_task_missing",
                    "download_status": download_item.get("download_status", ""),
                    "analysis_status": "",
                    "batch_name": "",
                    "task_run_dir": "",
                    "analysis_report": "",
                    "financial_output": "",
                }
            )
            if args.stop_on_failure:
                break
            continue

        batch_result = run_single_task_batch(
            runtime_config_path=runtime_config_path,
            task=batch_task,
            batch_root=batch_root,
            series_name=output_dir.name,
            review_bundle=not args.no_build_review_bundle,
        )
        batch_result["download_status"] = download_item.get("download_status", "")
        batch_result["analysis_status"] = "success" if batch_result["status"] == "success" else "failed"
        batch_result["failure_stage"] = "" if batch_result["status"] == "success" else "analysis"
        batch_result["failure_reason"] = batch_result.get("task_failure_reason", "") if batch_result["status"] != "success" else ""
        batch_result["source_pdf"] = str(download_item.get("output_pdf", ""))
        task_results.append(batch_result)

        if args.stop_on_failure and batch_result["status"] != "success":
            break

    write_jsonl(output_dir / SERIES_RESULTS_JSONL, task_results)
    series_manifest.update(
        build_series_manifest(
            p4_dir=p4_dir,
            output_dir=output_dir,
            runtime_config_path=runtime_config_path,
            skill_status=skill_status,
            download_manifest=download_manifest,
            preparation_manifest=preparation_manifest,
            task_results=task_results,
            download_only=args.download_only,
        )
    )
    series_manifest["stages"]["per_report"] = {
        "status": "success" if any(item.get("status") == "success" for item in task_results) else "failed",
        "processed_count": sum(1 for item in task_results if item.get("status") == "success"),
        "failed_count": sum(1 for item in task_results if item.get("status") != "success"),
        "task_results_path": str(output_dir / SERIES_RESULTS_JSONL),
    }
    write_json(output_dir / SERIES_MANIFEST, series_manifest)

    print(f"[OK] 系列输出目录: {output_dir}")
    print(
        "[OK] 结果汇总: "
        f"success={series_manifest['summary']['success_count']}, "
        f"failed={series_manifest['summary']['failed_count']}, "
        f"complete={series_manifest['summary']['complete_task_count']}"
    )
    print(f"[OK] series_manifest: {output_dir / SERIES_MANIFEST}")


if __name__ == "__main__":
    main()
