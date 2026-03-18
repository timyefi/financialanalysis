#!/usr/bin/env python3
"""
将结构化知识增量直接写入正式 knowledge_base.json，并记录 adoption log。
"""

import argparse
import copy
import datetime
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Tuple

from adoption_record_utils import (
    ALLOWED_CONFIDENCE_LEVELS,
    ALLOWED_RESULTS,
    ALLOWED_REVIEW_STATES,
    ALLOWED_RISK_LEVELS,
    build_canonical_record,
    flatten_canonical_record,
    normalize_audit,
    normalize_evidence_refs,
    normalize_identity,
    normalize_operations,
    normalize_review,
    normalize_rollback,
    normalize_source,
    stringify,
)
from runtime_support import RuntimeConfigError, load_runtime_config, resolve_runtime_path


def slugify(value: str) -> str:
    text = "".join(ch if ch.isalnum() else "_" for ch in str(value or "").strip())
    text = text.strip("_")
    return text or "unknown"


def read_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)



def write_json(path: Path, payload: Dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    temp_path.replace(path)



def md5_payload(payload: Dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.md5(encoded).hexdigest()



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="写入正式 knowledge_base 并记录 adoption log")
    parser.add_argument("--delta", required=True, help="结构化增量 JSON 路径")
    parser.add_argument("--runtime-config", help="显式指定 runtime/runtime_config.json")
    return parser.parse_args()


SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def bump_patch_version(version: str) -> str:
    match = SEMVER_RE.match(version.strip())
    if not match:
        raise SystemExit(f"knowledge_base 版本格式不支持: {version}")
    major, minor, patch = (int(part) for part in match.groups())
    return f"{major}.{minor}.{patch + 1}"


def require_text(value: Any, message: str) -> str:
    text = stringify(value)
    if not text:
        raise SystemExit(message)
    return text


def validate_identity(identity: Dict[str, str]):
    require_text(identity.get("adoption_id"), "identity.adoption_id 缺失")
    require_text(identity.get("delta_version"), "identity.delta_version 缺失")
    require_text(identity.get("logged_at"), "identity.logged_at 缺失")
    result = require_text(identity.get("result"), "identity.result 缺失")
    if result not in ALLOWED_RESULTS:
        raise SystemExit(f"identity.result 不合法: {result}")
    if result != "applied":
        raise SystemExit(f"write_knowledge_adoption.py 仅接受 result=applied，当前为 {result}")


def validate_source(source: Dict[str, Any]):
    for key in ("case_name", "chapter_no", "chapter_title", "run_dir", "chapter_record_path", "review_ledger_path"):
        require_text(source.get(key), f"source.{key} 缺失")
    scaffold = source.get("scaffold_artifacts")
    if not isinstance(scaffold, dict):
        raise SystemExit("source.scaffold_artifacts 必须是对象")
    for key in ("analysis_report_scaffold", "final_data_scaffold", "soul_export_payload_scaffold"):
        require_text(scaffold.get(key), f"source.scaffold_artifacts.{key} 缺失")


def validate_review(review: Dict[str, Any]):
    review_state = require_text(review.get("review_state"), "review.review_state 缺失")
    if review_state not in ALLOWED_REVIEW_STATES:
        raise SystemExit(f"review.review_state 不合法: {review_state}")
    reviewer = require_text(review.get("reviewer"), "review.reviewer 缺失")
    reviewed_at = require_text(review.get("reviewed_at"), "review.reviewed_at 缺失")
    summary = require_text(review.get("summary"), "review.summary 缺失")
    risk_level = require_text(review.get("risk_level"), "review.risk_level 缺失")
    if risk_level not in ALLOWED_RISK_LEVELS:
        raise SystemExit(f"review.risk_level 不合法: {risk_level}")
    confidence = require_text(review.get("confidence"), "review.confidence 缺失")
    if confidence not in ALLOWED_CONFIDENCE_LEVELS:
        raise SystemExit(f"review.confidence 不合法: {confidence}")
    _ = reviewer, reviewed_at, summary


def validate_operations(operations: Any):
    if not isinstance(operations, list) or not operations:
        raise SystemExit("operations 必须是非空列表")
    for operation in operations:
        if not isinstance(operation, dict):
            raise SystemExit("operations 中每项必须是对象")
        op = stringify(operation.get("op"))
        if op not in {"set", "append", "upsert_by_key"}:
            raise SystemExit(f"不支持的操作: {op}")
        require_text(operation.get("path"), "operation.path 缺失")
        if op == "upsert_by_key":
            require_text(operation.get("match_key"), "upsert_by_key 缺少 match_key")
            if not isinstance(operation.get("value"), dict):
                raise SystemExit("upsert_by_key 的 value 必须是对象")


def validate_evidence_refs(evidence_refs: Any):
    if not isinstance(evidence_refs, list) or not evidence_refs:
        raise SystemExit("evidence_refs 必须是非空列表")
    has_chapter_record = False
    for item in evidence_refs:
        if not isinstance(item, dict):
            raise SystemExit("evidence_refs 中每项必须是对象")
        if stringify(item.get("type")) == "chapter_record":
            has_chapter_record = True
        require_text(item.get("type"), "evidence_refs.type 缺失")
        require_text(item.get("path"), "evidence_refs.path 缺失")
    if not has_chapter_record:
        raise SystemExit("evidence_refs 至少需要一条 chapter_record 证据")


def validate_rollback(rollback: Dict[str, Any]):
    if "enabled" in rollback and rollback.get("enabled") is False:
        raise SystemExit("rollback.enabled 不能为 false")


def get_metadata_version(knowledge_base: Dict[str, Any]) -> str:
    metadata = knowledge_base.get("metadata")
    if not isinstance(metadata, dict):
        raise SystemExit("knowledge_base 缺少 metadata 对象")
    return require_text(metadata.get("version"), "knowledge_base.metadata.version 缺失")



def resolve_parent_and_key(root: Dict[str, Any], path_text: str, *, create_missing: bool) -> Tuple[Any, str]:
    parts = [part for part in path_text.split(".") if part]
    if not parts:
        raise SystemExit("operation.path 不能为空")

    current: Any = root
    for part in parts[:-1]:
        if isinstance(current, dict):
            if part not in current:
                if not create_missing:
                    raise SystemExit(f"路径不存在: {path_text}")
                current[part] = {}
            current = current[part]
            continue
        raise SystemExit(f"路径中间节点不是对象: {path_text}")
    return current, parts[-1]



def apply_operation(payload: Dict[str, Any], operation: Dict[str, Any]):
    op = str(operation.get("op", "")).strip()
    path_text = str(operation.get("path", "")).strip()
    if op not in {"set", "append", "upsert_by_key"}:
        raise SystemExit(f"不支持的操作: {op}")
    if not path_text:
        raise SystemExit("operation.path 缺失")

    parent, key = resolve_parent_and_key(payload, path_text, create_missing=True)

    if op == "set":
        if not isinstance(parent, dict):
            raise SystemExit(f"set 目标父节点必须是对象: {path_text}")
        parent[key] = operation.get("value")
        return

    if not isinstance(parent, dict):
        raise SystemExit(f"{op} 目标父节点必须是对象: {path_text}")

    if key not in parent:
        parent[key] = []
    target = parent[key]
    if not isinstance(target, list):
        raise SystemExit(f"{op} 目标必须是列表: {path_text}")

    if op == "append":
        target.append(operation.get("value"))
        return

    match_key = str(operation.get("match_key", "")).strip()
    match_value = operation.get("match_value")
    value = operation.get("value")
    if not match_key:
        raise SystemExit("upsert_by_key 缺少 match_key")
    if not isinstance(value, dict):
        raise SystemExit("upsert_by_key 的 value 必须是对象")

    for index, item in enumerate(target):
        if isinstance(item, dict) and item.get(match_key) == match_value:
            merged = dict(item)
            merged.update(value)
            target[index] = merged
            return
    target.append(value)



def main():
    args = parse_args()
    delta_path = Path(args.delta).resolve()
    if not delta_path.exists():
        raise SystemExit(f"delta 文件不存在: {delta_path}")

    try:
        runtime_config = load_runtime_config(
            config_path=Path(args.runtime_config) if args.runtime_config else None,
            cwd=Path.cwd(),
            require_knowledge_base=True,
            ensure_state_dirs=True,
        )
    except RuntimeConfigError as exc:
        raise SystemExit(str(exc)) from exc

    delta_payload = read_json(delta_path)
    identity = normalize_identity(delta_payload)
    source = normalize_source(delta_payload)
    review = normalize_review(delta_payload)
    operations = normalize_operations(delta_payload)
    evidence_refs = normalize_evidence_refs(delta_payload)
    rollback = normalize_rollback(delta_payload)
    audit_input = normalize_audit(delta_payload)

    validate_identity(identity)
    validate_source(source)
    validate_review(review)
    validate_operations(operations)
    validate_evidence_refs(evidence_refs)
    validate_rollback(rollback)

    audit_summary = require_text(audit_input.get("summary"), "audit.summary 缺失")

    knowledge_base_path = resolve_runtime_path(runtime_config, "knowledge_base")
    adoption_log_dir = resolve_runtime_path(runtime_config, "knowledge_adoption_log_dir")
    knowledge_base = read_json(knowledge_base_path)
    before_payload = copy.deepcopy(knowledge_base)
    before_hash = md5_payload(before_payload)
    before_version = get_metadata_version(before_payload)

    for operation in operations:
        apply_operation(knowledge_base, operation)

    metadata = knowledge_base.setdefault("metadata", {})
    after_version = bump_patch_version(before_version)
    metadata["version"] = after_version
    metadata["last_updated"] = datetime.date.today().isoformat()
    after_hash = md5_payload(knowledge_base)

    hashes = {
        "before_hash": before_hash,
        "after_hash": after_hash,
        "knowledge_base_version_before": before_version,
        "knowledge_base_version_after": after_version,
    }
    backup_name = slugify(identity["adoption_id"])
    base_name = backup_name
    backup_path = adoption_log_dir / f"{base_name}.before.json"
    log_path = adoption_log_dir / f"{base_name}.log.json"
    rollback = {
        "enabled": True,
        "backup_path": str(backup_path),
        "rollback_log_path": stringify(rollback.get("rollback_log_path")),
        "strategy": stringify(rollback.get("strategy")) or "restore_full_knowledge_base_snapshot",
    }
    canonical_audit = {
        "adoption_id": identity["adoption_id"],
        "logged_at": identity["logged_at"],
        "result": identity["result"],
        "delta_path": str(delta_path),
        "knowledge_base_path": str(knowledge_base_path),
        "backup_path": str(backup_path),
        "summary": audit_summary,
    }
    canonical_record = build_canonical_record(
        identity=identity,
        source=source,
        review=review,
        operations=operations,
        evidence_refs=evidence_refs,
        hashes=hashes,
        rollback=rollback,
        audit=canonical_audit,
    )
    log_payload = flatten_canonical_record(canonical_record)

    write_json(backup_path, before_payload)
    write_json(knowledge_base_path, knowledge_base)
    write_json(log_path, log_payload)

    print(f"[OK] knowledge_base: {knowledge_base_path}")
    print(f"[OK] adoption_log: {log_path}")
    print(f"[OK] before_hash={before_hash} after_hash={after_hash}")
    print(f"[OK] knowledge_base_version_before={before_version} knowledge_base_version_after={after_version}")


if __name__ == "__main__":
    main()
