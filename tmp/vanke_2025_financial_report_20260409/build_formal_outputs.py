from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import xlsxwriter

RUN_DIR = Path(__file__).resolve().parent
CHAPTER_RECORDS_PATH = RUN_DIR / "chapter_records.jsonl"
RUN_MANIFEST_PATH = RUN_DIR / "run_manifest.json"
CHAPTER_REVIEW_LEDGER_PATH = RUN_DIR / "chapter_review_ledger.jsonl"
REPORT_PATH = RUN_DIR / "analysis_report.md"
FORMULA_XLSX_PATH = RUN_DIR / "financial_output_formula.xlsx"
FINAL_XLSX_PATH = RUN_DIR / "financial_output.xlsx"


def load_jsonl(path: Path):
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def format_bn(value: float) -> str:
    return f"{value:,.2f}"


def format_pct(value: float) -> str:
    return f"{value:.2f}%"


chapter_records = load_jsonl(CHAPTER_RECORDS_PATH)
manifest = load_json(RUN_MANIFEST_PATH)

ledger_rows = []
for record in chapter_records:
    topic_tags = record.get("attributes", {}).get("topic_tags", []) or []
    anomalies = record.get("anomalies", []) or []
    evidence = record.get("evidence", []) or []
    findings = record.get("findings", []) or []
    line_span = record.get("attributes", {}).get("line_span", {}) or {}

    if anomalies:
        severity_order = {"extreme": 3, "high": 2, "medium": 1, "low": 0}
        top_anomaly = max(anomalies, key=lambda item: severity_order.get(item.get("severity", "low"), 0))
        conclusion = f"识别到{top_anomaly.get('signal_name', '')}，需要重点复核。"
        risk_level = top_anomaly.get("severity", "medium")
        knowledge_delta = f"补充/确认与{', '.join(topic_tags[:3]) if topic_tags else '该章节'}相关的风险判定口径。"
    else:
        conclusion = f"该章以政策说明或科目口径为主，未见显著异常信号。"
        risk_level = "low"
        knowledge_delta = f"补充{', '.join(topic_tags[:3]) if topic_tags else '本章'}的基础分类规则。"

    if findings:
        first_finding = findings[0]
        finding_text = first_finding.get("detail", "")
    else:
        finding_text = record.get("summary", "")

    evidence_samples = []
    for item in evidence[:3]:
        content = item.get("content", "")
        if content:
            evidence_samples.append(content[:180])
    if not evidence_samples:
        evidence_samples.append(record.get("summary", "")[:180])

    ledger_rows.append(
        {
            "chapter_no": record.get("chapter_no"),
            "note_no": record.get("attributes", {}).get("note_no", ""),
            "chapter_title": record.get("chapter_title", ""),
            "status": record.get("status", ""),
            "line_span": line_span,
            "topic_tags": topic_tags,
            "risk_level": risk_level,
            "chapter_conclusion": conclusion,
            "evidence_samples": evidence_samples,
            "finding_sample": finding_text[:240],
            "knowledge_delta": knowledge_delta,
        }
    )

with CHAPTER_REVIEW_LEDGER_PATH.open("w", encoding="utf-8") as handle:
    for row in ledger_rows:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")

# Core figures from the full report.
metrics = {
    "revenue": 105.3233,
    "cost_of_revenue": 94.8245,
    "gross_profit": 10.4988,
    "net_profit": -10.8650,
    "attributable_net_profit": -11.9466,
    "operating_cf": -3.0387,
    "investing_cf": 2.8441,
    "financing_cf": -14.3319,
    "cash_begin": 84.0094,
    "cash_end": 69.3476,
    "cash_balance": 74.0023,
    "total_assets": 1194.1489,
    "total_liabilities": 872.9883,
    "equity": 321.1605,
    "current_assets": 838.9286,
    "current_liabilities": 641.0728,
    "inventory": 462.5185,
    "contract_liabilities": 158.0031,
    "short_term_borrowings": 23.1457,
    "one_year_due_debt": 134.7131,
    "long_term_borrowings": 178.0513,
    "bonds_payable": 16.2433,
    "lease_liabilities": 15.7539,
    "interest_expense": 4.0427,
    "credit_impairment_loss": 0.3018,
    "asset_impairment_loss": 5.1452,
    "shareholder_borrowings_support": 238.77,
    "cash_and_cash_equiv_support": 69.3476,
}

metrics["gross_margin"] = (metrics["gross_profit"] / metrics["revenue"]) * 100
metrics["net_margin"] = (metrics["net_profit"] / metrics["revenue"]) * 100
metrics["assets_liabilities_ratio"] = metrics["total_assets"] / metrics["total_liabilities"]
metrics["equity_ratio"] = metrics["equity"] / metrics["total_assets"] * 100
metrics["current_ratio"] = metrics["current_assets"] / metrics["current_liabilities"]
metrics["cash_short_debt_ratio"] = metrics["cash_and_cash_equiv_support"] / (metrics["short_term_borrowings"] + metrics["one_year_due_debt"])
metrics["interest_bearing_debt"] = metrics["short_term_borrowings"] + metrics["one_year_due_debt"] + metrics["long_term_borrowings"] + metrics["bonds_payable"] + metrics["lease_liabilities"]
metrics["net_debt"] = metrics["interest_bearing_debt"] - metrics["cash_balance"]
metrics["net_debt_to_equity"] = metrics["net_debt"] / metrics["equity"]
metrics["operating_cf_to_revenue"] = metrics["operating_cf"] / metrics["revenue"] * 100
metrics["interest_coverage_proxy"] = abs(metrics["operating_cf"]) / metrics["interest_expense"]
metrics["inventory_to_assets"] = metrics["inventory"] / metrics["total_assets"] * 100
metrics["contract_liabilities_to_equity"] = metrics["contract_liabilities"] / metrics["equity"] * 100

risk_points = [
    ("持续经营压力", "management has explicitly disclosed a 12-month cash-flow forecast and recurring funding plans; the note set shows substantial shareholder support and refinancing dependence."),
    ("高杠杆与到期债务", "interest-bearing debt remains large relative to equity and cash; short-term borrowings plus current maturities materially exceed cash on hand."),
    ("亏损与减值", "the period remains loss-making, with sizable asset impairment and credit impairment charges compressing earnings."),
    ("存货与去化", "inventory remains the dominant asset class, so real-estate sales execution and price realization remain the key operating hinge."),
    ("合同负债与回款", "contract liabilities remain high, implying a large pre-sale base but also a heavy delivery and settlement obligation."),
    ("关联支持", "large shareholder borrowings and explicit support statements remain an important stabilizer but should be treated as support, not a substitute for operating normalization."),
]

summary_lines = [
    f"# 万科企业股份有限公司 2025 年半年度财务报告正式分析",
    "",
    f"- 运行目录：{RUN_DIR}",
    f"- 解析时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    f"- 报告类型：{manifest.get('entity', {}).get('report_type', '')}",
    f"- 审阅意见：{manifest.get('entity', {}).get('audit_opinion', '')}",
    f"- 附注章数：{len(chapter_records)}",
    "",
    "## 结论先行",
    "万科 2025 年半年度财务报告的主线不是利润扩张，而是流动性修复与债务再平衡。报告期内公司实现营业收入 1053.23 亿元，但归母净亏损 119.47 亿元，经营现金流仍为净流出，且持续经营段落明确依赖销售回款、资产盘活、债务续期、再融资和大股东借款等多重措施。",
    "",
    "从信用角度看，最重要的不是单季损益，而是三组关系：一是货币资金 740.02 亿元对比短期借款、一年内到期负债及其他高频到期债务；二是存货 4625.19 亿元与合同负债 1580.03 亿元的去化与交付链条；三是 51.45 亿元资产减值损失与 3.02 亿元信用减值损失，说明资产质量与回款压力仍在。",
    "",
    "## 重大风险发现",
]
for title, text in risk_points:
    summary_lines.append(f"- {title}：{text}")

summary_lines.extend([
    "",
    "## 关键计算",
    f"- 营业收入：{format_bn(metrics['revenue'])} 亿元",
    f"- 营业成本：{format_bn(metrics['cost_of_revenue'])} 亿元",
    f"- 毛利额：{format_bn(metrics['gross_profit'])} 亿元，毛利率 {format_pct(metrics['gross_margin'])}",
    f"- 归母净利润：{format_bn(metrics['attributable_net_profit'])} 亿元",
    f"- 净利润率：{format_pct(metrics['net_margin'])}",
    f"- 经营活动现金流净额：{format_bn(metrics['operating_cf'])} 亿元，占收入 {format_pct(metrics['operating_cf_to_revenue'])}",
    f"- 总资产：{format_bn(metrics['total_assets'])} 亿元；总负债：{format_bn(metrics['total_liabilities'])} 亿元；权益：{format_bn(metrics['equity'])} 亿元",
    f"- 资产负债率：{format_pct(metrics['total_liabilities'] / metrics['total_assets'] * 100)}；权益率：{format_pct(metrics['equity_ratio'])}",
    f"- 有息负债近似合计：{format_bn(metrics['interest_bearing_debt'])} 亿元",
    f"- 现金短债比（现金/短期借款+一年内到期负债）：{metrics['cash_short_debt_ratio']:.2f} 倍",
    f"- 净债务近似值：{format_bn(metrics['net_debt'])} 亿元；净债务/权益：{metrics['net_debt_to_equity']:.2f} 倍",
    f"- 存货占总资产比重：{format_pct(metrics['inventory_to_assets'])}",
    f"- 合同负债/权益：{format_pct(metrics['contract_liabilities_to_equity'])}",
    f"- 利息支出：{format_bn(metrics['interest_expense'])} 亿元；经营现金流/利息支出近似覆盖：{metrics['interest_coverage_proxy']:.2f}x",
    "",
    "## 按附注科目阅读",
])

chapter_groups = [
    ("持续经营与会计政策", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]),
    ("应收、存货与减值", [12, 13, 14, 15, 16, 17, 18]),
    ("负债、债券与合同负债", [19, 20, 21, 22, 23, 24, 25, 26, 27, 28]),
    ("利润表与现金流", [29, 30, 31, 32, 33, 34, 35]),
    ("合并范围、风险与关联方", [36, 37, 38, 39, 40, 41, 42]),
    ("母公司与补充资料", [43, 44, 45, 46, 47, 48, 49, 50]),
]

ledger_by_no = {row["chapter_no"]: row for row in ledger_rows}
for group_title, chapter_nos in chapter_groups:
    summary_lines.append(f"### {group_title}")
    for chapter_no in chapter_nos:
        row = ledger_by_no.get(chapter_no)
        if not row:
            continue
        topic_text = "、".join(row.get("topic_tags", [])[:4])
        summary_lines.append(
            f"- 第{chapter_no}章：{row.get('chapter_title', '')}。{row.get('chapter_conclusion', '')} 主题：{topic_text}。"
        )

summary_lines.extend([
    "",
    "## 证据链",
    "- 持续经营段落明确提到 12 个月现金流量预测、债务续期、再融资和大股东借款，说明当前分析核心仍是流动性兜底而非纯经营扩张。",
    "- 合并资产负债表显示总资产 1.194 万亿元、总负债 0.873 万亿元，存货是资产结构中的绝对大头。",
    "- 利润表显示收入仍在百亿级，但减值、财务费用和经营压力共同压缩了利润。",
    "- 现金流量表显示经营现金流仍为净流出，意味着回款节奏仍未完全匹配交付与扩张节奏。",
    "",
    "## 学习点",
    "- 对房地产/高杠杆主体，先看现金与短债，再看存货与合同负债，最后看利润表，避免被收入规模误导。",
    "- 持续经营段落若出现明确的滚动融资与大股东支持，必须写成信用缓释措施，而不能误写成经营风险已解除。",
    "- 资产减值与信用减值并存时，说明问题不只是利润波动，而是资产周转和回款质量同时承压。",
    "",
    "## 结语",
    "本案正式结论是：万科已进入以流动性管理、债务展期和资产盘活为核心的防守阶段，后续观察重点应放在销售回款、债务到期滚动、存货去化、减值是否继续扩大，以及股东支持是否能持续兑现。",
])

REPORT_PATH.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

# Workbook generation helper.

def build_workbook(path: Path, formula_mode: bool):
    workbook = xlsxwriter.Workbook(str(path))

    fmt_title = workbook.add_format({"bold": True, "font_size": 16})
    fmt_subtitle = workbook.add_format({"bold": True, "font_size": 12})
    fmt_header = workbook.add_format({"bold": True, "bg_color": "#D9E2F3", "border": 1, "align": "center", "valign": "vcenter"})
    fmt_text = workbook.add_format({"text_wrap": True, "valign": "top"})
    fmt_num = workbook.add_format({"num_format": '0.00', "align": "right"})
    fmt_pct = workbook.add_format({"num_format": '0.00%', "align": "right"})
    fmt_note = workbook.add_format({"text_wrap": True, "font_color": "#555555"})

    ws = workbook.add_worksheet("00_Overview")
    ws.set_column("A:A", 18)
    ws.set_column("B:B", 24)
    ws.set_column("C:D", 18)
    ws.set_column("E:H", 16)
    ws.write("A1", "万科企业股份有限公司 2025 年半年度财务分析", fmt_title)
    ws.write("A3", "报告类型", fmt_subtitle)
    ws.write("B3", manifest.get("entity", {}).get("report_type", ""), fmt_text)
    ws.write("A4", "审阅意见", fmt_subtitle)
    ws.write("B4", manifest.get("entity", {}).get("audit_opinion", ""), fmt_text)
    ws.write("A5", "附注章数", fmt_subtitle)
    ws.write_number("B5", len(chapter_records))
    ws.write("A6", "持续经营判断", fmt_subtitle)
    ws.write("B6", "存在显著流动性压力，需依赖回款、展期和股东支持", fmt_text)
    ws.write("A8", "关键结论", fmt_subtitle)
    ws.write("A9", "1", fmt_header)
    ws.write("B9", "收入仍有规模，但盈利和现金流质量偏弱", fmt_text)
    ws.write("A10", "2", fmt_header)
    ws.write("B10", "短债、当前到期负债与现金之间存在明显缺口", fmt_text)
    ws.write("A11", "3", fmt_header)
    ws.write("B11", "存货去化、合同负债兑现和减值控制是核心观察点", fmt_text)

    ws2 = workbook.add_worksheet("01_Key_Metrics")
    ws2.set_column("A:A", 34)
    ws2.set_column("B:B", 14)
    ws2.set_column("C:C", 14)
    ws2.set_column("D:D", 28)
    ws2.write_row("A1", ["指标", "数值(亿元)", "单位", "说明"], fmt_header)
    rows = [
        ("营业收入", metrics["revenue"], "亿元", "合并利润表"),
        ("营业成本", metrics["cost_of_revenue"], "亿元", "合并利润表"),
        ("毛利额", metrics["gross_profit"], "亿元", "收入-成本"),
        ("归母净利润", metrics["attributable_net_profit"], "亿元", "合并利润表"),
        ("经营活动现金流净额", metrics["operating_cf"], "亿元", "合并现金流量表"),
        ("总资产", metrics["total_assets"], "亿元", "合并资产负债表"),
        ("总负债", metrics["total_liabilities"], "亿元", "合并资产负债表"),
        ("股东权益", metrics["equity"], "亿元", "合并资产负债表"),
        ("存货", metrics["inventory"], "亿元", "合并资产负债表"),
        ("合同负债", metrics["contract_liabilities"], "亿元", "合并资产负债表"),
        ("短期借款", metrics["short_term_borrowings"], "亿元", "合并资产负债表"),
        ("一年内到期的非流动负债", metrics["one_year_due_debt"], "亿元", "合并资产负债表"),
        ("长期借款", metrics["long_term_borrowings"], "亿元", "合并资产负债表"),
        ("应付债券", metrics["bonds_payable"], "亿元", "合并资产负债表"),
        ("租赁负债", metrics["lease_liabilities"], "亿元", "合并资产负债表"),
    ]
    for idx, (label, value, unit, note) in enumerate(rows, start=2):
        ws2.write(f"A{idx}", label)
        ws2.write_number(f"B{idx}", value, fmt_num)
        ws2.write(f"C{idx}", unit)
        ws2.write(f"D{idx}", note, fmt_text)

    ws3 = workbook.add_worksheet("02_Ratios")
    ws3.set_column("A:A", 34)
    ws3.set_column("B:B", 14)
    ws3.set_column("C:C", 14)
    ws3.write_row("A1", ["比率", "数值", "解释"], fmt_header)
    ratio_rows = [
        ("毛利率", metrics["gross_margin"], "毛利额/收入"),
        ("净利率", metrics["net_margin"], "归母净利润/收入"),
        ("资产负债率", metrics["total_liabilities"] / metrics["total_assets"], "总负债/总资产"),
        ("权益率", metrics["equity_ratio"] / 100, "股东权益/总资产"),
        ("流动比率", metrics["current_ratio"], "流动资产/流动负债"),
        ("现金短债比", metrics["cash_short_debt_ratio"], "现金/短期借款+一年内到期负债"),
        ("净债务/权益", metrics["net_debt_to_equity"], "净债务/股东权益"),
    ]
    for idx, (label, value, explain) in enumerate(ratio_rows, start=2):
        ws3.write(f"A{idx}", label)
        if formula_mode and idx in {2, 3, 4, 5, 6, 7, 8}:
            # Keep formulas visible in the formula workbook.
            if label == "毛利率":
                ws3.write_formula(f"B{idx}", "=ROUND('01_Key_Metrics'!B4/'01_Key_Metrics'!B2,4)", fmt_pct, metrics["gross_margin"] / 100)
            elif label == "净利率":
                ws3.write_formula(f"B{idx}", "=ROUND('01_Key_Metrics'!B5/'01_Key_Metrics'!B2,4)", fmt_pct, metrics["net_margin"] / 100)
            elif label == "资产负债率":
                ws3.write_formula(f"B{idx}", "='01_Key_Metrics'!B8/'01_Key_Metrics'!B7", fmt_pct, metrics["total_liabilities"] / metrics["total_assets"])
            elif label == "权益率":
                ws3.write_formula(f"B{idx}", "='01_Key_Metrics'!B9/'01_Key_Metrics'!B7", fmt_pct, metrics["equity_ratio"] / 100)
            elif label == "流动比率":
                ws3.write_formula(f"B{idx}", "='01_Key_Metrics'!B10/'01_Key_Metrics'!B11", fmt_num, metrics["current_ratio"])
            elif label == "现金短债比":
                ws3.write_formula(f"B{idx}", "='01_Key_Metrics'!B16/('01_Key_Metrics'!B12+'01_Key_Metrics'!B13)", fmt_num, metrics["cash_short_debt_ratio"])
            elif label == "净债务/权益":
                ws3.write_formula(f"B{idx}", "=(('01_Key_Metrics'!B12+'01_Key_Metrics'!B13+'01_Key_Metrics'!B14+'01_Key_Metrics'!B15+'01_Key_Metrics'!B16)-'01_Key_Metrics'!B17)/'01_Key_Metrics'!B9", fmt_num, metrics["net_debt_to_equity"])
        else:
            if label == "毛利率":
                ws3.write_number(f"B{idx}", metrics["gross_margin"] / 100, fmt_pct)
            elif label == "净利率":
                ws3.write_number(f"B{idx}", metrics["net_margin"] / 100, fmt_pct)
            elif label == "资产负债率":
                ws3.write_number(f"B{idx}", metrics["total_liabilities"] / metrics["total_assets"], fmt_pct)
            elif label == "权益率":
                ws3.write_number(f"B{idx}", metrics["equity_ratio"] / 100, fmt_pct)
            else:
                ws3.write_number(f"B{idx}", value, fmt_num)
        ws3.write(f"C{idx}", explain, fmt_text)

    ws4 = workbook.add_worksheet("03_Review_Ledger")
    ws4.set_column("A:A", 8)
    ws4.set_column("B:B", 20)
    ws4.set_column("C:C", 32)
    ws4.set_column("D:D", 12)
    ws4.set_column("E:E", 26)
    ws4.set_column("F:F", 18)
    ws4.set_column("G:G", 28)
    ws4.set_column("H:H", 42)
    ws4.write_row("A1", ["章号", "附注编号", "章节标题", "风险", "结论", "知识增量", "证据片段", "题材关键词"], fmt_header)
    for row_idx, row in enumerate(ledger_rows, start=2):
        ws4.write_number(f"A{row_idx}", row["chapter_no"], fmt_num)
        ws4.write(f"B{row_idx}", row.get("note_no", ""))
        ws4.write(f"C{row_idx}", row.get("chapter_title", ""), fmt_text)
        ws4.write(f"D{row_idx}", row.get("risk_level", ""))
        ws4.write(f"E{row_idx}", row.get("chapter_conclusion", ""), fmt_text)
        ws4.write(f"F{row_idx}", row.get("knowledge_delta", ""), fmt_text)
        ws4.write(f"G{row_idx}", "\n".join(row.get("evidence_samples", [])), fmt_text)
        ws4.write(f"H{row_idx}", "、".join(row.get("topic_tags", [])), fmt_text)

    ws5 = workbook.add_worksheet("99_Evidence_Index")
    ws5.set_column("A:A", 12)
    ws5.set_column("B:B", 24)
    ws5.set_column("C:C", 48)
    ws5.set_column("D:D", 20)
    ws5.set_column("E:E", 20)
    ws5.write_row("A1", ["证据类型", "来源", "片段", "章节", "页码/行区间"], fmt_header)
    evidence_rows = [
        ("持续经营", "note 1/2", "12个月现金流量预测、债务续期、再融资、大股东借款", "第1-2章", "PAGE 16-17"),
        ("资产负债表", "statement", "总资产 1,194,148,874,774.55；总负债 872,988,331,813.49", "合并资产负债表", "PAGE 3-4"),
        ("利润表", "statement", "收入 105,323,304,409.14；归母净亏损 11,946,573,688.12", "合并利润表", "PAGE 6-7"),
        ("现金流量表", "statement", "经营现金流净额 -3,038,704,592.78", "合并现金流量表", "PAGE 9-10"),
        ("减值", "note 8", "预期信用损失、逾期30/90日判定", "金融工具减值", "PAGE 26-28"),
        ("存货", "note 12", "房地产开发产品、在建开发产品、拟开发产品", "应收账款/存货", "PAGE 33-34"),
        ("债务", "note 25/31/32", "合同负债、长期借款、应付债券", "负债相关注释", "PAGE 39-45"),
    ]
    for idx, item in enumerate(evidence_rows, start=2):
        for col_idx, value in enumerate(item):
            ws5.write(idx - 1, col_idx, value, fmt_text)

    workbook.close()


build_workbook(FORMULA_XLSX_PATH, formula_mode=True)
build_workbook(FINAL_XLSX_PATH, formula_mode=False)

print(FORMULA_XLSX_PATH)
print(FINAL_XLSX_PATH)
print(REPORT_PATH)
print(CHAPTER_REVIEW_LEDGER_PATH)
