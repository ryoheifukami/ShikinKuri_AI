"""配布用PDFを生成する(reportlab)。"""
from __future__ import annotations

import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .advisor import AdviceItem
from .financial_model import ROW_LABELS, CashFlowResult, PeriodRow

pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
JP_FONT = "HeiseiKakuGo-W5"

UNIT_DIVISOR = 1000
UNIT_LABEL = "千円"


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("Title", parent=base["Title"], fontName=JP_FONT, fontSize=20, leading=26),
        "h2": ParagraphStyle("H2", parent=base["Heading2"], fontName=JP_FONT, fontSize=14, leading=20, spaceAfter=8),
        "body": ParagraphStyle("Body", parent=base["BodyText"], fontName=JP_FONT, fontSize=10, leading=15),
        "small": ParagraphStyle("Small", parent=base["BodyText"], fontName=JP_FONT, fontSize=8, leading=12, textColor=colors.grey),
        "advice_head": ParagraphStyle(
            "AdviceHead", parent=base["BodyText"], fontName=JP_FONT, fontSize=11, leading=16, spaceAfter=2,
            textColor=colors.HexColor("#305496"),
        ),
    }


def _fmt(v: float | None) -> str:
    if v is None:
        return ""
    return f"{v / UNIT_DIVISOR:,.0f}"


def _table_data(periods: list[PeriodRow]) -> list[list[str]]:
    header = ["項目"]
    for p in periods:
        h = p.period if not p.label else f"{p.label}\n{p.period}"
        header.append(h)
    data: list[list[str]] = [header]
    for key, label in ROW_LABELS:
        if key.startswith("__section"):
            data.append([label] + [""] * len(periods))
            continue
        row_vals = [_fmt(getattr(p, key, None)) for p in periods]
        data.append([label] + row_vals)
    return data


def _build_table(periods: list[PeriodRow]) -> Table:
    data = _table_data(periods)
    page_w = landscape(A4)[0] - 30 * mm
    label_w = 40 * mm
    rest_w = max(20 * mm, (page_w - label_w) / max(1, len(periods)))
    col_widths = [label_w] + [rest_w] * len(periods)

    t = Table(data, colWidths=col_widths, repeatRows=1)
    style = TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), JP_FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#305496")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#BFBFBF")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ])
    for i, (key, _) in enumerate(ROW_LABELS, start=1):
        if key.startswith("__section"):
            style.add("BACKGROUND", (0, i), (-1, i), colors.HexColor("#DDEBF7"))
        if key in ("opening_cash", "ending_cash", "net_change", "operating_income", "gross_profit"):
            style.add("FONTNAME", (0, i), (-1, i), JP_FONT)

    # 予測列に背景色
    for col_idx, p in enumerate(periods, start=1):
        if p.is_forecast:
            for row_idx in range(1, len(ROW_LABELS) + 1):
                style.add("BACKGROUND", (col_idx, row_idx), (col_idx, row_idx), colors.HexColor("#FCE4D6"))

    t.setStyle(style)
    return t


def build_pdf(
    actual: CashFlowResult,
    forecasts: list[PeriodRow] | None,
    advice: list[AdviceItem],
    cash_chart_png: bytes | None = None,
    in_out_chart_png: bytes | None = None,
    company_name: str | None = None,
    user_notes: str | None = None,
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
    )
    s = _styles()
    story = []

    title = "資金繰り表"
    if company_name:
        title += f"  —  {company_name}"
    story.append(Paragraph(title, s["title"]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        f"作成日: {date.today().isoformat()}  /  単位: {UNIT_LABEL}", s["small"]
    ))
    story.append(Spacer(1, 6 * mm))

    if cash_chart_png:
        story.append(Paragraph("月末現預金残高の推移", s["h2"]))
        img = Image(io.BytesIO(cash_chart_png), width=240 * mm, height=120 * mm, kind="proportional")
        story.append(img)
        story.append(Spacer(1, 4 * mm))

    if advice:
        story.append(Paragraph("経営アドバイス", s["h2"]))
        story.append(Spacer(1, 2 * mm))
        priority_label = {"high": "[重要度:高]", "medium": "[重要度:中]", "low": "[重要度:低]"}
        for a in advice:
            tag = f"<b>【{a.category}】</b> {priority_label.get(a.priority, '')}  {a.headline}"
            story.append(Paragraph(tag, s["advice_head"]))
            story.append(Paragraph(a.detail, s["body"]))
            if a.action:
                story.append(Paragraph(f"→ <b>推奨アクション:</b> {a.action}", s["body"]))
            story.append(Spacer(1, 3 * mm))

    if user_notes and user_notes.strip():
        story.append(Paragraph("追記情報(担当者記入)", s["h2"]))
        for line in user_notes.strip().splitlines():
            if line.strip():
                story.append(Paragraph(line, s["body"]))
        story.append(Spacer(1, 4 * mm))

    story.append(PageBreak())

    section = "月次推移(実績+予測)" if actual.mode == "monthly" else "年次推移(実績+予測)"
    story.append(Paragraph(section, s["h2"]))
    if actual.notes:
        for n in actual.notes:
            story.append(Paragraph(f"注: {n}", s["small"]))
        story.append(Spacer(1, 2 * mm))

    combined = list(actual.periods) + list(forecasts or [])
    if combined:
        story.append(_build_table(combined))
        story.append(Spacer(1, 4 * mm))

    if in_out_chart_png:
        story.append(PageBreak())
        story.append(Paragraph("入金・出金の内訳", s["h2"]))
        story.append(Image(io.BytesIO(in_out_chart_png), width=240 * mm, height=120 * mm, kind="proportional"))

    doc.build(story)
    return buf.getvalue()
