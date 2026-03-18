#!/usr/bin/env python3
"""
正式知识库审计与 adoption log 运维工具。

历史 pending_updates / review bundle 入口已降级为兼容别名，不再作为主路径。
"""

import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from adoption_record_utils import normalize_audit, normalize_hashes, normalize_identity, normalize_review, normalize_source
from runtime_support import RuntimeConfigError, load_runtime_config, resolve_runtime_path


def now_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def script_root() -> Path:
    return Path(__file__).resolve().parent.parent


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


def formal_adoption_log_dir(runtime_config_arg: Optional[str]) -> Path:
    runtime_config = load_formal_runtime_config(runtime_config_arg)
    return resolve_runtime_path(runtime_config, "knowledge_adoption_log_dir")


def walk_strings(value: Any, path: str = "") -> Iterable[Tuple[str, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            yield from walk_strings(child, child_path)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            child_path = f"{path}[{index}]"
            yield from walk_strings(child, child_path)
        return
    if isinstance(value, str) and value.strip():
        yield path or "$", value


def count_nodes(value: Any) -> int:
    if isinstance(value, dict):
        return 1 + sum(count_nodes(child) for child in value.values())
    if isinstance(value, list):
        return 1 + sum(count_nodes(child) for child in value)
    return 1


class KnowledgeBaseManager:
    def __init__(self, kb_path: str):
        self.kb_path = Path(kb_path)
        self.kb = self._load()

    def _load(self) -> Dict[str, Any]:
        return read_json(self.kb_path)

    def get_version(self) -> str:
        metadata = self.kb.get("metadata") or {}
        return str(metadata.get("version", "unknown"))

    def validate_schema(self) -> List[str]:
        errors: List[str] = []
        if not isinstance(self.kb, dict):
            return ["knowledge_base 顶层必须是对象"]
        if not isinstance(self.kb.get("metadata"), dict):
            errors.append("knowledge_base 缺少 metadata 对象")
        if not isinstance(self.kb.get("knowledge"), dict):
            errors.append("knowledge_base 缺少 knowledge 对象")
        return errors

    def search_by_keyword(self, keyword: str) -> List[Dict[str, str]]:
        keyword_norm = str(keyword or "").strip().lower()
        if not keyword_norm:
            return []

        results: List[Dict[str, str]] = []
        for path, value in walk_strings(self.kb):
            if keyword_norm in value.lower():
                results.append({"path": path, "value": value})
        return results

    def print_summary(self):
        metadata = self.kb.get("metadata") or {}
        knowledge = self.kb.get("knowledge") or {}
        print("=== 财务分析正式知识库 ===")
        print(f"版本: {metadata.get('version', 'unknown')}")
        print(f"更新: {metadata.get('last_updated', 'unknown')}")
        print(f"来源: {metadata.get('source', 'N/A')}")
        print(f"节点数: {count_nodes(self.kb)}")
        print(f"knowledge_sources: {len(self.kb.get('knowledge_sources') or [])}")
        print(f"knowledge.sections: {len(knowledge)}")

        included = (((knowledge.get("interest_bearing_debt") or {}).get("criteria") or {}).get("included") or [])
        excluded = (((knowledge.get("interest_bearing_debt") or {}).get("criteria") or {}).get("excluded") or [])
        if included or excluded:
            print(f"有息债务判定: {len(included)} 项(含) / {len(excluded)} 项(不含)")

        indicators = knowledge.get("indicators") or {}
        if indicators:
            solvency = (indicators.get("solvency") or {})
            short_term = solvency.get("short_term") or []
            long_term = solvency.get("long_term") or []
            profitability = indicators.get("profitability") or []
            cashflow = ((indicators.get("cashflow") or {}).get("debt_coverage") or [])
            leverage = ((indicators.get("leverage") or {}).get("core") or [])
            print(f"偿债指标: {len(short_term) + len(long_term)} 项")
            print(f"盈利指标: {len(profitability)} 项")
            print(f"现金流指标: {len(cashflow)} 项")
            print(f"杠杆指标: {len(leverage)} 项")

    def print_keyword_hits(self, keyword: str):
        results = self.search_by_keyword(keyword)
        if not results:
            print(f"未找到关键词: {keyword}")
            return
        print(f"=== 关键词命中: {keyword} ===")
        for item in results[:50]:
            print(f"- {item['path']}: {item['value']}")


def load_adoption_logs(runtime_config_arg: Optional[str], limit: int) -> List[Dict[str, Any]]:
    adoption_log_dir = formal_adoption_log_dir(runtime_config_arg)
    if not adoption_log_dir.exists():
        return []
    paths = sorted(adoption_log_dir.glob("*.log.json"), key=lambda path: path.stat().st_mtime)
    selected = paths[-max(limit, 1):]
    return [read_json(path) for path in selected]


def summarize_adoption_logs(runtime_config_arg: Optional[str], limit: int = 10) -> Dict[str, Any]:
    logs = load_adoption_logs(runtime_config_arg, limit=limit)
    case_counts: Dict[str, int] = {}
    chapter_counts: Dict[str, int] = {}
    for log in logs:
        source = log.get("source") or {}
        case_name = str(source.get("case_name") or "unknown")
        chapter_no = str(source.get("chapter_no") or "unknown")
        case_counts[case_name] = case_counts.get(case_name, 0) + 1
        chapter_counts[chapter_no] = chapter_counts.get(chapter_no, 0) + 1
    return {
        "generated_at": now_iso(),
        "log_count": len(logs),
        "case_counts": case_counts,
        "chapter_counts": chapter_counts,
        "logs": logs,
    }


def print_adoption_summary(runtime_config_arg: Optional[str], limit: int = 10):
    summary = summarize_adoption_logs(runtime_config_arg, limit=limit)
    print("=== adoption log 摘要 ===")
    print(f"最近日志数: {summary['log_count']}")
    print(f"案例分布: {format_counter(summary['case_counts'])}")
    print(f"章节分布: {format_counter(summary['chapter_counts'])}")
    for log in summary["logs"]:
        identity = normalize_identity(log)
        source = normalize_source(log)
        review = normalize_review(log)
        hashes = normalize_hashes(log)
        audit = normalize_audit(log)
        print(
            "- "
            f"{identity.get('logged_at', 'unknown')} "
            f"{source.get('case_name', 'unknown')}#"
            f"{source.get('chapter_no', 'unknown')} "
            f"{source.get('chapter_title', '')}"
        )
        print(f"  result: {identity.get('result', 'unknown')} review_state: {review.get('review_state', 'unknown')}")
        if audit.get("summary"):
            print(f"  summary: {audit['summary']}")
        print(f"  before_hash: {hashes.get('before_hash', '')}")
        print(f"  after_hash: {hashes.get('after_hash', '')}")


def format_counter(counter: Dict[str, int]) -> str:
    if not counter:
        return "无"
    return "，".join(f"{key}={counter[key]}" for key in sorted(counter))


def print_deprecation(name: str, replacement: str):
    print(f"[DEPRECATED] `{name}` 已降级，不再是主路径；请改用 `{replacement}`。", file=sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="财务分析正式知识库与 adoption log 运维工具")
    parser.add_argument(
        "--runtime-config",
        help="显式指定 runtime/runtime_config.json；优先级高于环境变量和 cwd 自动搜索",
    )
    subparsers = parser.add_subparsers(dest="command")

    kb_parser = subparsers.add_parser("show-kb-summary", help="打印正式知识库摘要")
    kb_parser.add_argument("--keyword", help="可选关键词检索")

    validate_parser = subparsers.add_parser("validate-kb", help="校验正式知识库基础结构")

    adoption_parser = subparsers.add_parser("show-adoption-summary", help="打印 adoption log 摘要")
    adoption_parser.add_argument("--limit", type=int, default=10, help="最多展示最近多少条日志")

    legacy_validate = subparsers.add_parser("validate-pending", help="兼容旧命令：打印正式知识库摘要")
    legacy_validate.add_argument("--keyword", help="可选关键词检索")

    legacy_bundle = subparsers.add_parser("build-review-bundle", help="兼容旧命令：打印 adoption log 摘要")
    legacy_bundle.add_argument("--limit", type=int, default=10, help="最多展示最近多少条日志")

    legacy_summary = subparsers.add_parser("show-review-summary", help="兼容旧命令：打印 adoption log 摘要")
    legacy_summary.add_argument("--limit", type=int, default=10, help="最多展示最近多少条日志")

    return parser.parse_args()


def run_default(runtime_config_arg: Optional[str]):
    manager = KnowledgeBaseManager(str(formal_knowledge_base_path(runtime_config_arg)))
    manager.print_summary()
    print("\n=== 搜索 '融资租赁' ===")
    manager.print_keyword_hits("融资租赁")


def main():
    args = parse_args()

    if not args.command:
        run_default(args.runtime_config)
        return

    if args.command == "show-kb-summary":
        manager = KnowledgeBaseManager(str(formal_knowledge_base_path(args.runtime_config)))
        manager.print_summary()
        if args.keyword:
            print("")
            manager.print_keyword_hits(args.keyword)
        return

    if args.command == "validate-kb":
        manager = KnowledgeBaseManager(str(formal_knowledge_base_path(args.runtime_config)))
        errors = manager.validate_schema()
        if errors:
            for error in errors:
                print(f"[ERROR] {error}", file=sys.stderr)
            raise SystemExit(1)
        print("[OK] formal knowledge_base schema looks valid")
        return

    if args.command == "show-adoption-summary":
        print_adoption_summary(args.runtime_config, limit=args.limit)
        return

    if args.command == "validate-pending":
        print_deprecation("validate-pending", "show-kb-summary / validate-kb")
        manager = KnowledgeBaseManager(str(formal_knowledge_base_path(args.runtime_config)))
        manager.print_summary()
        if getattr(args, "keyword", None):
            print("")
            manager.print_keyword_hits(args.keyword)
        return

    if args.command in {"build-review-bundle", "show-review-summary"}:
        print_deprecation(args.command, "show-adoption-summary")
        print_adoption_summary(args.runtime_config, limit=getattr(args, "limit", 10))
        return

    raise SystemExit(f"未知命令: {args.command}")


if __name__ == "__main__":
    main()
