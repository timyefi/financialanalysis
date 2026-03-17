#!/usr/bin/env python3
"""
P2 processed reports registry 回归验证。
"""

import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from processed_reports_registry import ProcessedReportsRegistry
from runtime_support import (
    current_engine_version,
    load_knowledge_base_version,
    load_runtime_config,
    now_iso,
    read_json,
    resolve_runtime_path,
)


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT_DIR / "financial-analyzer" / "scripts"
TEST_RUNS_DIR = ROOT_DIR / "financial-analyzer" / "test_runs"
BATCH_SCRIPT = SCRIPT_DIR / "run_batch_pipeline.py"
RESULTS_PATH = TEST_RUNS_DIR / "p2_registry_regression_results.json"
REPORT_PATH = TEST_RUNS_DIR / "p2_registry_regression_report.md"
RUNTIME_CONFIG = load_runtime_config(
    cwd=ROOT_DIR,
    require_knowledge_base=True,
    ensure_state_dirs=True,
)
REGISTRY_PATH = resolve_runtime_path(RUNTIME_CONFIG, "processed_reports_registry")
TMP_ROOT = resolve_runtime_path(RUNTIME_CONFIG, "tmp_root") / "p2_registry_regression"
BATCH_ROOT = resolve_runtime_path(RUNTIME_CONFIG, "batch_root") / "p2_registry_regression"
HENGLONG_MD = ROOT_DIR / "output" / "恒隆地产" / "恒隆地产2024年報" / "恒隆地产2024年報.md"
HENGLONG_NOTES = ROOT_DIR / "financial-analyzer" / "testdata" / "henglong_notes_workfile.json"
W6_HENGLONG_MANIFEST = ROOT_DIR / "financial-analyzer" / "test_runs" / "w6_henglong" / "run_manifest.json"
W6_REGRESSION_RESULTS = ROOT_DIR / "financial-analyzer" / "test_runs" / "w6_regression_results.json"
W7_REGRESSION_RESULTS = ROOT_DIR / "financial-analyzer" / "test_runs" / "w7_batch_regression_results.json"


def write_json(path: Path, payload: Dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def write_text(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def run_command(args: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=str(ROOT_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def make_check(name: str, passed: bool, details: Dict[str, Any] = None, errors: List[str] = None) -> Dict[str, Any]:
    return {
        "name": name,
        "passed": passed,
        "details": details or {},
        "errors": errors or [],
    }


def reset_runtime_state():
    if REGISTRY_PATH.exists():
        REGISTRY_PATH.unlink()
    lock_path = REGISTRY_PATH.with_suffix(".lock")
    if lock_path.exists():
        lock_path.unlink()
    if TMP_ROOT.exists():
        shutil.rmtree(TMP_ROOT)
    if BATCH_ROOT.exists():
        shutil.rmtree(BATCH_ROOT)


def create_variant_assets() -> Dict[str, Path]:
    TMP_ROOT.mkdir(parents=True, exist_ok=True)

    md_variant_a = TMP_ROOT / "henglong_registry_variant_a.md"
    md_variant_b = TMP_ROOT / "henglong_registry_variant_b.md"
    notes_variant_a = TMP_ROOT / "henglong_notes_variant_a.json"
    notes_variant_b = TMP_ROOT / "henglong_notes_variant_b.json"

    md_text = HENGLONG_MD.read_text(encoding="utf-8")
    md_variant_a.write_text(md_text + "\n<!-- p2 registry variant a -->\n", encoding="utf-8")
    md_variant_b.write_text(md_text + "\n<!-- p2 registry variant b -->\n", encoding="utf-8")

    notes_payload = read_json(HENGLONG_NOTES)
    write_json(notes_variant_a, notes_payload)

    notes_variant_b_payload = read_json(HENGLONG_NOTES)
    notes_variant_b_payload["locator_evidence"] = list(notes_variant_b_payload["locator_evidence"]) + [
        {
            "step": "regression_marker",
            "keyword": "p2_registry",
            "excerpt": "notes fingerprint variant",
        }
    ]
    write_json(notes_variant_b, notes_variant_b_payload)

    return {
        "md_variant_a": md_variant_a,
        "md_variant_b": md_variant_b,
        "notes_variant_a": notes_variant_a,
        "notes_variant_b": notes_variant_b,
    }


def write_task_list(path: Path, task_id: str, md_path: Path, notes_workfile: Path):
    payload = {
        "batch_name": path.stem,
        "defaults": {},
        "tasks": [
            {
                "task_id": task_id,
                "issuer": "恒隆地产",
                "year": 2024,
                "md_path": str(md_path),
                "notes_workfile": str(notes_workfile),
            }
        ],
    }
    write_json(path, payload)


def run_batch(task_list_path: Path, batch_run_dir: Path, extra_flags: List[str] = None) -> Dict[str, Any]:
    command = [
        sys.executable,
        str(BATCH_SCRIPT),
        "--task-list",
        str(task_list_path),
        "--batch-run-dir",
        str(batch_run_dir),
    ]
    if extra_flags:
        command.extend(extra_flags)
    completed = run_command(command)
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout_tail": "\n".join(completed.stdout.strip().splitlines()[-30:]),
    }


def check_temp_registry_first_write() -> Dict[str, Any]:
    temp_registry_path = TMP_ROOT / "temp_registry.json"
    if temp_registry_path.exists():
        temp_registry_path.unlink()

    registry = ProcessedReportsRegistry(
        runtime_config=RUNTIME_CONFIG,
        registry_path=temp_registry_path,
        enable_backfill=False,
    )
    task = {
        "task_id": "temp_henglong_first_write",
        "issuer": "恒隆地产",
        "year": 2024,
        "md_path": HENGLONG_MD,
        "notes_workfile": HENGLONG_NOTES,
        "run_dir": TMP_ROOT / "temp_run",
    }
    context = registry.prepare_task_context(
        task,
        target_engine_version=current_engine_version(),
        knowledge_base_version=load_knowledge_base_version(RUNTIME_CONFIG),
    )
    update = registry.record_batch_task_result(
        task=task,
        result={
            "task_id": task["task_id"],
            "status": "success",
            "failure_reason": "",
            "manifest_path": str(W6_HENGLONG_MANIFEST),
            "completed_at": now_iso(),
            "notes_locator_status": "success",
            "pending_updates_path": "",
        },
        registry_context=context,
        batch_name="temp_first_write",
        batch_run_dir=TMP_ROOT / "temp_batch",
        task_results_path=TMP_ROOT / "temp_batch" / "task_results.jsonl",
        batch_manifest_path=TMP_ROOT / "temp_batch" / "batch_manifest.json",
        knowledge_base_version=load_knowledge_base_version(RUNTIME_CONFIG),
    )
    registry.refresh()
    stats = registry.payload["stats"]
    passed = (
        temp_registry_path.exists()
        and stats["report_count"] == 1
        and stats["attempt_count"] == 1
        and stats["success_attempt_count"] == 1
        and bool(update.get("report_key"))
    )
    errors = []
    if stats["report_count"] != 1:
        errors.append(f"report_count expected=1 actual={stats['report_count']}")
    if stats["attempt_count"] != 1:
        errors.append(f"attempt_count expected=1 actual={stats['attempt_count']}")
    return make_check(
        "temp_registry_first_write",
        passed,
        {
            "registry_path": str(temp_registry_path),
            "stats": stats,
            "report_key": update.get("report_key", ""),
        },
        errors,
    )


def main():
    reset_runtime_state()
    assets = create_variant_assets()
    results: List[Dict[str, Any]] = []

    temp_registry_check = check_temp_registry_first_write()
    results.append({"scenario": {"name": "temp_registry_first_write", "returncode": 0, "stdout_tail": ""}, "checks": [temp_registry_check]})

    reset_runtime_state()
    registry = ProcessedReportsRegistry(runtime_config=RUNTIME_CONFIG, enable_backfill=True)
    assets = create_variant_assets()
    backfill_stats = registry.payload["stats"]
    backfill_errors = []
    if backfill_stats["success_attempt_count"] < 3:
        backfill_errors.append(f"success_attempt_count expected>=3 actual={backfill_stats['success_attempt_count']}")
    if backfill_stats["failed_attempt_count"] < 2:
        backfill_errors.append(f"failed_attempt_count expected>=2 actual={backfill_stats['failed_attempt_count']}")
    if backfill_stats["report_count"] < 3:
        backfill_errors.append(f"report_count expected>=3 actual={backfill_stats['report_count']}")
    if not any("W7 回填" in warning or "w7_batch_regression_results.json" in warning for warning in registry.initialization_info["warnings"]):
        backfill_errors.append("missing W7 backfill warning")
    results.append(
        {
            "scenario": {"name": "registry_backfill_init", "returncode": 0, "stdout_tail": ""},
            "checks": [
                make_check(
                    "registry_backfill",
                    not backfill_errors,
                    {
                        "registry_path": str(REGISTRY_PATH),
                        "stats": backfill_stats,
                        "warnings": registry.initialization_info["warnings"],
                        "w6_results_exists": W6_REGRESSION_RESULTS.exists(),
                        "w7_results_exists": W7_REGRESSION_RESULTS.exists(),
                    },
                    backfill_errors,
                )
            ],
        }
    )

    task_list_a = TMP_ROOT / "batch_variant_a.json"
    task_list_b = TMP_ROOT / "batch_variant_b.json"
    task_list_doc_changed = TMP_ROOT / "batch_variant_doc_changed.json"
    write_task_list(task_list_a, "henglong_variant_a", assets["md_variant_a"], assets["notes_variant_a"])
    write_task_list(task_list_b, "henglong_variant_b", assets["md_variant_a"], assets["notes_variant_b"])
    write_task_list(task_list_doc_changed, "henglong_variant_doc_changed", assets["md_variant_b"], assets["notes_variant_a"])

    batch1_dir = BATCH_ROOT / "batch_variant_a_first"
    batch1 = run_batch(task_list_a, batch1_dir)
    batch1_manifest = read_json(batch1_dir / "batch_manifest.json") if (batch1_dir / "batch_manifest.json").exists() else {}
    batch1_errors = []
    if batch1["returncode"] != 0:
        batch1_errors.append("first batch returned nonzero")
    if (batch1_manifest.get("summary") or {}).get("success_count") != 1:
        batch1_errors.append(f"success_count expected=1 actual={(batch1_manifest.get('summary') or {}).get('success_count')}")
    results.append(
        {
            "scenario": batch1 | {"name": "batch_variant_a_first"},
            "checks": [make_check("batch_variant_a_first", not batch1_errors, batch1_manifest, batch1_errors)],
        }
    )

    registry.refresh()
    task_variant_b = {
        "task_id": "henglong_variant_b",
        "issuer": "恒隆地产",
        "year": 2024,
        "md_path": assets["md_variant_a"],
        "notes_workfile": assets["notes_variant_b"],
        "run_dir": BATCH_ROOT / "unused",
    }
    notes_changed_context = registry.prepare_task_context(
        task_variant_b,
        target_engine_version=current_engine_version(),
        knowledge_base_version=load_knowledge_base_version(RUNTIME_CONFIG),
    )
    notes_changed_errors = []
    if notes_changed_context["needs_rerun"]:
        notes_changed_errors.append(f"notes change should not require rerun: {notes_changed_context['rerun_reasons']}")
    if "notes_workfile_changed" not in notes_changed_context["audit_flags"]:
        notes_changed_errors.append("notes_workfile_changed audit flag missing")
    results.append(
        {
            "scenario": {"name": "notes_change_eval", "returncode": 0, "stdout_tail": ""},
            "checks": [make_check("notes_change_eval", not notes_changed_errors, notes_changed_context, notes_changed_errors)],
        }
    )

    batch2_dir = BATCH_ROOT / "batch_variant_a_resume"
    batch2 = run_batch(task_list_a, batch2_dir, extra_flags=["--resume"])
    batch2_manifest = read_json(batch2_dir / "batch_manifest.json") if (batch2_dir / "batch_manifest.json").exists() else {}
    batch2_latest_run = batch2_manifest.get("latest_run") or {}
    batch2_task_index = batch2_manifest.get("task_index") or []
    batch2_errors = []
    if batch2["returncode"] != 0:
        batch2_errors.append("second batch returned nonzero")
    if batch2_latest_run.get("executed_task_count") != 0:
        batch2_errors.append(f"executed_task_count expected=0 actual={batch2_latest_run.get('executed_task_count')}")
    if batch2_latest_run.get("skipped_existing_success_without_local_result_count") != 1:
        batch2_errors.append(
            "skipped_existing_success_without_local_result_count expected=1 actual="
            f"{batch2_latest_run.get('skipped_existing_success_without_local_result_count')}"
        )
    if not batch2_task_index or batch2_task_index[0].get("registry_decision") != "skipped_existing_success_in_registry":
        batch2_errors.append("registry skip decision missing in task_index")
    results.append(
        {
            "scenario": batch2 | {"name": "batch_variant_a_resume"},
            "checks": [make_check("batch_variant_a_resume", not batch2_errors, batch2_manifest, batch2_errors)],
        }
    )

    report_key = notes_changed_context["report_key"]
    before_attempt_count = len((registry.payload["reports"].get(report_key) or {}).get("attempts", []))
    batch3_dir = BATCH_ROOT / "batch_variant_b_forced"
    batch3 = run_batch(task_list_b, batch3_dir)
    registry.refresh()
    after_attempt_count = len((registry.payload["reports"].get(report_key) or {}).get("attempts", []))
    batch3_errors = []
    if batch3["returncode"] != 0:
        batch3_errors.append("forced notes-change batch returned nonzero")
    if after_attempt_count != before_attempt_count + 1:
        batch3_errors.append(f"attempt_count expected={before_attempt_count + 1} actual={after_attempt_count}")
    results.append(
        {
            "scenario": batch3 | {"name": "batch_variant_b_forced"},
            "checks": [
                make_check(
                    "batch_variant_b_forced",
                    not batch3_errors,
                    {
                        "report_key": report_key,
                        "before_attempt_count": before_attempt_count,
                        "after_attempt_count": after_attempt_count,
                    },
                    batch3_errors,
                )
            ],
        }
    )

    doc_changed_task = {
        "task_id": "henglong_variant_doc_changed",
        "issuer": "恒隆地产",
        "year": 2024,
        "md_path": assets["md_variant_b"],
        "notes_workfile": assets["notes_variant_a"],
        "run_dir": BATCH_ROOT / "unused_doc_changed",
    }
    doc_changed_context = registry.prepare_task_context(
        doc_changed_task,
        target_engine_version=current_engine_version(),
        knowledge_base_version=load_knowledge_base_version(RUNTIME_CONFIG),
    )
    doc_changed_errors = []
    if not doc_changed_context["needs_rerun"]:
        doc_changed_errors.append("document change should require rerun")
    if "document_fingerprint_changed" not in doc_changed_context["rerun_reasons"]:
        doc_changed_errors.append(f"missing document_fingerprint_changed reason: {doc_changed_context['rerun_reasons']}")
    results.append(
        {
            "scenario": {"name": "document_change_eval", "returncode": 0, "stdout_tail": ""},
            "checks": [make_check("document_change_eval", not doc_changed_errors, doc_changed_context, doc_changed_errors)],
        }
    )

    engine_changed_context = registry.prepare_task_context(
        {
            "task_id": "henglong_variant_engine_changed",
            "issuer": "恒隆地产",
            "year": 2024,
            "md_path": assets["md_variant_a"],
            "notes_workfile": assets["notes_variant_a"],
            "run_dir": BATCH_ROOT / "unused_engine_changed",
        },
        target_engine_version="9.9.9-test",
        knowledge_base_version=load_knowledge_base_version(RUNTIME_CONFIG),
    )
    engine_changed_errors = []
    if not engine_changed_context["needs_rerun"]:
        engine_changed_errors.append("engine version change should require rerun")
    if "engine_version_changed" not in engine_changed_context["rerun_reasons"]:
        engine_changed_errors.append(f"missing engine_version_changed reason: {engine_changed_context['rerun_reasons']}")
    results.append(
        {
            "scenario": {"name": "engine_change_eval", "returncode": 0, "stdout_tail": ""},
            "checks": [make_check("engine_change_eval", not engine_changed_errors, engine_changed_context, engine_changed_errors)],
        }
    )

    knowledge_changed_context = registry.prepare_task_context(
        {
            "task_id": "henglong_variant_knowledge_changed",
            "issuer": "恒隆地产",
            "year": 2024,
            "md_path": assets["md_variant_a"],
            "notes_workfile": assets["notes_variant_a"],
            "run_dir": BATCH_ROOT / "unused_knowledge_changed",
        },
        target_engine_version=current_engine_version(),
        knowledge_base_version="9.9.9-test",
    )
    knowledge_changed_errors = []
    if knowledge_changed_context["needs_rerun"]:
        knowledge_changed_errors.append(
            f"knowledge base version change should not require rerun: {knowledge_changed_context['rerun_reasons']}"
        )
    if "knowledge_base_version_changed" not in knowledge_changed_context["audit_flags"]:
        knowledge_changed_errors.append("knowledge_base_version_changed audit flag missing")
    results.append(
        {
            "scenario": {"name": "knowledge_change_eval", "returncode": 0, "stdout_tail": ""},
            "checks": [make_check("knowledge_change_eval", not knowledge_changed_errors, knowledge_changed_context, knowledge_changed_errors)],
        }
    )

    all_passed = all(
        item["scenario"]["returncode"] == 0 and all(check["passed"] for check in item["checks"])
        for item in results
    )
    summary = {
        "generated_at": now_iso(),
        "scenario_count": len(results),
        "all_passed": all_passed,
        "passed_scenarios": sum(
            1
            for item in results
            if item["scenario"]["returncode"] == 0 and all(check["passed"] for check in item["checks"])
        ),
        "failed_scenarios": sum(
            1
            for item in results
            if item["scenario"]["returncode"] != 0 or any(not check["passed"] for check in item["checks"])
        ),
        "registry_path": str(REGISTRY_PATH),
    }
    payload = {
        "summary": summary,
        "results": results,
    }
    write_json(RESULTS_PATH, payload)

    lines = [
        "# P2 Registry Regression Report",
        "",
        f"- Generated At: {summary['generated_at']}",
        f"- Scenario Count: {summary['scenario_count']}",
        f"- All Passed: {summary['all_passed']}",
        f"- Registry Path: {summary['registry_path']}",
        "",
    ]
    for item in results:
        scenario = item["scenario"]
        passed = scenario["returncode"] == 0 and all(check["passed"] for check in item["checks"])
        lines.append(f"## {scenario['name']} - {'PASS' if passed else 'FAIL'}")
        lines.append(f"- Returncode: {scenario['returncode']}")
        for check in item["checks"]:
            lines.append(f"- {check['name']}: {'PASS' if check['passed'] else 'FAIL'}")
            for error in check["errors"]:
                lines.append(f"  - {error}")
        lines.append("")
    write_text(REPORT_PATH, "\n".join(lines).rstrip() + "\n")

    print(f"[OK] results: {RESULTS_PATH}")
    print(f"[OK] report: {REPORT_PATH}")
    if not all_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
