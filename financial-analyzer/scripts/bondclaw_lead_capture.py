#!/usr/bin/env python3
"""
BondClaw contact loader.

This keeps the contact layer lightweight:
- read the manifest
- read the sample queue
- summarize delivery status
- validate the required structure
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
LEAD_CAPTURE_DIR = ROOT / "lead-capture"
LEAD_CAPTURE_MANIFEST_PATH = LEAD_CAPTURE_DIR / "manifest.json"
LEAD_CAPTURE_QUEUE_PATH = LEAD_CAPTURE_DIR / "queue.example.json"


class LeadCaptureError(RuntimeError):
    pass


@dataclass(frozen=True)
class LeadSubmissionSummary:
    name: str
    institution: str
    role: str
    delivery_status: str
    sink_count: int


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise LeadCaptureError(f"JSON 顶层必须是对象: {path}")
    return payload


def load_manifest() -> Dict[str, Any]:
    if not LEAD_CAPTURE_MANIFEST_PATH.exists():
        raise LeadCaptureError("缺少 lead-capture/manifest.json")
    return read_json(LEAD_CAPTURE_MANIFEST_PATH)


def load_queue() -> Dict[str, Any]:
    if not LEAD_CAPTURE_QUEUE_PATH.exists():
        raise LeadCaptureError("缺少 lead-capture/queue.example.json")
    return read_json(LEAD_CAPTURE_QUEUE_PATH)


def load_submission_summaries() -> List[LeadSubmissionSummary]:
    queue = load_queue()
    summaries: List[LeadSubmissionSummary] = []
    for submission in queue.get("submissions", []):
        if not isinstance(submission, dict):
            continue
        summaries.append(
            LeadSubmissionSummary(
                name=str(submission.get("name", "")),
                institution=str(submission.get("institution", "")),
                role=str(submission.get("role", "")),
                delivery_status=str(submission.get("delivery_status", "")),
                sink_count=len(submission.get("sink_receipts") or {}),
            )
        )
    return summaries


def build_lead_capture_summary() -> Dict[str, Any]:
    manifest = load_manifest()
    queue = load_queue()
    summaries = load_submission_summaries()
    return {
        "manifest": manifest,
        "queue_count": queue.get("queue_count", len(queue.get("submissions", []))),
        "delivery_order": manifest.get("default_delivery_order", []),
        "retry_policy": manifest.get("retry_policy", {}),
        "sink_types": manifest.get("sink_types", []),
        "form_behavior": manifest.get("form_behavior", {}),
        "submission_summaries": [summary.__dict__ for summary in summaries],
    }


def validate_lead_capture() -> List[str]:
    errors: List[str] = []
    try:
        manifest = load_manifest()
    except LeadCaptureError as exc:
        return [str(exc)]

    if manifest.get("schemaVersion") != 1:
        errors.append("lead-capture manifest schemaVersion 必须为 1")

    for field in ("required_fields", "default_delivery_order", "retry_policy", "sink_types", "form_behavior"):
        if field not in manifest:
            errors.append(f"lead-capture manifest 缺少 {field}")

    try:
        queue = load_queue()
    except LeadCaptureError as exc:
        errors.append(str(exc))
        queue = {}

    if not isinstance(queue.get("submissions"), list):
        errors.append("lead-capture queue.example.json 需要 submissions 数组")
    else:
        if int(queue.get("queue_count", len(queue["submissions"]))) != len(queue["submissions"]):
            errors.append("lead-capture queue_count 必须与 submissions 数量一致")
        for idx, submission in enumerate(queue["submissions"], start=1):
            if not isinstance(submission, dict):
                errors.append(f"lead-capture submission #{idx} 不是对象")
                continue
            for field in manifest.get("required_fields", []):
                if field not in submission:
                    errors.append(f"lead-capture submission #{idx} 缺少 {field}")
            receipts = submission.get("sink_receipts")
            if not isinstance(receipts, dict) or not receipts:
                errors.append(f"lead-capture submission #{idx} 需要 sink_receipts")
            if submission.get("delivery_status") not in {"queued", "partial", "delivered", "failed"}:
                errors.append(f"lead-capture submission #{idx} delivery_status 非法")

    return errors


if __name__ == "__main__":
    print(json.dumps(build_lead_capture_summary(), ensure_ascii=False, indent=2))
