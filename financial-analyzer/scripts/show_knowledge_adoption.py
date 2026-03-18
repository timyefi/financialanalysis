#!/usr/bin/env python3
"""
展示 knowledge adoption 日志摘要。
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from adoption_record_utils import normalize_audit, normalize_hashes, normalize_identity, normalize_review, normalize_source
from runtime_support import RuntimeConfigError, load_runtime_config, resolve_runtime_path


def read_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="展示 knowledge adoption 日志摘要")
    parser.add_argument("--runtime-config", help="显式指定 runtime/runtime_config.json")
    parser.add_argument("--limit", type=int, default=20, help="最多展示最近 N 条日志")
    return parser.parse_args()



def main():
    args = parse_args()
    try:
        runtime_config = load_runtime_config(
            config_path=Path(args.runtime_config) if args.runtime_config else None,
            cwd=Path.cwd(),
            require_knowledge_base=True,
            ensure_state_dirs=True,
        )
    except RuntimeConfigError as exc:
        raise SystemExit(str(exc)) from exc

    adoption_log_dir = resolve_runtime_path(runtime_config, "knowledge_adoption_log_dir")
    log_paths: List[Path] = sorted(adoption_log_dir.glob("*.log.json"))[-max(args.limit, 1):]
    if not log_paths:
        print("[INFO] adoption_logs 为空")
        return

    for path in log_paths:
        payload = read_json(path)
        identity = normalize_identity(payload)
        source = normalize_source(payload)
        review = normalize_review(payload)
        hashes = normalize_hashes(payload)
        audit = normalize_audit(payload)
        print(f"=== {path.name} ===")
        print(f"adoption_id: {identity.get('adoption_id', '')}")
        print(f"logged_at: {identity.get('logged_at', '')}")
        print(f"result: {identity.get('result', '')}")
        print(f"case: {source.get('case_name', source.get('issuer', ''))}")
        print(f"chapter: {source.get('chapter_no', '')} {source.get('chapter_title', '')}")
        print(f"review_state: {review.get('review_state', '')}")
        print(f"before_hash: {hashes.get('before_hash', '')}")
        print(f"after_hash: {hashes.get('after_hash', '')}")
        print(f"summary: {audit.get('summary', '')}")
        print()


if __name__ == "__main__":
    main()
