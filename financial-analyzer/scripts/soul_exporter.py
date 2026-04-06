#!/usr/bin/env python3
"""
Soul v1.1-alpha workbook exporter.
"""

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import xlsxwriter
from xlsxwriter.utility import xl_rowcol_to_cell


RISK_TEXT = {
    "extreme": "极高",
    "high": "高",
    "medium": "中",
    "low": "低",
    "unknown": "待补",
}

CATEGORY_LABELS = {
    "leverage": "杠杆",
    "debt_service": "偿债",
    "profitability": "盈利",
    "cashflow": "现金流",
}


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def ensure_parent(path):
    path.parent.mkdir(parents=True, exist_ok=True)


def first_evidence_excerpt(evidence_map, evidence_refs):
    for evidence_id in evidence_refs or []:
        entry = evidence_map.get(evidence_id)
        if entry:
            return entry.get("excerpt", "")
    return ""


def render_preview(output_path):
    soffice_path = shutil.which("soffice")
    if not soffice_path:
        return

    outdir = output_path.parent
    source_pdf = output_path.with_suffix(".pdf")
    preview_pdf = outdir / "preview.pdf"
    if source_pdf.exists():
        source_pdf.unlink()
    if preview_pdf.exists():
        preview_pdf.unlink()
    with tempfile.TemporaryDirectory() as profile_dir:
        subprocess.run(
            [
                soffice_path,
                f"-env:UserInstallation=file://{Path(profile_dir).resolve()}",
                "--headless",
                "--convert-to",
                "pdf:calc_pdf_Export",
                "--outdir",
                str(outdir),
                str(output_path),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    if source_pdf.exists():
        source_pdf.replace(preview_pdf)

    pdftoppm_path = shutil.which("pdftoppm")
    if not pdftoppm_path or not preview_pdf.exists():
        return

    prefix = outdir / "preview"
    for existing in outdir.glob("preview-*.png"):
        existing.unlink()
    subprocess.run(
        [
            pdftoppm_path,
            "-png",
            str(preview_pdf),
            str(prefix),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


class RawValueStore:
    def __init__(self):
        self.entries = []
        self.refs = {}

    def add(self, key, label, value, unit="", note=""):
        if key in self.refs:
            return self.refs[key]
        row_index = len(self.entries) + 2
        self.entries.append({
            "key": key,
            "label": label,
            "value": value,
            "unit": unit,
            "note": note,
            "row_index": row_index,
        })
        self.refs[key] = f"'RAW_INPUTS'!$B${row_index}"
        return self.refs[key]

    def get(self, key):
        return self.refs.get(key)


def raw_formula_ref(raw_ref):
    return f"={raw_ref}"


def add_raw_value(raw_store, key, label, value, unit="", note=""):
    if isinstance(value, (int, float)):
        return raw_store.add(key, label, value, unit, note)
    return None


def first_numeric_value(values):
    first = values[0] if values else {}
    value = first.get("value")
    if isinstance(value, (int, float)):
        return first
    return None


def write_formula_or_number(sheet, row, col, value, fmt, raw_ref=None, formula=None):
    if formula:
        sheet.write_formula(row, col, formula, fmt, value)
    elif raw_ref:
        sheet.write_formula(row, col, raw_formula_ref(raw_ref), fmt, value)
    elif isinstance(value, (int, float)):
        sheet.write_number(row, col, value, fmt)
    elif value is None:
        sheet.write(row, col, "-", fmt)
    else:
        sheet.write(row, col, value, fmt)


def render_raw_inputs_sheet(workbook, raw_store, formats):
    sheet = workbook.add_worksheet("RAW_INPUTS")
    sheet.hide()
    sheet.set_column("A:A", 34)
    sheet.set_column("B:B", 18)
    sheet.set_column("C:C", 12)
    sheet.set_column("D:D", 36)
    sheet.write_row(0, 0, ["键", "数值", "单位", "说明"], formats["header"])
    for entry in raw_store.entries:
        row = entry["row_index"] - 1
        sheet.write(row, 0, entry["label"], formats["text"])
        sheet.write_number(row, 1, entry["value"], formats["number"])
        sheet.write(row, 2, entry["unit"], formats["text"])
        sheet.write(row, 3, entry["note"], formats["text"])


def build_formats(workbook):
    return {
        "title": workbook.add_format({
            "bold": True,
            "font_size": 16,
            "font_color": "#FFFFFF",
            "bg_color": "#16324F",
            "align": "left",
            "valign": "vcenter",
        }),
        "section": workbook.add_format({
            "bold": True,
            "font_size": 11,
            "font_color": "#16324F",
            "bg_color": "#D9E2F3",
            "border": 1,
        }),
        "header": workbook.add_format({
            "bold": True,
            "font_color": "#FFFFFF",
            "bg_color": "#1F4E78",
            "border": 1,
            "align": "center",
            "valign": "vcenter",
        }),
        "subheader": workbook.add_format({
            "bold": True,
            "bg_color": "#EAF0F7",
            "border": 1,
        }),
        "text": workbook.add_format({
            "text_wrap": True,
            "valign": "top",
            "border": 1,
        }),
        "muted": workbook.add_format({
            "text_wrap": True,
            "valign": "top",
            "border": 1,
            "font_color": "#6B7280",
        }),
        "number": workbook.add_format({
            "border": 1,
            "num_format": '#,##0.00;[Red](#,##0.00);-',
        }),
        "integer": workbook.add_format({
            "border": 1,
            "num_format": '#,##0;[Red](#,##0);-',
        }),
        "multiple": workbook.add_format({
            "border": 1,
            "num_format": '0.00"x";[Red](0.00"x");-',
        }),
        "percent_text": workbook.add_format({
            "border": 1,
            "num_format": '0.0"%"',
        }),
        "risk_high": workbook.add_format({
            "border": 1,
            "bg_color": "#FDE9D9",
            "font_color": "#9C0006",
        }),
        "risk_medium": workbook.add_format({
            "border": 1,
            "bg_color": "#FFF2CC",
            "font_color": "#7F6000",
        }),
        "risk_low": workbook.add_format({
            "border": 1,
            "bg_color": "#E2F0D9",
            "font_color": "#385723",
        }),
        "note": workbook.add_format({
            "italic": True,
            "font_color": "#4B5563",
            "text_wrap": True,
        }),
    }


def value_format(formats, unit):
    normalized = str(unit or "").strip()
    if normalized in {"%", "pct", "percent"}:
        return formats["percent_text"]
    if normalized in {"x", "倍", "亿元/x"}:
        return formats["multiple"]
    return formats["number"]


def add_comment(sheet, row, col, evidence_map, evidence_refs):
    excerpt = first_evidence_excerpt(evidence_map, evidence_refs)
    if excerpt:
        sheet.write_comment(row, col, excerpt[:250])


def add_sheet_base(sheet):
    sheet.hide_gridlines(2)
    sheet.freeze_panes(2, 0)


def write_title(sheet, title, subtitle, formats):
    sheet.merge_range(0, 0, 0, 5, title, formats["title"])
    sheet.write(1, 0, subtitle, formats["note"])


def register_section_values(raw_store, prefix, items):
    for item in items or []:
        values = item.get("values") or []
        first = first_numeric_value(values)
        if not first:
            continue
        key = f"{prefix}.{item.get('metric_code') or item.get('row_code') or item.get('label')}"
        add_raw_value(raw_store, key, item.get("label", key), first.get("value"), first.get("unit", ""), item.get("commentary", ""))


def register_topic_values(raw_store, module_key, sections):
    for section in sections or []:
        section_title = section.get("section_title", "section")
        for item in section.get("items", []):
            value = item.get("value")
            if isinstance(value, (int, float)):
                key = f"{module_key}.{section_title}.{item.get('label', '')}"
                add_raw_value(raw_store, key, item.get("label", key), value, item.get("unit", ""), item.get("source_status", ""))


def register_payload_inputs(payload, raw_store):
    formula_inputs = payload.get("formula_inputs", {})
    for key, item in formula_inputs.items():
        add_raw_value(raw_store, f"formula_inputs.{key}", item.get("label", key), item.get("value"), item.get("unit", ""), "公式辅助输入")

    for section in payload.get("kpi_dashboard", {}).get("sections", []):
        for metric in section.get("metrics", []):
            value = metric.get("value")
            if isinstance(value, (int, float)):
                key = f"kpi_dashboard.{section.get('category', 'section')}.{metric.get('metric_code') or metric.get('label', '')}"
                add_raw_value(raw_store, key, metric.get("label", key), value, metric.get("unit", ""), metric.get("source_status", ""))

    financial_summary = payload.get("financial_summary", {}).get("statements", {})
    register_section_values(raw_store, "financial_summary.balance_sheet", financial_summary.get("balance_sheet", []))
    register_section_values(raw_store, "financial_summary.income_statement", financial_summary.get("income_statement", []))
    register_section_values(raw_store, "financial_summary.cash_flow", financial_summary.get("cash_flow", []))

    debt_profile = payload.get("debt_profile", {})
    register_section_values(raw_store, "debt_profile.totals", debt_profile.get("totals", []))
    register_section_values(raw_store, "debt_profile.maturity_buckets", debt_profile.get("maturity_buckets", []))
    register_section_values(raw_store, "debt_profile.financing_mix", debt_profile.get("financing_mix", []))
    register_section_values(raw_store, "debt_profile.rate_profile", debt_profile.get("rate_profile", []))

    liquidity = payload.get("liquidity_and_covenants", {})
    register_section_values(raw_store, "liquidity.cash_metrics", liquidity.get("cash_metrics", []))
    register_section_values(raw_store, "liquidity.restricted_assets", liquidity.get("restricted_assets", []))

    for module in payload.get("optional_modules", []):
        register_topic_values(raw_store, module.get("module_key", "optional"), module.get("payload", {}).get("sections", []))


def render_overview(sheet, payload, evidence_map, formats):
    add_sheet_base(sheet)
    entity = payload["entity_profile"]
    write_title(
        sheet,
        "Soul v1.1-alpha 概览",
        f"{entity['company_name']} | {entity['report_period']} | {entity['currency']} | {entity['industry_tag']}",
        formats,
    )
    sheet.set_column("A:A", 16)
    sheet.set_column("B:B", 22)
    sheet.set_column("C:F", 24)

    row = 3
    sheet.write(row, 0, "公司名称", formats["header"])
    sheet.write(row, 1, entity["company_name"], formats["text"])
    sheet.write(row, 2, "审计意见", formats["header"])
    sheet.write(row, 3, entity["audit_opinion"], formats["text"])
    sheet.write(row, 4, "报告类型", formats["header"])
    sheet.write(row, 5, entity["report_type"], formats["text"])

    row += 2
    sheet.merge_range(row, 0, row, 5, "执行摘要", formats["section"])
    row += 1
    for item in payload["overview"].get("executive_summary", []):
        sheet.merge_range(row, 0, row, 5, item, formats["text"])
        row += 1

    row += 1
    sheet.merge_range(row, 0, row, 5, "关键风险", formats["section"])
    row += 1
    sheet.write_row(row, 0, ["风险", "等级", "说明", "证据"], formats["header"])
    row += 1
    for risk in payload["overview"].get("key_risks", []):
        risk_fmt = formats["risk_high"] if risk["risk_level"] in {"high", "extreme"} else formats["risk_medium"]
        sheet.write(row, 0, risk["label"], formats["text"])
        sheet.write(row, 1, RISK_TEXT.get(risk["risk_level"], risk["risk_level"]), risk_fmt)
        sheet.write(row, 2, risk["description"], formats["text"])
        excerpt = first_evidence_excerpt(evidence_map, risk["evidence_refs"])
        sheet.write(row, 3, excerpt, formats["text"])
        sheet.merge_range(row, 4, row, 5, ", ".join(risk["evidence_refs"]), formats["muted"])
        row += 1

    row += 1
    sheet.merge_range(row, 0, row, 5, "报告亮点", formats["section"])
    row += 1
    for item in payload["overview"].get("report_highlights", []):
        sheet.write(row, 0, item["title"], formats["subheader"])
        sheet.merge_range(row, 1, row, 5, item["detail"], formats["text"])
        add_comment(sheet, row, 1, evidence_map, item.get("evidence_refs", []))
        row += 1


def render_kpi_dashboard(sheet, payload, evidence_map, formats, raw_store):
    add_sheet_base(sheet)
    write_title(sheet, "KPI Dashboard", "固定骨架模块 01", formats)
    sheet.set_column("A:A", 14)
    sheet.set_column("B:B", 22)
    sheet.set_column("C:C", 14)
    sheet.set_column("D:D", 12)
    sheet.set_column("E:E", 12)
    sheet.set_column("F:F", 12)
    sheet.set_column("G:G", 14)
    sheet.set_column("H:H", 24)
    sheet.set_column("J:K", 12, None, {"hidden": True})

    row = 3
    sheet.write_row(row, 0, ["分类", "指标", "当前值", "单位", "风险", "来源", "对比", "证据"], formats["header"])
    row += 1

    for section in payload["kpi_dashboard"].get("sections", []):
        metrics = section.get("metrics", [])
        if not metrics:
            continue
        start_row = row
        for metric in metrics:
            sheet.write(row, 1, metric["label"], formats["text"])
            metric_format = value_format(formats, metric.get("unit"))
            raw_key = f"kpi_dashboard.{section.get('category', 'section')}.{metric.get('metric_code') or metric['label']}"
            raw_ref = raw_store.get(raw_key)
            if metric["metric_code"] == "equity_ratio":
                total_assets_ref = raw_store.get("kpi_dashboard.leverage.total_assets")
                total_liabilities_ref = raw_store.get("kpi_dashboard.leverage.total_liabilities")
                formula = f'=IFERROR(({total_assets_ref}-{total_liabilities_ref})/{total_assets_ref}*100,"")'
                sheet.write_formula(row, 2, formula, metric_format, metric.get("value"))
            elif metric["metric_code"] == "current_ratio":
                current_assets_ref = raw_store.get("financial_summary.balance_sheet.流动资产合计")
                current_liabilities_ref = raw_store.get("financial_summary.balance_sheet.流动负债合计")
                formula = f'=IFERROR({current_assets_ref}/{current_liabilities_ref},"")'
                sheet.write_formula(row, 2, formula, metric_format, metric.get("value"))
            elif metric["metric_code"] == "gross_margin":
                revenue_ref = raw_store.get("financial_summary.income_statement.营业收入")
                cost_ref = raw_store.get("financial_summary.income_statement.营业成本")
                formula = f'=IFERROR(({revenue_ref}-{cost_ref})/{revenue_ref}*100,"")'
                sheet.write_formula(row, 2, formula, metric_format, metric.get("value"))
            elif metric["metric_code"] == "cash_to_short_term_debt":
                cash_ref = raw_store.get("financial_summary.cash_flow.期末现金及现金等价物") or raw_store.get("liquidity.cash_metrics.现金及现金等价物")
                short_debt_ref = raw_store.get("debt_profile.totals.短期借款")
                formula = f'=IFERROR({cash_ref}/{short_debt_ref},"")'
                sheet.write_formula(row, 2, formula, metric_format, metric.get("value"))
            elif metric["metric_code"] == "cash_and_cash_equiv":
                cash_ref = raw_store.get("financial_summary.cash_flow.期末现金及现金等价物") or raw_store.get("liquidity.cash_metrics.现金及现金等价物")
                write_formula_or_number(sheet, row, 2, metric.get("value"), metric_format, raw_ref=cash_ref)
            elif raw_ref:
                write_formula_or_number(sheet, row, 2, metric.get("value"), metric_format, raw_ref=raw_ref)
            elif isinstance(metric.get("value"), (int, float)):
                sheet.write_number(row, 2, metric["value"], metric_format)
            elif metric.get("value") is None:
                sheet.write(row, 2, "-", formats["muted"])
            else:
                sheet.write(row, 2, metric["value"], formats["text"])
            sheet.write(row, 3, metric.get("unit", ""), formats["text"])
            risk_fmt = {
                "high": formats["risk_high"],
                "extreme": formats["risk_high"],
                "medium": formats["risk_medium"],
                "low": formats["risk_low"],
            }.get(metric.get("risk_level"), formats["muted"])
            sheet.write(row, 4, RISK_TEXT.get(metric.get("risk_level"), "待补"), risk_fmt)
            sheet.write(row, 5, metric.get("source_status", ""), formats["text"])
            sheet.write(row, 6, metric.get("comparison") or metric.get("benchmark") or "", formats["text"])
            sheet.write(row, 7, ", ".join(metric.get("evidence_refs", [])), formats["muted"])
            add_comment(sheet, row, 2, evidence_map, metric.get("evidence_refs", []))
            row += 1
        category_label = CATEGORY_LABELS.get(section["category"], section["category"])
        if start_row == row - 1:
            sheet.write(start_row, 0, category_label, formats["section"])
        else:
            sheet.merge_range(start_row, 0, row - 1, 0, category_label, formats["section"])


def write_statement_block(sheet, row, title, rows, formats, raw_store=None, prefix=""):
    sheet.merge_range(row, 0, row, 4, title, formats["section"])
    row += 1
    sheet.write_row(row, 0, ["项目", "期间", "数值", "单位", "说明"], formats["header"])
    row += 1
    if not rows:
        sheet.merge_range(row, 0, row, 4, "当前无稳定结构化数据，保留空骨架。", formats["muted"])
        return row + 2
    for item in rows:
        values = item.get("values", [])
        first = values[0] if values else {}
        sheet.write(row, 0, item["label"], formats["text"])
        sheet.write(row, 1, first.get("period", ""), formats["text"])
        raw_ref = None
        if raw_store:
            raw_ref = raw_store.get(f"{prefix}.{item.get('label', '')}")
        if isinstance(first.get("value"), (int, float)):
            write_formula_or_number(sheet, row, 2, first["value"], value_format(formats, first.get("unit", "")), raw_ref=raw_ref)
        else:
            sheet.write(row, 2, first.get("value") or "-", formats["text"])
        sheet.write(row, 3, first.get("unit", ""), formats["text"])
        sheet.write(row, 4, item.get("commentary", ""), formats["text"])
        row += 1
    return row + 1


def render_financial_summary(sheet, payload, formats, raw_store):
    add_sheet_base(sheet)
    write_title(sheet, "Financial Summary", "固定骨架模块 02", formats)
    sheet.set_column("A:A", 24)
    sheet.set_column("B:E", 16)
    sheet.merge_range(2, 0, 2, 4, payload["financial_summary"].get("coverage_note", ""), formats["note"])
    row = 4
    statements = payload["financial_summary"].get("statements", {})
    row = write_statement_block(sheet, row, "资产负债表摘要", statements.get("balance_sheet", []), formats, raw_store, "financial_summary.balance_sheet")
    row = write_statement_block(sheet, row, "利润表摘要", statements.get("income_statement", []), formats, raw_store, "financial_summary.income_statement")
    write_statement_block(sheet, row, "现金流量表摘要", statements.get("cash_flow", []), formats, raw_store, "financial_summary.cash_flow")


def write_table_rows(sheet, start_row, title, rows, formats, evidence_map, raw_store=None, prefix=""):
    sheet.merge_range(start_row, 0, start_row, 5, title, formats["section"])
    row = start_row + 1
    sheet.write_row(row, 0, ["项目", "期间", "数值", "单位", "备注", "证据"], formats["header"])
    row += 1
    if not rows:
        sheet.merge_range(row, 0, row, 5, "当前无稳定数据。", formats["muted"])
        return row + 2
    for item in rows:
        values = item.get("values", [])
        first = values[0] if values else {}
        sheet.write(row, 0, item.get("label", ""), formats["text"])
        sheet.write(row, 1, first.get("period", ""), formats["text"])
        raw_ref = None
        if raw_store:
            raw_ref = raw_store.get(f"{prefix}.{item.get('row_code') or item.get('label', '')}")
        if isinstance(first.get("value"), (int, float)):
            write_formula_or_number(sheet, row, 2, first["value"], value_format(formats, first.get("unit", "")), raw_ref=raw_ref)
        else:
            sheet.write(row, 2, first.get("value") or "-", formats["text"])
        sheet.write(row, 3, first.get("unit", ""), formats["text"])
        sheet.write(row, 4, item.get("commentary", ""), formats["text"])
        refs = item.get("evidence_refs", [])
        sheet.write(row, 5, ", ".join(refs), formats["muted"])
        add_comment(sheet, row, 2, evidence_map, refs)
        row += 1
    return row + 1


def render_debt_profile(sheet, payload, evidence_map, formats, raw_store):
    add_sheet_base(sheet)
    write_title(sheet, "Debt Profile", "固定骨架模块 03", formats)
    sheet.set_column("A:A", 22)
    sheet.set_column("B:F", 16)
    row = 3
    row = write_table_rows(sheet, row, "债务总览", payload["debt_profile"].get("totals", []), formats, evidence_map, raw_store, "debt_profile.totals")
    row = write_table_rows(sheet, row, "期限结构", payload["debt_profile"].get("maturity_buckets", []), formats, evidence_map, raw_store, "debt_profile.maturity_buckets")
    row = write_table_rows(sheet, row, "融资结构", payload["debt_profile"].get("financing_mix", []), formats, evidence_map, raw_store, "debt_profile.financing_mix")

    rate_profile = payload["debt_profile"].get("rate_profile", [])
    sheet.merge_range(row, 0, row, 5, "利率结构", formats["section"])
    row += 1
    sheet.write_row(row, 0, ["项目", "期间", "数值", "单位", "说明"], formats["header"])
    row += 1
    for item in rate_profile:
        values = item.get("values", [])
        first = values[0] if values else {}
        sheet.write(row, 0, item.get("label", ""), formats["text"])
        sheet.write(row, 1, first.get("period", ""), formats["text"])
        raw_key = f"debt_profile.rate_profile.{item.get('label', '')}"
        raw_ref = raw_store.get(raw_key)
        if item.get("label") == "债务平均利率":
            interest_ref = raw_store.get("debt_profile.rate_profile.利息支出")
            begin_ref = raw_store.get("formula_inputs.interest_bearing_liabilities_begin")
            end_ref = raw_store.get("formula_inputs.interest_bearing_liabilities_end")
            formula = f'=IFERROR({interest_ref}/(({begin_ref}+{end_ref})/2)*100,"")'
            sheet.write_formula(row, 2, formula, value_format(formats, first.get("unit", "")), first.get("value"))
        else:
            write_formula_or_number(sheet, row, 2, first.get("value"), value_format(formats, first.get("unit", "")), raw_ref=raw_ref)
        sheet.write(row, 3, first.get("unit", ""), formats["text"])
        sheet.write(row, 4, item.get("commentary", ""), formats["text"])
        row += 1
    debt_comments = payload["debt_profile"].get("debt_comments", [])
    sheet.merge_range(row, 0, row, 5, "债务评论", formats["section"])
    row += 1
    sheet.write_row(row, 0, ["标签", "详情", "来源", "证据", "", ""], formats["header"])
    row += 1
    for item in debt_comments:
        sheet.write(row, 0, item.get("label", ""), formats["text"])
        sheet.merge_range(row, 1, row, 3, item.get("detail", ""), formats["text"])
        sheet.write(row, 4, item.get("source_status", ""), formats["text"])
        sheet.write(row, 5, ", ".join(item.get("evidence_refs", [])), formats["muted"])
        add_comment(sheet, row, 1, evidence_map, item.get("evidence_refs", []))
        row += 1


def render_liquidity(sheet, payload, evidence_map, formats, raw_store):
    add_sheet_base(sheet)
    write_title(sheet, "Liquidity And Covenants", "固定骨架模块 04", formats)
    sheet.set_column("A:A", 22)
    sheet.set_column("B:F", 16)
    row = 3
    liquidity = payload["liquidity_and_covenants"]
    row = write_table_rows(sheet, row, "现金指标", liquidity.get("cash_metrics", []), formats, evidence_map, raw_store, "liquidity.cash_metrics")
    row = write_table_rows(sheet, row, "授信与债务窗口", liquidity.get("credit_lines", []), formats, evidence_map, raw_store, "liquidity.credit_lines")
    row = write_table_rows(sheet, row, "受限资产", liquidity.get("restricted_assets", []), formats, evidence_map, raw_store, "liquidity.restricted_assets")

    sheet.merge_range(row, 0, row, 5, "财务契约", formats["section"])
    row += 1
    sheet.write_row(row, 0, ["条目", "状态", "受限债务", "单位", "来源", "证据"], formats["header"])
    row += 1
    for item in liquidity.get("covenants", []):
        sheet.write(row, 0, item.get("label", ""), formats["text"])
        risk_fmt = formats["risk_low"] if item.get("status") == "compliant" else formats["risk_medium"]
        sheet.write(row, 1, item.get("status", ""), risk_fmt)
        if isinstance(item.get("restricted_debt"), (int, float)):
            sheet.write_number(row, 2, item["restricted_debt"], formats["number"])
        else:
            sheet.write(row, 2, item.get("restricted_debt") or "-", formats["text"])
        sheet.write(row, 3, item.get("unit", ""), formats["text"])
        sheet.write(row, 4, item.get("source_status", ""), formats["text"])
        refs = item.get("evidence_refs", [])
        sheet.write(row, 5, ", ".join(refs), formats["muted"])
        add_comment(sheet, row, 2, evidence_map, refs)
        row += 1

    row += 1
    sheet.merge_range(row, 0, row, 5, "流动性观察", formats["section"])
    row += 1
    for item in liquidity.get("liquidity_observations", []):
        sheet.write(row, 0, item.get("label", ""), formats["subheader"])
        sheet.merge_range(row, 1, row, 4, item.get("detail", ""), formats["text"])
        sheet.write(row, 5, ", ".join(item.get("evidence_refs", [])), formats["muted"])
        add_comment(sheet, row, 1, evidence_map, item.get("evidence_refs", []))
        row += 1


def render_bond_detail(sheet, module, evidence_map, formats):
    add_sheet_base(sheet)
    write_title(sheet, module["title"], "可选标准模块", formats)
    sheet.set_column("A:F", 18)
    sheet.write_row(3, 0, ["债券/工具", "余额", "单位", "利率区间", "条款", "证据"], formats["header"])
    row = 4
    for item in module["payload"].get("bonds", []):
        sheet.write(row, 0, item.get("instrument_name", ""), formats["text"])
        if isinstance(item.get("balance"), (int, float)):
            sheet.write_number(row, 1, item["balance"], formats["number"])
        else:
            sheet.write(row, 1, item.get("balance") or "-", formats["text"])
        sheet.write(row, 2, item.get("unit", ""), formats["text"])
        sheet.write(row, 3, item.get("coupon_range", ""), formats["text"])
        sheet.write(row, 4, item.get("terms", "") or item.get("guarantee", ""), formats["text"])
        refs = item.get("evidence_refs", [])
        sheet.write(row, 5, ", ".join(refs), formats["muted"])
        add_comment(sheet, row, 1, evidence_map, refs)
        row += 1


def render_topic(sheet, module, evidence_map, formats, raw_store):
    add_sheet_base(sheet)
    write_title(sheet, module["title"], "专题模块", formats)
    sheet.set_column("A:A", 20)
    sheet.set_column("B:E", 18)
    payload = module["payload"]
    sheet.merge_range(3, 0, 4, 4, payload.get("summary", "") or "专题摘要待补充。", formats["text"])
    add_comment(sheet, 3, 0, evidence_map, payload.get("summary_evidence_refs", []))

    row = 6
    for section in payload.get("sections", []):
        sheet.merge_range(row, 0, row, 4, section.get("section_title", "专题要点"), formats["section"])
        row += 1
        sheet.write_row(row, 0, ["指标", "数值", "单位", "来源", "证据"], formats["header"])
        row += 1
        items = section.get("items", [])
        if not items:
            sheet.merge_range(row, 0, row, 4, "当前无稳定结构化数据。", formats["muted"])
            row += 2
            continue
        for item in items:
            sheet.write(row, 0, item.get("label", ""), formats["text"])
            raw_key = f"{module.get('module_key', 'optional')}.{section.get('section_title', 'section')}.{item.get('label', '')}"
            raw_ref = raw_store.get(raw_key)
            if module.get("module_key") == "financing_cost":
                revenue_ref = raw_store.get("financial_summary.income_statement.营业收入")
                if item.get("label") == "净利息负担":
                    interest_ref = raw_store.get("financing_cost.融资成本口径.利息支出")
                    income_ref = raw_store.get("financing_cost.融资成本口径.利息收入")
                    formula = f'=IFERROR({interest_ref}-{income_ref},"")'
                    sheet.write_formula(row, 1, formula, value_format(formats, item.get("unit", "")), item.get("value"))
                elif item.get("label") == "财务费用/营业收入":
                    finance_ref = raw_store.get("financing_cost.融资成本口径.财务费用")
                    formula = f'=IFERROR({finance_ref}/{revenue_ref}*100,"")'
                    sheet.write_formula(row, 1, formula, value_format(formats, item.get("unit", "")), item.get("value"))
                elif item.get("label") == "利息支出/平均有息负债":
                    interest_ref = raw_store.get("financing_cost.融资成本口径.利息支出")
                    begin_ref = raw_store.get("formula_inputs.interest_bearing_liabilities_begin")
                    end_ref = raw_store.get("formula_inputs.interest_bearing_liabilities_end")
                    formula = f'=IFERROR({interest_ref}/(({begin_ref}+{end_ref})/2)*100,"")'
                    sheet.write_formula(row, 1, formula, value_format(formats, item.get("unit", "")), item.get("value"))
                else:
                    write_formula_or_number(sheet, row, 1, item.get("value"), value_format(formats, item.get("unit", "")), raw_ref=raw_ref)
            elif module.get("module_key") == "platform_special":
                if item.get("label") == "政府相关库存资产":
                    total_ref = raw_store.get("formula_inputs.platform_inventory_total")
                    market_ref = raw_store.get("formula_inputs.platform_inventory_market")
                    formula = f'=IFERROR({total_ref}-{market_ref},"")'
                    sheet.write_formula(row, 1, formula, value_format(formats, item.get("unit", "")), item.get("value"))
                elif item.get("label") == "市场相关库存资产":
                    formula_ref = raw_store.get("formula_inputs.platform_inventory_market")
                    formula = f'={formula_ref}'
                    sheet.write_formula(row, 1, formula, value_format(formats, item.get("unit", "")), item.get("value"))
                elif item.get("label") == "政府相关库存占比":
                    gov_ref = raw_store.get("platform_special.城投业务拆分.政府相关库存资产")
                    total_ref = raw_store.get("formula_inputs.platform_inventory_total")
                    formula = f'=IFERROR({gov_ref}/{total_ref}*100,"")'
                    sheet.write_formula(row, 1, formula, value_format(formats, item.get("unit", "")), item.get("value"))
                elif item.get("label") == "应收账款政府组合占比":
                    gov_ref = raw_store.get("platform_special.政府往来与资产端.应收账款政府组合")
                    total_ref = raw_store.get("formula_inputs.platform_ar_total")
                    formula = f'=IFERROR({gov_ref}/{total_ref}*100,"")'
                    sheet.write_formula(row, 1, formula, value_format(formats, item.get("unit", "")), item.get("value"))
                elif item.get("label") == "其他应收款政府组合占比":
                    gov_ref = raw_store.get("platform_special.政府往来与资产端.其他应收款政府组合")
                    total_ref = raw_store.get("formula_inputs.platform_other_ar_total")
                    formula = f'=IFERROR({gov_ref}/{total_ref}*100,"")'
                    sheet.write_formula(row, 1, formula, value_format(formats, item.get("unit", "")), item.get("value"))
                elif item.get("label") == "预付款项政府对象占比":
                    gov_ref = raw_store.get("platform_special.政府往来与资产端.预付款项政府对象")
                    total_ref = raw_store.get("formula_inputs.platform_prepayment_total")
                    formula = f'=IFERROR({gov_ref}/{total_ref}*100,"")'
                    sheet.write_formula(row, 1, formula, value_format(formats, item.get("unit", "")), item.get("value"))
                else:
                    write_formula_or_number(sheet, row, 1, item.get("value"), value_format(formats, item.get("unit", "")), raw_ref=raw_ref)
            elif isinstance(item.get("value"), (int, float)):
                write_formula_or_number(sheet, row, 1, item.get("value"), value_format(formats, item.get("unit", "")), raw_ref=raw_ref)
            else:
                sheet.write(row, 1, item.get("value") or "-", formats["text"])
            sheet.write(row, 2, item.get("unit", ""), formats["text"])
            sheet.write(row, 3, item.get("source_status", ""), formats["text"])
            refs = item.get("evidence_refs", [])
            sheet.write(row, 4, ", ".join(refs), formats["muted"])
            add_comment(sheet, row, 1, evidence_map, refs)
            row += 1

    risk_signals = payload.get("ext_fields", {}).get("risk_signals", [])
    if risk_signals:
        row += 1
        sheet.merge_range(row, 0, row, 4, "风险信号", formats["section"])
        row += 1
        sheet.write_row(row, 0, ["信号", "等级", "影响", "证据", ""], formats["header"])
        row += 1
        for item in risk_signals:
            sheet.write(row, 0, item.get("signal_name", ""), formats["text"])
            risk_fmt = formats["risk_high"] if item.get("severity") in {"high", "extreme"} else formats["risk_medium"]
            sheet.write(row, 1, RISK_TEXT.get(item.get("severity"), item.get("severity", "")), risk_fmt)
            sheet.write(row, 2, item.get("impact_hint", ""), formats["text"])
            evidence = "；".join(item.get("evidence", [])[:2])
            sheet.merge_range(row, 3, row, 4, evidence, formats["text"])
            row += 1


def render_evidence_index(sheet, payload, formats):
    add_sheet_base(sheet)
    write_title(sheet, "Evidence Index", "固定骨架模块 99", formats)
    sheet.set_column("A:A", 12)
    sheet.set_column("B:B", 28)
    sheet.set_column("C:C", 18)
    sheet.set_column("D:D", 42)
    sheet.set_column("E:H", 14)
    sheet.write_row(3, 0, ["证据ID", "字段路径", "Sheet", "证据片段", "文档", "章节", "附注", "置信度"], formats["header"])
    row = 4
    for item in payload.get("evidence_index", []):
        sheet.write(row, 0, item.get("evidence_id", ""), formats["text"])
        sheet.write(row, 1, item.get("field_path", ""), formats["text"])
        sheet.write(row, 2, item.get("sheet_name", ""), formats["text"])
        sheet.write(row, 3, item.get("excerpt", ""), formats["text"])
        sheet.write(row, 4, item.get("source_document", ""), formats["text"])
        sheet.write(row, 5, item.get("chapter_title", ""), formats["text"])
        sheet.write(row, 6, item.get("note_no", ""), formats["text"])
        sheet.write(row, 7, item.get("confidence", ""), formats["text"])
        row += 1


def render_workbook(payload, output_path):
    ensure_parent(output_path)
    workbook = xlsxwriter.Workbook(str(output_path))
    workbook.set_properties({
        "title": f"Soul {payload['entity_profile']['company_name']}",
        "subject": payload.get("template_version", ""),
        "company": "Codex",
    })
    formats = build_formats(workbook)
    raw_store = RawValueStore()
    register_payload_inputs(payload, raw_store)
    evidence_map = {
        entry["evidence_id"]: entry
        for entry in payload.get("evidence_index", [])
    }
    optional_map = {
        item["module_key"]: item
        for item in payload.get("optional_modules", [])
    }

    for manifest_item in payload.get("module_manifest", []):
        if not manifest_item.get("enabled", True):
            continue
        sheet = workbook.add_worksheet(manifest_item["sheet_name"][:31])
        module_key = manifest_item["module_key"]
        if module_key == "overview":
            render_overview(sheet, payload, evidence_map, formats)
        elif module_key == "kpi_dashboard":
            render_kpi_dashboard(sheet, payload, evidence_map, formats, raw_store)
        elif module_key == "financial_summary":
            render_financial_summary(sheet, payload, formats, raw_store)
        elif module_key == "debt_profile":
            render_debt_profile(sheet, payload, evidence_map, formats, raw_store)
        elif module_key == "liquidity_and_covenants":
            render_liquidity(sheet, payload, evidence_map, formats, raw_store)
        elif module_key == "evidence_index":
            render_evidence_index(sheet, payload, formats)
        else:
            module = optional_map.get(module_key)
            if not module:
                continue
            if module_key == "bond_detail":
                render_bond_detail(sheet, module, evidence_map, formats)
            else:
                render_topic(sheet, module, evidence_map, formats, raw_store)

    render_raw_inputs_sheet(workbook, raw_store, formats)

    workbook.close()
    render_preview(output_path)


def export_payload_to_workbook(payload_path, output_path):
    payload_path = Path(payload_path).resolve()
    output_path = Path(output_path).resolve()
    payload = load_json(payload_path)
    render_workbook(payload, output_path)
    return output_path


def main():
    parser = argparse.ArgumentParser(description="将 soul_export_payload.json 导出为 Soul v1.1-alpha Excel")
    parser.add_argument("--payload", required=True, help="输入 Soul payload JSON")
    parser.add_argument("--output", required=True, help="输出 Excel 路径")
    args = parser.parse_args()

    output_path = export_payload_to_workbook(args.payload, args.output)
    print(f"[OK] Soul workbook generated: {output_path}")


if __name__ == "__main__":
    main()
