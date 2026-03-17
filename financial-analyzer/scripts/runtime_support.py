#!/usr/bin/env python3
"""
运行时配置与批处理共享元数据辅助模块。
"""

import datetime
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


SKILL_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_CONFIG_ENV_VAR = "FINANCIAL_ANALYZER_RUNTIME_CONFIG"
RUNTIME_CONFIG_FILENAME = "runtime_config.json"
RUNTIME_CONFIG_CONTRACT_VERSION = "runtime_config_v1"
REQUIRED_RUNTIME_PATH_KEYS = [
    "knowledge_base",
    "knowledge_adoption_log_dir",
    "processed_reports_registry",
    "batch_root",
    "governance_review_root",
    "logs_root",
    "tmp_root",
]
RUNTIME_STATE_DIRECTORY_KEYS = [
    "knowledge_adoption_log_dir",
    "batch_root",
    "governance_review_root",
    "logs_root",
    "tmp_root",
]
RUNTIME_STATE_FILE_KEYS = [
    "processed_reports_registry",
]


class RuntimeConfigError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def read_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def resolve_input_path(raw_path: Path, cwd: Optional[Path] = None) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path.resolve()
    base_dir = (cwd or Path.cwd()).resolve()
    return (base_dir / path).resolve()


def ensure_path_under_root(path: Path, root: Path, label: str):
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise RuntimeConfigError(f"{label} 超出 project_root: {path}") from exc


def runtime_config_search_candidates(cwd: Optional[Path] = None) -> List[Path]:
    search_root = (cwd or Path.cwd()).resolve()
    candidates: List[Path] = []
    current = search_root
    while True:
        candidates.append((current / "runtime" / RUNTIME_CONFIG_FILENAME).resolve())
        if current.parent == current:
            break
        current = current.parent
    return candidates


def discover_runtime_config_path(
    config_path: Optional[Path] = None,
    cwd: Optional[Path] = None,
) -> Tuple[Optional[Path], List[Tuple[str, Path]], str]:
    checked_paths: List[Tuple[str, Path]] = []
    if config_path is not None:
        candidate = resolve_input_path(config_path, cwd=cwd)
        checked_paths.append(("cli_arg", candidate))
        if candidate.exists():
            return candidate, checked_paths, "cli_arg"
        return None, checked_paths, "cli_arg"

    env_value = os.environ.get(RUNTIME_CONFIG_ENV_VAR, "").strip()
    if env_value:
        candidate = resolve_input_path(Path(env_value), cwd=cwd)
        checked_paths.append((RUNTIME_CONFIG_ENV_VAR, candidate))
        if candidate.exists():
            return candidate, checked_paths, RUNTIME_CONFIG_ENV_VAR
        return None, checked_paths, RUNTIME_CONFIG_ENV_VAR

    for candidate in runtime_config_search_candidates(cwd=cwd):
        checked_paths.append(("cwd_search", candidate))
        if candidate.exists():
            return candidate, checked_paths, "cwd_search"
    return None, checked_paths, "cwd_search"


def format_checked_paths(checked_paths: List[Tuple[str, Path]]) -> str:
    return "\n".join(f"- {label}: {path}" for label, path in checked_paths)


def _load_runtime_config_json(candidate: Path) -> Dict[str, Any]:
    try:
        return read_json(candidate)
    except json.JSONDecodeError as exc:
        raise RuntimeConfigError(f"runtime_config.json 不是合法 JSON: {candidate}") from exc


def runtime_config_path(runtime_config: Dict[str, Any]) -> Path:
    config_path = runtime_config.get("_config_path")
    if not config_path:
        raise RuntimeConfigError("runtime_config 缺少 _config_path 元数据")
    return Path(str(config_path)).resolve()


def runtime_project_root(runtime_config: Dict[str, Any]) -> Path:
    return Path(str(runtime_config["project_root"])).resolve()


def resolve_runtime_path(runtime_config: Dict[str, Any], key: str) -> Path:
    project_root = runtime_project_root(runtime_config)
    raw_value = runtime_config["paths"][key]
    configured_path = Path(str(raw_value))
    if configured_path.is_absolute():
        resolved = configured_path.resolve()
    else:
        resolved = (project_root / configured_path).resolve()
    if runtime_config.get("policies", {}).get("require_paths_under_project_root", False):
        ensure_path_under_root(resolved, project_root, f"runtime.paths.{key}")
    if runtime_config.get("policies", {}).get("forbid_skill_dir_writes", False):
        try:
            resolved.relative_to(SKILL_ROOT)
        except ValueError:
            pass
        else:
            raise RuntimeConfigError(f"runtime.paths.{key} 不得落在 skill 目录内: {resolved}")
    return resolved


def validate_runtime_config(runtime_config: Dict[str, Any]):
    contract_version = str(runtime_config.get("contract_version", ""))
    if contract_version != RUNTIME_CONFIG_CONTRACT_VERSION:
        raise RuntimeConfigError(
            f"runtime_config contract_version 不匹配: expected={RUNTIME_CONFIG_CONTRACT_VERSION}, actual={contract_version!r}"
        )

    config_path = runtime_config_path(runtime_config)
    project_root = runtime_project_root(runtime_config)
    runtime_root = Path(str(runtime_config.get("runtime_root", ""))).resolve()
    if not project_root.is_absolute():
        raise RuntimeConfigError(f"project_root 必须是绝对路径: {project_root}")
    if not runtime_root.is_absolute():
        raise RuntimeConfigError(f"runtime_root 必须是绝对路径: {runtime_root}")
    if config_path.name != RUNTIME_CONFIG_FILENAME:
        raise RuntimeConfigError(f"runtime_config 文件名必须为 {RUNTIME_CONFIG_FILENAME}: {config_path}")
    if config_path.parent != runtime_root:
        raise RuntimeConfigError(
            f"runtime_config 路径与 runtime_root 不一致: config={config_path}, runtime_root={runtime_root}"
        )

    if runtime_config.get("policies", {}).get("require_paths_under_project_root", False):
        ensure_path_under_root(runtime_root, project_root, "runtime_root")

    paths = runtime_config.get("paths")
    if not isinstance(paths, dict):
        raise RuntimeConfigError("runtime_config.paths 必须是对象")
    for key in REQUIRED_RUNTIME_PATH_KEYS:
        value = paths.get(key)
        if not isinstance(value, str) or not value.strip():
            raise RuntimeConfigError(f"runtime_config.paths.{key} 缺失或为空")
        resolve_runtime_path(runtime_config, key)


def ensure_runtime_layout(runtime_config: Dict[str, Any], require_knowledge_base: bool = True):
    runtime_root = Path(str(runtime_config.get("runtime_root", ""))).resolve()
    runtime_root.mkdir(parents=True, exist_ok=True)

    knowledge_base_path = resolve_runtime_path(runtime_config, "knowledge_base")
    if require_knowledge_base and not knowledge_base_path.exists():
        raise RuntimeConfigError(f"正式 knowledge_base 不存在: {knowledge_base_path}")
    knowledge_base_path.parent.mkdir(parents=True, exist_ok=True)

    for key in RUNTIME_STATE_DIRECTORY_KEYS:
        resolve_runtime_path(runtime_config, key).mkdir(parents=True, exist_ok=True)
    for key in RUNTIME_STATE_FILE_KEYS:
        resolve_runtime_path(runtime_config, key).parent.mkdir(parents=True, exist_ok=True)


def load_runtime_config(
    config_path: Optional[Path] = None,
    *,
    cwd: Optional[Path] = None,
    require_knowledge_base: bool = False,
    ensure_state_dirs: bool = False,
) -> Dict[str, Any]:
    candidate, checked_paths, discovery_source = discover_runtime_config_path(config_path=config_path, cwd=cwd)
    if candidate is None:
        checked_text = format_checked_paths(checked_paths)
        raise RuntimeConfigError(
            "未找到 runtime_config.json。\n"
            f"已检查路径:\n{checked_text}\n"
            f"修复方式: 传 --runtime-config，或设置 {RUNTIME_CONFIG_ENV_VAR}，或在项目目录内运行。"
        )

    payload = _load_runtime_config_json(candidate)
    payload["_config_path"] = str(candidate)
    payload["_discovery_source"] = discovery_source
    payload["_checked_paths"] = [
        {"source": label, "path": str(path)}
        for label, path in checked_paths
    ]
    validate_runtime_config(payload)
    if require_knowledge_base or ensure_state_dirs:
        ensure_runtime_layout(payload, require_knowledge_base=require_knowledge_base)
    return payload


def try_load_runtime_config(
    config_path: Optional[Path] = None,
    *,
    cwd: Optional[Path] = None,
    require_knowledge_base: bool = False,
    ensure_state_dirs: bool = False,
) -> Optional[Dict[str, Any]]:
    try:
        return load_runtime_config(
            config_path=config_path,
            cwd=cwd,
            require_knowledge_base=require_knowledge_base,
            ensure_state_dirs=ensure_state_dirs,
        )
    except RuntimeConfigError:
        return None


def load_knowledge_base_version(runtime_config: Optional[Dict[str, Any]]) -> str:
    if runtime_config is None:
        return ""

    knowledge_base_path = resolve_runtime_path(runtime_config, "knowledge_base")
    if not knowledge_base_path.exists():
        return ""

    payload = read_json(knowledge_base_path)
    metadata = payload.get("metadata") or {}
    return str(metadata.get("version", ""))


def current_engine_version() -> str:
    from financial_analyzer import ENGINE_VERSION

    return str(ENGINE_VERSION)


def detect_report_identity(md_path: Path) -> Dict[str, str]:
    from financial_analyzer import (
        classify_report,
        extract_company_name,
        extract_report_period,
        normalize_text,
    )

    raw_text = normalize_text(read_text(md_path))
    company_name = extract_company_name(raw_text, md_path.stem)
    report_period = extract_report_period(raw_text, md_path.stem)
    classification = classify_report(raw_text, md_path)
    return {
        "company_name": company_name,
        "report_period": report_period,
        "report_type": str(classification.get("report_type", "")),
        "audit_opinion": str(classification.get("audit_opinion", "")),
    }


def md5_file(path: Path) -> str:
    from financial_analyzer import md5_file as analyzer_md5_file

    return str(analyzer_md5_file(path))
