#!/usr/bin/env python3
"""
知识库更新工具 - 财务分析知识库版本管理。
同时提供 W5 pending_updates 知识治理入口。
"""

import argparse
import collections
import datetime
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from runtime_support import RuntimeConfigError, load_runtime_config, resolve_runtime_path


VALID_CANDIDATE_TYPES = {
    "topic_candidate",
    "field_candidate",
    "rule_candidate",
}
VALID_STATUSES = {"candidate", "validated", "promoted"}
CONFIDENCE_SCORES = {
    "low": 0.30,
    "medium": 0.60,
    "high": 0.85,
    "extreme": 0.95,
}
NOISY_SHORT_TITLES = {
    "重要",
    "典型",
    "一般",
    "其他",
    "摘要",
}
STABLE_OPEN_TOPIC_ALLOWLIST = set()


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


def script_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_pending_input_paths() -> List[Path]:
    root = script_root()
    return [
        root / "test_runs" / "w6_henglong" / "pending_updates.json",
        root / "test_runs" / "w6_country_garden" / "pending_updates.json",
        root / "test_runs" / "w6_hanghai" / "pending_updates.json",
    ]


def default_review_output_dir() -> Path:
    return script_root() / "test_runs" / "w5_knowledge_governance"


def load_formal_runtime_config(runtime_config_arg: Optional[str]) -> Dict[str, Any]:
    try:
        return load_runtime_config(
            config_path=Path(runtime_config_arg) if runtime_config_arg else None,
            cwd=Path.cwd(),
            require_knowledge_base=True,
            ensure_state_dirs=True,
        )
    except RuntimeConfigError as exc:
        raise SystemExit(str(exc)) from exc


def formal_knowledge_base_path(runtime_config_arg: Optional[str]) -> Path:
    runtime_config = load_formal_runtime_config(runtime_config_arg)
    return resolve_runtime_path(runtime_config, "knowledge_base")


class KnowledgeBaseManager:
    def __init__(self, kb_path: str):
        self.kb_path = kb_path
        self.kb = self._load()

    def _load(self) -> Dict:
        """加载知识库"""
        with open(self.kb_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self):
        """保存知识库"""
        with open(self.kb_path, "w", encoding="utf-8") as f:
            json.dump(self.kb, f, ensure_ascii=False, indent=2)

    def get_version(self) -> str:
        """获取当前版本"""
        return self.kb["metadata"]["version"]

    def add_knowledge_source(self, name: str, summary: str, kb_type: str = "case_study") -> str:
        """添加知识来源"""
        source_id = f"source_{len(self.kb['knowledge_sources']) + 1:03d}"
        source = {
            "id": source_id,
            "name": name,
            "date": datetime.datetime.now().strftime("%Y-%m-%d"),
            "type": kb_type,
            "summary": summary,
        }
        self.kb["knowledge_sources"].append(source)
        return source_id

    def add_interest_debt_type(
        self,
        debt_type: str,
        is_interest: bool,
        reason: str,
        source: str = None,
        identification: str = None,
        note: str = None,
    ):
        """添加有息债务类型判定"""
        target_list = "included" if is_interest else "excluded"
        code = (
            f"{'IBD' if is_interest else 'EXC'}_"
            f"{len(self.kb['knowledge']['interest_bearing_debt']['criteria'][target_list]) + 1:03d}"
        )

        entry = {
            "type": debt_type,
            "code": code,
            "interest": is_interest,
            "reason": reason,
        }
        if source:
            entry["source"] = source
        if identification:
            entry["identification"] = identification
        if note:
            entry["note"] = note

        self.kb["knowledge"]["interest_bearing_debt"]["criteria"][target_list].append(entry)
        return code

    def add_note_extraction_tip(self, section: str, name: str, focus: str, importance: str = "中"):
        """添加附注提取技巧"""
        section_num = section.replace("#", "")
        code = f"NOTE_{section_num:03d}"

        self.kb["knowledge"]["notes_extraction"]["key_sections"][section] = {
            "name": name,
            "importance": importance,
            "focus": focus,
            "code": code,
        }
        return code

    def add_common_mistake(self, description: str, correction: str, example: str = None) -> str:
        """添加常见错误"""
        mistake_id = f"MST_{len(self.kb['knowledge']['common_mistakes']['mistakes']) + 1:03d}"

        entry = {
            "id": mistake_id,
            "description": description,
            "correction": correction,
        }
        if example:
            entry["example"] = example

        self.kb["knowledge"]["common_mistakes"]["mistakes"].append(entry)
        return mistake_id

    def update_version(self, changes: List[str], source_ids: List[str]):
        """更新版本"""
        current = self.kb["metadata"]["version"]
        major, minor, patch = map(int, current.split("."))
        new_version = f"{major}.{minor + 1}.{patch}"

        self.kb["metadata"]["version"] = new_version
        self.kb["metadata"]["last_updated"] = datetime.datetime.now().strftime("%Y-%m-%d")
        self.kb["version_history"].append(
            {
                "version": new_version,
                "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                "changes": changes,
                "knowledge_sources": source_ids,
            }
        )

        self._save()
        return new_version

    def search_by_keyword(self, keyword: str) -> List[Dict]:
        """关键词搜索"""
        results = []
        keyword = keyword.lower()

        for item in self.kb["knowledge"]["interest_bearing_debt"]["criteria"]["included"]:
            if keyword in item["type"].lower() or keyword in item.get("reason", "").lower():
                results.append({"section": "included", "item": item})

        for item in self.kb["knowledge"]["interest_bearing_debt"]["criteria"]["excluded"]:
            if keyword in item["type"].lower() or keyword in item.get("reason", "").lower():
                results.append({"section": "excluded", "item": item})

        if "fraud_detection" in self.kb["knowledge"]:
            for item in self.kb["knowledge"]["fraud_detection"].get("signals", []):
                if keyword in item.get("signal", "").lower() or keyword in item.get("problem", "").lower():
                    results.append({"section": "fraud_detection", "item": item})

        return results

    def print_summary(self):
        """打印知识库摘要"""
        print("=== 财务分析知识库 ===")
        print(f"版本: {self.kb['metadata']['version']}")
        print(f"更新: {self.kb['metadata']['last_updated']}")
        print(f"来源: {self.kb['metadata'].get('source', 'N/A')}")
        print(f"知识来源: {len(self.kb['knowledge_sources'])}个")

        included = len(self.kb["knowledge"]["interest_bearing_debt"]["criteria"]["included"])
        excluded = len(self.kb["knowledge"]["interest_bearing_debt"]["criteria"]["excluded"])
        print(f"有息债务判定: {included}项(含) / {excluded}项(不含)")

        solvency_st = len(self.kb["knowledge"]["indicators"]["solvency"]["short_term"])
        solvency_lt = len(self.kb["knowledge"]["indicators"]["solvency"]["long_term"])
        print(f"偿债指标: {solvency_st + solvency_lt}项")

        profitability = len(self.kb["knowledge"]["indicators"]["profitability"])
        print(f"盈利指标: {profitability}项")

        cashflow = len(self.kb["knowledge"]["indicators"]["cashflow"]["debt_coverage"])
        print(f"现金流指标: {cashflow}项")

        leverage = len(self.kb["knowledge"]["indicators"]["leverage"]["core"])
        print(f"杠杆指标: {leverage}项")

        if "fraud_detection" in self.kb["knowledge"]:
            signals = len(self.kb["knowledge"]["fraud_detection"]["signals"])
            print(f"欺诈识别信号: {signals}项")


class PendingUpdateGovernance:
    def __init__(self):
        self.required_fields = [
            "source",
            "evidence",
            "applicable_scope",
            "status",
            "introduced_in",
            "confidence",
        ]

    def validate_pending_updates(self, pending_updates_path: str) -> Dict[str, Any]:
        path = Path(pending_updates_path).resolve()
        case_name = path.parent.name
        result = {
            "path": str(path),
            "case_name": case_name,
            "metadata_issues": [],
            "item_results": [],
            "item_count": 0,
            "blocking_issue_count": 0,
            "quality_issue_count": 0,
        }

        try:
            pending_updates = read_json(path)
        except Exception as exc:
            result["metadata_issues"].append(
                {
                    "severity": "blocking_issue",
                    "code": "file_read_error",
                    "message": f"读取文件失败: {exc}",
                }
            )
            result["blocking_issue_count"] += 1
            return result

        if not isinstance(pending_updates, dict):
            result["metadata_issues"].append(
                {
                    "severity": "blocking_issue",
                    "code": "top_level_not_object",
                    "message": "pending_updates 顶层必须是对象",
                }
            )
            result["blocking_issue_count"] += 1
            return result

        metadata = pending_updates.get("metadata")
        if not isinstance(metadata, dict):
            result["metadata_issues"].append(
                {
                    "severity": "blocking_issue",
                    "code": "metadata_missing",
                    "message": "顶层缺少 metadata 对象",
                }
            )
            result["blocking_issue_count"] += 1

        items = pending_updates.get("items")
        if not isinstance(items, list):
            result["metadata_issues"].append(
                {
                    "severity": "blocking_issue",
                    "code": "items_missing",
                    "message": "顶层缺少 items 列表",
                }
            )
            result["blocking_issue_count"] += 1
            return result

        result["item_count"] = len(items)
        for index, item in enumerate(items, start=1):
            item_result = self._validate_item(index, item, case_name)
            result["item_results"].append(item_result)
            result["blocking_issue_count"] += item_result["blocking_issue_count"]
            result["quality_issue_count"] += item_result["quality_issue_count"]

        return result

    def summarize_pending_updates(self, pending_updates_path: str) -> Dict[str, Any]:
        validation = self.validate_pending_updates(pending_updates_path)
        type_counts: Dict[str, int] = {}
        status_counts: Dict[str, int] = {}
        for item_result in validation["item_results"]:
            item = item_result.get("item", {})
            item_type = item.get("type", "unknown")
            status = item.get("status", "unknown")
            type_counts[item_type] = type_counts.get(item_type, 0) + 1
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "path": validation["path"],
            "case_name": validation["case_name"],
            "item_count": validation["item_count"],
            "type_counts": type_counts,
            "status_counts": status_counts,
            "blocking_issue_count": validation["blocking_issue_count"],
            "quality_issue_count": validation["quality_issue_count"],
        }

    def build_review_bundle(self, pending_updates_paths: List[str]) -> Dict[str, Any]:
        normalized_paths = [str(Path(path).resolve()) for path in pending_updates_paths]
        file_results = [self.validate_pending_updates(path) for path in normalized_paths]
        group_map: Dict[Tuple[str, str], Dict[str, Any]] = {}

        for file_result in file_results:
            case_name = file_result["case_name"]
            for item_result in file_result["item_results"]:
                group_key = (
                    item_result["item"].get("type", "unknown"),
                    item_result["normalized_title"] or item_result["title"] or "",
                )
                group = group_map.setdefault(
                    group_key,
                    {
                        "candidate_type": group_key[0],
                        "normalized_title": group_key[1],
                        "original_titles": [],
                        "cases": [],
                        "items": [],
                        "confidence_values": [],
                        "applicable_scopes": [],
                    },
                )
                if item_result["title"] and item_result["title"] not in group["original_titles"]:
                    group["original_titles"].append(item_result["title"])
                if case_name not in group["cases"]:
                    group["cases"].append(case_name)
                group["items"].append(item_result)
                if item_result["confidence_score"] is not None:
                    group["confidence_values"].append(item_result["confidence_score"])
                scope = item_result["item"].get("applicable_scope")
                if scope and scope not in group["applicable_scopes"]:
                    group["applicable_scopes"].append(scope)

        group_summaries = [self._summarize_group(group) for group in group_map.values()]
        group_summaries.sort(
            key=lambda item: (
                {"promoted": 0, "validated": 1, "candidate": 2}.get(item["recommended_status"], 9),
                {"high": 0, "medium": 1, "low": 2}.get(item["review_priority"], 9),
                -item["case_count"],
                item["candidate_type"],
                item["normalized_title"],
            )
        )

        status_counts = collections.Counter(item["recommended_status"] for item in group_summaries)
        type_counts = collections.Counter(item["candidate_type"] for item in group_summaries)
        issue_counts = collections.Counter()
        for item in group_summaries:
            for issue in item["validation_issues"]:
                issue_counts[issue["severity"]] += 1

        summary = {
            "input_file_count": len(file_results),
            "validated_case_count": len({item["case_name"] for item in file_results}),
            "group_count": len(group_summaries),
            "candidate_count": sum(file_result["item_count"] for file_result in file_results),
            "recommended_status_counts": dict(status_counts),
            "candidate_type_counts": dict(type_counts),
            "issue_counts": dict(issue_counts),
            "promoted_titles": [item["normalized_title"] for item in group_summaries if item["recommended_status"] == "promoted"],
            "sample_review_titles": [
                item["normalized_title"]
                for item in group_summaries
                if item["review_priority"] == "high"
            ][:10],
        }

        return {
            "metadata": {
                "generated_at": now_iso(),
                "governance_version": "w5-mvp-1",
                "input_files": normalized_paths,
                "default_input_baseline": [str(path) for path in default_pending_input_paths()],
                "knowledge_base_written": False,
                "soul_structure_changed": False,
            },
            "summary": summary,
            "file_results": file_results,
            "group_summaries": group_summaries,
        }

    def write_review_bundle(self, bundle: Dict[str, Any], output_dir: str) -> Dict[str, str]:
        target_dir = Path(output_dir).resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = target_dir / "knowledge_review_bundle.json"
        report_path = target_dir / "knowledge_review_report.md"
        write_json(bundle_path, bundle)
        write_text(report_path, self.render_review_report(bundle))
        return {
            "bundle_path": str(bundle_path),
            "report_path": str(report_path),
        }

    def render_review_report(self, bundle: Dict[str, Any]) -> str:
        summary = bundle["summary"]
        lines = [
            "# W5 知识治理审核包",
            "",
            "## 审核摘要",
            f"- 生成时间：{bundle['metadata']['generated_at']}",
            f"- 输入案例数：{summary['validated_case_count']}",
            f"- 输入文件数：{summary['input_file_count']}",
            f"- 原始候选总数：{summary['candidate_count']}",
            f"- 归并后审核组数：{summary['group_count']}",
            f"- 推荐状态分布：{self._format_counter(summary['recommended_status_counts'])}",
            f"- 候选类型分布：{self._format_counter(summary['candidate_type_counts'])}",
            f"- 问题分布：{self._format_counter(summary['issue_counts'])}",
            "",
            "## 单文件校验",
        ]

        for file_result in bundle["file_results"]:
            lines.append(
                f"- `{file_result['case_name']}`：items={file_result['item_count']}，"
                f"blocking={file_result['blocking_issue_count']}，quality={file_result['quality_issue_count']}"
            )

        promoted_items = [item for item in bundle["group_summaries"] if item["recommended_status"] == "promoted"]
        validated_items = [item for item in bundle["group_summaries"] if item["recommended_status"] == "validated"]
        review_items = [
            item
            for item in bundle["group_summaries"]
            if item["review_priority"] == "high" or item["recommended_status"] == "candidate"
        ]

        lines.extend(["", "## 推荐升级为 Promoted"])
        if promoted_items:
            for item in promoted_items:
                lines.append(
                    f"- `{item['candidate_type']}` / `{item['normalized_title']}`："
                    f"cases={item['case_count']}，avg_confidence={item['avg_confidence']:.2f}，"
                    f"action={item['review_action']}"
                )
        else:
            lines.append("- 本轮无推荐为 `promoted` 的审核组。")

        lines.extend(["", "## 推荐升级为 Validated"])
        if validated_items:
            for item in validated_items[:12]:
                lines.append(
                    f"- `{item['candidate_type']}` / `{item['normalized_title']}`："
                    f"cases={item['case_count']}，action={item['review_action']}"
                )
        else:
            lines.append("- 本轮无推荐为 `validated` 的审核组。")

        lines.extend(["", "## 需优先抽样复核"])
        if review_items:
            for item in review_items[:15]:
                issue_codes = ",".join(issue["code"] for issue in item["validation_issues"]) or "-"
                lines.append(
                    f"- `{item['candidate_type']}` / `{item['normalized_title']}`："
                    f"status={item['recommended_status']}，priority={item['review_priority']}，issues={issue_codes}"
                )
        else:
            lines.append("- 当前没有高优先级抽样项。")

        lines.extend(["", "## 审核说明"])
        lines.append("- 本轮只生成建议决议，不直接写入 `knowledge_base.json`。")
        lines.append("- 抽样优先看 `recommended_status=promoted`、有 blocking/quality issue 的组，以及标题归一化后仍可疑的组。")
        lines.append("- `field_candidate` 在 MVP 最高只建议到 `validated`。")
        return "\n".join(lines) + "\n"

    def print_review_summary(self, bundle: Dict[str, Any]):
        summary = bundle["summary"]
        print("=== W5 知识治理摘要 ===")
        print(f"生成时间: {bundle['metadata']['generated_at']}")
        print(f"输入文件: {summary['input_file_count']} 个")
        print(f"案例数: {summary['validated_case_count']} 个")
        print(f"原始候选: {summary['candidate_count']} 条")
        print(f"审核组: {summary['group_count']} 个")
        print(f"推荐状态: {self._format_counter(summary['recommended_status_counts'])}")
        print(f"候选类型: {self._format_counter(summary['candidate_type_counts'])}")
        print(f"问题分布: {self._format_counter(summary['issue_counts'])}")
        print("推荐 promoted:")
        promoted = summary["promoted_titles"] or ["无"]
        for title in promoted:
            print(f"- {title}")
        print("优先抽样复核:")
        review_titles = summary["sample_review_titles"] or ["无"]
        for title in review_titles:
            print(f"- {title}")

    def _validate_item(self, index: int, item: Any, case_name: str) -> Dict[str, Any]:
        if not isinstance(item, dict):
            return {
                "index": index,
                "title": f"item_{index}",
                "normalized_title": "",
                "item": {},
                "case_name": case_name,
                "confidence_score": None,
                "validation_issues": [
                    {
                        "severity": "blocking_issue",
                        "code": "item_not_object",
                        "message": "候选项必须是对象",
                    }
                ],
                "blocking_issue_count": 1,
                "quality_issue_count": 0,
            }

        issues: List[Dict[str, str]] = []
        title = str(item.get("title", f"item_{index}"))
        normalized_title = self._normalize_title(title)
        confidence_score = self._parse_confidence(item.get("confidence"), issues)

        for field in self.required_fields:
            if field not in item or item.get(field) in (None, "", []):
                issues.append(
                    {
                        "severity": "blocking_issue",
                        "code": "required_field_missing",
                        "message": f"缺少必填字段: {field}",
                    }
                )

        item_type = item.get("type")
        if item_type not in VALID_CANDIDATE_TYPES:
            issues.append(
                {
                    "severity": "blocking_issue",
                    "code": "candidate_type_invalid",
                    "message": f"非法候选类型: {item_type}",
                }
            )

        status = item.get("status")
        if status not in VALID_STATUSES:
            issues.append(
                {
                    "severity": "blocking_issue",
                    "code": "status_invalid",
                    "message": f"非法状态: {status}",
                }
            )

        source = item.get("source", "")
        if source and not re.fullmatch(r"chapter_\d+", str(source)):
            issues.append(
                {
                    "severity": "quality_issue",
                    "code": "source_pattern_unexpected",
                    "message": f"source 未匹配 chapter_<n>: {source}",
                }
            )

        evidence = item.get("evidence")
        if evidence is not None:
            if not isinstance(evidence, list) or not evidence:
                issues.append(
                    {
                        "severity": "blocking_issue",
                        "code": "evidence_empty",
                        "message": "evidence 必须是非空列表",
                    }
                )
            else:
                for evidence_index, evidence_item in enumerate(evidence, start=1):
                    if not isinstance(evidence_item, dict):
                        issues.append(
                            {
                                "severity": "blocking_issue",
                                "code": "evidence_not_object",
                                "message": f"evidence[{evidence_index}] 必须是对象",
                            }
                        )
                        continue
                    for field in ("source", "type", "content"):
                        if evidence_item.get(field) in (None, "", []):
                            issues.append(
                                {
                                    "severity": "blocking_issue",
                                    "code": "evidence_field_missing",
                                    "message": f"evidence[{evidence_index}] 缺少字段: {field}",
                                }
                            )

        issues.extend(self._validate_title_quality(title, normalized_title))

        blocking_issue_count = sum(1 for issue in issues if issue["severity"] == "blocking_issue")
        quality_issue_count = sum(1 for issue in issues if issue["severity"] == "quality_issue")
        return {
            "index": index,
            "title": title,
            "normalized_title": normalized_title,
            "item": item,
            "case_name": case_name,
            "confidence_score": confidence_score,
            "validation_issues": issues,
            "blocking_issue_count": blocking_issue_count,
            "quality_issue_count": quality_issue_count,
        }

    def _validate_title_quality(self, title: str, normalized_title: str) -> List[Dict[str, str]]:
        issues = []
        if not normalized_title:
            issues.append(
                {
                    "severity": "quality_issue",
                    "code": "title_empty_after_normalization",
                    "message": "标题去除 markdown 和注记后为空",
                }
            )
            return issues

        if any(symbol in title for symbol in ("|", "#", "*", "`")):
            issues.append(
                {
                    "severity": "quality_issue",
                    "code": "title_markdown_noise",
                    "message": "标题包含明显 markdown 碎片",
                }
            )

        if re.search(r"[（(].*[)）]", title):
            stripped = re.sub(r"（[^）]*）|\([^)]*\)", " ", title)
            stripped = re.sub(r"\s+", " ", stripped).strip()
            if not stripped:
                issues.append(
                    {
                        "severity": "quality_issue",
                        "code": "title_decorator_only",
                        "message": "标题主要由括号装饰构成",
                    }
                )

        if normalized_title.endswith("…") or (
            len(normalized_title) >= 20
            and (
                re.search(r"[\u4e00-\u9fff]", normalized_title)
                or " " in normalized_title
            )
        ):
            issues.append(
                {
                    "severity": "quality_issue",
                    "code": "title_too_long",
                    "message": "标题过长，更像证据截断句而非稳定知识项",
                }
            )

        if normalized_title in NOISY_SHORT_TITLES:
            issues.append(
                {
                    "severity": "quality_issue",
                    "code": "title_too_short",
                    "message": "标题过短且属于高噪声词",
                }
            )

        return issues

    def _parse_confidence(self, raw_confidence: Any, issues: List[Dict[str, str]]) -> Optional[float]:
        if raw_confidence is None:
            return None

        if isinstance(raw_confidence, (int, float)):
            value = float(raw_confidence)
            if 0.0 <= value <= 1.0:
                return value
            issues.append(
                {
                    "severity": "blocking_issue",
                    "code": "confidence_out_of_range",
                    "message": f"confidence 超出 0.0-1.0: {raw_confidence}",
                }
            )
            return None

        if isinstance(raw_confidence, str):
            normalized = raw_confidence.strip().lower()
            if normalized in CONFIDENCE_SCORES:
                return CONFIDENCE_SCORES[normalized]
            try:
                value = float(normalized)
            except ValueError:
                issues.append(
                    {
                        "severity": "blocking_issue",
                        "code": "confidence_invalid",
                        "message": f"confidence 非法: {raw_confidence}",
                    }
                )
                return None
            if 0.0 <= value <= 1.0:
                return value

        issues.append(
            {
                "severity": "blocking_issue",
                "code": "confidence_invalid",
                "message": f"confidence 非法: {raw_confidence}",
            }
        )
        return None

    def _normalize_title(self, title: str) -> str:
        normalized = title or ""
        normalized = re.sub(r"[#*|`]+", " ", normalized)
        normalized = re.sub(r"（[^）]*）|\([^)]*\)", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        normalized = re.sub(r"^[\W_]+|[\W_]+$", "", normalized, flags=re.UNICODE)
        return normalized.lower()

    def _summarize_group(self, group: Dict[str, Any]) -> Dict[str, Any]:
        validation_issues = []
        seen_issue_keys = set()
        evidence_samples = []
        current_statuses = []
        has_blocking = False
        has_quality = False

        for item_result in group["items"]:
            current_statuses.append(item_result["item"].get("status", "unknown"))
            for issue in item_result["validation_issues"]:
                issue_key = (issue["severity"], issue["code"], issue["message"])
                if issue_key not in seen_issue_keys:
                    validation_issues.append(issue)
                    seen_issue_keys.add(issue_key)
                if issue["severity"] == "blocking_issue":
                    has_blocking = True
                if issue["severity"] == "quality_issue":
                    has_quality = True
            for evidence in item_result["item"].get("evidence", [])[:1]:
                evidence_samples.append(
                    {
                        "case_name": item_result["case_name"],
                        "source": evidence.get("source", ""),
                        "type": evidence.get("type", ""),
                        "content": evidence.get("content", ""),
                    }
                )

        case_count = len(group["cases"])
        avg_confidence = (
            round(sum(group["confidence_values"]) / len(group["confidence_values"]), 4)
            if group["confidence_values"]
            else 0.0
        )
        contract_impact = self._contract_impact(group["candidate_type"])
        recommended_status = self._recommended_status(
            candidate_type=group["candidate_type"],
            normalized_title=group["normalized_title"],
            case_count=case_count,
            avg_confidence=avg_confidence,
            has_blocking=has_blocking,
            has_quality=has_quality,
            contract_impact=contract_impact,
        )
        review_action, review_priority = self._review_action(
            recommended_status,
            has_blocking,
            has_quality,
            len(group["applicable_scopes"]) > 1,
        )

        if len(group["applicable_scopes"]) > 1:
            validation_issues.append(
                {
                    "severity": "quality_issue",
                    "code": "scope_divergence",
                    "message": "同组候选的 applicable_scope 不一致，建议抽样复核",
                }
            )

        return {
            "normalized_title": group["normalized_title"],
            "original_titles": sorted(group["original_titles"]),
            "candidate_type": group["candidate_type"],
            "case_count": case_count,
            "cases": sorted(group["cases"]),
            "evidence_samples": evidence_samples[:5],
            "confidence_values": group["confidence_values"],
            "avg_confidence": avg_confidence,
            "current_statuses": sorted(set(current_statuses)),
            "validation_issues": validation_issues,
            "contract_impact": contract_impact,
            "recommended_status": recommended_status,
            "review_action": review_action,
            "review_priority": review_priority,
        }

    def _contract_impact(self, candidate_type: str) -> str:
        if candidate_type == "rule_candidate":
            return "compatible_internal_rule_candidate"
        if candidate_type == "topic_candidate":
            return "compatible_internal_open_topic_candidate"
        if candidate_type == "field_candidate":
            return "compatible_case_extension_candidate_no_auto_promotion"
        return "requires_manual_contract_review"

    def _recommended_status(
        self,
        candidate_type: str,
        normalized_title: str,
        case_count: int,
        avg_confidence: float,
        has_blocking: bool,
        has_quality: bool,
        contract_impact: str,
    ) -> str:
        if has_blocking or has_quality or case_count < 2 or contract_impact == "requires_manual_contract_review":
            return "candidate"

        if candidate_type == "rule_candidate" and case_count >= 2 and avg_confidence >= 0.80:
            return "promoted"

        if candidate_type == "topic_candidate":
            if case_count >= 3:
                return "promoted"
            if case_count >= 2 and normalized_title in STABLE_OPEN_TOPIC_ALLOWLIST:
                return "promoted"

        return "validated"

    def _review_action(
        self,
        recommended_status: str,
        has_blocking: bool,
        has_quality: bool,
        has_scope_divergence: bool,
    ) -> Tuple[str, str]:
        if has_blocking:
            return ("hold_candidate_fix_source_metadata", "high")
        if has_quality:
            return ("sample_review_title_cleanup_before_upgrade", "high")
        if recommended_status == "promoted":
            return ("sample_review_then_prepare_apply_bundle", "high")
        if has_scope_divergence:
            return ("sample_review_scope_divergence", "medium")
        if recommended_status == "validated":
            return ("accept_validated_keep_out_of_kb_for_now", "low")
        return ("keep_observing_collect_more_cases", "medium")

    def _format_counter(self, counter: Dict[str, int]) -> str:
        if not counter:
            return "无"
        parts = [f"{key}={counter[key]}" for key in sorted(counter)]
        return "，".join(parts)


def print_validation_results(results: List[Dict[str, Any]]):
    for result in results:
        print(f"=== {result['case_name']} ===")
        print(f"path: {result['path']}")
        print(f"items: {result['item_count']}")
        print(f"blocking: {result['blocking_issue_count']}")
        print(f"quality: {result['quality_issue_count']}")
        if result["metadata_issues"]:
            print("metadata issues:")
            for issue in result["metadata_issues"]:
                print(f"- [{issue['severity']}] {issue['code']}: {issue['message']}")
        item_issues = [
            item_result
            for item_result in result["item_results"]
            if item_result["validation_issues"]
        ]
        if not item_issues:
            print("- no item issues")
            continue
        for item_result in item_issues:
            print(f"- item#{item_result['index']} {item_result['title']}")
            for issue in item_result["validation_issues"]:
                print(f"  - [{issue['severity']}] {issue['code']}: {issue['message']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="财务分析知识库和 W5 知识治理工具")
    parser.add_argument(
        "--runtime-config",
        help="显式指定 runtime/runtime_config.json；优先级高于环境变量和 cwd 自动搜索",
    )
    subparsers = parser.add_subparsers(dest="command")

    validate_parser = subparsers.add_parser("validate-pending", help="校验一个或多个 pending_updates.json")
    validate_parser.add_argument(
        "--input",
        nargs="+",
        default=[str(path) for path in default_pending_input_paths()],
        help="pending_updates.json 路径列表",
    )
    validate_parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 打印完整校验结果",
    )

    build_parser = subparsers.add_parser("build-review-bundle", help="构建 review bundle 和 Markdown 审核报告")
    build_parser.add_argument(
        "--input",
        nargs="*",
        default=[str(path) for path in default_pending_input_paths()],
        help="pending_updates.json 路径列表；默认使用 3 个 W6 案例",
    )
    build_parser.add_argument(
        "--output-dir",
        default=str(default_review_output_dir()),
        help="审核包输出目录",
    )
    build_parser.add_argument(
        "--print-summary",
        action="store_true",
        help="生成后额外打印高层摘要",
    )

    summary_parser = subparsers.add_parser("show-review-summary", help="读取 review bundle 并打印摘要")
    summary_parser.add_argument(
        "--bundle",
        default=str(default_review_output_dir() / "knowledge_review_bundle.json"),
        help="knowledge_review_bundle.json 路径",
    )

    return parser.parse_args()


def run_legacy_demo(runtime_config_arg: Optional[str]):
    manager = KnowledgeBaseManager(str(formal_knowledge_base_path(runtime_config_arg)))
    manager.print_summary()
    print("\n=== 搜索'融资租赁' ===")
    results = manager.search_by_keyword("融资租赁")
    for result in results:
        print(f"- [{result['section']}] {result['item']['type']}: {result['item'].get('reason', '')}")


def main():
    args = parse_args()
    governance = PendingUpdateGovernance()

    if not args.command:
        run_legacy_demo(args.runtime_config)
        return

    if args.command == "validate-pending":
        results = [governance.validate_pending_updates(path) for path in args.input]
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            print_validation_results(results)
        return

    if args.command == "build-review-bundle":
        if len(args.input) < 3:
            raise SystemExit("build-review-bundle 至少需要 3 个 pending_updates.json 输入")
        bundle = governance.build_review_bundle(args.input)
        output_paths = governance.write_review_bundle(bundle, args.output_dir)
        print(f"[OK] bundle: {output_paths['bundle_path']}")
        print(f"[OK] report: {output_paths['report_path']}")
        if args.print_summary:
            governance.print_review_summary(bundle)
        return

    if args.command == "show-review-summary":
        bundle = read_json(Path(args.bundle).resolve())
        governance.print_review_summary(bundle)
        return

    raise SystemExit(f"未知命令: {args.command}")


if __name__ == "__main__":
    main()
