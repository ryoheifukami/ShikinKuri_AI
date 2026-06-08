"""Claude APIで経営者向けアドバイスを生成する。

専門家(税理士)の視点で複数の観点から整理されたアドバイスを返す。
ユーザー追記情報(備考)も考慮する。
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from anthropic import Anthropic

from .financial_model import CashFlowResult, PeriodRow

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")


# 観点カテゴリの定義(順序が優先順)
CATEGORIES: list[tuple[str, str]] = [
    ("資金繰り", "💰"),
    ("安全性", "🛡"),
    ("収益性", "📈"),
    ("成長性", "🚀"),
    ("経営課題", "🎯"),
]
CATEGORY_NAMES = [c for c, _ in CATEGORIES]
CATEGORY_ICONS = dict(CATEGORIES)


ADVICE_SYSTEM_PROMPT = """\
あなたは中小企業の経営支援を専門とする経験豊富な税理士です。
顧問先の経営者(中小企業の社長)に対して、資金繰りに関するアドバイスを行います。

【絶対に守るルール】
1. 数字は具体的に挙げる(「現預金が3,000万円から1,800万円に減る」など)
2. 「だから何をすべきか」を action フィールドに必ず示す
3. 専門用語(自己資本比率、固定長期適合率など)は使わない。使うなら必ず注釈
4. 過度に楽観・悲観せず、事実ベースで率直に
5. 経営者がその場で行動できる粒度の具体的な提言にする
6. 当たり前すぎる一般論(「コスト削減を検討」のような)は書かない

【分析の5観点】
次の5つの観点を網羅するように分析してください。同じ観点で複数指摘があっても可。

- 資金繰り: 短期キャッシュの確保、運転資金、資金ショートの危険性
- 安全性: 借入返済負担、有利子負債、自己資本の厚さ
- 収益性: 粗利率、営業利益率、コスト構造の歪み
- 成長性: 売上トレンド、投資余力、戦略的余裕
- 経営課題: 数字の裏にある構造的な課題、経営者が向き合うべき本質的なテーマ

【追記情報】
税理士(=利用者)が手で記入した「追記情報」がある場合、それは決算書に表れない事業実態。
必ず参照し、関連する指摘に反映する。
"""


@dataclass
class AdviceItem:
    category: str  # "資金繰り" / "安全性" / "収益性" / "成長性" / "経営課題"
    headline: str
    detail: str
    action: str
    priority: str  # "high" / "medium" / "low"


def _fmt(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:,.0f}"


def _summarize(rows: list[PeriodRow], name: str) -> str:
    if not rows:
        return f"{name}: データなし"
    lines = [f"【{name}】"]
    for r in rows:
        label = r.label or ""
        lines.append(
            f"  {label} {r.period}: "
            f"売上 {_fmt(r.sales)} / 売上原価 {_fmt(r.cogs)} / 販管費 {_fmt(r.sga_cash)} / "
            f"営業利益 {_fmt(r.operating_income)} / 支払利息 {_fmt(r.interest_paid)} / "
            f"税金 {_fmt(r.tax_paid)} / 借入返済 {_fmt(r.debt_repayment)} / "
            f"期末現預金 {_fmt(r.ending_cash)}"
        )
    return "\n".join(lines)


def generate_advice(
    actual: CashFlowResult,
    forecasts: list[PeriodRow] | None = None,
    company_name: str | None = None,
    user_notes: str | None = None,
    *,
    client: Anthropic | None = None,
    model: str = DEFAULT_MODEL,
) -> list[AdviceItem]:
    """過去実績+予測+追記情報から、観点別の経営アドバイスを生成する。"""
    cli = client or Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    summary_actual = _summarize(actual.periods, f"実績({actual.mode})")
    summary_forecast = _summarize(forecasts or [], "予測")
    notes_text = "\n".join(f"- {n}" for n in actual.notes) if actual.notes else "なし"

    user_notes_section = ""
    if user_notes and user_notes.strip():
        user_notes_section = f"\n【追記情報(税理士による手入力)】\n{user_notes.strip()}\n"

    user_prompt = f"""\
以下は{company_name or "ある会社"}の資金繰り状況です(単位: 円)。

{summary_actual}

{summary_forecast}

【データの注記】
{notes_text}
{user_notes_section}
これらすべてを踏まえ、税理士として経営者に伝えるべきアドバイスを観点別に整理し、
最大5本のJSONで返してください。

【返答形式】
{{
  "advice": [
    {{
      "category": "資金繰り | 安全性 | 収益性 | 成長性 | 経営課題",
      "priority": "high | medium | low",
      "headline": "1文の見出し(40字以内)",
      "detail": "事実の整理。数字を含めた1〜3文",
      "action": "経営者がこの場で着手できる具体的な推奨アクション(1〜2文)"
    }}
  ]
}}

JSONのみ出力してください。
"""

    resp = cli.messages.create(
        model=model,
        max_tokens=3000,
        system=ADVICE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    parsed = _safe_json(text)
    items = parsed.get("advice", [])

    result: list[AdviceItem] = []
    for it in items:
        category = str(it.get("category", "経営課題"))
        if category not in CATEGORY_NAMES:
            category = "経営課題"
        result.append(
            AdviceItem(
                category=category,
                headline=str(it.get("headline", ""))[:80],
                detail=str(it.get("detail", "")),
                action=str(it.get("action", "")),
                priority=str(it.get("priority", "medium")),
            )
        )

    # 優先度高→中→低、観点順 でソート
    priority_order = {"high": 0, "medium": 1, "low": 2}
    cat_order = {c: i for i, c in enumerate(CATEGORY_NAMES)}
    result.sort(key=lambda a: (priority_order.get(a.priority, 99), cat_order.get(a.category, 99)))
    return result


def _safe_json(text: str) -> dict[str, Any]:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return {"advice": []}
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {"advice": []}
