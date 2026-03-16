#!/usr/bin/env python3
"""
附注优先的财务分析主脚本。
"""

import argparse
import collections
import datetime
import hashlib
import json
import re
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill


if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


ENGINE_VERSION = "3.0.0"

TOPIC_PATTERNS = {
    "audit": ["核数师", "审计", "审计意见", "保留意见", "无法表示意见", "否定意见"],
    "debt": ["借贷", "借款", "债券", "贷款", "融资", "票据", "债项"],
    "cash": ["现金", "现金流", "银行存款", "受限资金", "货币资金"],
    "profitability": ["收入", "利润", "溢利", "毛利", "EBITDA", "收益"],
    "liquidity": ["流动", "短期", "到期", "偿债", "再融资", "期限结构"],
    "investment_property": ["投资物业", "公允价值", "估值", "资本化率", "物业估值"],
    "risk_management": ["风险", "掉期", "对冲", "汇率", "利率", "契约"],
    "governance": ["董事会", "管治", "薪酬", "合规", "股东"],
    "sustainability": ["可持续", "碳", "环保", "绿色融资", "ESG"],
    "tax": ["税项", "递延税项", "所得税", "税率"],
}

RISK_RULES = [
    {"name": "extreme_audit_issue", "severity": "extreme", "patterns": ["无法表示意见", "否定意见"]},
    {"name": "high_audit_issue", "severity": "high", "patterns": ["保留意见", "持续经营"]},
    {"name": "litigation_or_default", "severity": "high", "patterns": ["违约", "逾期", "诉讼", "仲裁"]},
    {"name": "liquidity_pressure", "severity": "high", "patterns": ["一年内到期", "再融资", "短期债务", "流动性风险"]},
    {"name": "asset_impairment", "severity": "high", "patterns": ["减值", "减值准备", "公允价值减少"]},
    {"name": "restricted_cash", "severity": "medium", "patterns": ["受限资金", "受限制", "质押"]},
    {"name": "interest_capitalization", "severity": "medium", "patterns": ["资本化之借贷支出", "利息资本化", "资本化利息"]},
    {"name": "guarantee_exposure", "severity": "medium", "patterns": ["担保", "反担保"]},
    {"name": "fx_or_rate_exposure", "severity": "medium", "patterns": ["汇率", "利率掉期", "货币掉期", "净投资对冲"]},
]

STOPWORDS = {
    "目录",
    "附注",
    "章节",
    "项目",
    "年度",
    "报告",
    "综合",
    "本集团",
    "本公司",
    "第",
    "项",
    "表",
}

SEVERITY_SCORE = {
    "extreme": 100,
    "high": 70,
    "medium": 45,
    "low": 20,
}


def read_text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def write_json(path, payload):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_lines(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().splitlines()


def md5_file(path):
    digest = hashlib.md5()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_text(text):
    text = text.replace("\ufeff", "")
    text = re.sub(r"\r\n?", "\n", text)
    return text


def clean_line(line):
    line = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", line)
    line = re.sub(r"<[^>]+>", " ", line)
    line = re.sub(r"\s+", " ", line)
    return line.strip()


def shorten(text, limit=120):
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def fallback_company_name(stem):
    cleaned = re.sub(r"(20\d{2}).*$", "", stem)
    cleaned = re.sub(r"[（(].*?[)）]", "", cleaned)
    return cleaned.strip("-_ ")


def extract_company_name(text, fallback_name):
    patterns = [
        r"^\s*([^\n]{2,40}?(?:股份有限公司|集团股份有限公司|有限公司|集团有限公司))(?:（|\(|\s|$)",
        r"公司名称[：:]\s*([^\n]{2,50})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.MULTILINE)
        if match:
            return match.group(1).strip()
    return fallback_company_name(fallback_name)


def extract_report_period(text, fallback_name):
    stem_match = re.search(r"(20\d{2})", fallback_name)
    if stem_match:
        return stem_match.group(1)

    patterns = [
        r"(20\d{2})年度报告",
        r"(20\d{2})年年度报告",
        r"(20\d{2})年报",
        r"截至(20\d{2})年12月31日止年度",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return ""


def detect_currency(text):
    if "港币" in text or "港元" in text:
        return "HKD"
    if "美元" in text or "USD" in text:
        return "USD"
    return "CNY"


def classify_report(text, md_path):
    lower_name = md_path.name.lower()
    report_type = "a_share_full_report"
    basis = []

    if "香港财务报告准则" in text or "港币" in text or "hkfrs" in lower_name or "年報" in md_path.name:
        report_type = "hong_kong_full_report"
        basis.append("检测到港币/HKFRS/年報字样")
    elif "交易商协会" in text or ("合并资产负债表" not in text and "财务报表附注" not in text):
        report_type = "nfmii_brief_report"
        basis.append("未检测到完整报表与附注结构")
    else:
        basis.append("检测到完整财务报表与附注结构")

    if re.search(r"无法表示意见", text):
        audit_opinion = "无法表示意见"
    elif re.search(r"否定意见", text):
        audit_opinion = "否定意见"
    elif re.search(r"我们认为[\s\S]{0,200}真实而中肯地反映", text):
        audit_opinion = "标准无保留"
    elif re.search(r"保留意见的基础|发表保留意见", text):
        audit_opinion = "保留意见"
    elif re.search(r"强调事项", text):
        audit_opinion = "带强调事项"
    else:
        audit_opinion = "未识别"

    return {
        "report_type": report_type,
        "audit_opinion": audit_opinion,
        "classification_basis": basis,
    }


def resolve_run_dir(run_dir_arg):
    run_dir = Path(run_dir_arg).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def load_notes_workfile(notes_workfile_path, total_lines):
    notes_workfile = Path(notes_workfile_path).resolve()
    if not notes_workfile.exists():
        raise FileNotFoundError(f"notes_workfile 不存在: {notes_workfile}")

    with open(notes_workfile, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    required_fields = [
        "notes_start_line",
        "notes_end_line",
        "locator_evidence",
        "notes_catalog",
    ]
    missing_fields = [field for field in required_fields if field not in payload]
    if missing_fields:
        raise ValueError(f"notes_workfile 缺少字段: {', '.join(missing_fields)}")

    notes_start_line = payload["notes_start_line"]
    notes_end_line = payload["notes_end_line"]
    notes_catalog = payload["notes_catalog"]
    locator_evidence = payload["locator_evidence"]

    if not isinstance(notes_start_line, int) or not isinstance(notes_end_line, int):
        raise ValueError("notes_start_line 和 notes_end_line 必须为整数")
    if notes_start_line < 1 or notes_end_line < notes_start_line or notes_end_line > total_lines:
        raise ValueError("附注区间无效")
    if not isinstance(locator_evidence, list) or not locator_evidence:
        raise ValueError("locator_evidence 不能为空")
    if not isinstance(notes_catalog, list) or not notes_catalog:
        raise ValueError("notes_catalog 不能为空")

    normalized_catalog = []
    required_note_fields = ["note_no", "chapter_title", "start_line", "end_line", "evidence"]
    previous_end_line = notes_start_line - 1
    for index, note in enumerate(notes_catalog, start=1):
        missing_note_fields = [field for field in required_note_fields if field not in note]
        if missing_note_fields:
            raise ValueError(f"notes_catalog 第 {index} 项缺少字段: {', '.join(missing_note_fields)}")

        chapter_title = str(note["chapter_title"]).strip()
        start_line = note["start_line"]
        end_line = note["end_line"]
        evidence = note["evidence"]

        if not chapter_title:
            raise ValueError(f"notes_catalog 第 {index} 项 chapter_title 不能为空")
        if not isinstance(start_line, int) or not isinstance(end_line, int):
            raise ValueError(f"notes_catalog 第 {index} 项边界必须为整数")
        if start_line < notes_start_line or end_line > notes_end_line or end_line < start_line:
            raise ValueError(f"notes_catalog 第 {index} 项边界超出附注区间")
        if start_line <= previous_end_line:
            raise ValueError(f"notes_catalog 第 {index} 项边界未按顺序排列")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError(f"notes_catalog 第 {index} 项 evidence 不能为空")

        normalized_catalog.append({
            "note_no": str(note["note_no"]).strip(),
            "chapter_title": chapter_title,
            "start_line": start_line,
            "end_line": end_line,
            "evidence": evidence,
        })
        previous_end_line = end_line

    return {
        "path": str(notes_workfile),
        "notes_start_line": notes_start_line,
        "notes_end_line": notes_end_line,
        "locator_evidence": locator_evidence,
        "notes_catalog": normalized_catalog,
    }


def split_sentences(text):
    text = clean_line(text)
    parts = re.split(r"[。！？!?；;\n]+", text)
    return [item.strip() for item in parts if len(item.strip()) >= 8]


def summarize_chapter(text):
    sentences = split_sentences(text)
    if not sentences:
        return "章节内容较少，保留原始证据以待后续补充。"
    return "；".join(sentences[:2])


def numeric_value(raw):
    raw = raw.replace(",", "").strip()
    raw = raw.rstrip("%")
    try:
        return float(raw)
    except ValueError:
        return None


def detect_unit(line):
    candidates = [
        "港币百万元",
        "人民币百万元",
        "亿港元",
        "亿元",
        "亿",
        "百万",
        "万元",
        "元",
        "%",
        "倍",
    ]
    for candidate in candidates:
        if candidate in line:
            return candidate
    return ""


def extract_numeric_data(text, limit=12):
    entries = []
    seen_lines = set()
    for raw_line in text.splitlines():
        line = clean_line(raw_line)
        if not line or line in seen_lines:
            continue
        if not re.search(r"\d", line):
            continue
        matches = re.findall(r"(?<!\d)(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?", line)
        if not matches:
            continue

        seen_lines.add(line)
        value = numeric_value(matches[0])
        prefix = line.split(matches[0], 1)[0].strip(" ：:，,.-")
        label = shorten(prefix or line, limit=40)
        entries.append({
            "label": label or "数值片段",
            "value": value,
            "raw_value": matches[0],
            "unit": detect_unit(line),
            "evidence": shorten(line, limit=160),
        })

    entries.sort(
        key=lambda item: (
            0 if item["value"] is None else -abs(item["value"]),
            item["label"],
        )
    )
    return entries[:limit]


def extract_title_tokens(title):
    tokens = []
    for token in re.findall(r"[A-Za-z]{2,}|[\u4e00-\u9fff]{2,12}", title):
        candidate = token.strip()
        if candidate in STOPWORDS:
            continue
        if candidate.startswith("财务报表"):
            continue
        if candidate not in tokens:
            tokens.append(candidate)
    return tokens


def infer_topics(title, text):
    topics = []
    content = f"{title}\n{text}"

    for topic_name, patterns in TOPIC_PATTERNS.items():
        if any(pattern in content for pattern in patterns):
            topics.append(topic_name)

    for token in extract_title_tokens(title):
        if token not in topics:
            topics.append(token)

    if not topics:
        topics.append("general")

    return topics[:8]


def find_evidence_lines(text, patterns, limit=2):
    evidences = []
    for raw_line in text.splitlines():
        line = clean_line(raw_line)
        if not line:
            continue
        if any(pattern in line for pattern in patterns):
            evidences.append(shorten(line, limit=160))
        if len(evidences) >= limit:
            break
    return evidences


def build_findings(title, text, topic_tags, numeric_data):
    findings = []
    candidate_sentences = split_sentences(text)

    for sentence in candidate_sentences:
        if len(findings) >= 4:
            break
        if re.search(r"\d", sentence) or any(tag in sentence for tag in topic_tags if len(tag) >= 2):
            findings.append({
                "finding_name": shorten(f"{title}关键信息", limit=40),
                "detail": shorten(sentence, limit=160),
                "topics": topic_tags[:3],
                "confidence": "medium",
            })

    if not findings:
        findings.append({
            "finding_name": shorten(f"{title}章节概览", limit=40),
            "detail": summarize_chapter(text),
            "topics": topic_tags[:3],
            "confidence": "medium",
        })

    if numeric_data and len(findings) < 5:
        first_numeric = numeric_data[0]
        findings.append({
            "finding_name": shorten(f"{title}数值提要", limit=40),
            "detail": first_numeric["evidence"],
            "topics": topic_tags[:3],
            "confidence": "medium",
        })

    return findings[:5]


def build_anomalies(text):
    anomalies = []
    for rule in RISK_RULES:
        evidence_lines = find_evidence_lines(text, rule["patterns"], limit=2)
        if not evidence_lines:
            continue
        anomalies.append({
            "signal_name": rule["name"],
            "severity": rule["severity"],
            "evidence": evidence_lines,
            "impact_hint": f"检测到 {', '.join(rule['patterns'][:2])} 相关表述",
        })
    return anomalies


def build_evidence(title, text, numeric_data, anomalies):
    evidence = []
    summary = summarize_chapter(text)
    if summary:
        evidence.append({
            "source": title,
            "type": "summary",
            "content": summary,
        })

    for item in numeric_data[:4]:
        evidence.append({
            "source": title,
            "type": "numeric_data",
            "content": item["evidence"],
        })

    for anomaly in anomalies[:3]:
        for line in anomaly["evidence"]:
            evidence.append({
                "source": title,
                "type": "risk_signal",
                "content": line,
            })

    return evidence[:8]


def build_chapter_record(index, note_entry, markdown_lines, report_context, locator_evidence):
    text = "\n".join(markdown_lines[note_entry["start_line"] - 1:note_entry["end_line"]]).strip()
    cleaned_text = normalize_text(text)
    chapter_title = f"{note_entry['note_no']} {note_entry['chapter_title']}".strip()
    topic_tags = infer_topics(chapter_title, cleaned_text)
    numeric_data = extract_numeric_data(cleaned_text)
    anomalies = build_anomalies(cleaned_text)
    findings = build_findings(chapter_title, cleaned_text, topic_tags, numeric_data)
    evidence = build_evidence(chapter_title, cleaned_text, numeric_data, anomalies)
    status = "completed" if cleaned_text else "empty"

    return {
        "chapter_no": index,
        "chapter_title": chapter_title,
        "status": status,
        "summary": summarize_chapter(cleaned_text),
        "attributes": {
            "chapter_type": "notes_chapter",
            "note_no": note_entry["note_no"],
            "note_scope": "notes_only",
            "locator_evidence": locator_evidence,
            "topic_tags": topic_tags,
            "line_span": {
                "start": note_entry["start_line"],
                "end": note_entry["end_line"],
            },
            "line_count": note_entry["end_line"] - note_entry["start_line"] + 1,
            "char_count": len(cleaned_text),
            "table_count": cleaned_text.count("<table>"),
            "image_count": cleaned_text.count("![]("),
            "report_type": report_context["report_type"],
        },
        "numeric_data": numeric_data,
        "findings": findings,
        "anomalies": anomalies,
        "evidence": evidence,
        "extensions": {
            "raw_title_tokens": extract_title_tokens(chapter_title),
            "section_evidence": note_entry["evidence"],
            "dynamic_topics": [tag for tag in topic_tags if tag not in TOPIC_PATTERNS],
        },
    }


def group_focus_candidates(chapter_records):
    grouped = {}
    for record in chapter_records:
        base_topics = record["attributes"]["topic_tags"][:3] or ["general"]
        for anomaly in record["anomalies"]:
            key = anomaly["signal_name"]
            grouped.setdefault(key, {
                "focus_name": key,
                "score": 0,
                "severity": anomaly["severity"],
                "evidence_chapters": set(),
                "related_topics": set(base_topics),
                "evidence_samples": [],
            })
            item = grouped[key]
            item["score"] += SEVERITY_SCORE.get(anomaly["severity"], 20)
            item["evidence_chapters"].add(record["chapter_no"])
            item["related_topics"].update(base_topics)
            item["evidence_samples"].extend(anomaly["evidence"][:1])

        if record["numeric_data"]:
            key = base_topics[0]
            grouped.setdefault(key, {
                "focus_name": key,
                "score": 0,
                "severity": "low",
                "evidence_chapters": set(),
                "related_topics": set(base_topics),
                "evidence_samples": [],
            })
            item = grouped[key]
            item["score"] += min(len(record["numeric_data"]) * 4, 20)
            item["evidence_chapters"].add(record["chapter_no"])
            item["related_topics"].update(base_topics)
            item["evidence_samples"].extend(
                [entry["evidence"] for entry in record["numeric_data"][:1]]
            )

    return grouped


def build_focus_list(chapter_records):
    candidates = list(group_focus_candidates(chapter_records).values())
    candidates.sort(key=lambda item: (-item["score"], item["focus_name"]))

    focus_list = []
    for candidate in candidates[:6]:
        evidence_chapters = sorted(candidate["evidence_chapters"])
        focus_list.append({
            "focus_name": candidate["focus_name"],
            "why_selected": shorten(
                "基于章节证据密度与风险信号强度自动选出，需在综合分析时优先展开。",
                limit=80,
            ),
            "evidence_chapters": evidence_chapters,
            "focus_attributes": {
                "severity": candidate["severity"],
                "score": candidate["score"],
                "evidence_count": len(candidate["evidence_samples"]),
            },
            "related_topics": sorted(candidate["related_topics"]),
            "knowledge_gap": (
                "待确认是否需要沉淀为正式规则"
                if candidate["focus_name"] not in TOPIC_PATTERNS
                else "已有主题，可继续补充案例证据"
            ),
            "impact_scope": sorted(candidate["related_topics"])[:3],
        })
    return focus_list


def aggregate_topic_results(chapter_records):
    topic_map = collections.OrderedDict()
    for record in chapter_records:
        for topic in record["attributes"]["topic_tags"]:
            if topic not in topic_map:
                topic_map[topic] = {
                    "summary_parts": [],
                    "chapters": [],
                    "numeric_highlights": [],
                    "anomalies": [],
                }
            bucket = topic_map[topic]
            bucket["summary_parts"].append(record["summary"])
            bucket["chapters"].append(record["chapter_no"])
            bucket["numeric_highlights"].extend(record["numeric_data"][:2])
            bucket["anomalies"].extend(record["anomalies"][:2])

    results = {}
    for topic, bucket in topic_map.items():
        results[topic] = {
            "summary": shorten("；".join(bucket["summary_parts"][:3]), limit=200),
            "attributes": {
                "chapter_count": len(sorted(set(bucket["chapters"]))),
                "chapter_refs": sorted(set(bucket["chapters"])),
            },
            "evidence": [item["evidence"] for item in bucket["numeric_highlights"][:4]],
            "extensions": {
                "risk_signals": bucket["anomalies"][:3],
            },
        }
    return results


def build_final_data(report_context, chapter_records, focus_list):
    topic_results = aggregate_topic_results(chapter_records)
    conclusions = []

    conclusions.append(
        f"报告类型识别为 {report_context['report_type']}，审计意见为 {report_context['audit_opinion']}。"
    )
    if focus_list:
        conclusions.append(
            f"本次动态重点共 {len(focus_list)} 项，优先关注 {focus_list[0]['focus_name']}。"
        )
    conclusions.append(
        f"附注章节记录共生成 {len(chapter_records)} 条，覆盖章节 {chapter_records[0]['chapter_no']} 至 {chapter_records[-1]['chapter_no']}。"
    )

    return {
        "entity_profile": {
            "company_name": report_context["company_name"],
            "report_period": report_context["report_period"],
            "currency": report_context["currency"],
            "report_type": report_context["report_type"],
            "audit_opinion": report_context["audit_opinion"],
            "input_file": report_context["input_file"],
        },
        "key_conclusions": conclusions,
        "topic_results": topic_results,
        "extensions": {
            "focus_count": len(focus_list),
            "chapter_count": len(chapter_records),
            "classification_basis": report_context["classification_basis"],
        },
    }


def report_scope_hint(topic_tags):
    if "investment_property" in topic_tags:
        return "适用于投资性房地产占比较高的地产企业"
    if "debt" in topic_tags or "liquidity" in topic_tags:
        return "适用于存在明显债务融资结构的发行人"
    if "audit" in topic_tags:
        return "适用于所有需要审计意见判断的完整年报"
    return "适用于案例相近的完整年报分析"


def build_pending_updates(chapter_records):
    items = []
    seen_titles = set()

    for record in chapter_records:
        for topic in record["extensions"]["dynamic_topics"]:
            if topic in seen_titles:
                continue
            seen_titles.add(topic)
            items.append({
                "type": "topic_candidate",
                "title": topic,
                "proposal": f"将章节主题“{topic}”作为开放主题标签候选，等待更多案例验证。",
                "source": f"chapter_{record['chapter_no']}",
                "evidence": record["evidence"][:2],
                "applicable_scope": report_scope_hint(record["attributes"]["topic_tags"]),
                "status": "candidate",
                "introduced_in": ENGINE_VERSION,
                "confidence": "medium",
            })

        for item in record["numeric_data"][:2]:
            label = item["label"]
            if len(label) < 4 or label in seen_titles:
                continue
            seen_titles.add(label)
            items.append({
                "type": "field_candidate",
                "title": label,
                "proposal": f"新增可选扩展字段“{label}”，保留为案例级扩展载荷。",
                "source": f"chapter_{record['chapter_no']}",
                "evidence": [{"source": record["chapter_title"], "type": "numeric_data", "content": item["evidence"]}],
                "applicable_scope": report_scope_hint(record["attributes"]["topic_tags"]),
                "status": "candidate",
                "introduced_in": ENGINE_VERSION,
                "confidence": "low",
            })

        for anomaly in record["anomalies"]:
            if anomaly["signal_name"] in seen_titles:
                continue
            seen_titles.add(anomaly["signal_name"])
            items.append({
                "type": "rule_candidate",
                "title": anomaly["signal_name"],
                "proposal": f"补充“{anomaly['signal_name']}”识别规则，并明确证据模式与适用范围。",
                "source": f"chapter_{record['chapter_no']}",
                "evidence": [{"source": record["chapter_title"], "type": "risk_signal", "content": line} for line in anomaly["evidence"]],
                "applicable_scope": report_scope_hint(record["attributes"]["topic_tags"]),
                "status": "candidate",
                "introduced_in": ENGINE_VERSION,
                "confidence": anomaly["severity"],
            })

        if len(items) >= 12:
            break

    return {
        "metadata": {
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "required_fields": [
                "source",
                "evidence",
                "applicable_scope",
                "status",
                "introduced_in",
                "confidence",
            ],
            "governance_rule": "缺少元数据的候选项不能直接进入正式知识库。",
        },
        "items": items[:12],
    }


def build_report_markdown(report_context, focus_list, final_data, pending_updates, chapter_records):
    lines = [
        f"# {report_context['company_name']} {report_context['report_period']} 年报分析报告",
        "",
        "## 运行概览",
        f"- 报告类型：{report_context['report_type']}",
        f"- 审计意见：{report_context['audit_opinion']}",
        f"- 币种：{report_context['currency']}",
        f"- 附注章节记录数：{len(chapter_records)}",
        "",
        "## 动态重点",
    ]

    for focus in focus_list:
        lines.append(
            f"- `{focus['focus_name']}`：{focus['why_selected']}（章节：{', '.join(str(item) for item in focus['evidence_chapters'])}）"
        )

    lines.extend([
        "",
        "## 关键结论",
    ])

    for conclusion in final_data["key_conclusions"]:
        lines.append(f"- {conclusion}")

    lines.extend([
        "",
        "## 章节速览",
    ])

    for record in chapter_records[:12]:
        lines.append(
            f"- 附注第{record['attributes']['note_no']}章 `{record['chapter_title']}`：{record['summary']}"
        )

    lines.extend([
        "",
        "## 待固化更新",
    ])

    for item in pending_updates["items"][:10]:
        lines.append(f"- `{item['type']}` / `{item['title']}`：{item['proposal']}")

    lines.append("")
    return "\n".join(lines)


def autosize_sheet(sheet):
    for column in sheet.columns:
        max_length = 0
        letter = column[0].column_letter
        for cell in column:
            if cell.value is None:
                continue
            max_length = max(max_length, len(str(cell.value)))
        sheet.column_dimensions[letter].width = min(max_length + 2, 50)


def build_workbook(report_context, focus_list, final_data, pending_updates, chapter_records, output_path):
    workbook = Workbook()
    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_font = Font(color="FFFFFF", bold=True)

    summary_sheet = workbook.active
    summary_sheet.title = "summary"
    summary_rows = [
        ("company_name", report_context["company_name"]),
        ("report_period", report_context["report_period"]),
        ("report_type", report_context["report_type"]),
        ("audit_opinion", report_context["audit_opinion"]),
        ("currency", report_context["currency"]),
        ("chapter_count", len(chapter_records)),
        ("focus_count", len(focus_list)),
    ]
    for row_index, (key, value) in enumerate(summary_rows, start=1):
        summary_sheet.cell(row=row_index, column=1, value=key)
        summary_sheet.cell(row=row_index, column=2, value=value)

    focus_sheet = workbook.create_sheet("focus")
    focus_headers = ["focus_name", "severity", "score", "evidence_chapters", "related_topics", "knowledge_gap"]
    for col_index, header in enumerate(focus_headers, start=1):
        cell = focus_sheet.cell(row=1, column=col_index, value=header)
        cell.fill = header_fill
        cell.font = header_font
    for row_index, focus in enumerate(focus_list, start=2):
        focus_sheet.cell(row=row_index, column=1, value=focus["focus_name"])
        focus_sheet.cell(row=row_index, column=2, value=focus["focus_attributes"]["severity"])
        focus_sheet.cell(row=row_index, column=3, value=focus["focus_attributes"]["score"])
        focus_sheet.cell(row=row_index, column=4, value=", ".join(str(item) for item in focus["evidence_chapters"]))
        focus_sheet.cell(row=row_index, column=5, value=", ".join(focus["related_topics"]))
        focus_sheet.cell(row=row_index, column=6, value=focus["knowledge_gap"])

    chapter_sheet = workbook.create_sheet("chapters")
    chapter_headers = ["chapter_no", "chapter_title", "status", "topics", "summary", "anomaly_count", "numeric_count"]
    for col_index, header in enumerate(chapter_headers, start=1):
        cell = chapter_sheet.cell(row=1, column=col_index, value=header)
        cell.fill = header_fill
        cell.font = header_font
    for row_index, record in enumerate(chapter_records, start=2):
        chapter_sheet.cell(row=row_index, column=1, value=record["chapter_no"])
        chapter_sheet.cell(row=row_index, column=2, value=record["chapter_title"])
        chapter_sheet.cell(row=row_index, column=3, value=record["status"])
        chapter_sheet.cell(row=row_index, column=4, value=", ".join(record["attributes"]["topic_tags"]))
        chapter_sheet.cell(row=row_index, column=5, value=record["summary"])
        chapter_sheet.cell(row=row_index, column=6, value=len(record["anomalies"]))
        chapter_sheet.cell(row=row_index, column=7, value=len(record["numeric_data"]))

    topic_sheet = workbook.create_sheet("topic_results")
    topic_headers = ["topic", "chapter_count", "chapter_refs", "summary"]
    for col_index, header in enumerate(topic_headers, start=1):
        cell = topic_sheet.cell(row=1, column=col_index, value=header)
        cell.fill = header_fill
        cell.font = header_font
    for row_index, (topic, payload) in enumerate(final_data["topic_results"].items(), start=2):
        topic_sheet.cell(row=row_index, column=1, value=topic)
        topic_sheet.cell(row=row_index, column=2, value=payload["attributes"]["chapter_count"])
        topic_sheet.cell(row=row_index, column=3, value=", ".join(str(item) for item in payload["attributes"]["chapter_refs"]))
        topic_sheet.cell(row=row_index, column=4, value=payload["summary"])

    update_sheet = workbook.create_sheet("pending_updates")
    update_headers = ["type", "title", "status", "confidence", "applicable_scope", "proposal"]
    for col_index, header in enumerate(update_headers, start=1):
        cell = update_sheet.cell(row=1, column=col_index, value=header)
        cell.fill = header_fill
        cell.font = header_font
    for row_index, item in enumerate(pending_updates["items"], start=2):
        update_sheet.cell(row=row_index, column=1, value=item["type"])
        update_sheet.cell(row=row_index, column=2, value=item["title"])
        update_sheet.cell(row=row_index, column=3, value=item["status"])
        update_sheet.cell(row=row_index, column=4, value=item["confidence"])
        update_sheet.cell(row=row_index, column=5, value=item["applicable_scope"])
        update_sheet.cell(row=row_index, column=6, value=item["proposal"])

    for sheet in workbook.worksheets:
        autosize_sheet(sheet)

    workbook.save(output_path)


def build_manifest(md_path, notes_work, run_dir, report_context, chapter_records, focus_list, pending_updates):
    return {
        "engine_version": ENGINE_VERSION,
        "status": "success",
        "failure_reason": "",
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "input": {
            "md_path": str(md_path),
            "md5": md5_file(md_path),
            "file_size": md_path.stat().st_size,
            "notes_workfile": notes_work["path"],
        },
        "entity": {
            "company_name": report_context["company_name"],
            "report_period": report_context["report_period"],
            "report_type": report_context["report_type"],
            "audit_opinion": report_context["audit_opinion"],
        },
        "notes_locator": {
            "status": "success",
            "start_line": notes_work["notes_start_line"],
            "end_line": notes_work["notes_end_line"],
            "locator_evidence": notes_work["locator_evidence"],
        },
        "notes_catalog_summary": {
            "note_chapter_count": len(notes_work["notes_catalog"]),
            "first_note": notes_work["notes_catalog"][0]["note_no"],
            "last_note": notes_work["notes_catalog"][-1]["note_no"],
        },
        "artifacts": {
            "run_manifest": str(run_dir / "run_manifest.json"),
            "chapter_records": str(run_dir / "chapter_records.jsonl"),
            "focus_list": str(run_dir / "focus_list.json"),
            "final_data": str(run_dir / "final_data.json"),
            "pending_updates": str(run_dir / "pending_updates.json"),
            "analysis_report": str(run_dir / "analysis_report.md"),
            "financial_output": str(run_dir / "financial_output.xlsx"),
        },
        "counts": {
            "chapter_records": len(chapter_records),
            "focus_items": len(focus_list),
            "pending_updates": len(pending_updates["items"]),
        },
    }


def build_failure_manifest(md_path, notes_workfile_path, run_dir, report_context, failure_reason, details):
    return {
        "engine_version": ENGINE_VERSION,
        "status": "failed",
        "failure_reason": failure_reason,
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "input": {
            "md_path": str(md_path),
            "md5": md5_file(md_path),
            "file_size": md_path.stat().st_size,
            "notes_workfile": str(Path(notes_workfile_path).resolve()),
        },
        "entity": {
            "company_name": report_context["company_name"],
            "report_period": report_context["report_period"],
            "report_type": report_context["report_type"],
            "audit_opinion": report_context["audit_opinion"],
        },
        "notes_locator": {
            "status": "failed",
            "start_line": None,
            "end_line": None,
            "locator_evidence": [],
        },
        "notes_catalog_summary": {
            "note_chapter_count": 0,
            "first_note": "",
            "last_note": "",
        },
        "artifacts": {
            "run_manifest": str(run_dir / "run_manifest.json"),
        },
        "details": details,
    }


def fail_with_manifest(md_path, notes_workfile_path, run_dir, report_context, failure_reason, details):
    manifest = build_failure_manifest(
        md_path,
        notes_workfile_path,
        run_dir,
        report_context,
        failure_reason,
        details,
    )
    write_json(run_dir / "run_manifest.json", manifest)
    raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description="附注优先的财务分析主脚本")
    parser.add_argument("--md", required=True, help="输入 Markdown 路径")
    parser.add_argument("--notes-workfile", required=True, help="附注工作文件路径")
    parser.add_argument("--run-dir", required=True, help="显式指定运行目录")
    args = parser.parse_args()

    md_path = Path(args.md).resolve()
    if not md_path.exists():
        raise FileNotFoundError(f"Markdown 文件不存在: {md_path}")

    run_dir = resolve_run_dir(args.run_dir)
    stable_excel_path = run_dir / "financial_output.xlsx"

    print(f"[INFO] 输入文件: {md_path}")
    print(f"[INFO] 运行目录: {run_dir}")

    raw_text = normalize_text(read_text(md_path))
    markdown_lines = read_lines(md_path)
    company_name = extract_company_name(raw_text, md_path.stem)
    report_period = extract_report_period(raw_text, md_path.stem)
    report_context = {
        "company_name": company_name,
        "report_period": report_period,
        "currency": detect_currency(raw_text),
        "input_file": str(md_path),
    }
    report_context.update(classify_report(raw_text, md_path))

    try:
        notes_work = load_notes_workfile(args.notes_workfile, len(markdown_lines))
    except FileNotFoundError as exc:
        fail_with_manifest(md_path, args.notes_workfile, run_dir, report_context, "notes_workfile_missing", str(exc))
    except ValueError as exc:
        fail_with_manifest(md_path, args.notes_workfile, run_dir, report_context, "notes_workfile_invalid", str(exc))

    chapter_records = [
        build_chapter_record(
            index,
            note_entry,
            markdown_lines,
            report_context,
            notes_work["locator_evidence"],
        )
        for index, note_entry in enumerate(notes_work["notes_catalog"], start=1)
    ]
    if not chapter_records:
        fail_with_manifest(md_path, args.notes_workfile, run_dir, report_context, "notes_catalog_empty", "notes_catalog 为空")

    focus_list = build_focus_list(chapter_records)
    final_data = build_final_data(report_context, chapter_records, focus_list)
    pending_updates = build_pending_updates(chapter_records)
    analysis_report = build_report_markdown(
        report_context,
        focus_list,
        final_data,
        pending_updates,
        chapter_records,
    )

    manifest = build_manifest(
        md_path,
        notes_work,
        run_dir,
        report_context,
        chapter_records,
        focus_list,
        pending_updates,
    )

    write_json(run_dir / "run_manifest.json", manifest)
    write_jsonl(run_dir / "chapter_records.jsonl", chapter_records)
    write_json(run_dir / "focus_list.json", focus_list)
    write_json(run_dir / "final_data.json", final_data)
    write_json(run_dir / "pending_updates.json", pending_updates)

    with open(run_dir / "analysis_report.md", "w", encoding="utf-8") as handle:
        handle.write(analysis_report)

    build_workbook(
        report_context,
        focus_list,
        final_data,
        pending_updates,
        chapter_records,
        stable_excel_path,
    )

    print(f"[OK] 章节记录: {len(chapter_records)}")
    print(f"[OK] 动态重点: {len(focus_list)}")
    print(f"[OK] 待固化更新: {len(pending_updates['items'])}")
    print(f"✅ 成功: 产物已生成 -> {run_dir}")


if __name__ == "__main__":
    main()
