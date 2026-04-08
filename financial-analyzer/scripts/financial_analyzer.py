#!/usr/bin/env python3
"""
附注优先的财务分析主脚本。
"""

import argparse
import datetime
import hashlib
import json
import re
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


ENGINE_VERSION = "3.1.2"
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
KNOWLEDGE_BASE_PATH = REPO_ROOT / "runtime" / "knowledge" / "knowledge_base.json"

TOPIC_PATTERNS = {
    "audit": ["核数师", "审计", "审计意见", "保留意见", "无法表示意见", "否定意见"],
    "debt": ["借贷", "借款", "债券", "贷款", "融资", "票据", "债项"],
    "cash": ["现金", "现金流", "银行存款", "受限资金", "货币资金"],
    "profitability": ["收入", "利润", "溢利", "毛利", "EBITDA", "收益"],
    "liquidity": ["流动", "短期", "到期", "偿债", "再融资", "期限结构"],
    "investment_property": ["投资物业", "公允价值", "估值", "资本化率", "物业估值"],
    "restricted_assets": ["受限资金", "受限资产", "抵押", "质押", "冻结资金", "保证金"],
    "risk_management": ["风险", "掉期", "对冲", "汇率", "利率", "契约"],
    "lgfv_features": ["LGFV", "城投", "国资", "政府补助", "专项债", "资本公积注入", "化债", "置换债"],
    "external_guarantees": ["对外担保", "担保网络", "被担保单位", "互保", "反担保"],
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

GENERIC_PENDING_TOPIC_TITLES = {
    "general",
    "事项描述",
    "审计应对",
    "公司概况",
    "会计期间",
    "会计年度",
    "营业周期",
    "编制基础",
    "记账本位币",
    "财务报告的批准报出",
    "合并财务报表的编制方法",
    "企业合并",
    "收入与成本",
    "研发投入",
    "遵循企业会计准则的声明",
    "合并资产负债表",
    "母公司资产负债表",
    "合并利润表",
    "母公司利润表",
    "合并现金流量表",
    "母公司现金流量表",
    "合并所有者权益变动表",
    "母公司所有者权益变动表",
}

GENERIC_PENDING_TOPIC_MARKERS = (
    "会计",
    "编制基础",
    "本位币",
    "财务报告",
    "财务报表",
    "企业合并",
    "营业周期",
    "批准报出",
    "合并财务报表",
    "母公司",
    "情况如下",
    "确定标准",
    "选择依据",
    "折算",
    "控制的判断",
    "认定和分类",
    "固定资产",
    "金融工具",
    "金融资产投资",
    "长期股权投资",
    "现金及现金等价物",
    "现金流",
    "总体情况",
)

PENDING_TOPIC_ALLOWLIST = {
    "持续经营",
}

PENDING_TOPIC_INTEREST_MARKERS = (
    "关联交易",
    "收购",
    "出售",
    "重分类",
    "租赁",
    "托管",
    "承包",
    "担保",
    "违约",
    "诉讼",
    "仲裁",
    "持续经营",
    "公允价值",
    "业绩约定",
)

PENDING_FIELD_NOISE_MARKERS = (
    "期末余额",
    "期初余额",
    "流动资产",
    "流动负债",
    "资产总计",
    "负债合计",
    "所有者权益合计",
    "负债和所有者权益总计",
    "财务报表附注",
    "管理层",
)

SEVERITY_SCORE = {
    "extreme": 100,
    "high": 70,
    "medium": 45,
    "low": 20,
}

RISK_LABELS = {
    "extreme_audit_issue": "极端审计意见风险",
    "high_audit_issue": "审计或持续经营提示",
    "litigation_or_default": "违约或诉讼风险",
    "liquidity_pressure": "流动性与再融资压力",
    "asset_impairment": "资产减值或公允价值下行压力",
    "restricted_cash": "受限资金占用风险",
    "interest_capitalization": "资本化利息口径风险",
    "guarantee_exposure": "担保敞口风险",
    "fx_or_rate_exposure": "汇率或利率敞口风险",
}

FORMAL_TOPIC_MODULES = {
    "investment_property": "投资性房地产",
    "restricted_assets": "受限资产与抵押",
    "lgfv_features": "城投平台特征",
    "inventory_quality": "存货质量",
    "external_guarantees": "对外担保",
}

CASE_TOPIC_ALLOWLIST = {
    "henglong": {"investment_property"},
    "country_garden": {"restricted_assets"},
    "hanghai": {"lgfv_features", "external_guarantees"},
}


def read_text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


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
            return match.group(1).lstrip("# ").strip()
    return fallback_company_name(fallback_name).lstrip("# ").strip()


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
    if re.search(r"人民币元|记账本位币.*人民币|元\s*指\s*人民币元|本位币.*人民币", text):
        return "CNY"
    if re.search(r"香港财务报告准则|HKFRS", text) and not re.search(r"中国企业会计准则|企业会计准则", text):
        if "港币" in text or "港元" in text:
            return "HKD"
    if "美元" in text or "USD" in text:
        return "USD"
    return "CNY"


def classify_report(text, md_path):
    lower_name = md_path.name.lower()
    report_type = "a_share_full_report"
    basis = []

    a_share_signals = [
        "中国企业会计准则",
        "企业会计准则",
        "A股证券代码",
        "深圳证券交易所",
        "上海证券交易所",
        "本报告之财务报告乃按照中国企业会计准则编制",
        "遵循企业会计准则的声明",
        "A 股证券代码",
        "深交所",
    ]
    hk_signals = [
        "香港财务报告准则",
        "HKFRS",
        "港股",
        "联交所年报",
        "香港上市公司",
    ]

    if any(signal in text for signal in a_share_signals):
        report_type = "a_share_full_report"
        basis.append("检测到A股/中国企业会计准则信号")
    elif any(signal in text for signal in hk_signals) or "hkfrs" in lower_name or "年報" in md_path.name:
        report_type = "hong_kong_full_report"
        basis.append("检测到HKFRS/港股信号")
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


NUMERIC_CONTEXT_HINTS = (
    "现金",
    "借款",
    "债务",
    "负债",
    "资产",
    "收入",
    "利润",
    "净亏损",
    "净利润",
    "成本",
    "应收",
    "应付",
    "存货",
    "利息",
    "融资",
    "余额",
    "净额",
    "合计",
    "期末",
    "期初",
)

NUMERIC_NOISE_LABELS = {
    "#",
    "注",
    "项目",
    "金额",
    "单位",
    "截至",
}


def score_numeric_candidate(line, raw_value, value, match_start, match_end, match_count):
    score = 0
    if any(marker in line for marker in ("亿元", "百万元", "万元", "元", "人民币", "港元", "美元")):
        score += 20
    if any(marker in line for marker in ("%", "倍", "x")):
        score += 16
    if any(marker in line for marker in NUMERIC_CONTEXT_HINTS):
        score += 12
    if any(marker in line for marker in ("本集团", "本公司", "公司", "期末", "期初")):
        score += 4
    if 1900 <= value <= 2100:
        score -= 30
        if match_count > 1:
            score -= 18
    if line.lstrip().startswith("#"):
        score -= 12
    if re.match(r"^\s*[#(（\d一二三四五六七八九十]+[、.．)）\-\s]*$", line[:match_end]):
        score -= 8
    if raw_value.endswith("%"):
        score += 8
    if match_start == 0 and match_count == 1:
        score -= 4
    return score


def derive_numeric_label(line, match_start, match_end):
    prefix = line[:match_start].strip(" ：:，,.-#")
    prefix = re.sub(r"^[\s#(（)）\-]+", "", prefix).strip()
    if prefix and prefix not in NUMERIC_NOISE_LABELS and not re.fullmatch(r"[\d.％%]+", prefix):
        return shorten(prefix, limit=40)

    suffix = line[match_end:].strip(" ：:，,.-#")
    suffix = re.sub(r"^[、.．)）\-\s]+", "", suffix).strip()
    if suffix and suffix not in NUMERIC_NOISE_LABELS and not re.fullmatch(r"[\d.％%]+", suffix):
        return shorten(suffix, limit=40)

    cleaned = clean_line(line)
    return shorten(cleaned, limit=40)


def select_best_numeric_match(line):
    pattern = re.compile(r"(?<!\d)(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?")
    matches = list(pattern.finditer(line))
    if not matches:
        return None

    best = None
    for match in matches:
        raw_value = match.group(0)
        value = numeric_value(raw_value)
        if value is None:
            continue
        score = score_numeric_candidate(line, raw_value, value, match.start(), match.end(), len(matches))
        candidate = {
            "label": derive_numeric_label(line, match.start(), match.end()),
            "value": value,
            "raw_value": raw_value,
            "unit": detect_unit(line),
            "evidence": shorten(line, limit=160),
            "score": score,
        }
        if best is None or candidate["score"] > best["score"]:
            best = candidate

    if best is None:
        return None
    best.pop("score", None)
    return best


def extract_numeric_data(text, limit=12):
    entries = []
    seen_lines = set()
    for raw_line in text.splitlines():
        line = clean_line(raw_line)
        if not line or line in seen_lines:
            continue
        if not re.search(r"\d", line):
            continue
        best = select_best_numeric_match(line)
        if not best:
            continue

        seen_lines.add(line)
        entries.append(best)

    entries.sort(
        key=lambda item: (
            0 if item["value"] is None else -abs(item["value"]),
            item["label"],
        )
    )
    return entries[:limit]


def extract_title_tokens(title):
    tokens = []
    normalized_title = re.sub(r"^[#\s]*\d+\s*[、.．)\-]?\s*", "", str(title or ""))
    normalized_title = re.sub(r"[（(][^）)]*[）)]", " ", normalized_title)
    normalized_title = re.sub(r"[，,；;：:、/\\|《》<>【】\[\]\"'“”‘’]", " ", normalized_title)
    normalized_title = re.sub(r"\s+", " ", normalized_title).strip()

    for token in normalized_title.split(" "):
        candidate = token.strip(" -_.")
        if re.fullmatch(r"[A-Za-z]{2,}", candidate):
            pass
        elif re.fullmatch(r"[\u4e00-\u9fff]{2,24}", candidate):
            pass
        else:
            continue
        if candidate in STOPWORDS:
            continue
        if candidate.startswith("财务报表"):
            continue
        if len(candidate) > 16 and re.search(r"[\u4e00-\u9fff]", candidate):
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


def detect_case_key(company_name, input_file):
    content = f"{company_name} {input_file}"
    if "恒隆" in content:
        return "henglong"
    if "碧桂园" in content:
        return "country_garden"
    if "杭海新城" in content:
        return "hanghai"
    return ""


def infer_industry_tag(chapter_records):
    combined_text = " ".join(
        f"{record.get('chapter_title', '')} {record.get('chapter_text_cleaned', '')}"
        for record in chapter_records
    )
    if any(keyword in combined_text for keyword in ["LGFV", "城投", "地方政府融资平台", "化债", "专项债"]):
        return "lgfv"
    if any(keyword in combined_text for keyword in ["银行", "证券", "保险", "金融", "理财", "信托"]):
        return "financial"
    if any(keyword in combined_text for keyword in ["房地产", "物业", "租赁", "商业开发", "开发业务", "房地产业"]):
        return "property"
    return "general"


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
        "chapter_text": text,
        "chapter_text_cleaned": cleaned_text,
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
    focus_list = []
    for record in chapter_records:
        focus_list.append({
            "chapter_no": record["chapter_no"],
            "note_no": record["attributes"].get("note_no", ""),
            "chapter_title": record["chapter_title"],
            "line_span": record["attributes"].get("line_span", {}),
            "status": record["status"],
            "topic_tags": record["attributes"].get("topic_tags", []),
            "summary": record["summary"],
        })
    return focus_list


def build_final_data(report_context, chapter_records, focus_list):
    return {
        "entity_profile": {
            "company_name": report_context["company_name"],
            "report_period": report_context["report_period"],
            "currency": report_context["currency"],
            "report_type": report_context["report_type"],
            "audit_opinion": report_context["audit_opinion"],
            "input_file": report_context["input_file"],
        },
        "chapter_count": len(chapter_records),
        "focus_count": len(focus_list),
        "extensions": {
            "classification_basis": report_context["classification_basis"],
        },
    }


def chapter_blob(record):
    return "\n".join(
        part for part in [
            str(record.get("chapter_title", "")),
            str(record.get("chapter_text_cleaned", "")),
            str(record.get("summary", "")),
        ]
        if part
    )


def record_matches_terms(record, terms):
    haystack = chapter_blob(record)
    return any(term and term in haystack for term in terms or [])


def score_record_numeric_item(item, terms=None):
    score = 0
    label = str(item.get("label", ""))
    evidence = str(item.get("evidence", ""))
    text = f"{label} {evidence}"
    value = item.get("value")
    unit = str(item.get("unit", ""))

    if terms and any(term in text for term in terms):
        score += 24
    if unit in {"亿元", "百万元", "万元", "元", "%", "倍", "x"}:
        score += 12
    if any(marker in text for marker in NUMERIC_CONTEXT_HINTS):
        score += 10
    if label and label not in NUMERIC_NOISE_LABELS and not re.fullmatch(r"[\d.％%]+", label):
        score += 2
    if isinstance(value, (int, float)) and 1900 <= value <= 2100:
        score -= 30
    if label in NUMERIC_NOISE_LABELS:
        score -= 14
    if text.startswith("#"):
        score -= 6
    return score


def pick_best_record_numeric(record, terms=None):
    candidates = record.get("numeric_data", []) or []
    best = None
    best_score = None
    for item in candidates:
        score = score_record_numeric_item(item, terms=terms)
        if best is None or score > best_score:
            best = item
            best_score = score
    return best


def build_metric_entry(chapter_records, chapter_evidence_refs, label, patterns, metric_code=None, unit="", commentary="", source_status="chapter_review", risk_level="medium", comparison="", benchmark=""):
    for record in chapter_records:
        if not record_matches_terms(record, patterns):
            continue
        numeric_item = pick_best_record_numeric(record, terms=patterns)
        if not numeric_item:
            continue
        evidence_refs = chapter_evidence_refs.get(record.get("chapter_no"), [])[:2]
        value = numeric_item.get("value")
        return {
            "metric_code": metric_code or label,
            "label": label,
            "value": value,
            "unit": unit or numeric_item.get("unit", ""),
            "risk_level": risk_level,
            "source_status": source_status,
            "comparison": comparison or record.get("chapter_title", ""),
            "benchmark": benchmark,
            "evidence_refs": evidence_refs,
            "commentary": commentary or numeric_item.get("evidence", "") or record.get("summary", ""),
        }
    return None


def build_metric_list(chapter_records, chapter_evidence_refs, specs):
    items = []
    for spec in specs:
        entry = build_metric_entry(
            chapter_records,
            chapter_evidence_refs,
            label=spec["label"],
            patterns=spec.get("patterns", []),
            metric_code=spec.get("metric_code"),
            unit=spec.get("unit", ""),
            commentary=spec.get("commentary", ""),
            source_status=spec.get("source_status", "chapter_review"),
            risk_level=spec.get("risk_level", "medium"),
            comparison=spec.get("comparison", ""),
            benchmark=spec.get("benchmark", ""),
        )
        if entry:
            items.append(entry)
    return items


def collect_overview_payload(chapter_records, chapter_evidence_refs):
    severity_rank = {"extreme": 3, "high": 2, "medium": 1, "low": 0}
    ranked_records = []
    for record in chapter_records:
        anomaly_severity = 0
        for anomaly in record.get("anomalies", []):
            anomaly_severity = max(anomaly_severity, severity_rank.get(anomaly.get("severity", "low"), 0))
        ranked_records.append((anomaly_severity, len(record.get("numeric_data", [])), len(record.get("findings", [])), -int(record.get("chapter_no", 0)), record))
    ranked_records.sort(reverse=True)

    executive_summary = []
    for _, _, _, _, record in ranked_records[:3]:
        summary = record.get("summary") or summarize_chapter(record.get("chapter_text_cleaned", ""))
        if summary:
            executive_summary.append(f"{record.get('chapter_title', '')}：{summary}")

    key_risks = []
    seen_signals = set()
    for _, _, _, _, record in ranked_records:
        for anomaly in record.get("anomalies", []):
            signal_name = anomaly.get("signal_name", "")
            if not signal_name or signal_name in seen_signals:
                continue
            seen_signals.add(signal_name)
            key_risks.append({
                "label": signal_name,
                "risk_level": anomaly.get("severity", "medium"),
                "description": anomaly.get("impact_hint", ""),
                "evidence_refs": chapter_evidence_refs.get(record.get("chapter_no"), [])[:2],
            })
            if len(key_risks) >= 5:
                break
        if len(key_risks) >= 5:
            break

    report_highlights = []
    for _, _, _, _, record in ranked_records[:5]:
        findings = record.get("findings", []) or []
        detail = findings[0].get("detail", "") if findings else ""
        if not detail:
            detail = record.get("summary", "")
        report_highlights.append({
            "title": record.get("chapter_title", ""),
            "detail": detail,
            "evidence_refs": chapter_evidence_refs.get(record.get("chapter_no"), [])[:2],
        })

    rating_snapshot = [
        f"报告类型：{chapter_records[0].get('attributes', {}).get('report_type', '') if chapter_records else ''}",
        f"附注章数：{len(chapter_records)}",
    ]

    return {
        "executive_summary": executive_summary,
        "key_risks": key_risks,
        "rating_snapshot": rating_snapshot,
        "report_highlights": report_highlights,
    }


def find_first_record(chapter_records, patterns):
    for record in chapter_records:
        if record_matches_terms(record, patterns):
            return record
    return None


def make_manifest_item(sheet_name, module_key, module_type, required, enabled, title, empty_state):
    return {
        "sheet_name": sheet_name,
        "module_key": module_key,
        "module_type": module_type,
        "required": required,
        "enabled": enabled,
        "title": title,
        "empty_state": empty_state,
    }


def build_soul_export_payload(report_context, notes_work, run_dir, chapter_records):
    period = report_context["report_period"]
    period_end = f"{period}-12-31" if period else ""
    currency = report_context["currency"]
    case_key = detect_case_key(report_context["company_name"], report_context["input_file"])
    source_artifacts = {
        "run_manifest": str(run_dir / "run_manifest.json"),
        "chapter_records": str(run_dir / "chapter_records.jsonl"),
        "focus_list_scaffold": str(run_dir / "focus_list_scaffold.json"),
        "final_data_scaffold": str(run_dir / "final_data_scaffold.json"),
        "analysis_report_scaffold": str(run_dir / "analysis_report_scaffold.md"),
        "notes_workfile": notes_work["path"],
    }
    evidence_index = []
    chapter_evidence_refs = {}
    next_evidence_id = 1

    def add_evidence(field_path, sheet_name, excerpt, confidence="medium", record=None, source_document="annual_report_notes"):
        nonlocal next_evidence_id
        clean_excerpt = shorten(clean_line(excerpt), limit=160)
        if not clean_excerpt:
            return []
        evidence_id = f"EVD-{next_evidence_id:04d}"
        next_evidence_id += 1
        note_no = None
        line_span = {"start": None, "end": None}
        chapter_no = None
        chapter_title = ""
        if record:
            note_no = record["attributes"].get("note_no")
            line_span = record["attributes"].get("line_span", line_span)
            chapter_no = record.get("chapter_no")
            chapter_title = record.get("chapter_title", "")
        evidence_index.append({
            "evidence_id": evidence_id,
            "field_path": field_path,
            "sheet_name": sheet_name,
            "excerpt": clean_excerpt,
            "source_document": source_document,
            "chapter_no": chapter_no,
            "chapter_title": chapter_title,
            "note_no": note_no,
            "line_span": line_span,
            "confidence": confidence,
        })
        return [evidence_id]

    for record in chapter_records:
        record_refs = []
        for evidence_item in record.get("evidence", [])[:2]:
            record_refs.extend(add_evidence(
                f"chapter_records.{record['chapter_no']}.evidence",
                "00_overview",
                evidence_item.get("content", ""),
                confidence="medium",
                record=record,
                source_document="chapter_records",
            ))
        chapter_evidence_refs[record.get("chapter_no")] = record_refs

    overview_payload = collect_overview_payload(chapter_records, chapter_evidence_refs)

    kpi_dashboard_sections = [
        {
            "category": "leverage",
            "metrics": build_metric_list(
                chapter_records,
                chapter_evidence_refs,
                [
                    {"label": "总资产", "metric_code": "total_assets", "patterns": ["资产总计", "总资产"], "unit": currency and "亿元" or ""},
                    {"label": "总负债", "metric_code": "total_liabilities", "patterns": ["负债合计", "总负债"], "unit": currency and "亿元" or ""},
                    {"label": "所有者权益", "metric_code": "equity", "patterns": ["所有者权益合计", "归属于母公司股东权益", "股东权益合计"], "unit": currency and "亿元" or ""},
                    {"label": "权益率", "metric_code": "equity_ratio", "patterns": ["所有者权益合计", "归属于母公司股东权益", "股东权益合计"], "unit": "%", "risk_level": "medium", "source_status": "derived"},
                    {"label": "流动比率", "metric_code": "current_ratio", "patterns": ["流动资产合计", "流动负债合计"], "unit": "倍", "risk_level": "medium", "source_status": "derived"},
                ],
            ),
        },
        {
            "category": "debt_service",
            "metrics": build_metric_list(
                chapter_records,
                chapter_evidence_refs,
                [
                    {"label": "短期借款", "metric_code": "short_term_borrowings", "patterns": ["短期借款"], "unit": currency and "亿元" or ""},
                    {"label": "一年内到期有息负债", "metric_code": "one_year_due_debt", "patterns": ["一年内到期的有息负债", "一年内到期的非流动负债", "一年内到期"], "unit": currency and "亿元" or ""},
                    {"label": "长期借款", "metric_code": "long_term_borrowings", "patterns": ["长期借款"], "unit": currency and "亿元" or ""},
                    {"label": "现金短债比", "metric_code": "cash_to_short_term_debt", "patterns": ["现金及现金等价物", "货币资金", "短期借款"], "unit": "倍", "risk_level": "high", "source_status": "derived"},
                ],
            ),
        },
        {
            "category": "profitability",
            "metrics": build_metric_list(
                chapter_records,
                chapter_evidence_refs,
                [
                    {"label": "营业收入", "metric_code": "revenue", "patterns": ["营业收入"], "unit": currency and "亿元" or ""},
                    {"label": "营业成本", "metric_code": "cost_of_revenue", "patterns": ["营业成本"], "unit": currency and "亿元" or ""},
                    {"label": "毛利率", "metric_code": "gross_margin", "patterns": ["营业收入", "营业成本"], "unit": "%", "risk_level": "medium", "source_status": "derived"},
                    {"label": "净利润", "metric_code": "net_profit", "patterns": ["净利润", "净亏损", "归属于母公司股东的净利润"], "unit": currency and "亿元" or ""},
                ],
            ),
        },
        {
            "category": "cashflow",
            "metrics": build_metric_list(
                chapter_records,
                chapter_evidence_refs,
                [
                    {"label": "经营活动现金流净额", "metric_code": "operating_cash_flow", "patterns": ["经营活动产生的现金流量净额"], "unit": currency and "亿元" or ""},
                    {"label": "投资活动现金流净额", "metric_code": "investing_cash_flow", "patterns": ["投资活动产生的现金流量净额"], "unit": currency and "亿元" or ""},
                    {"label": "筹资活动现金流净额", "metric_code": "financing_cash_flow", "patterns": ["筹资活动产生的现金流量净额"], "unit": currency and "亿元" or ""},
                    {"label": "现金及现金等价物", "metric_code": "cash_and_cash_equiv", "patterns": ["现金及现金等价物", "货币资金"], "unit": currency and "亿元" or ""},
                ],
            ),
        },
    ]

    financial_summary = {
        "unit_label": f"{currency}_100m" if currency else "",
        "statements": {
            "balance_sheet": build_metric_list(
                chapter_records,
                chapter_evidence_refs,
                [
                    {"label": "货币资金", "metric_code": "cash_balance", "patterns": ["货币资金", "现金及现金等价物"], "unit": currency and "亿元" or ""},
                    {"label": "流动资产合计", "metric_code": "current_assets", "patterns": ["流动资产合计"], "unit": currency and "亿元" or ""},
                    {"label": "流动负债合计", "metric_code": "current_liabilities", "patterns": ["流动负债合计"], "unit": currency and "亿元" or ""},
                    {"label": "资产总计", "metric_code": "total_assets", "patterns": ["资产总计", "总资产"], "unit": currency and "亿元" or ""},
                    {"label": "负债合计", "metric_code": "total_liabilities", "patterns": ["负债合计", "总负债"], "unit": currency and "亿元" or ""},
                    {"label": "所有者权益合计", "metric_code": "equity", "patterns": ["所有者权益合计", "归属于母公司股东权益", "股东权益合计"], "unit": currency and "亿元" or ""},
                ],
            ),
            "income_statement": build_metric_list(
                chapter_records,
                chapter_evidence_refs,
                [
                    {"label": "营业收入", "metric_code": "revenue", "patterns": ["营业收入"], "unit": currency and "亿元" or ""},
                    {"label": "营业成本", "metric_code": "cost_of_revenue", "patterns": ["营业成本"], "unit": currency and "亿元" or ""},
                    {"label": "营业利润", "metric_code": "operating_profit", "patterns": ["营业利润"], "unit": currency and "亿元" or ""},
                    {"label": "利润总额", "metric_code": "profit_before_tax", "patterns": ["利润总额"], "unit": currency and "亿元" or ""},
                    {"label": "净利润", "metric_code": "net_profit", "patterns": ["净利润", "净亏损"], "unit": currency and "亿元" or ""},
                    {"label": "归属于母公司股东的净利润", "metric_code": "net_profit_attrib", "patterns": ["归属于母公司股东的净利润", "归母净利润", "归属于母公司股东的净亏损"], "unit": currency and "亿元" or ""},
                ],
            ),
            "cash_flow": build_metric_list(
                chapter_records,
                chapter_evidence_refs,
                [
                    {"label": "经营活动产生的现金流量净额", "metric_code": "operating_cash_flow", "patterns": ["经营活动产生的现金流量净额"], "unit": currency and "亿元" or ""},
                    {"label": "投资活动产生的现金流量净额", "metric_code": "investing_cash_flow", "patterns": ["投资活动产生的现金流量净额"], "unit": currency and "亿元" or ""},
                    {"label": "筹资活动产生的现金流量净额", "metric_code": "financing_cash_flow", "patterns": ["筹资活动产生的现金流量净额"], "unit": currency and "亿元" or ""},
                    {"label": "期末现金及现金等价物", "metric_code": "cash_and_cash_equiv", "patterns": ["期末现金及现金等价物", "现金及现金等价物"], "unit": currency and "亿元" or ""},
                ],
            ),
        },
        "coverage_note": "脚本根据章节级证据自动聚合稳定指标；空位会保留为未识别。",
    }

    debt_profile = {
        "totals": build_metric_list(
            chapter_records,
            chapter_evidence_refs,
            [
                {"label": "短期借款", "metric_code": "short_term_borrowings", "patterns": ["短期借款"], "unit": currency and "亿元" or ""},
                {"label": "长期借款", "metric_code": "long_term_borrowings", "patterns": ["长期借款"], "unit": currency and "亿元" or ""},
                {"label": "应付债券", "metric_code": "bonds_payable", "patterns": ["应付债券"], "unit": currency and "亿元" or ""},
                {"label": "租赁负债", "metric_code": "lease_liabilities", "patterns": ["租赁负债"], "unit": currency and "亿元" or ""},
                {"label": "一年内到期有息负债", "metric_code": "one_year_due_debt", "patterns": ["一年内到期的有息负债", "一年内到期的非流动负债", "一年内到期"], "unit": currency and "亿元" or ""},
            ],
        ),
        "maturity_buckets": build_metric_list(
            chapter_records,
            chapter_evidence_refs,
            [
                {"label": "一年内到期", "metric_code": "due_within_one_year", "patterns": ["一年内到期"], "unit": currency and "亿元" or ""},
                {"label": "1-2年到期", "metric_code": "due_in_one_to_two_years", "patterns": ["1-2年", "一年后两年内"], "unit": currency and "亿元" or ""},
                {"label": "2年以上到期", "metric_code": "due_after_two_years", "patterns": ["2年以上", "两年以上"], "unit": currency and "亿元" or ""},
            ],
        ),
        "financing_mix": build_metric_list(
            chapter_records,
            chapter_evidence_refs,
            [
                {"label": "银行借款", "metric_code": "bank_borrowings", "patterns": ["银行借款", "银行贷款"], "unit": currency and "亿元" or ""},
                {"label": "债券融资", "metric_code": "bond_financing", "patterns": ["债券", "应付债券"], "unit": currency and "亿元" or ""},
                {"label": "其他借款", "metric_code": "other_borrowings", "patterns": ["其他借款", "股东借款"], "unit": currency and "亿元" or ""},
            ],
        ),
        "rate_profile": build_metric_list(
            chapter_records,
            chapter_evidence_refs,
            [
                {"label": "利息支出", "metric_code": "interest_expense", "patterns": ["利息支出"], "unit": currency and "亿元" or ""},
                {"label": "利息收入", "metric_code": "interest_income", "patterns": ["利息收入"], "unit": currency and "亿元" or ""},
                {"label": "资本化利息", "metric_code": "capitalized_interest", "patterns": ["资本化利息", "资本化之借贷支出", "利息资本化"], "unit": currency and "亿元" or ""},
            ],
        ),
        "debt_comments": [],
    }

    liquidity_and_covenants = {
        "cash_metrics": build_metric_list(
            chapter_records,
            chapter_evidence_refs,
            [
                {"label": "现金及现金等价物", "metric_code": "cash_and_cash_equiv", "patterns": ["现金及现金等价物", "货币资金"], "unit": currency and "亿元" or ""},
                {"label": "短期借款", "metric_code": "short_term_borrowings", "patterns": ["短期借款"], "unit": currency and "亿元" or ""},
                {"label": "现金短债比", "metric_code": "cash_to_short_term_debt", "patterns": ["现金及现金等价物", "短期借款"], "unit": "倍", "risk_level": "high", "source_status": "derived"},
            ],
        ),
        "credit_lines": build_metric_list(
            chapter_records,
            chapter_evidence_refs,
            [
                {"label": "授信额度", "metric_code": "credit_lines_total", "patterns": ["授信", "授信额度"], "unit": currency and "亿元" or ""},
                {"label": "已使用授信", "metric_code": "credit_lines_used", "patterns": ["已使用", "使用授信"], "unit": currency and "亿元" or ""},
                {"label": "未使用授信", "metric_code": "credit_lines_unused", "patterns": ["未使用", "剩余授信"], "unit": currency and "亿元" or ""},
            ],
        ),
        "restricted_assets": build_metric_list(
            chapter_records,
            chapter_evidence_refs,
            [
                {"label": "受限资金", "metric_code": "restricted_cash", "patterns": ["受限资金", "受限制资金", "受限制现金"], "unit": currency and "亿元" or ""},
                {"label": "受限资产", "metric_code": "restricted_assets", "patterns": ["受限资产", "抵押", "质押"], "unit": currency and "亿元" or ""},
            ],
        ),
        "covenants": [],
        "liquidity_observations": [
            {
                "label": "持续经营提示",
                "detail": next((item.get("impact_hint", "") for record in chapter_records for item in record.get("anomalies", []) if item.get("signal_name") in {"high_audit_issue", "liquidity_pressure"}), "持续经营或流动性相关风险已被章节级规则识别。"),
                "evidence_refs": chapter_evidence_refs.get(next((record.get("chapter_no") for record in chapter_records if any(item.get("signal_name") in {"high_audit_issue", "liquidity_pressure"} for item in record.get("anomalies", []))), None), [])[:2],
            }
        ],
    }

    module_manifest = [
        make_manifest_item("00_overview", "overview", "fixed", True, True, "概览", "仅保留运行壳，不做脚本摘要"),
        make_manifest_item("01_kpi_dashboard", "kpi_dashboard", "fixed", True, True, "KPI 面板", "由后续 skill 阅读生成"),
        make_manifest_item("02_financial_summary", "financial_summary", "fixed", True, True, "财务摘要", "由后续 skill 阅读生成"),
        make_manifest_item("03_debt_profile", "debt_profile", "fixed", True, True, "债务画像", "由后续 skill 阅读生成"),
        make_manifest_item("04_liquidity_and_covenants", "liquidity_and_covenants", "fixed", True, True, "流动性与契约", "由后续 skill 阅读生成"),
        make_manifest_item("99_evidence_index", "evidence_index", "fixed", True, True, "证据索引", "仅保留章节证据索引"),
    ]

    return {
        "contract_version": "soul_export_v1",
        "template_version": "soul_v1_1_alpha",
        "generated_at": now_iso(),
        "entity_profile": {
            "company_name": report_context["company_name"],
            "report_period": report_context["report_period"],
            "currency": report_context["currency"],
            "report_type": report_context["report_type"],
            "audit_opinion": report_context["audit_opinion"],
            "industry_tag": infer_industry_tag(chapter_records),
            "input_file": report_context["input_file"],
        },
        "source_artifacts": source_artifacts,
        "module_manifest": module_manifest,
        "overview": overview_payload,
        "kpi_dashboard": {
            "periods": [period, period_end] if period_end else [period] if period else [],
            "sections": kpi_dashboard_sections,
        },
        "financial_summary": financial_summary,
        "debt_profile": debt_profile,
        "liquidity_and_covenants": liquidity_and_covenants,
        "optional_modules": [],
        "evidence_index": evidence_index,
    }


def build_report_scaffold_markdown(report_context, focus_list, chapter_records):
    lines = [
        f"# {report_context['company_name']} {report_context['report_period']} 年报分析报告（Scaffold）",
        "",
        "> 该文件由模板脚本自动生成，仅作为 Codex 后续逐章复核与正式成稿的起点。",
        "",
        "## 运行概览",
        f"- 报告类型：{report_context['report_type']}",
        f"- 审计意见：{report_context['audit_opinion']}",
        f"- 币种：{report_context['currency']}",
        f"- 附注章节记录数：{len(chapter_records)}",
        "- 当前状态：`script_output_mode=scaffold_only`",
        "- 下一步：Codex 需要复核附注边界、逐章阅读并输出正式结论。",
        "",
        "## 章节索引",
    ]

    for focus in focus_list[:20]:
        lines.append(
            f"- 第{focus['chapter_no']}章 `附注{focus['note_no']}` `{focus['chapter_title']}`：{focus['summary']}"
        )

    lines.extend([
        "",
        "## Codex 复核清单",
        "- 复核 `notes_workfile` 的起止边界是否可信。",
        "- 逐章确认 `chapter_records` 是否有错切、漏切或标题误判。",
        "- 优先阅读 `chapter_text` 原文，再回看 `summary`、`numeric_data` 与 `evidence`。",
        "- 报告必须基于底稿写作，禁止直接从 scaffold 拼接结论。",
        "- 逐章提炼证据、结论与知识增量，再写入正式知识库。",
        "- 完成正式 `analysis_report.md`、`final_data.json`、`soul_export_payload.json` 与 `financial_output.xlsx`。",
    ])

    lines.append("")
    return "\n".join(lines)


def build_artifact_paths(run_dir):
    return {
        "run_manifest": str(run_dir / "run_manifest.json"),
        "chapter_records": str(run_dir / "chapter_records.jsonl"),
        "analysis_report_scaffold": str(run_dir / "analysis_report_scaffold.md"),
        "focus_list_scaffold": str(run_dir / "focus_list_scaffold.json"),
        "final_data_scaffold": str(run_dir / "final_data_scaffold.json"),
        "soul_export_payload_scaffold": str(run_dir / "soul_export_payload_scaffold.json"),
        "analysis_report": str(run_dir / "analysis_report.md"),
        "final_data": str(run_dir / "final_data.json"),
        "soul_export_payload": str(run_dir / "soul_export_payload.json"),
        "financial_output": str(run_dir / "financial_output.xlsx"),
    }


def build_manifest(md_path, notes_work, run_dir, report_context, chapter_records, focus_list):
    return {
        "engine_version": ENGINE_VERSION,
        "status": "success",
        "failure_reason": "",
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "script_output_mode": "scaffold_only",
        "codex_review_required": True,
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
        "artifacts": build_artifact_paths(run_dir),
        "counts": {
            "chapter_records": len(chapter_records),
            "focus_items_scaffold": len(focus_list),
        },
    }


def build_failure_manifest(
    md_path,
    notes_workfile_path,
    run_dir,
    report_context,
    failure_reason,
    details,
    notes_work=None,
):
    manifest = {
        "engine_version": ENGINE_VERSION,
        "status": "failed",
        "failure_reason": failure_reason,
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "script_output_mode": "failed_before_scaffold",
        "codex_review_required": False,
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
        "artifacts": build_artifact_paths(run_dir),
        "details": details,
    }
    if notes_work is None:
        manifest["notes_locator"] = {
            "status": "failed",
            "start_line": None,
            "end_line": None,
            "locator_evidence": [],
        }
        manifest["notes_catalog_summary"] = {
            "note_chapter_count": 0,
            "first_note": "",
            "last_note": "",
        }
    else:
        manifest["notes_locator"] = {
            "status": "success",
            "start_line": notes_work["notes_start_line"],
            "end_line": notes_work["notes_end_line"],
            "locator_evidence": notes_work["locator_evidence"],
        }
        manifest["notes_catalog_summary"] = {
            "note_chapter_count": len(notes_work["notes_catalog"]),
            "first_note": notes_work["notes_catalog"][0]["note_no"],
            "last_note": notes_work["notes_catalog"][-1]["note_no"],
        }
    return manifest


def fail_with_manifest(md_path, notes_workfile_path, run_dir, report_context, failure_reason, details, notes_work=None):
    manifest = build_failure_manifest(
        md_path,
        notes_workfile_path,
        run_dir,
        report_context,
        failure_reason,
        details,
        notes_work=notes_work,
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
    final_data_scaffold = build_final_data(report_context, chapter_records, focus_list)
    soul_export_payload_scaffold = build_soul_export_payload(
        report_context,
        notes_work,
        run_dir,
        chapter_records,
    )
    analysis_report_scaffold = build_report_scaffold_markdown(
        report_context,
        focus_list,
        chapter_records,
    )

    write_jsonl(run_dir / "chapter_records.jsonl", chapter_records)
    write_json(run_dir / "focus_list_scaffold.json", focus_list)
    write_json(run_dir / "final_data_scaffold.json", final_data_scaffold)
    write_json(run_dir / "soul_export_payload_scaffold.json", soul_export_payload_scaffold)

    with open(run_dir / "analysis_report_scaffold.md", "w", encoding="utf-8") as handle:
        handle.write(analysis_report_scaffold)

    manifest = build_manifest(
        md_path,
        notes_work,
        run_dir,
        report_context,
        chapter_records,
        focus_list,
    )
    write_json(run_dir / "run_manifest.json", manifest)

    print(f"[OK] 章节记录: {len(chapter_records)}")
    print(f"[OK] scaffold 初步重点: {len(focus_list)}")
    print("[OK] script_output_mode: scaffold_only")
    print(f"✅ 成功: 抽取与 scaffold 已生成 -> {run_dir}")


if __name__ == "__main__":
    main()
