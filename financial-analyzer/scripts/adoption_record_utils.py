#!/usr/bin/env python3
"""
Utilities for canonical knowledge adoption records.
"""

from typing import Any, Dict, Iterable, List


ALLOWED_RESULTS = {"applied", "rejected", "rolled_back", "dry_run"}
ALLOWED_REVIEW_STATES = {"proposed", "reviewed", "adopted", "rejected", "blocked"}
ALLOWED_RISK_LEVELS = {"low", "medium", "high"}
ALLOWED_CONFIDENCE_LEVELS = {"low", "medium", "high"}
DEFAULT_ROLLBACK_STRATEGY = "restore_full_knowledge_base_snapshot"


def coerce_mapping(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def coerce_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def stringify(value: Any, default: str = "") -> str:
    text = str(value).strip() if value is not None else ""
    return text if text else default


def first_non_empty(*values: Any, default: str = "") -> str:
    for value in values:
        text = stringify(value)
        if text:
            return text
    return default


def normalize_identity(payload: Dict[str, Any]) -> Dict[str, str]:
    identity = coerce_mapping(payload.get("identity"))
    audit = coerce_mapping(payload.get("audit"))
    return {
        "adoption_id": first_non_empty(
            identity.get("adoption_id"),
            payload.get("adoption_id"),
            audit.get("adoption_id"),
        ),
        "delta_version": first_non_empty(
            identity.get("delta_version"),
            payload.get("delta_version"),
        ),
        "logged_at": first_non_empty(
            identity.get("logged_at"),
            payload.get("logged_at"),
            audit.get("logged_at"),
        ),
        "result": first_non_empty(
            identity.get("result"),
            payload.get("result"),
            audit.get("result"),
        ),
    }


def normalize_source(payload: Dict[str, Any]) -> Dict[str, Any]:
    source = coerce_mapping(payload.get("source"))
    scaffold_artifacts = coerce_mapping(source.get("scaffold_artifacts"))
    if not scaffold_artifacts:
        scaffold_artifacts = {
            "analysis_report_scaffold": stringify(payload.get("analysis_report_scaffold")),
            "final_data_scaffold": stringify(payload.get("final_data_scaffold")),
            "soul_export_payload_scaffold": stringify(payload.get("soul_export_payload_scaffold")),
        }
        scaffold_artifacts = {
            key: value for key, value in scaffold_artifacts.items() if value
        }
    normalized = {
        "case_name": first_non_empty(source.get("case_name"), payload.get("case_name")),
        "chapter_no": first_non_empty(source.get("chapter_no"), payload.get("chapter_no")),
        "chapter_title": first_non_empty(source.get("chapter_title"), payload.get("chapter_title")),
        "run_dir": first_non_empty(source.get("run_dir"), payload.get("run_dir")),
        "chapter_record_path": first_non_empty(
            source.get("chapter_record_path"),
            payload.get("chapter_record_path"),
        ),
        "review_ledger_path": first_non_empty(
            source.get("review_ledger_path"),
            payload.get("review_ledger_path"),
        ),
        "scaffold_artifacts": scaffold_artifacts,
    }
    for key in ("issuer", "report_period", "run_manifest_path"):
        value = first_non_empty(source.get(key), payload.get(key))
        if value:
            normalized[key] = value
    return normalized


def normalize_review(payload: Dict[str, Any]) -> Dict[str, Any]:
    review = coerce_mapping(payload.get("review"))
    normalized = {
        "review_state": first_non_empty(review.get("review_state"), payload.get("review_state")),
        "reviewer": first_non_empty(review.get("reviewer"), payload.get("reviewer")),
        "reviewed_at": first_non_empty(review.get("reviewed_at"), payload.get("reviewed_at")),
        "summary": first_non_empty(review.get("summary"), payload.get("review_summary"), payload.get("summary")),
        "risk_level": first_non_empty(review.get("risk_level"), payload.get("risk_level")),
        "confidence": first_non_empty(review.get("confidence"), payload.get("confidence")),
    }
    decision = first_non_empty(review.get("decision"), payload.get("decision"))
    if decision:
        normalized["decision"] = decision
    return normalized


def normalize_operations(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [item for item in coerce_list(payload.get("operations")) if isinstance(item, dict)]


def normalize_evidence_refs(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [item for item in coerce_list(payload.get("evidence_refs")) if isinstance(item, dict)]


def normalize_hashes(payload: Dict[str, Any]) -> Dict[str, str]:
    hashes = coerce_mapping(payload.get("hashes"))
    return {
        "before_hash": first_non_empty(hashes.get("before_hash"), payload.get("before_hash")),
        "after_hash": first_non_empty(hashes.get("after_hash"), payload.get("after_hash")),
        "knowledge_base_version_before": first_non_empty(
            hashes.get("knowledge_base_version_before"),
            payload.get("knowledge_base_version_before"),
        ),
        "knowledge_base_version_after": first_non_empty(
            hashes.get("knowledge_base_version_after"),
            payload.get("knowledge_base_version_after"),
        ),
    }


def normalize_rollback(payload: Dict[str, Any]) -> Dict[str, Any]:
    rollback = coerce_mapping(payload.get("rollback"))
    normalized = {
        "enabled": bool(rollback.get("enabled", payload.get("rollback_enabled", True))),
        "backup_path": first_non_empty(rollback.get("backup_path"), payload.get("backup_path")),
        "rollback_log_path": first_non_empty(
            rollback.get("rollback_log_path"),
            payload.get("rollback_log_path"),
        ),
        "strategy": first_non_empty(
            rollback.get("strategy"),
            payload.get("rollback_strategy"),
            DEFAULT_ROLLBACK_STRATEGY,
        ),
    }
    return normalized


def normalize_audit(payload: Dict[str, Any]) -> Dict[str, str]:
    audit = coerce_mapping(payload.get("audit"))
    return {
        "adoption_id": first_non_empty(audit.get("adoption_id"), payload.get("adoption_id")),
        "logged_at": first_non_empty(audit.get("logged_at"), payload.get("logged_at")),
        "result": first_non_empty(audit.get("result"), payload.get("result")),
        "delta_path": first_non_empty(audit.get("delta_path"), payload.get("delta_path")),
        "knowledge_base_path": first_non_empty(
            audit.get("knowledge_base_path"),
            payload.get("knowledge_base_path"),
        ),
        "backup_path": first_non_empty(audit.get("backup_path"), payload.get("backup_path")),
        "summary": first_non_empty(audit.get("summary"), payload.get("summary")),
    }


def build_canonical_record(
    identity: Dict[str, str],
    source: Dict[str, Any],
    review: Dict[str, Any],
    operations: List[Dict[str, Any]],
    evidence_refs: List[Dict[str, Any]],
    hashes: Dict[str, str],
    rollback: Dict[str, Any],
    audit: Dict[str, str],
) -> Dict[str, Any]:
    return {
        "identity": identity,
        "source": source,
        "review": review,
        "operations": operations,
        "evidence_refs": evidence_refs,
        "hashes": hashes,
        "rollback": rollback,
        "audit": audit,
    }


def flatten_canonical_record(record: Dict[str, Any]) -> Dict[str, Any]:
    identity = coerce_mapping(record.get("identity"))
    hashes = coerce_mapping(record.get("hashes"))
    rollback = coerce_mapping(record.get("rollback"))
    audit = coerce_mapping(record.get("audit"))
    flattened = dict(record)
    flattened.update(
        {
            "adoption_id": identity.get("adoption_id", ""),
            "delta_version": identity.get("delta_version", ""),
            "logged_at": identity.get("logged_at", ""),
            "result": identity.get("result", ""),
            "before_hash": hashes.get("before_hash", ""),
            "after_hash": hashes.get("after_hash", ""),
            "knowledge_base_version_before": hashes.get("knowledge_base_version_before", ""),
            "knowledge_base_version_after": hashes.get("knowledge_base_version_after", ""),
            "delta_path": audit.get("delta_path", ""),
            "knowledge_base_path": audit.get("knowledge_base_path", ""),
            "backup_path": audit.get("backup_path", ""),
            "summary": audit.get("summary", ""),
            "rollback": rollback,
            "audit": audit,
            "hashes": hashes,
        }
    )
    return flattened
