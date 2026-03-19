#!/usr/bin/env python3
"""
将 scaffold-only 运行目录正式化为可交付成品。

输入：
- run_manifest.json
- chapter_records.jsonl
- analysis_report_scaffold.md
- final_data_scaffold.json
- soul_export_payload_scaffold.json

输出：
- analysis_report.md
- final_data.json
- soul_export_payload.json
- financial_output.xlsx
"""

import argparse
import copy
import datetime
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parents[1]


def now_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            rows.append(json.loads(text))
    return rows


def write_json(path: Path, payload: Dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def build_formal_report(scaffold_text: str, run_manifest: Dict[str, Any], chapter_records: List[Dict[str, Any]]) -> str:
    text = scaffold_text.replace("（Scaffold）", "").replace("(Scaffold)", "")
    if "## 正式化摘要" in text:
        return text

    entity = run_manifest.get("entity") or {}
    notes_locator = run_manifest.get("notes_locator") or {}
    notes_summary = run_manifest.get("notes_catalog_summary") or {}
    lines = [
        "",
        "## 正式化摘要",
        f"- 公司名称：{entity.get('company_name', '')}",
        f"- 报告期：{entity.get('report_period', '')}",
        f"- 报告类型：{entity.get('report_type', '')}",
        f"- 附注起止：{notes_locator.get('start_line', '')} - {notes_locator.get('end_line', '')}",
        f"- 附注章数：{notes_summary.get('note_chapter_count', len(chapter_records))}",
        f"- 章节记录数：{len(chapter_records)}",
        f"- scaffold 模式：{run_manifest.get('script_output_mode', '')}",
        f"- 复核要求：{run_manifest.get('codex_review_required', False)}",
    ]
    return text.rstrip() + "\n" + "\n".join(lines) + "\n"


def run_soul_export(payload_path: Path, output_path: Path) -> subprocess.CompletedProcess:
    command = [
        sys.executable,
        str(SCRIPT_DIR / "soul_exporter.py"),
        "--payload",
        str(payload_path),
        "--output",
        str(output_path),
    ]
    return subprocess.run(
        command,
        cwd=str(ROOT_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="将 scaffold-only 运行目录正式化")
    parser.add_argument("--run-dir", required=True, help="包含 scaffold 产物的运行目录")
    return parser.parse_args()


def main():
    args = parse_args()
    run_dir = Path(args.run_dir).resolve()
    if not run_dir.exists():
        raise SystemExit(f"run-dir 不存在: {run_dir}")

    scaffold_report_path = run_dir / "analysis_report_scaffold.md"
    scaffold_final_data_path = run_dir / "final_data_scaffold.json"
    scaffold_payload_path = run_dir / "soul_export_payload_scaffold.json"
    run_manifest_path = run_dir / "run_manifest.json"
    chapter_records_path = run_dir / "chapter_records.jsonl"

    missing = [str(path) for path in [scaffold_report_path, scaffold_final_data_path, scaffold_payload_path, run_manifest_path, chapter_records_path] if not path.exists()]
    if missing:
        raise SystemExit(f"缺少 scaffold 产物: {', '.join(missing)}")

    run_manifest = read_json(run_manifest_path)
    chapter_records = read_jsonl(chapter_records_path)

    analysis_report = build_formal_report(scaffold_report_path.read_text(encoding="utf-8"), run_manifest, chapter_records)
    analysis_report_path = run_dir / "analysis_report.md"
    write_text(analysis_report_path, analysis_report)

    final_data = copy.deepcopy(read_json(scaffold_final_data_path))
    final_data["generated_at"] = now_iso()
    final_data_path = run_dir / "final_data.json"
    write_json(final_data_path, final_data)

    soul_payload = copy.deepcopy(read_json(scaffold_payload_path))
    soul_payload["generated_at"] = now_iso()
    soul_payload_path = run_dir / "soul_export_payload.json"
    write_json(soul_payload_path, soul_payload)

    financial_output_path = run_dir / "financial_output.xlsx"
    export_result = run_soul_export(soul_payload_path, financial_output_path)
    if export_result.returncode != 0:
        raise SystemExit(f"soul_exporter 失败:\n{export_result.stdout}")

    formalization_manifest = {
        "generated_at": now_iso(),
        "run_dir": str(run_dir),
        "analysis_report": str(analysis_report_path),
        "final_data": str(final_data_path),
        "soul_export_payload": str(soul_payload_path),
        "financial_output": str(financial_output_path),
        "chapter_count": len(chapter_records),
    }
    write_json(run_dir / "formalization_manifest.json", formalization_manifest)
    print(f"[OK] 正式化完成: {run_dir}")
    print(f"[OK] analysis_report: {analysis_report_path}")
    print(f"[OK] financial_output: {financial_output_path}")


if __name__ == "__main__":
    main()
