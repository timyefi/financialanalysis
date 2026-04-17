#!/usr/bin/env python3
"""
BondClaw 资产加载器与最小校验入口。

这个模块不负责业务实现，只负责把 contracts / provider-registry /
prompt-library / research-brain / lead-capture 这些骨架文件读进来，
并给后续桌面壳、适配器和自动化脚本提供统一访问层。
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import bondclaw_research_brain
import bondclaw_lead_capture


ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = ROOT.parent
CONTRACTS_DIR = ROOT / "contracts"
PROVIDER_REGISTRY_DIR = ROOT / "provider-registry"
PROMPT_LIBRARY_DIR = ROOT / "prompt-library"
RESEARCH_BRAIN_DIR = ROOT / "research-brain"
LEAD_CAPTURE_DIR = ROOT / "lead-capture"
PROMPT_PACKS_DIR = PROMPT_LIBRARY_DIR / "packs"


class BondClawAssetError(RuntimeError):
    pass


@dataclass(frozen=True)
class PromptPackSummary:
    role: str
    display_name: str
    canonical_skill: str
    workflow_count: int
    sample_count: int


@dataclass(frozen=True)
class ProviderSummary:
    provider_id: str
    display_name: str
    plan_kind: str
    protocol: str
    base_url_count: int
    model_count: int


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise BondClawAssetError(f"JSON 顶层必须是对象: {path}")
    return payload


def read_text(path: Path) -> str:
    with path.open("r", encoding="utf-8") as handle:
        return handle.read()


def iter_json_files(directory: Path) -> Iterable[Path]:
    if not directory.exists():
        return []
    return sorted(path for path in directory.rglob("*.json") if path.is_file())


def load_branding_config() -> Dict[str, Any]:
    return read_json(CONTRACTS_DIR / "branding-config.example.json")


def load_execution_shell_config() -> Dict[str, Any]:
    return read_json(CONTRACTS_DIR / "execution-shell.example.json")


def load_provider_registry() -> Dict[str, Any]:
    registry = read_json(PROVIDER_REGISTRY_DIR / "coding-plan.providers.json")
    providers = registry.get("providers")
    if not isinstance(providers, list):
        raise BondClawAssetError("provider registry.providers 必须是数组")
    return registry


def load_providers() -> List[Dict[str, Any]]:
    return list(load_provider_registry().get("providers", []))


def load_official_sources() -> str:
    return read_text(PROVIDER_REGISTRY_DIR / "official-sources.md")


def load_prompt_template() -> Dict[str, Any]:
    return read_json(PROMPT_LIBRARY_DIR / "prompt-pack.template.json")


def load_prompt_pack_summary() -> List[PromptPackSummary]:
    summaries: List[PromptPackSummary] = []
    if not PROMPT_PACKS_DIR.exists():
        return summaries
    for role_dir in sorted(path for path in PROMPT_PACKS_DIR.iterdir() if path.is_dir()):
        manifest_path = role_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        manifest = read_json(manifest_path)
        workflows = manifest.get("workflows") or []
        summary = PromptPackSummary(
            role=str(manifest.get("role", role_dir.name)),
            display_name=str(manifest.get("display_name", role_dir.name)),
            canonical_skill=str(manifest.get("canonical_skill", "")),
            workflow_count=len(workflows) if isinstance(workflows, list) else 0,
            sample_count=len([path for path in role_dir.glob("*.json") if path.name != "manifest.json"]),
        )
        summaries.append(summary)
    return summaries


def load_prompt_pack_manifest(role: str) -> Dict[str, Any]:
    manifest_path = PROMPT_PACKS_DIR / role / "manifest.json"
    if not manifest_path.exists():
        raise BondClawAssetError(f"缺少 prompt pack manifest: {role}")
    return read_json(manifest_path)


def load_prompt_pack(role: str, prompt_name: str) -> Dict[str, Any]:
    prompt_path = PROMPT_PACKS_DIR / role / f"{prompt_name}.json"
    if not prompt_path.exists():
        raise BondClawAssetError(f"缺少 prompt pack: {role}/{prompt_name}")
    return read_json(prompt_path)


def load_provider_summary() -> List[ProviderSummary]:
    summaries: List[ProviderSummary] = []
    for provider in load_providers():
        base_urls = provider.get("base_urls") or {}
        models = provider.get("models") or []
        summaries.append(
            ProviderSummary(
                provider_id=str(provider.get("id", "")),
                display_name=str(provider.get("display_name", provider.get("id", ""))),
                plan_kind=str(provider.get("plan_kind", "")),
                protocol=str(provider.get("protocol", "")),
                base_url_count=len(base_urls) if isinstance(base_urls, dict) else 0,
                model_count=len(models) if isinstance(models, list) else 0,
            )
        )
    return summaries


def load_research_brain_manifest() -> Dict[str, Any]:
    return bondclaw_research_brain.load_manifest()


def load_research_brain_sources() -> Dict[str, Any]:
    return bondclaw_research_brain.load_feed_sources()


def load_research_brain_case_index() -> Dict[str, Any]:
    return bondclaw_research_brain.load_case_index()


def list_role_ids() -> List[str]:
    if not PROMPT_PACKS_DIR.exists():
        return []
    return sorted(role_dir.name for role_dir in PROMPT_PACKS_DIR.iterdir() if role_dir.is_dir())


def list_prompt_pack_names(role: Optional[str] = None) -> List[str]:
    if role is None:
        names: List[str] = []
        for role_id in list_role_ids():
            names.extend(list_prompt_pack_names(role=role_id))
        return sorted(names)
    role_dir = PROMPT_PACKS_DIR / role
    if not role_dir.exists():
        return []
    return sorted(
        prompt_path.stem
        for prompt_path in role_dir.glob("*.json")
        if prompt_path.name != "manifest.json"
    )


def load_lead_capture_policy() -> str:
    return read_text(LEAD_CAPTURE_DIR / "lead-capture.policy.md")


def load_lead_capture_manifest() -> Dict[str, Any]:
    return bondclaw_lead_capture.load_manifest()


def load_lead_capture_queue() -> Dict[str, Any]:
    return bondclaw_lead_capture.load_queue()


def validate_contract_files() -> List[str]:
    errors: List[str] = []
    required_files = [
        "branding-config.example.json",
        "execution-shell.example.json",
        "provider-profile.schema.json",
        "prompt-pack.schema.json",
        "skill-pack-manifest.schema.json",
        "feed-source.schema.json",
        "lead-submission.schema.json",
    ]
    for filename in required_files:
        path = CONTRACTS_DIR / filename
        if not path.exists():
            errors.append(f"缺少 contracts 文件: {filename}")
            continue
        read_json(path)
    return errors


def validate_prompt_library() -> List[str]:
    errors: List[str] = []
    template = load_prompt_template()
    if template.get("required_skills") != ["research-writing"]:
        errors.append("prompt template 必须默认使用 research-writing")
    if not PROMPT_PACKS_DIR.exists():
        errors.append("缺少 prompt-library/packs 目录")
        return errors
    for role_dir in sorted(path for path in PROMPT_PACKS_DIR.iterdir() if path.is_dir()):
        manifest_path = role_dir / "manifest.json"
        if not manifest_path.exists():
            errors.append(f"缺少 manifest: {role_dir.name}")
            continue
        manifest = read_json(manifest_path)
        if manifest.get("canonical_skill") != "research-writing":
            errors.append(f"{role_dir.name} 的 canonical_skill 必须是 research-writing")
        for prompt_path in role_dir.glob("*.json"):
            if prompt_path.name == "manifest.json":
                continue
            prompt = read_json(prompt_path)
            if prompt.get("required_skills") != ["research-writing"]:
                errors.append(f"{prompt_path.relative_to(ROOT)} 必须使用 research-writing")
    return errors


def validate_provider_registry() -> List[str]:
    errors: List[str] = []
    registry = load_provider_registry()
    if registry.get("default_flow", {}).get("key_only") is not True:
        errors.append("provider registry 默认流必须是 key_only")
    providers = registry.get("providers", [])
    for provider in providers:
        if "base_urls" not in provider:
            errors.append(f"provider {provider.get('id')} 缺少 base_urls")
        if "models" not in provider or not provider.get("models"):
            errors.append(f"provider {provider.get('id')} 缺少 models")
        if "source" not in provider:
            errors.append(f"provider {provider.get('id')} 缺少 source")
    return errors


def build_summary() -> Dict[str, Any]:
    branding = load_branding_config()
    shell = load_execution_shell_config()
    provider_registry = load_provider_registry()
    prompt_summaries = load_prompt_pack_summary()
    research_brain = bondclaw_research_brain.build_research_brain_summary()
    lead_capture = bondclaw_lead_capture.build_lead_capture_summary()
    try:
        release_manifest = read_json(REPO_ROOT / "vendor" / "AionUi" / "src" / "common" / "config" / "bondclaw-release-manifest.example.json")
    except Exception:
        release_manifest = {}
    distribution = release_manifest.get("distribution", {}) if isinstance(release_manifest, dict) else {}
    feature_flags = release_manifest.get("featureFlags", {}) if isinstance(release_manifest, dict) else {}
    return {
        "branding": branding,
        "release_manifest": release_manifest,
        "release_version": release_manifest.get("releaseVersion", "") if isinstance(release_manifest, dict) else "",
        "release_channel": release_manifest.get("releaseChannel", "") if isinstance(release_manifest, dict) else "",
        "update_repo": distribution.get("updateRepo", ""),
        "manifest_url": distribution.get("manifestUrl", ""),
        "feature_flags": feature_flags,
        "shell": shell,
        "provider_count": len(provider_registry.get("providers", [])),
        "provider_summaries": [summary.__dict__ for summary in load_provider_summary()],
        "prompt_pack_summaries": [summary.__dict__ for summary in prompt_summaries],
        "role_ids": list_role_ids(),
        "prompt_pack_names": list_prompt_pack_names(),
        "research_source_count": research_brain.get("source_count", 0),
        "research_source_group_count": research_brain.get("source_group_count", 0),
        "research_source_card_count": research_brain.get("source_card_count", 0),
        "research_theme_overview_count": research_brain.get("theme_overview_count", 0),
        "research_case_count": research_brain.get("case_count", 0),
        "research_case_highlight_count": research_brain.get("case_highlight_count", 0),
        "research_case_detail_card_count": research_brain.get("case_detail_card_count", 0),
        "research_brain": research_brain,
        "lead_capture_queue_count": lead_capture.get("queue_count", 0),
        "lead_capture": lead_capture,
    }


def build_catalog() -> Dict[str, Any]:
    provider_registry = load_provider_registry()
    research_brain = load_research_brain_sources()
    lead_capture_manifest = load_lead_capture_manifest()
    lead_capture_queue = load_lead_capture_queue()
    return {
        "branding": load_branding_config(),
        "execution_shell": load_execution_shell_config(),
        "provider_registry": provider_registry,
        "prompt_library": {
            "template": load_prompt_template(),
            "roles": {
                role_id: {
                    "manifest": load_prompt_pack_manifest(role_id),
                    "prompt_names": list_prompt_pack_names(role_id),
                }
                for role_id in list_role_ids()
            },
        },
        "research_brain": {
            "manifest": load_research_brain_manifest(),
            "sources": research_brain,
            "case_index": load_research_brain_case_index(),
        },
        "lead_capture": {
            "manifest": lead_capture_manifest,
            "queue": lead_capture_queue,
        },
        "lead_capture_policy": load_lead_capture_policy(),
    }


def validate_all() -> List[str]:
    errors: List[str] = []
    errors.extend(validate_contract_files())
    errors.extend(validate_provider_registry())
    errors.extend(validate_prompt_library())
    errors.extend(bondclaw_research_brain.validate_research_brain())
    errors.extend(bondclaw_lead_capture.validate_lead_capture())
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BondClaw 资产加载与校验")
    parser.add_argument("--summary", action="store_true", help="输出资产摘要")
    parser.add_argument("--validate", action="store_true", help="执行完整校验")
    parser.add_argument("--catalog", action="store_true", help="输出完整资产目录")
    parser.add_argument("--providers", action="store_true", help="输出 provider 摘要")
    parser.add_argument("--roles", action="store_true", help="输出角色与 prompt pack 摘要")
    parser.add_argument("--research-brain", action="store_true", help="输出研究大脑摘要")
    parser.add_argument("--lead-capture", action="store_true", help="输出联系方式摘要")
    parser.add_argument("--role", help="指定角色 ID，用于输出该角色的 prompt manifest")
    parser.add_argument("--prompt", help="指定 prompt 名称，用于输出 prompt pack")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.providers:
        print(json.dumps([summary.__dict__ for summary in load_provider_summary()], ensure_ascii=False, indent=2))
        return 0
    if args.roles:
        print(json.dumps([summary.__dict__ for summary in load_prompt_pack_summary()], ensure_ascii=False, indent=2))
        return 0
    if args.research_brain:
        print(json.dumps(bondclaw_research_brain.build_research_brain_summary(), ensure_ascii=False, indent=2))
        return 0
    if args.lead_capture:
        print(json.dumps(bondclaw_lead_capture.build_lead_capture_summary(), ensure_ascii=False, indent=2))
        return 0
    if args.role and args.prompt:
        print(json.dumps(load_prompt_pack(args.role, args.prompt), ensure_ascii=False, indent=2))
        return 0
    if args.role:
        print(json.dumps(load_prompt_pack_manifest(args.role), ensure_ascii=False, indent=2))
        return 0
    if args.prompt:
        raise SystemExit("--prompt 需要同时提供 --role")
    if args.catalog:
        print(json.dumps(build_catalog(), ensure_ascii=False, indent=2))
        return 0
    if args.summary:
        print(json.dumps(build_summary(), ensure_ascii=False, indent=2))
        return 0
    if args.validate:
        errors = validate_all()
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print("BondClaw asset validation passed.")
        return 0
    print("Use --summary, --validate, --catalog, --providers, --roles, --research-brain, or --lead-capture.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
