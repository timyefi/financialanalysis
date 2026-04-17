#!/usr/bin/env python3
"""
BondClaw 订阅与案例加载器。

This module keeps the subscriptions layer lightweight:
- read manifest
- read feed sources
- read case library
- build summary and validate structure
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[2]
RESEARCH_BRAIN_DIR = ROOT / "research-brain"
RESEARCH_BRAIN_MANIFEST_PATH = RESEARCH_BRAIN_DIR / "manifest.json"
RESEARCH_BRAIN_SOURCES_PATH = RESEARCH_BRAIN_DIR / "feed-sources.example.json"
RESEARCH_CASE_INDEX_PATH = RESEARCH_BRAIN_DIR / "case-library" / "index.json"


class ResearchBrainError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResearchSourceSummary:
    source_url: str
    topic_tags: int
    role_tags: int
    polling_interval: str
    notification_policy: str


@dataclass(frozen=True)
class CaseCardSummary:
    case_id: str
    title: str
    prompt_role: str
    prompt_workflow: str
    role_tag_count: int
    topic_tag_count: int


@dataclass(frozen=True)
class CaseDetailCard:
    case_id: str
    title: str
    prompt_role: str
    prompt_workflow: str
    recommended_prompt: str
    role_tags: List[str]
    topic_tags: List[str]
    source_refs: List[str]
    summary: str
    evidence_hints: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "title": self.title,
            "prompt_role": self.prompt_role,
            "prompt_workflow": self.prompt_workflow,
            "recommended_prompt": self.recommended_prompt,
            "role_tags": self.role_tags,
            "topic_tags": self.topic_tags,
            "source_refs": self.source_refs,
            "summary": self.summary,
            "evidence_hints": self.evidence_hints,
        }


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ResearchBrainError(f"JSON 顶层必须是对象: {path}")
    return payload


def load_manifest() -> Dict[str, Any]:
    if not RESEARCH_BRAIN_MANIFEST_PATH.exists():
        raise ResearchBrainError("缺少 research-brain/manifest.json")
    return read_json(RESEARCH_BRAIN_MANIFEST_PATH)


def load_feed_sources() -> Dict[str, Any]:
    if not RESEARCH_BRAIN_SOURCES_PATH.exists():
        raise ResearchBrainError("缺少 research-brain/feed-sources.example.json")
    return read_json(RESEARCH_BRAIN_SOURCES_PATH)


def load_case_index() -> Dict[str, Any]:
    if not RESEARCH_CASE_INDEX_PATH.exists():
        raise ResearchBrainError("缺少 research-brain/case-library/index.json")
    return read_json(RESEARCH_CASE_INDEX_PATH)


def load_source_summaries() -> List[ResearchSourceSummary]:
    source_payload = load_feed_sources()
    summaries: List[ResearchSourceSummary] = []
    for source in source_payload.get("sources", []):
        if not isinstance(source, dict):
            continue
        summaries.append(
            ResearchSourceSummary(
                source_url=str(source.get("source_url", "")),
                topic_tags=len(source.get("topic_tags") or []),
                role_tags=len(source.get("role_tags") or []),
                polling_interval=str(source.get("polling_interval", "")),
                notification_policy=str(source.get("notification_policy", "")),
            )
        )
    return summaries


def load_case_summaries() -> List[CaseCardSummary]:
    case_payload = load_case_index()
    summaries: List[CaseCardSummary] = []
    for case in case_payload.get("cases", []):
        if not isinstance(case, dict):
            continue
        summaries.append(
            CaseCardSummary(
                case_id=str(case.get("case_id", "")),
                title=str(case.get("title", "")),
                prompt_role=str(case.get("prompt_role", "")),
                prompt_workflow=str(case.get("prompt_workflow", "")),
                role_tag_count=len(case.get("role_tags") or []),
                topic_tag_count=len(case.get("topic_tags") or []),
            )
        )
    return summaries


def load_case_detail_cards() -> List[CaseDetailCard]:
    case_payload = load_case_index()
    cards: List[CaseDetailCard] = []
    for case in case_payload.get("cases", []):
        if not isinstance(case, dict):
            continue
        cards.append(
            CaseDetailCard(
                case_id=str(case.get("case_id", "")),
                title=str(case.get("title", "")),
                prompt_role=str(case.get("prompt_role", "")),
                prompt_workflow=str(case.get("prompt_workflow", "")),
                recommended_prompt=str(case.get("recommended_prompt", "")),
                role_tags=[str(value) for value in (case.get("role_tags") or []) if value],
                topic_tags=[str(value) for value in (case.get("topic_tags") or []) if value],
                source_refs=[str(value) for value in (case.get("source_refs") or []) if value],
                summary=str(case.get("summary", "")),
                evidence_hints=[str(value) for value in (case.get("evidence_hints") or []) if value],
            )
        )
    return cards


def load_source_group_summaries() -> List[Dict[str, Any]]:
    manifest = load_manifest()
    groups = manifest.get("source_groups", [])
    if not isinstance(groups, list):
        return []
    summaries: List[Dict[str, Any]] = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        summaries.append(
            {
                "group_id": str(group.get("group_id", "")),
                "display_name": str(group.get("display_name", "")),
                "topic_tags": list(group.get("topic_tags") or []),
                "role_tags": list(group.get("role_tags") or []),
                "polling_interval": str(group.get("polling_interval", "")),
                "notification_policy": str(group.get("notification_policy", "")),
            }
        )
    return summaries


def load_source_cards() -> List[Dict[str, Any]]:
    cards: List[Dict[str, Any]] = []
    for group in load_source_group_summaries():
        topic_tags = list(group.get("topic_tags") or [])
        role_tags = list(group.get("role_tags") or [])
        cards.append(
            {
                "group_id": group.get("group_id", ""),
                "title": group.get("display_name", ""),
                "topic_count": len(topic_tags),
                "role_count": len(role_tags),
                "topic_tags": topic_tags[:4],
                "role_tags": role_tags[:4],
                "polling_interval": group.get("polling_interval", ""),
                "notification_policy": group.get("notification_policy", ""),
                "summary": f"{len(topic_tags)} 个主题标签，覆盖 {len(role_tags)} 个角色标签",
            }
        )
    return cards


def load_theme_overview() -> List[Dict[str, Any]]:
    cases = load_case_index().get("cases", [])
    sources = load_source_group_summaries()
    themes = [
        ("macro", "宏观"),
        ("rates", "利率"),
        ("credit", "信用"),
        ("convertibles", "转债"),
        ("multi-asset", "多资产"),
        ("fund-manager", "固收基金经理"),
        ("trader", "固收交易员"),
    ]
    overview: List[Dict[str, Any]] = []
    for theme_id, display_name in themes:
        matching_cases: List[Dict[str, Any]] = []
        matching_sources: List[Dict[str, Any]] = []
        topic_tags: List[str] = []
        for case in cases:
            if not isinstance(case, dict):
                continue
            role_tags = [str(value) for value in (case.get("role_tags") or []) if value]
            if case.get("prompt_role") == theme_id or theme_id in role_tags:
                matching_cases.append(case)
                topic_tags.extend([str(value) for value in (case.get("topic_tags") or []) if value])
        for source in sources:
            role_tags = [str(value) for value in (source.get("role_tags") or []) if value]
            if theme_id in role_tags:
                matching_sources.append(source)
        overview.append(
            {
                "theme_id": theme_id,
                "display_name": display_name,
                "case_count": len(matching_cases),
                "source_group_count": len(matching_sources),
                "topic_tags": sorted(set(topic_tags))[:4],
                "role_tag_count": len({tag for case in matching_cases for tag in [str(value) for value in (case.get("role_tags") or []) if value]}),
                "summary": f"{len(matching_cases)} 个案例，{len(matching_sources)} 个来源分组",
            }
        )
    return overview


def filter_case_summaries(role: Optional[str] = None, topic: Optional[str] = None) -> List[CaseCardSummary]:
    summaries = load_case_summaries()
    filtered: List[CaseCardSummary] = []
    for summary in summaries:
        if role and role != summary.prompt_role and role not in load_case_tags(summary.case_id, "role_tags"):
            continue
        if topic and topic not in load_case_tags(summary.case_id, "topic_tags"):
            continue
        filtered.append(summary)
    return filtered


def load_case_tags(case_id: str, field: str) -> List[str]:
    case_payload = load_case_index()
    for case in case_payload.get("cases", []):
        if isinstance(case, dict) and str(case.get("case_id", "")) == case_id:
            values = case.get(field) or []
            return [str(value) for value in values if value]
    return []


def get_case_detail(case_id: str) -> Dict[str, Any]:
    for card in load_case_detail_cards():
        if card.case_id == case_id:
            return card.to_dict()
    raise ResearchBrainError(f"找不到 research-brain case: {case_id}")


def build_research_brain_summary() -> Dict[str, Any]:
    manifest = load_manifest()
    sources = load_feed_sources()
    cases = load_case_index()
    source_summaries = load_source_summaries()
    case_summaries = load_case_summaries()
    source_groups = load_source_group_summaries()
    source_cards = load_source_cards()
    theme_overview = load_theme_overview()
    case_highlights = [card.to_dict() for card in load_case_detail_cards()[:3]]
    case_detail_cards = [card.to_dict() for card in load_case_detail_cards()]
    return {
        "manifest": manifest,
        "source_count": len(sources.get("sources", [])),
        "case_count": len(cases.get("cases", [])),
        "source_group_count": len(source_groups),
        "source_card_count": len(source_cards),
        "theme_overview_count": len(theme_overview),
        "case_highlight_count": len(case_highlights),
        "case_detail_card_count": len(case_detail_cards),
        "default_polling_interval": manifest.get("default_polling_interval", "15m"),
        "notification_order": manifest.get("notification_order", []),
        "supported_formats": manifest.get("supported_formats", []),
        "source_groups": source_groups,
        "source_cards": source_cards,
        "theme_overview": theme_overview,
        "source_summaries": [summary.__dict__ for summary in source_summaries],
        "case_summaries": [summary.__dict__ for summary in case_summaries],
        "case_highlights": case_highlights,
        "case_detail_cards": case_detail_cards,
    }


def validate_research_brain() -> List[str]:
    errors: List[str] = []
    try:
        manifest = load_manifest()
    except ResearchBrainError as exc:
        return [str(exc)]

    if manifest.get("schemaVersion") != 1:
        errors.append("research-brain manifest schemaVersion 必须为 1")

    if not isinstance(manifest.get("source_groups"), list) or not manifest.get("source_groups"):
        errors.append("research-brain manifest 需要 source_groups")
    else:
        for idx, group in enumerate(manifest["source_groups"], start=1):
            if not isinstance(group, dict):
                errors.append(f"research-brain source_group #{idx} 不是对象")
                continue
            for field in ("group_id", "display_name", "topic_tags", "role_tags", "polling_interval", "notification_policy"):
                if field not in group:
                    errors.append(f"research-brain source_group #{idx} 缺少 {field}")

    if not isinstance(manifest.get("notification_order"), list) or not manifest.get("notification_order"):
        errors.append("research-brain manifest 需要 notification_order")

    if not isinstance(manifest.get("case_library"), dict):
        errors.append("research-brain manifest 需要 case_library")
    else:
        case_library = manifest["case_library"]
        if case_library.get("case_index_path") != "case-library/index.json":
            errors.append("research-brain case_library.case_index_path 必须指向 case-library/index.json")

    try:
        sources = load_feed_sources()
    except ResearchBrainError as exc:
        errors.append(str(exc))
        sources = {}

    if not isinstance(sources.get("sources"), list) or not sources.get("sources"):
        errors.append("research-brain feed-sources.example.json 需要 sources 数组")
    else:
        for idx, source in enumerate(sources["sources"], start=1):
            if not isinstance(source, dict):
                errors.append(f"research-brain source #{idx} 不是对象")
                continue
            for field in ("source_url", "topic_tags", "role_tags", "polling_interval", "dedupe_key", "notification_policy"):
                if field not in source:
                    errors.append(f"research-brain source #{idx} 缺少 {field}")

    try:
        cases = load_case_index()
    except ResearchBrainError as exc:
        errors.append(str(exc))
        cases = {}
        case_library = {}

    if not isinstance(cases.get("cases"), list) or not cases.get("cases"):
        errors.append("research-brain case index 需要 cases 数组")
    else:
        if manifest.get("case_library", {}).get("starter_case_count") != len(cases["cases"]):
            errors.append("research-brain case_library.starter_case_count 必须与 case count 一致")
        for idx, case in enumerate(cases["cases"], start=1):
            if not isinstance(case, dict):
                errors.append(f"research-brain case #{idx} 不是对象")
                continue
            for field in ("case_id", "title", "role_tags", "topic_tags", "prompt_role", "prompt_workflow", "recommended_prompt", "summary"):
                if field not in case:
                    errors.append(f"research-brain case #{idx} 缺少 {field}")
            if not isinstance(case.get("source_refs"), list) or not case.get("source_refs"):
                errors.append(f"research-brain case #{idx} 需要 source_refs")
            if not isinstance(case.get("evidence_hints"), list) or not case.get("evidence_hints"):
                errors.append(f"research-brain case #{idx} 需要 evidence_hints")

    return errors
