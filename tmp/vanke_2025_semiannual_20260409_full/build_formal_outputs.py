from __future__ import annotations

import json
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


def fmt_bn(value: float) -> str:
    return f"{value:,.2f}"


def fmt_pct(value: float) -> str:
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
        conclusion = "该章以科目口径或披露说明为主，未见显著异常信号。"
        risk_level = "low"
        knowledge_delta = f"补充{', '.join(topic_tags[:3]) if topic_tags else '本章'}的基础分类规则。"

    finding_text = findings[0].get("detail", "") if findings else record.get("summary", "")
    evidence_samples = [item.get("content", "")[:180] for item in evidence[:3] if item.get("content")]
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
    "restricted_cash": 4.6547,
    "total_assets": 1194.1489,
    "total_liabilities": 872.9883,
    "equity": 321.1605,
    "current_assets": 838.9286,
    "current_liabilities": 641.0728,
    "inventory": 462.5185,
    "contract_assets": 123.3782,
    "contract_liabilities": 158.0031,
    "other_receivables": 215.2598,
    "investment_property": 137.3630,
    "short_term_borrowings": 23.1156,
    "one_year_due_debt": 134.7131,
    "long_term_borrowings": 178.0513,
    "bonds_payable": 43.6020,
    "lease_liabilities": 15.7539,
    "interest_expense": 4.0427,
    "credit_impairment_loss": 0.3018,
    "asset_impairment_loss": 5.1452,
    "shareholder_support": 238.80,
    "public_debt_repaid": 243.90,
    "capitalized_interest": 1.7423,
}

metrics["gross_margin"] = metrics["gross_profit"] / metrics["revenue"]
metrics["net_margin"] = metrics["net_profit"] / metrics["revenue"]
metrics["asset_liability_ratio"] = metrics["total_liabilities"] / metrics["total_assets"]
metrics["equity_ratio"] = metrics["equity"] / metrics["total_assets"]
metrics["current_ratio"] = metrics["current_assets"] / metrics["current_liabilities"]
metrics["cash_short_debt_ratio"] = metrics["cash_balance"] / (metrics["short_term_borrowings"] + metrics["one_year_due_debt"])
metrics["interest_bearing_debt"] = metrics["short_term_borrowings"] + metrics["one_year_due_debt"] + metrics["long_term_borrowings"] + metrics["bonds_payable"] + metrics["lease_liabilities"]
metrics["net_debt"] = metrics["interest_bearing_debt"] - metrics["cash_balance"]
metrics["net_debt_to_equity"] = metrics["net_debt"] / metrics["equity"]
metrics["ocf_to_revenue"] = metrics["operating_cf"] / metrics["revenue"]
metrics["inventory_to_assets"] = metrics["inventory"] / metrics["total_assets"]
metrics["contract_liabilities_to_equity"] = metrics["contract_liabilities"] / metrics["equity"]

chapter_map = {row["chapter_no"]: row for row in ledger_rows}
key_chapters = [1, 3, 5, 6, 7, 8, 9, 10, 12, 15, 23, 25, 28, 29, 31, 32, 33, 41, 47, 48, 49, 52, 55, 56, 57, 58, 59]

summary_lines = [
    "# 万科企业股份有限公司 2025 年半年度财务分析",
    "",
    f"- 运行目录：{RUN_DIR}",
    f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    f"- 报告类型：{manifest.get('entity', {}).get('report_type', '')}",
    f"- 审阅意见：{manifest.get('entity', {}).get('audit_opinion', '')}",
    f"- 附注章数：{len(chapter_records)}",
    "",
    "## 结论先行",
    "本期分析的主线仍然是流动性修复而不是利润扩张。营业收入维持百亿级，但归母净亏损和经营现金流净流出并未同步修复，持续经营段落明确依赖回款、债务续期、再融资和大股东支持。",
    "",
    "## 核心判断",
    "- 现金并不等于可用现金，受限资金和近端债务会显著压缩真实缓冲。",
    "- 存货、合同负债和减值是最重要的信用分析三角。",
    "- 股东支持和再融资是缓冲项，不应被误写成经营问题已解决。",
    "",
    "## 关键数字",
    f"- 营业收入 {fmt_bn(metrics['revenue'])} 亿元，毛利率 {fmt_pct(metrics['gross_margin'] * 100)}。",
    f"- 归母净亏损 {fmt_bn(metrics['attributable_net_profit'])} 亿元，净利率 {fmt_pct(metrics['net_margin'] * 100)}。",
    f"- 经营活动现金流净额 {fmt_bn(metrics['operating_cf'])} 亿元，现金短债比 {metrics['cash_short_debt_ratio']:.2f} 倍。",
    f"- 总资产 {fmt_bn(metrics['total_assets'])} 亿元、总负债 {fmt_bn(metrics['total_liabilities'])} 亿元、权益 {fmt_bn(metrics['equity'])} 亿元。",
    f"- 有息负债近似合计 {fmt_bn(metrics['interest_bearing_debt'])} 亿元，净债务/权益 {metrics['net_debt_to_equity']:.2f} 倍。",
    f"- 存货占总资产比重 {fmt_pct(metrics['inventory_to_assets'] * 100)}，合同负债/权益 {fmt_pct(metrics['contract_liabilities_to_equity'] * 100)}。",
    "",
    "## 章节阅读摘要",
]

for no in key_chapters:
    row = chapter_map.get(no)
    if not row:
        continue
    summary_lines.append(f"- 第{no}章 {row['chapter_title']}：{row['chapter_conclusion']} 主题：{'、'.join(row.get('topic_tags', [])[:4])}。")

summary_lines.extend([
    "",
    "## 证据链",
    "- 货币资金、受限资金和短债合并判断，决定了真实流动性而不是名义现金。",
    "- 存货和合同负债共同反映交付与去化节奏。",
    "- 减值、信用减值和利润补充资料说明资产质量压力仍在。",
    "- 股东借款和公开债务偿还是当前阶段的主要缓冲机制。",
])

REPORT_PATH.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")


def write_table(ws, start_row: int, headers, rows, widths=None):
    if widths:
        for col_idx, width in widths.items():
            ws.set_column(col_idx - 1, col_idx - 1, width)
    for col_idx, header in enumerate(headers):
        ws.write(start_row - 1, col_idx, header, HEADER_FMT)
    for row_offset, row in enumerate(rows, start=0):
        for col_idx, value in enumerate(row):
            if isinstance(value, (int, float)):
                ws.write_number(start_row + row_offset, col_idx, value, NUM_FMT)
            else:
                ws.write(start_row + row_offset, col_idx, value, TEXT_FMT)


def title_block(ws, title, subtitle):
    ws.write("A1", title, TITLE_FMT)
    ws.write("A2", subtitle, SUBTITLE_FMT)
    ws.freeze_panes(3, 0)


def build_workbook(path: Path, formula_mode: bool):
    wb = xlsxwriter.Workbook(str(path))
    global TITLE_FMT, SUBTITLE_FMT, HEADER_FMT, TEXT_FMT, NUM_FMT, PCT_FMT, BOX_FMT
    TITLE_FMT = wb.add_format({"bold": True, "font_size": 16})
    SUBTITLE_FMT = wb.add_format({"bold": True, "font_size": 11, "font_color": "#444444"})
    HEADER_FMT = wb.add_format({"bold": True, "bg_color": "#D9E2F3", "border": 1, "align": "center", "valign": "vcenter"})
    TEXT_FMT = wb.add_format({"text_wrap": True, "valign": "top"})
    NUM_FMT = wb.add_format({"num_format": '0.00', "align": "right"})
    PCT_FMT = wb.add_format({"num_format": '0.00%', "align": "right"})
    BOX_FMT = wb.add_format({"text_wrap": True, "valign": "top", "border": 1})

    ws = wb.add_worksheet("00_overview")
    ws.set_column("A:A", 18)
    ws.set_column("B:B", 58)
    ws.set_column("C:H", 14)
    title_block(ws, "万科企业股份有限公司 2025 年半年度财务分析", "结构已对齐到 target 的 11-sheet 框架，内容聚焦流动性、债务、存货和减值。")
    overview_rows = [
        ["报告类型", manifest.get("entity", {}).get("report_type", "")],
        ["审阅意见", manifest.get("entity", {}).get("audit_opinion", "")],
        ["附注章数", len(chapter_records)],
        ["持续经营", "存在显著压力，依赖回款、展期、再融资和股东支持"],
        ["核心结论", "利润和现金流仍未修复，信用分析重点仍是流动性和资产质量"],
    ]
    write_table(ws, 4, ["项目", "内容"], overview_rows, widths={1: 18, 2: 58})
    ws.write("A11", "工作流提示", SUBTITLE_FMT)
    ws.write("A12", "本次输出采用 notes-first 路径，先读附注、再做分类、再出公式工作簿和正式工作簿。", BOX_FMT)

    ws = wb.add_worksheet("01_kpi_dashboard")
    ws.set_column("A:A", 26)
    ws.set_column("B:C", 14)
    ws.set_column("D:D", 34)
    title_block(ws, "KPI Dashboard", "把收入、利润、现金、债务和存货放在一张表里看。")
    kpi_rows = [
        ["营业收入", metrics["revenue"], "亿元", "合并利润表"],
        ["归母净利润", metrics["attributable_net_profit"], "亿元", "合并利润表"],
        ["经营现金流净额", metrics["operating_cf"], "亿元", "合并现金流量表"],
        ["总资产", metrics["total_assets"], "亿元", "合并资产负债表"],
        ["总负债", metrics["total_liabilities"], "亿元", "合并资产负债表"],
        ["存货", metrics["inventory"], "亿元", "合并资产负债表"],
        ["合同负债", metrics["contract_liabilities"], "亿元", "合并资产负债表"],
        ["现金余额", metrics["cash_balance"], "亿元", "现金流/货币资金"],
        ["受限资金", metrics["restricted_cash"], "亿元", "货币资金注释"],
        ["现金短债比", metrics["cash_short_debt_ratio"], "倍", "现金/短债"],
        ["净债务/权益", metrics["net_debt_to_equity"], "倍", "有息负债-现金"],
    ]
    for idx, row in enumerate(kpi_rows, start=4):
        ws.write(f"A{idx}", row[0], TEXT_FMT)
        if formula_mode and row[0] == "现金短债比":
            ws.write_formula(f"B{idx}", "='02_financial_summary'!B12/('02_financial_summary'!B10+'02_financial_summary'!B11)", NUM_FMT, row[1])
        elif formula_mode and row[0] == "净债务/权益":
            ws.write_formula(f"B{idx}", "=(('02_financial_summary'!B10+'02_financial_summary'!B11+'02_financial_summary'!B14+'02_financial_summary'!B15+'02_financial_summary'!B16)-'02_financial_summary'!B12)/'02_financial_summary'!B8", NUM_FMT, row[1])
        else:
            ws.write_number(f"B{idx}", row[1], NUM_FMT)
        ws.write(f"C{idx}", row[2], TEXT_FMT)
        ws.write(f"D{idx}", row[3], TEXT_FMT)

    ws = wb.add_worksheet("02_financial_summary")
    ws.set_column("A:A", 30)
    ws.set_column("B:B", 14)
    ws.set_column("C:C", 12)
    ws.set_column("D:D", 34)
    title_block(ws, "Financial Summary", "资产负债表、利润表、现金流量表的合并摘要。")
    summary_rows = [
        ["营业收入", metrics["revenue"], "亿元", "收入规模"],
        ["营业成本", metrics["cost_of_revenue"], "亿元", "成本规模"],
        ["毛利额", metrics["gross_profit"], "亿元", "收入-成本"],
        ["归母净利润", metrics["attributable_net_profit"], "亿元", "利润表"],
        ["经营现金流净额", metrics["operating_cf"], "亿元", "现金流量表"],
        ["总资产", metrics["total_assets"], "亿元", "资产负债表"],
        ["总负债", metrics["total_liabilities"], "亿元", "资产负债表"],
        ["股东权益", metrics["equity"], "亿元", "资产负债表"],
        ["现金余额", metrics["cash_balance"], "亿元", "货币资金"],
        ["有息负债", metrics["interest_bearing_debt"], "亿元", "短+长+债券+租赁"],
        ["毛利率", metrics["gross_margin"], "比例", "毛利/收入"],
        ["净利率", metrics["net_margin"], "比例", "净利/收入"],
        ["资产负债率", metrics["asset_liability_ratio"], "比例", "总负债/总资产"],
        ["流动比率", metrics["current_ratio"], "倍", "流动资产/流动负债"],
    ]
    write_table(ws, 4, ["项目", "数值", "单位", "说明"], summary_rows, widths={1: 30, 2: 14, 3: 12, 4: 34})

    ws = wb.add_worksheet("03_debt_profile")
    ws.set_column("A:A", 26)
    ws.set_column("B:B", 14)
    ws.set_column("C:C", 12)
    ws.set_column("D:D", 34)
    title_block(ws, "Debt Profile", "短债、到期负债、长债、债券和租赁负债放在一起看。")
    debt_rows = [
        ["短期借款", metrics["short_term_borrowings"], "亿元", "短期融资"],
        ["一年内到期的非流动负债", metrics["one_year_due_debt"], "亿元", "近端到期"],
        ["长期借款", metrics["long_term_borrowings"], "亿元", "中长期融资"],
        ["应付债券", metrics["bonds_payable"], "亿元", "公开债"],
        ["租赁负债", metrics["lease_liabilities"], "亿元", "广义债务"],
        ["有息负债合计", metrics["interest_bearing_debt"], "亿元", "合计口径"],
        ["现金余额", metrics["cash_balance"], "亿元", "抵扣项"],
        ["净债务", metrics["net_debt"], "亿元", "有息负债-现金"],
        ["净债务/权益", metrics["net_debt_to_equity"], "倍", "杠杆比率"],
        ["股东借款支持", metrics["shareholder_support"], "亿元", "流动性支持"],
        ["公开债务偿还", metrics["public_debt_repaid"], "亿元", "已完成偿付"],
    ]
    write_table(ws, 4, ["项目", "数值", "单位", "说明"], debt_rows, widths={1: 26, 2: 14, 3: 12, 4: 34})

    ws = wb.add_worksheet("04_liquidity_and_covenants")
    ws.set_column("A:A", 28)
    ws.set_column("B:B", 14)
    ws.set_column("C:C", 12)
    ws.set_column("D:D", 34)
    title_block(ws, "Liquidity and Covenants", "现金、受限资金、短债和支持项一起看。")
    liquidity_rows = [
        ["现金余额", metrics["cash_balance"], "亿元", "可用度高于名义现金口径"],
        ["受限资金", metrics["restricted_cash"], "亿元", "不能完全计入缓冲"],
        ["短期借款", metrics["short_term_borrowings"], "亿元", "短端融资"],
        ["一年内到期负债", metrics["one_year_due_debt"], "亿元", "刚性到期"],
        ["现金短债比", metrics["cash_short_debt_ratio"], "倍", "基本流动性指标"],
        ["股东借款支持", metrics["shareholder_support"], "亿元", "重要缓冲"],
        ["公开债务偿还", metrics["public_debt_repaid"], "亿元", "已兑现支持"],
        ["持续经营判断", 0, "—", "仍需依赖多重融资安排"],
    ]
    write_table(ws, 4, ["项目", "数值", "单位", "说明"], liquidity_rows, widths={1: 28, 2: 14, 3: 12, 4: 34})

    ws = wb.add_worksheet("05_asset_quality")
    ws.set_column("A:A", 30)
    ws.set_column("B:B", 14)
    ws.set_column("C:C", 12)
    ws.set_column("D:D", 34)
    title_block(ws, "Asset Quality", "存货、其他应收款、合同资产和投资性房地产是资产质量核心。")
    asset_rows = [
        ["存货", metrics["inventory"], "亿元", "去化和减值压力最大"],
        ["其他应收款", metrics["other_receivables"], "亿元", "合作方/联营往来沉淀"],
        ["合同资产", metrics["contract_assets"], "亿元", "建造合同"],
        ["投资性房地产", metrics["investment_property"], "亿元", "商业资产"],
        ["资产减值损失", metrics["asset_impairment_loss"], "亿元", "利润冲减"],
        ["信用减值损失", metrics["credit_impairment_loss"], "亿元", "回款风险"],
        ["存货/总资产", metrics["inventory_to_assets"], "比例", "资产占用"],
        ["受限资金", metrics["restricted_cash"], "亿元", "可用现金折减项"],
    ]
    write_table(ws, 4, ["项目", "数值", "单位", "说明"], asset_rows, widths={1: 30, 2: 14, 3: 12, 4: 34})

    ws = wb.add_worksheet("06_cash_flow_bridge")
    ws.set_column("A:A", 28)
    ws.set_column("B:B", 14)
    ws.set_column("C:C", 12)
    ws.set_column("D:D", 34)
    title_block(ws, "Cash Flow Bridge", "从利润到现金的桥梁。")
    bridge_rows = [
        ["归母净亏损", metrics["attributable_net_profit"], "亿元", "利润端起点"],
        ["经营现金流净额", metrics["operating_cf"], "亿元", "现金结果"],
        ["投资现金流净额", metrics["investing_cf"], "亿元", "资产盘活/投资"],
        ["筹资现金流净额", metrics["financing_cf"], "亿元", "滚动融资"],
        ["资产减值损失", metrics["asset_impairment_loss"], "亿元", "利润桥梁"],
        ["信用减值损失", metrics["credit_impairment_loss"], "亿元", "利润桥梁"],
        ["资本化利息", metrics["capitalized_interest"], "亿元", "存货/在建工程"],
    ]
    write_table(ws, 4, ["项目", "数值", "单位", "说明"], bridge_rows, widths={1: 28, 2: 14, 3: 12, 4: 34})

    ws = wb.add_worksheet("07_notes_map")
    ws.set_column("A:A", 8)
    ws.set_column("B:B", 22)
    ws.set_column("C:C", 14)
    ws.set_column("D:D", 20)
    ws.set_column("E:E", 48)
    ws.set_column("F:F", 24)
    title_block(ws, "Notes Map", "把最关键的附注章节映射成可回溯的工作底稿索引。")
    note_rows = []
    for no in key_chapters:
        row = chapter_map.get(no)
        if not row:
            continue
        span = row.get("line_span", {})
        note_rows.append([
            row["chapter_no"],
            row["chapter_title"],
            row.get("note_no", ""),
            f"{span.get('start', '')}-{span.get('end', '')}",
            row.get("finding_sample", "")[:140],
            "、".join(row.get("topic_tags", [])[:4]),
        ])
    write_table(ws, 4, ["章号", "章节", "附注", "行区间", "关键摘要", "主题标签"], note_rows, widths={1: 8, 2: 22, 3: 10, 4: 14, 5: 48, 6: 24})

    ws = wb.add_worksheet("08_management_support")
    ws.set_column("A:A", 28)
    ws.set_column("B:B", 14)
    ws.set_column("C:C", 12)
    ws.set_column("D:D", 34)
    title_block(ws, "Management Support", "把股东支持、债务偿还和再融资窗口单独列出来。")
    support_rows = [
        ["深铁集团借款支持", metrics["shareholder_support"], "亿元", "最重要的流动性缓冲"],
        ["公开债务偿还", metrics["public_debt_repaid"], "亿元", "已完成偿付"],
        ["持续经营预测", 0, "—", "未来12个月资金安排已披露"],
        ["管理层判断", 0, "—", "短期依靠支持和回款"],
    ]
    write_table(ws, 4, ["事项", "数值", "单位", "说明"], support_rows, widths={1: 28, 2: 14, 3: 12, 4: 34})
    ws.write("A10", "原文摘要", SUBTITLE_FMT)
    ws.write("A11", "报告正文持续强调：股东支持、销售回款、资产处置、债务续期和再融资。", BOX_FMT)

    ws = wb.add_worksheet("09_capital_structure")
    ws.set_column("A:A", 28)
    ws.set_column("B:B", 14)
    ws.set_column("C:C", 12)
    ws.set_column("D:D", 34)
    title_block(ws, "Capital Structure", "杠杆、权益和净债务的结构化观察。")
    capital_rows = [
        ["总资产", metrics["total_assets"], "亿元", "分母"],
        ["总负债", metrics["total_liabilities"], "亿元", "分子"],
        ["股东权益", metrics["equity"], "亿元", "资本缓冲"],
        ["有息负债", metrics["interest_bearing_debt"], "亿元", "短+长+债券+租赁"],
        ["净债务", metrics["net_debt"], "亿元", "有息负债-现金"],
        ["资产负债率", metrics["asset_liability_ratio"], "比例", "总负债/总资产"],
        ["权益率", metrics["equity_ratio"], "比例", "权益/总资产"],
        ["净债务/权益", metrics["net_debt_to_equity"], "倍", "杠杆压力"],
        ["合同负债/权益", metrics["contract_liabilities_to_equity"], "比例", "预收规模"],
    ]
    write_table(ws, 4, ["项目", "数值", "单位", "说明"], capital_rows, widths={1: 28, 2: 14, 3: 12, 4: 34})

    ws = wb.add_worksheet("99_evidence_index")
    ws.set_column("A:A", 12)
    ws.set_column("B:B", 22)
    ws.set_column("C:C", 56)
    ws.set_column("D:D", 18)
    ws.set_column("E:E", 18)
    title_block(ws, "Evidence Index", "把最常用的证据放到索引表里，便于回溯。")
    evidence_rows = [
        ["EVD-0001", "1 货币资金", "受限资金 46.55 亿元、可用现金约 69.35 亿元", "现金与限制", "行 1330-1337"],
        ["EVD-0002", "3 应收账款", "坏账率、账龄和前五名回款集中度", "回款质量", "行 1342-1390"],
        ["EVD-0003", "5 其他应收款", "单项计提 97.47%，沉淀资金规模大", "沉淀资金", "行 1398-1460"],
        ["EVD-0004", "6 存货", "存货 4625.19 亿元、减值 152.41 亿元、抵押 627.47 亿元", "存货压力", "行 1461-1658"],
        ["EVD-0005", "7 合同资产", "合同资产 123.38 亿元，信用风险较小", "合同结算", "行 1659-1678"],
        ["EVD-0006", "8 其他流动资产", "合同取得成本与待抵扣增值税", "流动资产", "行 1679-1694"],
        ["EVD-0007", "12 投资性房地产", "核心商业资产抵押和产权手续", "资产质量", "行 2830-2842"],
        ["EVD-0008", "25 合同负债", "合同负债 1580.03 亿元", "预收房款", "行 2989-3006"],
        ["EVD-0009", "29 一年内到期负债", "一年内到期的非流动负债 1347.13 亿元", "到期压力", "行 3069-3080"],
        ["EVD-0010", "31 长期借款", "借款附带财务契约条件", "融资约束", "行 3089-3121"],
        ["EVD-0011", "32 应付债券", "应付债券 436.02 亿元", "公开债", "行 3122-3143"],
        ["EVD-0012", "33 租赁负债", "租赁负债 157.54 亿元", "广义负债", "行 3144-3149"],
        ["EVD-0013", "55 利润表补充资料", "资产减值与财务费用拖累营业亏损", "利润质量", "行 3345-3350"],
        ["EVD-0014", "57 现金流量补充资料", "经营活动现金流净额 -30.39 亿元", "现金流", "行 3397-3436"],
        ["EVD-0015", "59 租赁", "末章补充信息", "补充披露", "行 3443-end"],
    ]
    write_table(ws, 4, ["证据ID", "来源章节", "证据摘要", "主题", "区间"], evidence_rows, widths={1: 12, 2: 22, 3: 56, 4: 18, 5: 18})

    wb.close()


build_workbook(FORMULA_XLSX_PATH, formula_mode=True)
build_workbook(FINAL_XLSX_PATH, formula_mode=False)

manifest_out = {
    "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    "chapter_count": len(chapter_records),
    "formula_workbook": str(FORMULA_XLSX_PATH),
    "final_workbook": str(FINAL_XLSX_PATH),
    "report": str(REPORT_PATH),
    "ledger": str(CHAPTER_REVIEW_LEDGER_PATH),
}
(RUN_DIR / "formalization_manifest.json").write_text(json.dumps(manifest_out, ensure_ascii=False, indent=2), encoding="utf-8")

print(json.dumps(manifest_out, ensure_ascii=False, indent=2))
