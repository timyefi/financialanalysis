#!/usr/bin/env python3
"""
全局 processed reports registry。
"""

import hashlib
import json
import os
import re
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from runtime_support import (
    current_engine_version,
    detect_report_identity,
    load_knowledge_base_version,
    load_runtime_config,
    md5_file,
    now_iso,
    read_json,
    resolve_runtime_path,
    runtime_project_root,
)


SCHEMA_VERSION = "processed_reports_registry_v1"
LOCK_TIMEOUT_SECONDS = 30.0
LOCK_POLL_INTERVAL_SECONDS = 0.2


def parse_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows

    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            rows.append(json.loads(text))
    return rows


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_company_name(company_name: str) -> str:
    normalized = re.sub(r"\s+", "", str(company_name or "").strip()).lower()
    normalized = re.sub(r"[^\w\u4e00-\u9fff]+", "", normalized, flags=re.UNICODE)
    return normalized


def build_report_key(normalized_company_name: str, report_period: str, report_type: str) -> str:
    return sha256_text(f"{normalized_company_name}|{report_period}|{report_type}")


def build_document_fingerprint(md5_value: str, file_size: Any) -> str:
    return f"md5:{md5_value}|size:{file_size}"


def fingerprint_notes_workfile(raw_path: str) -> str:
    path = Path(str(raw_path)).resolve()
    if not path.exists():
        return f"missing:{path}"
    return f"sha256:{sha256_file(path)}"


def build_processing_fingerprint(
    report_key: str,
    document_fingerprint: str,
    engine_version: str,
    notes_workfile_fingerprint: str,
) -> str:
    return sha256_text(
        f"{report_key}|{document_fingerprint}|{engine_version}|{notes_workfile_fingerprint}"
    )


class ProcessedReportsRegistry:
    def __init__(
        self,
        runtime_config: Optional[Dict[str, Any]] = None,
        registry_path: Optional[Path] = None,
        enable_backfill: bool = True,
    ):
        self.runtime_config = runtime_config or load_runtime_config(
            cwd=Path.cwd(),
            require_knowledge_base=True,
            ensure_state_dirs=True,
        )
        self.registry_path = registry_path or resolve_runtime_path(
            self.runtime_config,
            "processed_reports_registry",
        )
        self.enable_backfill = enable_backfill
        self.lock_path = self.registry_path.with_suffix(".lock")
        self.initialization_info = {
            "backfill_performed": False,
            "warnings": [],
        }
        self.ensure_initialized()

    def ensure_initialized(self):
        if self.registry_path.exists():
            self.refresh()
            return

        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        with self._registry_lock():
            if self.registry_path.exists():
                self.refresh()
                return

            payload = self.empty_registry()
            warnings: List[str] = []
            if self.enable_backfill:
                warnings = self._backfill_payload(payload)
                payload["updated_at"] = now_iso()
            self._recompute_stats(payload)
            self._write_payload_atomic(payload)
            self.initialization_info = {
                "backfill_performed": self.enable_backfill,
                "warnings": warnings,
            }
        self.refresh()

    def refresh(self):
        payload = read_json(self.registry_path)
        schema_version = payload.get("schema_version", "")
        if schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"processed_reports registry schema 不匹配: expected={SCHEMA_VERSION}, actual={schema_version!r}"
            )
        self.payload = payload

    def empty_registry(self) -> Dict[str, Any]:
        timestamp = now_iso()
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at": timestamp,
            "updated_at": timestamp,
            "stats": {
                "report_count": 0,
                "document_version_count": 0,
                "attempt_count": 0,
                "success_attempt_count": 0,
                "failed_attempt_count": 0,
                "needs_rerun_count": 0,
            },
            "reports": {},
        }

    @contextmanager
    def _registry_lock(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        started_at = time.time()
        file_descriptor = None
        while True:
            try:
                file_descriptor = os.open(
                    str(self.lock_path),
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                )
                os.write(file_descriptor, str(os.getpid()).encode("utf-8"))
                break
            except FileExistsError:
                if time.time() - started_at >= LOCK_TIMEOUT_SECONDS:
                    raise TimeoutError(f"获取 processed_reports lock 超时: {self.lock_path}")
                time.sleep(LOCK_POLL_INTERVAL_SECONDS)

        try:
            yield
        finally:
            if file_descriptor is not None:
                os.close(file_descriptor)
            if self.lock_path.exists():
                self.lock_path.unlink()

    def _write_payload_atomic(self, payload: Dict[str, Any]):
        temp_path = self.registry_path.with_name(f"{self.registry_path.name}.tmp.{os.getpid()}")
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        temp_path.replace(self.registry_path)

    def _attempt_by_id(self, report_entry: Dict[str, Any], attempt_id: str) -> Optional[Dict[str, Any]]:
        for attempt in report_entry.get("attempts", []):
            if attempt.get("attempt_id") == attempt_id:
                return attempt
        return None

    def _ensure_report_entry(self, payload: Dict[str, Any], identity: Dict[str, str]) -> Dict[str, Any]:
        normalized_company_name = normalize_company_name(identity["company_name"])
        report_key = build_report_key(
            normalized_company_name,
            identity["report_period"],
            identity["report_type"],
        )
        report_entry = payload["reports"].get(report_key)
        if report_entry is None:
            report_entry = {
                "identity": {
                    "company_name": identity["company_name"],
                    "normalized_company_name": normalized_company_name,
                    "report_period": identity["report_period"],
                    "report_type": identity["report_type"],
                },
                "aliases": {
                    "issuer_names": [],
                    "task_ids": [],
                    "source_pdfs": [],
                },
                "document_versions": {},
                "attempts": [],
                "latest_attempt_id": "",
                "latest_success_attempt_id": "",
                "processing_state": {
                    "latest_status": "",
                    "latest_processed_at": "",
                    "latest_engine_version": "",
                    "latest_document_fingerprint": "",
                    "latest_success_engine_version": "",
                    "latest_success_document_fingerprint": "",
                    "needs_rerun": True,
                    "rerun_reasons": ["report_not_in_registry"],
                    "audit_flags": [],
                },
            }
            payload["reports"][report_key] = report_entry
        return report_entry

    def _update_aliases(
        self,
        report_entry: Dict[str, Any],
        *,
        issuer: str = "",
        task_id: str = "",
        source_pdf: str = "",
    ):
        alias_map = report_entry["aliases"]
        for key, value in [
            ("issuer_names", issuer),
            ("task_ids", task_id),
            ("source_pdfs", source_pdf),
        ]:
            if value and value not in alias_map[key]:
                alias_map[key].append(value)
                alias_map[key].sort()

    def _record_document_version(
        self,
        report_entry: Dict[str, Any],
        *,
        document_fingerprint: str,
        md5_value: str,
        file_size: Any,
        md_path: str,
        attempt_id: str,
        processed_at: str,
        status: str,
    ):
        document_versions = report_entry["document_versions"]
        version = document_versions.get(document_fingerprint)
        if version is None:
            version = {
                "document_fingerprint": document_fingerprint,
                "md5": md5_value,
                "file_size": file_size,
                "sample_md_path": md_path,
                "first_seen_at": processed_at,
                "last_seen_at": processed_at,
                "latest_attempt_id": attempt_id,
                "latest_success_attempt_id": "",
                "success_count": 0,
                "failed_count": 0,
            }
            document_versions[document_fingerprint] = version

        version["last_seen_at"] = processed_at
        version["latest_attempt_id"] = attempt_id
        version["sample_md_path"] = md_path or version.get("sample_md_path", "")
        if status == "success":
            version["latest_success_attempt_id"] = attempt_id
            version["success_count"] += 1
        else:
            version["failed_count"] += 1

    def _evaluate_report_entry(
        self,
        report_entry: Optional[Dict[str, Any]],
        *,
        current_document_fingerprint: str,
        current_engine_version_value: str,
        current_notes_workfile_fingerprint: str,
        current_knowledge_base_version: str,
    ) -> Dict[str, Any]:
        if report_entry is None:
            return {
                "needs_rerun": True,
                "rerun_reasons": ["report_not_in_registry"],
                "audit_flags": [],
                "latest_attempt_id": "",
                "latest_success_attempt_id": "",
                "skip_allowed": False,
            }

        latest_attempt = self._attempt_by_id(report_entry, report_entry.get("latest_attempt_id", ""))
        latest_success = self._attempt_by_id(report_entry, report_entry.get("latest_success_attempt_id", ""))
        rerun_reasons: List[str] = []
        audit_flags: List[str] = []

        if latest_success is None:
            rerun_reasons.append("no_successful_attempt")

        if latest_attempt and latest_attempt.get("status") == "failed":
            if latest_success is None or latest_attempt.get("attempt_id") != latest_success.get("attempt_id"):
                rerun_reasons.append("latest_attempt_failed")

        if latest_success:
            if latest_success.get("document_fingerprint") != current_document_fingerprint:
                rerun_reasons.append("document_fingerprint_changed")
            if latest_success.get("engine_version") != current_engine_version_value:
                rerun_reasons.append("engine_version_changed")

            success_notes = (latest_success.get("notes_workfile") or {}).get("fingerprint", "")
            if success_notes and success_notes != current_notes_workfile_fingerprint:
                audit_flags.append("notes_workfile_changed")

            success_knowledge_version = str(latest_success.get("knowledge_base_version", ""))
            if (
                success_knowledge_version
                and current_knowledge_base_version
                and success_knowledge_version != current_knowledge_base_version
            ):
                audit_flags.append("knowledge_base_version_changed")

        rerun_reasons = sorted(set(rerun_reasons))
        audit_flags = sorted(set(audit_flags))
        return {
            "needs_rerun": bool(rerun_reasons),
            "rerun_reasons": rerun_reasons,
            "audit_flags": audit_flags,
            "latest_attempt_id": report_entry.get("latest_attempt_id", ""),
            "latest_success_attempt_id": report_entry.get("latest_success_attempt_id", ""),
            "skip_allowed": latest_success is not None and not rerun_reasons,
        }

    def _update_processing_state(
        self,
        report_entry: Dict[str, Any],
        *,
        current_document_fingerprint: str,
        current_engine_version_value: str,
        current_notes_workfile_fingerprint: str,
        current_knowledge_base_version: str,
    ):
        latest_attempt = self._attempt_by_id(report_entry, report_entry.get("latest_attempt_id", ""))
        latest_success = self._attempt_by_id(report_entry, report_entry.get("latest_success_attempt_id", ""))
        evaluation = self._evaluate_report_entry(
            report_entry,
            current_document_fingerprint=current_document_fingerprint,
            current_engine_version_value=current_engine_version_value,
            current_notes_workfile_fingerprint=current_notes_workfile_fingerprint,
            current_knowledge_base_version=current_knowledge_base_version,
        )
        report_entry["processing_state"] = {
            "latest_status": (latest_attempt or {}).get("status", ""),
            "latest_processed_at": (latest_attempt or {}).get("processed_at", ""),
            "latest_engine_version": (latest_attempt or {}).get("engine_version", ""),
            "latest_document_fingerprint": (latest_attempt or {}).get("document_fingerprint", ""),
            "latest_success_engine_version": (latest_success or {}).get("engine_version", ""),
            "latest_success_document_fingerprint": (latest_success or {}).get("document_fingerprint", ""),
            "needs_rerun": evaluation["needs_rerun"],
            "rerun_reasons": evaluation["rerun_reasons"],
            "audit_flags": evaluation["audit_flags"],
        }

    def _recompute_stats(self, payload: Dict[str, Any]):
        report_count = len(payload["reports"])
        document_version_count = 0
        attempt_count = 0
        success_attempt_count = 0
        failed_attempt_count = 0
        needs_rerun_count = 0

        for report_entry in payload["reports"].values():
            document_version_count += len(report_entry.get("document_versions", {}))
            attempts = report_entry.get("attempts", [])
            attempt_count += len(attempts)
            success_attempt_count += sum(1 for item in attempts if item.get("status") == "success")
            failed_attempt_count += sum(1 for item in attempts if item.get("status") == "failed")
            if (report_entry.get("processing_state") or {}).get("needs_rerun"):
                needs_rerun_count += 1

        payload["stats"] = {
            "report_count": report_count,
            "document_version_count": document_version_count,
            "attempt_count": attempt_count,
            "success_attempt_count": success_attempt_count,
            "failed_attempt_count": failed_attempt_count,
            "needs_rerun_count": needs_rerun_count,
        }

    def _upsert_attempt(
        self,
        payload: Dict[str, Any],
        *,
        identity: Dict[str, str],
        issuer: str,
        task_id: str,
        source_pdf: str,
        md_path: str,
        md5_value: str,
        file_size: Any,
        notes_workfile_path: str,
        status: str,
        failure_reason: str,
        engine_version_value: str,
        knowledge_base_version: str,
        notes_locator_status: str,
        artifacts: Dict[str, Any],
        source_ref: Dict[str, Any],
        processed_at: str,
    ) -> Dict[str, Any]:
        report_entry = self._ensure_report_entry(payload, identity)
        normalized_company_name = report_entry["identity"]["normalized_company_name"]
        report_key = build_report_key(
            normalized_company_name,
            report_entry["identity"]["report_period"],
            report_entry["identity"]["report_type"],
        )
        document_fingerprint = build_document_fingerprint(md5_value, file_size)
        notes_workfile_fingerprint = fingerprint_notes_workfile(notes_workfile_path)
        processing_fingerprint = build_processing_fingerprint(
            report_key,
            document_fingerprint,
            engine_version_value,
            notes_workfile_fingerprint,
        )

        manifest_path = str(source_ref.get("manifest_path", ""))
        run_dir = str(source_ref.get("run_dir", ""))
        for existing in report_entry.get("attempts", []):
            existing_source = existing.get("source_ref") or {}
            if (
                existing.get("processing_fingerprint") == processing_fingerprint
                and str(existing_source.get("manifest_path", "")) == manifest_path
                and str(existing_source.get("run_dir", "")) == run_dir
            ):
                self._update_aliases(report_entry, issuer=issuer, task_id=task_id, source_pdf=source_pdf)
                self._update_processing_state(
                    report_entry,
                    current_document_fingerprint=document_fingerprint,
                    current_engine_version_value=engine_version_value,
                    current_notes_workfile_fingerprint=notes_workfile_fingerprint,
                    current_knowledge_base_version=knowledge_base_version,
                )
                return {
                    "report_key": report_key,
                    "document_fingerprint": document_fingerprint,
                    "processing_fingerprint": processing_fingerprint,
                    "attempt_id": existing.get("attempt_id", ""),
                    "registered": True,
                    "deduplicated": True,
                    "evaluation": self._evaluate_report_entry(
                        report_entry,
                        current_document_fingerprint=document_fingerprint,
                        current_engine_version_value=engine_version_value,
                        current_notes_workfile_fingerprint=notes_workfile_fingerprint,
                        current_knowledge_base_version=knowledge_base_version,
                    ),
                }

        attempt_id = sha256_text(
            "|".join(
                [
                    processing_fingerprint,
                    manifest_path,
                    run_dir,
                    processed_at,
                    status,
                    failure_reason,
                ]
            )
        )
        attempt = {
            "attempt_id": attempt_id,
            "processed_at": processed_at,
            "status": status,
            "failure_reason": failure_reason,
            "engine_version": engine_version_value,
            "knowledge_base_version": knowledge_base_version,
            "document_fingerprint": document_fingerprint,
            "processing_fingerprint": processing_fingerprint,
            "notes_locator_status": notes_locator_status,
            "notes_workfile": {
                "path": notes_workfile_path,
                "fingerprint": notes_workfile_fingerprint,
            },
            "artifacts": artifacts,
            "source_ref": source_ref,
        }
        report_entry["attempts"].append(attempt)
        report_entry["latest_attempt_id"] = attempt_id
        if status == "success":
            report_entry["latest_success_attempt_id"] = attempt_id

        self._update_aliases(report_entry, issuer=issuer, task_id=task_id, source_pdf=source_pdf)
        self._record_document_version(
            report_entry,
            document_fingerprint=document_fingerprint,
            md5_value=md5_value,
            file_size=file_size,
            md_path=md_path,
            attempt_id=attempt_id,
            processed_at=processed_at,
            status=status,
        )
        self._update_processing_state(
            report_entry,
            current_document_fingerprint=document_fingerprint,
            current_engine_version_value=engine_version_value,
            current_notes_workfile_fingerprint=notes_workfile_fingerprint,
            current_knowledge_base_version=knowledge_base_version,
        )
        return {
            "report_key": report_key,
            "document_fingerprint": document_fingerprint,
            "processing_fingerprint": processing_fingerprint,
            "attempt_id": attempt_id,
            "registered": True,
            "deduplicated": False,
            "evaluation": self._evaluate_report_entry(
                report_entry,
                current_document_fingerprint=document_fingerprint,
                current_engine_version_value=engine_version_value,
                current_notes_workfile_fingerprint=notes_workfile_fingerprint,
                current_knowledge_base_version=knowledge_base_version,
            ),
        }

    def prepare_task_context(
        self,
        task: Dict[str, Any],
        *,
        target_engine_version: Optional[str] = None,
        knowledge_base_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        self.refresh()
        md_path = Path(task["md_path"])
        if not md_path.exists():
            return {
                "available": False,
                "report_key": "",
                "document_fingerprint": "",
                "processing_fingerprint": "",
                "needs_rerun": True,
                "rerun_reasons": ["md_path_not_found"],
                "audit_flags": [],
                "skip_allowed": False,
            }

        identity = detect_report_identity(md_path)
        normalized_company_name = normalize_company_name(identity["company_name"])
        report_key = build_report_key(
            normalized_company_name,
            identity["report_period"],
            identity["report_type"],
        )
        md5_value = md5_file(md_path)
        file_size = md_path.stat().st_size
        document_fingerprint = build_document_fingerprint(md5_value, file_size)
        notes_workfile_fingerprint = fingerprint_notes_workfile(str(task["notes_workfile"]))
        effective_engine_version = target_engine_version or current_engine_version()
        effective_knowledge_base_version = knowledge_base_version
        if effective_knowledge_base_version is None:
            effective_knowledge_base_version = load_knowledge_base_version(self.runtime_config)
        report_entry = self.payload.get("reports", {}).get(report_key)
        evaluation = self._evaluate_report_entry(
            report_entry,
            current_document_fingerprint=document_fingerprint,
            current_engine_version_value=effective_engine_version,
            current_notes_workfile_fingerprint=notes_workfile_fingerprint,
            current_knowledge_base_version=effective_knowledge_base_version,
        )
        return {
            "available": True,
            "identity": identity,
            "report_key": report_key,
            "document_md5": md5_value,
            "document_file_size": file_size,
            "document_fingerprint": document_fingerprint,
            "notes_workfile_fingerprint": notes_workfile_fingerprint,
            "processing_fingerprint": build_processing_fingerprint(
                report_key,
                document_fingerprint,
                effective_engine_version,
                notes_workfile_fingerprint,
            ),
            "needs_rerun": evaluation["needs_rerun"],
            "rerun_reasons": evaluation["rerun_reasons"],
            "audit_flags": evaluation["audit_flags"],
            "skip_allowed": evaluation["skip_allowed"],
            "latest_attempt_id": evaluation["latest_attempt_id"],
            "latest_success_attempt_id": evaluation["latest_success_attempt_id"],
        }

    def record_batch_task_result(
        self,
        *,
        task: Dict[str, Any],
        result: Dict[str, Any],
        registry_context: Dict[str, Any],
        batch_name: str,
        batch_run_dir: Path,
        task_results_path: Path,
        batch_manifest_path: Path,
        knowledge_base_version: str,
    ) -> Dict[str, Any]:
        manifest_path_text = str(result.get("manifest_path", ""))
        manifest = None
        if manifest_path_text:
            manifest_path = Path(manifest_path_text).resolve()
            if manifest_path.exists():
                manifest = read_json(manifest_path)

        if manifest is None and not registry_context.get("available"):
            return {
                "registered": False,
                "report_key": "",
                "document_fingerprint": "",
                "processing_fingerprint": "",
                "needs_rerun": True,
                "rerun_reasons": ["registry_context_unavailable"],
                "audit_flags": [],
            }

        if manifest:
            input_info = manifest.get("input") or {}
            entity = manifest.get("entity") or {}
            identity = {
                "company_name": str(entity.get("company_name", task.get("issuer", ""))),
                "report_period": str(entity.get("report_period", task.get("year", ""))),
                "report_type": str(entity.get("report_type", "")),
            }
            md_path = str(input_info.get("md_path", task["md_path"]))
            md5_value = str(input_info.get("md5", registry_context.get("document_md5", "")))
            file_size = input_info.get("file_size", registry_context.get("document_file_size", 0))
            notes_workfile_path = str(input_info.get("notes_workfile", task["notes_workfile"]))
            status = str(manifest.get("status", result.get("status", "failed")))
            failure_reason = str(manifest.get("failure_reason", result.get("failure_reason", "")))
            engine_version_value = str(manifest.get("engine_version", result.get("engine_version", "")))
            notes_locator_status = str((manifest.get("notes_locator") or {}).get("status", result.get("notes_locator_status", "")))
            artifacts = dict(manifest.get("artifacts") or {})
            processed_at = str(manifest.get("generated_at", result.get("completed_at", now_iso())))
        else:
            identity = dict(registry_context["identity"])
            md_path = str(task["md_path"])
            md5_value = str(registry_context["document_md5"])
            file_size = registry_context["document_file_size"]
            notes_workfile_path = str(task["notes_workfile"])
            status = str(result.get("status", "failed"))
            failure_reason = str(result.get("failure_reason", ""))
            engine_version_value = current_engine_version()
            notes_locator_status = str(result.get("notes_locator_status", ""))
            artifacts = {
                "run_manifest": manifest_path_text,
                "analysis_report": "",
                "financial_output": "",
                "pending_updates": str(result.get("pending_updates_path", "")),
            }
            processed_at = str(result.get("completed_at", now_iso()))

        source_ref = {
            "source_kind": "batch_task",
            "batch_name": batch_name,
            "batch_run_dir": str(batch_run_dir),
            "batch_manifest_path": str(batch_manifest_path),
            "task_results_path": str(task_results_path),
            "task_id": str(task["task_id"]),
            "run_dir": str(task["run_dir"]),
            "manifest_path": manifest_path_text,
            "completed_at": str(result.get("completed_at", processed_at)),
        }

        with self._registry_lock():
            payload = read_json(self.registry_path) if self.registry_path.exists() else self.empty_registry()
            update = self._upsert_attempt(
                payload,
                identity=identity,
                issuer=str(task.get("issuer", "")),
                task_id=str(task.get("task_id", "")),
                source_pdf=str(task.get("source_pdf", "")),
                md_path=md_path,
                md5_value=md5_value,
                file_size=file_size,
                notes_workfile_path=notes_workfile_path,
                status=status,
                failure_reason=failure_reason,
                engine_version_value=engine_version_value,
                knowledge_base_version=knowledge_base_version,
                notes_locator_status=notes_locator_status,
                artifacts=artifacts,
                source_ref=source_ref,
                processed_at=processed_at,
            )
            payload["updated_at"] = now_iso()
            self._recompute_stats(payload)
            self._write_payload_atomic(payload)

        self.refresh()
        return {
            "registered": update["registered"],
            "report_key": update["report_key"],
            "document_fingerprint": update["document_fingerprint"],
            "processing_fingerprint": update["processing_fingerprint"],
            "attempt_id": update["attempt_id"],
            "deduplicated": update["deduplicated"],
            "needs_rerun": update["evaluation"]["needs_rerun"],
            "rerun_reasons": update["evaluation"]["rerun_reasons"],
            "audit_flags": update["evaluation"]["audit_flags"],
        }

    def _record_legacy_manifest(
        self,
        payload: Dict[str, Any],
        *,
        manifest_path: Path,
        source_ref: Dict[str, Any],
        task_id: str,
        issuer: str,
        source_pdf: str,
        knowledge_base_version: str,
    ):
        manifest = read_json(manifest_path)
        input_info = manifest.get("input") or {}
        entity = manifest.get("entity") or {}
        identity = {
            "company_name": str(entity.get("company_name", issuer)),
            "report_period": str(entity.get("report_period", "")),
            "report_type": str(entity.get("report_type", "")),
        }
        self._upsert_attempt(
            payload,
            identity=identity,
            issuer=issuer,
            task_id=task_id,
            source_pdf=source_pdf,
            md_path=str(input_info.get("md_path", "")),
            md5_value=str(input_info.get("md5", "")),
            file_size=input_info.get("file_size", 0),
            notes_workfile_path=str(input_info.get("notes_workfile", "")),
            status=str(manifest.get("status", "failed")),
            failure_reason=str(manifest.get("failure_reason", "")),
            engine_version_value=str(manifest.get("engine_version", "")),
            knowledge_base_version=knowledge_base_version,
            notes_locator_status=str((manifest.get("notes_locator") or {}).get("status", "")),
            artifacts=dict(manifest.get("artifacts") or {}),
            source_ref=source_ref,
            processed_at=str(manifest.get("generated_at", now_iso())),
        )

    def _backfill_payload(self, payload: Dict[str, Any]) -> List[str]:
        warnings: List[str] = []
        knowledge_base_version = load_knowledge_base_version(self.runtime_config)
        project_root = runtime_project_root(self.runtime_config)
        test_runs_root = project_root / "financial-analyzer" / "test_runs"

        for run_dir in sorted(test_runs_root.glob("w6_*")):
            manifest_path = run_dir / "run_manifest.json"
            if not manifest_path.exists():
                continue
            self._record_legacy_manifest(
                payload,
                manifest_path=manifest_path,
                source_ref={
                    "source_kind": "legacy_single_run",
                    "batch_name": "",
                    "batch_run_dir": "",
                    "batch_manifest_path": "",
                    "task_results_path": "",
                    "task_id": run_dir.name,
                    "run_dir": str(run_dir.resolve()),
                    "manifest_path": str(manifest_path.resolve()),
                    "completed_at": str(read_json(manifest_path).get("generated_at", "")),
                },
                task_id=run_dir.name,
                issuer="",
                source_pdf="",
                knowledge_base_version=knowledge_base_version,
            )

        batch_root = test_runs_root / "batches"
        if batch_root.exists():
            for batch_dir in sorted(path for path in batch_root.iterdir() if path.is_dir()):
                task_results_path = batch_dir / "task_results.jsonl"
                batch_manifest_path = batch_dir / "batch_manifest.json"
                if not task_results_path.exists():
                    warnings.append(f"W7 batch 缺少 task_results.jsonl，跳过回填: {batch_dir}")
                    continue

                for row in parse_jsonl(task_results_path):
                    manifest_path_text = str(row.get("manifest_path", "")).strip()
                    if not manifest_path_text:
                        continue
                    manifest_path = Path(manifest_path_text).resolve()
                    if not manifest_path.exists():
                        warnings.append(f"W7 batch manifest 不存在，跳过回填: {manifest_path}")
                        continue
                    self._record_legacy_manifest(
                        payload,
                        manifest_path=manifest_path,
                        source_ref={
                            "source_kind": "batch_task",
                            "batch_name": str((read_json(batch_manifest_path).get("batch_name", batch_dir.name)) if batch_manifest_path.exists() else batch_dir.name),
                            "batch_run_dir": str(batch_dir.resolve()),
                            "batch_manifest_path": str(batch_manifest_path.resolve()),
                            "task_results_path": str(task_results_path.resolve()),
                            "task_id": str(row.get("task_id", "")),
                            "run_dir": str(row.get("run_dir", "")),
                            "manifest_path": str(manifest_path),
                            "completed_at": str(row.get("completed_at", "")),
                        },
                        task_id=str(row.get("task_id", "")),
                        issuer=str(row.get("issuer", "")),
                        source_pdf=str(row.get("source_pdf", "")),
                        knowledge_base_version=knowledge_base_version,
                    )
        elif (test_runs_root / "w7_batch_regression_results.json").exists():
            warnings.append("检测到 w7_batch_regression_results.json，但 financial-analyzer/test_runs/batches/ 不存在，已跳过 W7 回填。")

        for warning in warnings:
            print(f"[WARN] {warning}")
        return warnings

    def registry_summary(
        self,
        *,
        knowledge_base_version: str,
        engine_version_value: str,
    ) -> Dict[str, Any]:
        self.refresh()
        return {
            "registry_path": str(self.registry_path),
            "schema_version": self.payload["schema_version"],
            "updated_at": self.payload["updated_at"],
            "stats": self.payload["stats"],
            "knowledge_base_version": knowledge_base_version,
            "engine_version": engine_version_value,
            "backfill_performed_on_init": self.initialization_info["backfill_performed"],
            "init_warnings": self.initialization_info["warnings"],
        }
