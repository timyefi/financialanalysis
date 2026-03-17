#!/usr/bin/env python3
"""
W7 批处理回归验证。
"""

import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT_DIR / "financial-analyzer" / "scripts"
TESTDATA_DIR = ROOT_DIR / "financial-analyzer" / "testdata" / "w7_batch_tasks"
TEST_RUNS_DIR = ROOT_DIR / "financial-analyzer" / "test_runs"
BATCH_SCRIPT = SCRIPT_DIR / "run_batch_pipeline.py"
RESULTS_PATH = TEST_RUNS_DIR / "w7_batch_regression_results.json"
REPORT_PATH = TEST_RUNS_DIR / "w7_batch_regression_report.md"

SCENARIOS = {
    "mixed": {
        "task_list": TESTDATA_DIR / "mixed_batch_tasks.json",
        "batch_run_dir": TEST_RUNS_DIR / "batches" / "w7_mixed_smoke",
        "flags": ["--build-review-bundle"],
    },
    "success": {
        "task_list": TESTDATA_DIR / "success_batch_tasks.json",
        "batch_run_dir": TEST_RUNS_DIR / "batches" / "w7_success_smoke",
        "flags": ["--build-review-bundle"],
    },
    "pair": {
        "task_list": TESTDATA_DIR / "pair_batch_tasks.json",
        "batch_run_dir": TEST_RUNS_DIR / "batches" / "w7_pair_smoke",
        "flags": ["--build-review-bundle"],
    },
}


def now_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Dict[str, Any]):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def write_text(path: Path, content: str):
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


def scenario_command(config: Dict[str, Any], extra_flags: List[str] = None) -> List[str]:
    command = [
        sys.executable,
        str(BATCH_SCRIPT),
        "--task-list",
        str(config["task_list"]),
        "--batch-run-dir",
        str(config["batch_run_dir"]),
    ]
    command.extend(config["flags"])
    if extra_flags:
        command.extend(extra_flags)
    return command


def validate_manifest(batch_run_dir: Path, expected_summary: Dict[str, int], expected_governance_status: str) -> List[Dict[str, Any]]:
    checks = []
    manifest_path = batch_run_dir / "batch_manifest.json"
    pending_index_path = batch_run_dir / "pending_updates_index.json"
    failed_tasks_path = batch_run_dir / "failed_tasks.json"
    errors = []
    details = {
        "manifest_exists": manifest_path.exists(),
        "pending_updates_index_exists": pending_index_path.exists(),
        "failed_tasks_exists": failed_tasks_path.exists(),
    }
    if not manifest_path.exists():
        return [make_check("batch_manifest", False, details, ["batch_manifest.json 未生成"])]

    manifest = read_json(manifest_path)
    details["summary"] = manifest.get("summary", {})
    details["governance_status"] = (manifest.get("governance") or {}).get("governance_status")
    for key, value in expected_summary.items():
        actual = (manifest.get("summary") or {}).get(key)
        if actual != value:
            errors.append(f"summary.{key} expected={value}, actual={actual}")
    if details["governance_status"] != expected_governance_status:
        errors.append(
            "governance_status 不匹配: "
            f"expected={expected_governance_status!r}, actual={details['governance_status']!r}"
        )
    checks.append(make_check("batch_manifest", not errors, details, errors))

    if pending_index_path.exists():
        pending_index = read_json(pending_index_path)
        checks.append(
            make_check(
                "pending_updates_index",
                True,
                {
                    "success_task_count": pending_index.get("success_task_count"),
                    "item_count": len(pending_index.get("items", [])),
                },
                [],
            )
        )
    else:
        checks.append(make_check("pending_updates_index", False, details, ["pending_updates_index.json 未生成"]))

    if failed_tasks_path.exists():
        failed_payload = read_json(failed_tasks_path)
        checks.append(
            make_check(
                "failed_tasks",
                True,
                {"failed_count": failed_payload.get("failed_count"), "task_count": len(failed_payload.get("tasks", []))},
                [],
            )
        )
    else:
        checks.append(make_check("failed_tasks", False, details, ["failed_tasks.json 未生成"]))

    return checks


def validate_governance_artifacts(batch_run_dir: Path, should_exist: bool) -> Dict[str, Any]:
    governance_dir = batch_run_dir / "governance_review"
    bundle_path = governance_dir / "knowledge_review_bundle.json"
    report_path = governance_dir / "knowledge_review_report.md"
    details = {
        "bundle_exists": bundle_path.exists(),
        "report_exists": report_path.exists(),
    }
    passed = details["bundle_exists"] == should_exist and details["report_exists"] == should_exist
    errors = []
    if not passed:
        errors.append(f"governance_review 产物存在性不匹配: expected={should_exist}")
    return make_check("governance_review_artifacts", passed, details, errors)


def validate_latest_run(batch_run_dir: Path, expected_selected: int, expected_executed: int, expected_skipped: int) -> Dict[str, Any]:
    manifest = read_json(batch_run_dir / "batch_manifest.json")
    latest_run = manifest.get("latest_run") or {}
    details = latest_run
    errors = []
    if latest_run.get("selected_task_count") != expected_selected:
        errors.append(
            f"selected_task_count expected={expected_selected}, actual={latest_run.get('selected_task_count')}"
        )
    if latest_run.get("executed_task_count") != expected_executed:
        errors.append(
            f"executed_task_count expected={expected_executed}, actual={latest_run.get('executed_task_count')}"
        )
    if latest_run.get("skipped_existing_success_count") != expected_skipped:
        errors.append(
            "skipped_existing_success_count expected="
            f"{expected_skipped}, actual={latest_run.get('skipped_existing_success_count')}"
        )
    return make_check("latest_run", not errors, details, errors)


def run_scenario(name: str, config: Dict[str, Any], extra_flags: List[str] = None) -> Dict[str, Any]:
    command = scenario_command(config, extra_flags=extra_flags)
    completed = run_command(command)
    return {
        "name": name,
        "command": command,
        "returncode": completed.returncode,
        "stdout_tail": "\n".join(completed.stdout.strip().splitlines()[-30:]),
    }


def main():
    for config in SCENARIOS.values():
        if config["batch_run_dir"].exists():
            shutil.rmtree(config["batch_run_dir"])

    results: List[Dict[str, Any]] = []

    mixed_run = run_scenario("mixed_initial", SCENARIOS["mixed"])
    mixed_checks = validate_manifest(
        SCENARIOS["mixed"]["batch_run_dir"],
        {"task_count": 5, "success_count": 3, "failed_count": 2, "pending_count": 0},
        "review_bundle_built",
    )
    mixed_checks.append(validate_governance_artifacts(SCENARIOS["mixed"]["batch_run_dir"], should_exist=True))
    results.append({"scenario": mixed_run, "checks": mixed_checks})

    success_run = run_scenario("success_initial", SCENARIOS["success"])
    success_checks = validate_manifest(
        SCENARIOS["success"]["batch_run_dir"],
        {"task_count": 3, "success_count": 3, "failed_count": 0, "pending_count": 0},
        "review_bundle_built",
    )
    success_checks.append(validate_governance_artifacts(SCENARIOS["success"]["batch_run_dir"], should_exist=True))
    results.append({"scenario": success_run, "checks": success_checks})

    pair_run = run_scenario("pair_initial", SCENARIOS["pair"])
    pair_checks = validate_manifest(
        SCENARIOS["pair"]["batch_run_dir"],
        {"task_count": 2, "success_count": 2, "failed_count": 0, "pending_count": 0},
        "not_built",
    )
    pair_checks.append(validate_governance_artifacts(SCENARIOS["pair"]["batch_run_dir"], should_exist=False))
    results.append({"scenario": pair_run, "checks": pair_checks})

    resume_run = run_scenario("success_resume", SCENARIOS["success"], extra_flags=["--resume"])
    resume_checks = [
        validate_latest_run(
            SCENARIOS["success"]["batch_run_dir"],
            expected_selected=0,
            expected_executed=0,
            expected_skipped=3,
        )
    ]
    results.append({"scenario": resume_run, "checks": resume_checks})

    only_failed_run = run_scenario("mixed_only_failed", SCENARIOS["mixed"], extra_flags=["--only-failed"])
    only_failed_checks = [
        validate_latest_run(
            SCENARIOS["mixed"]["batch_run_dir"],
            expected_selected=2,
            expected_executed=2,
            expected_skipped=0,
        )
    ]
    results.append({"scenario": only_failed_run, "checks": only_failed_checks})

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
    }
    payload = {
        "summary": summary,
        "results": results,
    }
    write_json(RESULTS_PATH, payload)

    lines = [
        "# W7 Batch Regression Report",
        "",
        f"- Generated At: {summary['generated_at']}",
        f"- Scenario Count: {summary['scenario_count']}",
        f"- All Passed: {summary['all_passed']}",
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
