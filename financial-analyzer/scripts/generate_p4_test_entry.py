#!/usr/bin/env python3
"""
P4 自动选样入口：
- 从 ChinaMoney 全市场 2024 年报池自动发现候选
- 执行过滤、去重、多样性补齐
- 输出 selection_manifest / download_config / task_seed_list
"""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from runtime_support import load_runtime_config, resolve_runtime_path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
CHINAMONEY_SCRIPT_DIR = REPO_ROOT / "chinamoney" / "scripts"
if str(CHINAMONEY_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(CHINAMONEY_SCRIPT_DIR))

from discover_reports import (  # type: ignore
    bootstrap_session,
    build_download_url,
    default_headers,
    fetch_finance_repo_page,
    head_attachment_metadata,
    sanitize_filename,
)


DEFAULT_BUCKET_ORDER = [
    "real_estate",
    "lgfv_platform",
    "industrial_energy_manufacturing",
    "consumer_services_logistics",
    "general_holding_other_nonfinancial",
]
BUCKET_TARGET = 2
BUCKET_CAP = 3
MIN_CONTENT_LENGTH = 10 * 1024 * 1024
DEFAULT_MAX_PAGES = 20
DEFAULT_PAGE_SIZE = 30
DEFAULT_SAMPLE_COUNT = 10
DEFAULT_RESERVE_COUNT = 5
DEFAULT_MAX_HEAD_CHECKS = 60

FINANCE_EXCLUDE_KEYWORDS = [
    "银行",
    "保险",
    "证券",
    "信托",
    "基金",
    "创业投资",
    "融资租赁",
    "担保",
    "资产管理",
]
ANNOUNCEMENT_EXCLUDE_KEYWORDS = [
    "公告",
    "更正",
    "变更",
    "前期会计差错",
]

MULTI_YEAR_PATTERN = re.compile(r"20\d{2}\s*[-至]\s*20\d{2}")


def now_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def timestamp_slug() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def write_json(path: Path, payload: Dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate P4 automatic 10-report entry")
    parser.add_argument("--runtime-config", help="显式指定 runtime_config.json")
    parser.add_argument("--year", type=int, default=2024, help="报告年度，默认 2024")
    parser.add_argument("--sample-count", type=int, default=DEFAULT_SAMPLE_COUNT, help="最终样本数")
    parser.add_argument("--reserve-count", type=int, default=DEFAULT_RESERVE_COUNT, help="备用样本数")
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES, help="最多扫描页数")
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE, help="每页条数")
    parser.add_argument("--max-head-checks", type=int, default=DEFAULT_MAX_HEAD_CHECKS, help="最多执行 HEAD 的候选数")
    parser.add_argument("--out-dir", help="输出目录")
    return parser.parse_args()


def extract_issuer_name(title: str, year: int) -> str:
    patterns = [
        rf"^(.*?)(?:{year}年年度报告)",
        rf"^(.*?)(?:{year}年度)",
        rf"^(.*?)(?:于{year}年12月31日)",
        rf"^(.*?)(?:截至{year}年12月31日止财务年度)",
        rf"^(.*?)(?:{year}年)",
    ]
    for pattern in patterns:
        match = re.search(pattern, title)
        if match:
            return match.group(1).strip(" -_（）()")
    return title.strip()


def normalize_issuer_name(name: str) -> str:
    value = re.sub(r"\s+", "", name.strip())
    value = re.sub(r"[^\w\u4e00-\u9fff]+", "", value, flags=re.UNICODE)
    return value.lower()


def ascii_task_id(content_id: str) -> str:
    return f"p4_2024_{content_id}"


def quick_filter_reason(title: str, suffix: str, issuer_name: str) -> str:
    if suffix.lower() != "pdf":
        return "excluded_non_pdf"
    if MULTI_YEAR_PATTERN.search(title):
        return "excluded_multi_year_bundle"
    for keyword in ANNOUNCEMENT_EXCLUDE_KEYWORDS:
        if keyword in title:
            return "excluded_announcement_noise"
    for keyword in FINANCE_EXCLUDE_KEYWORDS:
        if keyword in title or keyword in issuer_name:
            return "excluded_financial_sector"
    return ""


def classify_bucket(issuer_name: str, title: str) -> str:
    text = f"{issuer_name} {title}"
    if any(keyword in text for keyword in ["地产", "置地", "置业", "房地产", "蛇口", "龙湖", "万科", "碧桂园", "恒隆"]):
        return "real_estate"
    if any(
        keyword in text
        for keyword in [
            "建设投资",
            "开发建设",
            "城市建设",
            "城市发展",
            "国有资本投资控股",
            "城投",
            "建投",
            "城建",
            "交通投资",
            "产业投资",
            "新城控股集团",
        ]
    ):
        return "lgfv_platform"
    if any(keyword in text for keyword in ["能源", "煤业", "电力", "钢铁", "有色", "制造", "实业", "矿业", "稀土", "化工", "材料", "机械", "装备"]):
        return "industrial_energy_manufacturing"
    if any(keyword in text for keyword in ["物流", "商贸", "文旅", "酒店", "航空", "港口", "公路", "公交", "零售", "旅游", "服务", "食品", "农业"]):
        return "consumer_services_logistics"
    return "general_holding_other_nonfinancial"


def parse_release_date(value: str) -> datetime.date:
    return datetime.datetime.strptime(value, "%Y-%m-%d").date()


def quality_score(title: str, content_length: int, release_date: str) -> float:
    score = 0.0
    if "经审计" in title:
        score += 5.0
    if "附注" in title:
        score += 4.0
    if "合并及母公司财务报告" in title:
        score += 3.0
    if "年度报告" in title:
        score += 2.0
    score += min(content_length / (1024 * 1024), 40) / 10.0
    score += parse_release_date(release_date).toordinal() / 1000000.0
    return score


def pre_head_score(title: str, release_date: str) -> float:
    score = 0.0
    if "经审计" in title:
        score += 5.0
    if "附注" in title:
        score += 4.0
    if "合并及母公司财务报告" in title:
        score += 3.0
    if "年度报告" in title:
        score += 2.0
    if "审计报告" in title:
        score += 1.0
    score += parse_release_date(release_date).toordinal() / 1000000.0
    return score


def better_candidate(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    left_length = int(left.get("content_length") or 0)
    right_length = int(right.get("content_length") or 0)
    if left_length != right_length:
        return left_length > right_length
    return left.get("release_date", "") > right.get("release_date", "")


def selection_reason(candidate: Dict[str, Any]) -> str:
    size_mb = (candidate.get("content_length") or 0) / 1024 / 1024
    return (
        f"bucket={candidate['bucket']}; "
        f"size_mb={size_mb:.2f}; "
        f"size_source={candidate.get('content_length_source', 'unknown')}; "
        f"release_date={candidate['release_date']}; "
        f"score={candidate['quality_score']:.2f}"
    )


def fetch_market_candidates(
    *,
    year: int,
    page_size: int,
    max_pages: int,
) -> Dict[str, Any]:
    session = bootstrap_session()
    pages: List[Dict[str, Any]] = []
    raw_candidates: List[Dict[str, Any]] = []
    seen_content_ids = set()
    total_records = 0
    total_pages = 0

    def append_record(record: Dict[str, Any], source_kind: str):
        content_id = str(record.get("contentId", ""))
        if content_id in seen_content_ids:
            return
        seen_content_ids.add(content_id)
        raw_candidates.append(
            {
                "content_id": content_id,
                "title": str(record.get("title", "")),
                "release_date": str(record.get("releaseDate", "")),
                "draft_path": str(record.get("draftPath", "")),
                "draft_page_url": "https://www.chinamoney.com.cn" + str(record.get("draftPath", "")),
                "download_url": build_download_url(content_id),
                "channel_path": str(record.get("channelPath", "")),
                "suffix": str(record.get("suffix", "")),
                "attachment_count": int(record.get("attSize") or 0),
                "source_kind": source_kind,
            }
        )

    for page_no in range(1, max_pages + 1):
        page = fetch_finance_repo_page(
            session,
            year=year,
            report_type="4",
            org_name="",
            page_no=page_no,
            page_size=page_size,
        )
        pages.append({"page_no": page_no, "record_count": len(page["records"])})
        total_records = page["total"]
        total_pages = page["page_total_size"]

        for record in page["records"]:
            append_record(record, "market_pool")

        if page_no >= total_pages or not page["records"]:
            break

    repo_issuers = discover_repo_issuers()
    for issuer in repo_issuers:
        page = fetch_finance_repo_page(
            session,
            year=year,
            report_type="4",
            org_name=issuer,
            page_no=1,
            page_size=3,
        )
        for record in page["records"]:
            append_record(record, "repo_seed_exact_query")

    return {
        "session": session,
        "pages": pages,
        "raw_candidates": raw_candidates,
        "reported_total_records": total_records,
        "reported_total_pages": total_pages,
        "repo_seed_issuer_count": len(repo_issuers),
    }


def build_local_size_calibration() -> List[Dict[str, Any]]:
    calibration: List[Dict[str, Any]] = []
    seen = set()
    for pdf_path in sorted((REPO_ROOT / "cases").glob("*.pdf")):
        stem = pdf_path.stem
        short_name = re.sub(r"(20\d{2}).*$", "", stem).strip(" -_（）()")
        item = (
            short_name,
            pdf_path.stat().st_size,
            str(pdf_path),
        )
        if short_name and item not in seen:
            calibration.append(
                {
                    "keyword": short_name,
                    "content_length": pdf_path.stat().st_size,
                    "source_path": str(pdf_path),
                }
            )
            seen.add(item)

    company_patterns = [
        re.compile(r"- \*\*公司\*\*:\s*(.+)"),
        re.compile(r"- \*\*公司全称\*\*:\s*(.+)"),
        re.compile(r"- \*\*公司名称\*\*:\s*(.+)"),
    ]
    size_pattern = re.compile(r"- \*\*文件大小\*\*:\s*~?(\d+(?:\.\d+)?)\s*(KB|MB)", re.IGNORECASE)

    for md_path in sorted((REPO_ROOT / "cases").glob("*.md")):
        text = md_path.read_text(encoding="utf-8", errors="ignore")
        company_name = ""
        for pattern in company_patterns:
            match = pattern.search(text)
            if match:
                company_name = match.group(1).strip()
                break
        size_match = size_pattern.search(text)
        if not company_name or not size_match:
            continue
        size_value = float(size_match.group(1))
        size_unit = size_match.group(2).upper()
        if size_unit == "MB":
            content_length = int(size_value * 1024 * 1024)
        else:
            content_length = int(size_value * 1024)
        item = (company_name, content_length, str(md_path))
        if item in seen:
            continue
        calibration.append(
            {
                "keyword": company_name,
                "content_length": content_length,
                "source_path": str(md_path),
            }
        )
        seen.add(item)
    return calibration


def discover_repo_issuers() -> List[str]:
    issuers: List[str] = []
    seen = set()
    patterns = [
        re.compile(r"- \*\*公司\*\*:\s*(.+)"),
        re.compile(r"- \*\*公司全称\*\*:\s*(.+)"),
        re.compile(r"- \*\*公司名称\*\*:\s*(.+)"),
        re.compile(r"\*\*分析对象：\*\*\s*(.+?)(?:20\d{2}|$)"),
    ]
    for md_path in sorted((REPO_ROOT / "cases").glob("*.md")):
        text = md_path.read_text(encoding="utf-8", errors="ignore")
        for pattern in patterns:
            match = pattern.search(text)
            if not match:
                continue
            issuer = match.group(1).strip().strip("：:")
            issuer = issuer.split("（")[0].split("(")[0].strip()
            if issuer and issuer not in seen:
                issuers.append(issuer)
                seen.add(issuer)
            break
    return issuers


def fallback_content_length(candidate: Dict[str, Any], calibration: List[Dict[str, Any]]) -> Tuple[int, str]:
    title = candidate["title"]
    issuer_name = candidate["issuer_name"]
    for item in calibration:
        keyword = item["keyword"]
        if keyword and (keyword in issuer_name or keyword in title):
            return int(item["content_length"]), f"local_repo_calibration:{item['source_path']}"

    semantic_patterns = [
        "附注",
        "合并及母公司财务报告",
        "财务报告及母公司会计报表",
        "审计报告及财务报表",
        "经审计的财务报告",
    ]
    if any(pattern in title for pattern in semantic_patterns):
        return 12 * 1024 * 1024, "semantic_full_report_estimate"
    if "年度报告" in title and "财务报表" in title:
        return 11 * 1024 * 1024, "semantic_financial_statement_estimate"
    return 0, ""


def evaluate_candidates(
    session: Any,
    raw_candidates: List[Dict[str, Any]],
    *,
    year: int,
    max_head_checks: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    excluded: List[Dict[str, Any]] = []
    quick_pass: List[Dict[str, Any]] = []
    calibration = build_local_size_calibration()

    for candidate in raw_candidates:
        issuer_name = extract_issuer_name(candidate["title"], year)
        reason = quick_filter_reason(candidate["title"], candidate["suffix"], issuer_name)
        enriched = dict(candidate)
        enriched["issuer_name"] = issuer_name
        enriched["normalized_issuer_name"] = normalize_issuer_name(issuer_name)
        enriched["year"] = year
        if reason:
            enriched["exclusion_reason"] = reason
            excluded.append(enriched)
        else:
            enriched["bucket"] = classify_bucket(enriched["issuer_name"], enriched["title"])
            enriched["pre_head_score"] = pre_head_score(enriched["title"], enriched["release_date"])
            if enriched.get("source_kind") == "repo_seed_exact_query":
                enriched["pre_head_score"] += 20.0
            quick_pass.append(enriched)

    bucket_lists: Dict[str, List[Dict[str, Any]]] = {}
    for bucket in DEFAULT_BUCKET_ORDER:
        items = [item for item in quick_pass if item["bucket"] == bucket]
        items.sort(
            key=lambda item: (
                item["pre_head_score"],
                item["release_date"],
                item["content_id"],
            ),
            reverse=True,
        )
        bucket_lists[bucket] = items

    probe_order: List[Dict[str, Any]] = []
    probe_ids = set()
    while len(probe_order) < len(quick_pass):
        progressed = False
        for bucket in DEFAULT_BUCKET_ORDER:
            items = bucket_lists[bucket]
            if not items:
                continue
            candidate = items.pop(0)
            if candidate["content_id"] in probe_ids:
                continue
            probe_order.append(candidate)
            probe_ids.add(candidate["content_id"])
            progressed = True
        if not progressed:
            break

    qualified: List[Dict[str, Any]] = []
    head_checks = 0
    for candidate in probe_order:
        if head_checks >= max_head_checks:
            candidate["exclusion_reason"] = "excluded_head_check_budget_exhausted"
            excluded.append(candidate)
            continue
        try:
            head_meta = head_attachment_metadata(
                session,
                content_id=candidate["content_id"],
                draft_page_url=candidate["draft_page_url"],
                timeout=5,
                max_attempts=1,
            )
        except RuntimeError as exc:
            candidate["head_error"] = str(exc)
            fallback_length, fallback_source = fallback_content_length(candidate, calibration)
            if fallback_length < MIN_CONTENT_LENGTH:
                candidate["exclusion_reason"] = "excluded_attachment_head_failed"
                excluded.append(candidate)
                head_checks += 1
                continue
            candidate["content_length"] = fallback_length
            candidate["content_type"] = "application/pdf"
            candidate["content_disposition"] = ""
            candidate["content_length_source"] = fallback_source

        if "content_length" not in candidate:
            content_length = int(head_meta.get("content_length") or 0)
            candidate["attachment_head"] = head_meta
            candidate["content_length"] = content_length
            candidate["content_type"] = str(head_meta.get("content_type", ""))
            candidate["content_disposition"] = str(head_meta.get("content_disposition", ""))
            candidate["content_length_source"] = "attachment_head"
        else:
            content_length = int(candidate["content_length"])

        if content_length < MIN_CONTENT_LENGTH:
            candidate["exclusion_reason"] = "excluded_below_size_threshold"
            excluded.append(candidate)
        else:
            candidate["quality_score"] = quality_score(
                candidate["title"],
                content_length,
                candidate["release_date"],
            )
            qualified.append(candidate)
        head_checks += 1

    processed_ids = {item["content_id"] for item in qualified}
    processed_ids.update(
        item["content_id"]
        for item in excluded
        if item.get("exclusion_reason") != "excluded_financial_sector"
        and item.get("exclusion_reason") != "excluded_multi_year_bundle"
    )
    for item in probe_order:
        if item["content_id"] not in processed_ids and item["content_id"] not in {x["content_id"] for x in excluded}:
            item["exclusion_reason"] = "excluded_not_evaluated_after_early_stop"
            excluded.append(item)

    return qualified, excluded


def dedupe_candidates(qualified: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    deduped: Dict[str, Dict[str, Any]] = {}
    dedupe_events: List[Dict[str, Any]] = []
    for candidate in qualified:
        key = f"{candidate['normalized_issuer_name']}|{candidate['year']}"
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = candidate
            continue
        if better_candidate(candidate, existing):
            dedupe_events.append(
                {
                    "dedupe_key": key,
                    "kept_content_id": candidate["content_id"],
                    "replaced_content_id": existing["content_id"],
                    "reason": "prefer_larger_then_newer",
                }
            )
            deduped[key] = candidate
        else:
            dedupe_events.append(
                {
                    "dedupe_key": key,
                    "kept_content_id": existing["content_id"],
                    "replaced_content_id": candidate["content_id"],
                    "reason": "prefer_larger_then_newer",
                }
            )
    return list(deduped.values()), dedupe_events


def choose_selected_and_reserve(
    deduped: List[Dict[str, Any]],
    *,
    sample_count: int,
    reserve_count: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    ordered = sorted(
        deduped,
        key=lambda item: (
            float(item["quality_score"]),
            item.get("content_length") or 0,
            item["release_date"],
        ),
        reverse=True,
    )

    bucket_counts = {bucket: 0 for bucket in DEFAULT_BUCKET_ORDER}
    selected: List[Dict[str, Any]] = []
    selected_ids = set()

    for bucket in DEFAULT_BUCKET_ORDER:
        for candidate in ordered:
            if candidate["content_id"] in selected_ids:
                continue
            if candidate["bucket"] != bucket:
                continue
            if bucket_counts[bucket] >= BUCKET_TARGET or len(selected) >= sample_count:
                break
            selected.append(candidate)
            selected_ids.add(candidate["content_id"])
            bucket_counts[bucket] += 1

    for candidate in ordered:
        if len(selected) >= sample_count:
            break
        if candidate["content_id"] in selected_ids:
            continue
        bucket = candidate["bucket"]
        if bucket_counts.get(bucket, 0) >= BUCKET_CAP:
            continue
        selected.append(candidate)
        selected_ids.add(candidate["content_id"])
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1

    reserve: List[Dict[str, Any]] = []
    for candidate in ordered:
        if len(reserve) >= reserve_count:
            break
        if candidate["content_id"] in selected_ids:
            continue
        reserve.append(candidate)

    return selected, reserve


def build_download_task(candidate: Dict[str, Any], out_dir: Path) -> Dict[str, Any]:
    filename = sanitize_filename(f"{candidate['title']}.pdf")
    relative_path = Path("downloads") / candidate["task_id"] / filename
    return {
        "name": candidate["title"],
        "url": candidate["download_url"],
        "output_path": str(relative_path),
        "retries": 3,
        "source": {
            "content_id": candidate["content_id"],
            "draft_page_url": candidate["draft_page_url"],
            "release_date": candidate["release_date"],
        },
    }


def build_task_seed(candidate: Dict[str, Any], out_dir: Path) -> Dict[str, Any]:
    filename = sanitize_filename(f"{candidate['title']}.pdf")
    source_pdf = out_dir / "downloads" / candidate["task_id"] / filename
    return {
        "task_id": candidate["task_id"],
        "issuer": candidate["issuer_name"],
        "year": candidate["year"],
        "source_pdf": str(source_pdf),
        "md_path": str(out_dir / "markdown" / candidate["task_id"] / f"{candidate['task_id']}.md"),
        "notes_workfile": str(out_dir / "notes_workfiles" / f"{candidate['task_id']}.json"),
        "run_dir": str(out_dir / "runs" / candidate["task_id"]),
        "tags": ["p4", "autoselected", candidate["bucket"]],
        "selection_bucket": candidate["bucket"],
        "selection_reason": selection_reason(candidate),
        "source": {
            "content_id": candidate["content_id"],
            "title": candidate["title"],
            "draft_page_url": candidate["draft_page_url"],
            "download_url": candidate["download_url"],
            "release_date": candidate["release_date"],
            "content_length": candidate["content_length"],
        },
    }


def make_candidate_summary(candidate: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "task_id": candidate["task_id"],
        "issuer_name": candidate["issuer_name"],
        "normalized_issuer_name": candidate["normalized_issuer_name"],
        "year": candidate["year"],
        "bucket": candidate["bucket"],
        "content_id": candidate["content_id"],
        "title": candidate["title"],
        "release_date": candidate["release_date"],
        "draft_page_url": candidate["draft_page_url"],
        "download_url": candidate["download_url"],
        "content_length": candidate["content_length"],
        "content_length_source": candidate.get("content_length_source", ""),
        "source_kind": candidate.get("source_kind", ""),
        "quality_score": round(float(candidate["quality_score"]), 4),
        "selection_reason": selection_reason(candidate),
    }


def prepare_output_dir(args: argparse.Namespace) -> Path:
    if args.out_dir:
        return Path(args.out_dir).resolve()

    runtime_config = load_runtime_config(
        config_path=Path(args.runtime_config) if args.runtime_config else None,
        cwd=Path.cwd(),
        require_knowledge_base=True,
        ensure_state_dirs=True,
    )
    return resolve_runtime_path(runtime_config, "tmp_root") / "p4_auto_test_entry" / timestamp_slug()


def main():
    args = parse_args()
    out_dir = prepare_output_dir(args)
    out_dir.mkdir(parents=True, exist_ok=True)

    market_payload = fetch_market_candidates(
        year=args.year,
        page_size=args.page_size,
        max_pages=args.max_pages,
    )
    qualified, excluded = evaluate_candidates(
        market_payload["session"],
        market_payload["raw_candidates"],
        year=args.year,
        max_head_checks=args.max_head_checks,
    )
    deduped, dedupe_events = dedupe_candidates(qualified)

    for candidate in deduped:
        candidate["task_id"] = ascii_task_id(candidate["content_id"])

    selected, reserve = choose_selected_and_reserve(
        deduped,
        sample_count=args.sample_count,
        reserve_count=args.reserve_count,
    )

    selected_summaries = [make_candidate_summary(item) for item in selected]
    reserve_summaries = [make_candidate_summary(item) for item in reserve]
    download_tasks = [build_download_task(item, out_dir) for item in selected]
    task_seeds = [build_task_seed(item, out_dir) for item in selected]

    coverage_summary = {
        "bucket_counts": {
            bucket: sum(1 for item in selected if item["bucket"] == bucket)
            for bucket in DEFAULT_BUCKET_ORDER
        },
        "selected_count": len(selected),
        "reserve_count": len(reserve),
    }

    selection_manifest = {
        "generated_at": now_iso(),
        "out_dir": str(out_dir),
        "policy": {
            "source_pool": {
                "channel": "ChinaMoney financeRepo",
                "report_type": "4",
                "year": args.year,
                "org_name": "",
                "max_pages": args.max_pages,
                "page_size": args.page_size,
            },
            "filters": {
                "suffix": "pdf",
                "exclude_multi_year_bundle": True,
                "exclude_announcement_noise_keywords": ANNOUNCEMENT_EXCLUDE_KEYWORDS,
                "exclude_financial_sector_keywords": FINANCE_EXCLUDE_KEYWORDS,
                "min_content_length_bytes": MIN_CONTENT_LENGTH,
            },
            "dedupe": "normalized_issuer_name + year; keep larger content_length then newer release_date",
            "size_fallback": [
                "attachment_head",
                "local_repo_calibration",
                "semantic_full_report_estimate",
            ],
            "diversity_targets": {
                "bucket_target": BUCKET_TARGET,
                "bucket_cap": BUCKET_CAP,
                "bucket_order": DEFAULT_BUCKET_ORDER,
            },
        },
        "candidate_pool_summary": {
            "reported_total_records": market_payload["reported_total_records"],
            "reported_total_pages": market_payload["reported_total_pages"],
            "fetched_page_count": len(market_payload["pages"]),
            "raw_candidate_count": len(market_payload["raw_candidates"]),
            "repo_seed_issuer_count": market_payload.get("repo_seed_issuer_count", 0),
            "qualified_before_dedupe_count": len(qualified),
            "qualified_after_dedupe_count": len(deduped),
            "excluded_count": len(excluded),
        },
        "dedupe_events": dedupe_events,
        "excluded_candidates": excluded,
        "selected_candidates": selected_summaries,
        "reserve_candidates": reserve_summaries,
        "coverage_summary": coverage_summary,
    }
    download_config = {
        "generated_at": now_iso(),
        "output_dir": str(out_dir),
        "tasks": download_tasks,
    }
    task_seed_list = {
        "generated_at": now_iso(),
        "task_count": len(task_seeds),
        "tasks": task_seeds,
    }

    write_json(out_dir / "selection_manifest.json", selection_manifest)
    write_json(out_dir / "download_config.json", download_config)
    write_json(out_dir / "task_seed_list.json", task_seed_list)

    print(f"[OK] 输出目录: {out_dir}")
    print(f"[OK] selected={len(selected)}, reserve={len(reserve)}")
    print(f"[OK] selection_manifest: {out_dir / 'selection_manifest.json'}")
    print(f"[OK] download_config: {out_dir / 'download_config.json'}")
    print(f"[OK] task_seed_list: {out_dir / 'task_seed_list.json'}")


if __name__ == "__main__":
    main()
