"""決算資料から資金繰り表データを生成する。

設計方針:
- アップロードされた資料に書かれている数字のみを使う
- 推測・按分・補完は一切行わない(ソースがなければ空欄)
- 月次試算表があれば月次モード、なければ年次モード
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PeriodRow:
    """1期間(月次 or 年次)分のデータ。値が None なら出力時に空欄。"""

    period: str  # "YYYY-MM" または "2025年3月期" 等
    period_type: str = "monthly"  # "monthly" / "annual"
    label: str | None = None  # "前期" / "当期" / "予測(次期)" 等

    # 損益
    sales: float | None = None
    cogs: float | None = None
    gross_profit: float | None = None
    sga_cash: float | None = None  # 販管費(減価償却控除後)
    operating_income: float | None = None
    interest_paid: float | None = None
    # キャッシュ系
    tax_paid: float | None = None
    new_borrowing: float | None = None
    debt_repayment: float | None = None
    operating_cf: float | None = None
    investing_cf: float | None = None
    financing_cf: float | None = None
    # 現預金
    opening_cash: float | None = None
    net_change: float | None = None
    ending_cash: float | None = None

    is_forecast: bool = False
    notes: list[str] = field(default_factory=list)


# 後方互換用エイリアス
MonthlyRow = PeriodRow


# 表の行ラベル(縦) — Excel/PDF/UI で共通利用
ROW_LABELS: list[tuple[str, str]] = [
    ("opening_cash", "期首現預金"),
    ("__section_pl__", "【損益】"),
    ("sales", "売上高"),
    ("cogs", "売上原価"),
    ("gross_profit", "売上総利益"),
    ("sga_cash", "販管費(現金支出)"),
    ("operating_income", "営業利益"),
    ("interest_paid", "支払利息"),
    ("__section_cash__", "【資金収支】"),
    ("tax_paid", "税金"),
    ("new_borrowing", "新規借入"),
    ("debt_repayment", "借入返済"),
    ("operating_cf", "営業CF(C/Fから)"),
    ("investing_cf", "投資CF(C/Fから)"),
    ("financing_cf", "財務CF(C/Fから)"),
    ("net_change", "期間中増減"),
    ("ending_cash", "期末現預金"),
]


@dataclass
class CashFlowResult:
    periods: list[PeriodRow]
    mode: str  # "monthly" / "annual"
    company_name: str | None = None
    fiscal_year_end: str | None = None
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    # 後方互換
    @property
    def months(self) -> list[PeriodRow]:
        return self.periods


def _opt(d: dict[str, Any] | None, *keys: str) -> float | None:
    """安全に取得。キー欠損 or None なら None を返す。"""
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
        if cur is None:
            return None
    try:
        return float(cur)
    except (TypeError, ValueError):
        return None


def reconstruct_cashflow(
    financial: dict[str, Any] | None,
    breakdown: dict[str, Any] | None = None,
    tax: dict[str, Any] | None = None,
    monthly_trial: dict[str, Any] | None = None,
) -> CashFlowResult:
    """アップロード資料から資金繰り表データを構成する。

    - financial がなければ何も作れない
    - monthly_trial があれば月次モード、なければ年次モード
    - breakdown / tax は対応行に反映、なければ空欄のまま
    """
    if not financial:
        return CashFlowResult(
            periods=[],
            mode="annual",
            warnings=["決算書(財務諸表)が必要です。資金繰り表を作成できません。"],
        )

    company_name = financial.get("company_name")
    fye = financial.get("fiscal_year_end")

    if monthly_trial and monthly_trial.get("months"):
        return _build_monthly(financial, breakdown, tax, monthly_trial, company_name, fye)

    return _build_annual(financial, breakdown, tax, company_name, fye)


# 後方互換
reconstruct_monthly = reconstruct_cashflow


# ---- 年次モード -------------------------------------------------------------


def _fy_label(fye: str | None, offset: int = 0) -> str:
    """会計年度の表示ラベルを返す。fye='2026-03-31'+offset=0 → '2026年3月期'。"""
    if not fye or len(fye) < 7:
        if offset == 0:
            return "当期"
        return f"予測(+{offset}期)"
    try:
        y = int(fye[:4]) + offset
        m = int(fye[5:7])
        return f"{y}年{m}月期"
    except ValueError:
        return f"FY({fye})"


def _make_annual_row(
    pl: dict[str, Any] | None,
    bs: dict[str, Any] | None,
    cf: dict[str, Any] | None,
    breakdown: dict[str, Any] | None,
    tax: dict[str, Any] | None,
    *,
    is_current_year: bool,
) -> PeriodRow:
    """年次1期分のRowを作る。"""
    row = PeriodRow(period="", period_type="annual")
    pl = pl or {}
    bs = bs or {}
    cf = cf or {}

    row.sales = _opt(pl, "sales")
    row.cogs = _opt(pl, "cost_of_sales")
    row.gross_profit = _opt(pl, "gross_profit")
    sga = _opt(pl, "sga")
    dep = _opt(pl, "depreciation") or 0
    if sga is not None:
        row.sga_cash = sga - dep
    row.operating_income = _opt(pl, "operating_income")
    row.interest_paid = _opt(pl, "interest_expense")

    row.ending_cash = _opt(bs, "cash")

    row.operating_cf = _opt(cf, "operating_cf")
    row.investing_cf = _opt(cf, "investing_cf")
    row.financing_cf = _opt(cf, "financing_cf")

    # 税金は税申告書PDFがあるときのみ(かつ当期のみ判定可能)
    if is_current_year and tax:
        parts = [
            _opt(tax, "corporate_tax_current") or 0,
            _opt(tax, "local_tax_current") or 0,
            _opt(tax, "consumption_tax_current") or 0,
        ]
        total = sum(parts)
        if total > 0:
            row.tax_paid = total

    # 借入返済は内訳明細があるときのみ
    if is_current_year and breakdown and breakdown.get("loans_payable"):
        any_repay = False
        annual_repay = 0.0
        for loan in breakdown["loans_payable"]:
            mr = loan.get("monthly_repayment")
            if mr is not None:
                try:
                    annual_repay += float(mr) * 12
                    any_repay = True
                except (TypeError, ValueError):
                    pass
        if any_repay:
            row.debt_repayment = annual_repay

    return row


def _build_annual(
    financial: dict[str, Any],
    breakdown: dict[str, Any] | None,
    tax: dict[str, Any] | None,
    company_name: str | None,
    fye: str | None,
) -> CashFlowResult:
    pl_cur = (financial.get("profit_loss") or {}).get("current")
    pl_prior = (financial.get("profit_loss") or {}).get("prior")
    bs_cur = (financial.get("balance_sheet") or {}).get("current")
    bs_prior = (financial.get("balance_sheet") or {}).get("prior")
    cf_cur = (financial.get("cash_flow_statement") or {}).get("current")
    cf_prior = (financial.get("cash_flow_statement") or {}).get("prior")

    periods: list[PeriodRow] = []
    notes: list[str] = []

    # 前期(あれば)
    if pl_prior or bs_prior:
        prior = _make_annual_row(pl_prior, bs_prior, cf_prior, breakdown, tax, is_current_year=False)
        prior.period = _fy_label(fye, offset=-1)
        prior.label = "前期"
        periods.append(prior)

    # 当期
    cur = _make_annual_row(pl_cur, bs_cur, cf_cur, breakdown, tax, is_current_year=True)
    cur.period = _fy_label(fye, offset=0)
    cur.label = "当期"

    # 当期 期首現預金 = 前期 期末現預金(あれば)
    if bs_prior:
        cur.opening_cash = _opt(bs_prior, "cash")
    if cur.opening_cash is not None and cur.ending_cash is not None:
        cur.net_change = cur.ending_cash - cur.opening_cash

    periods.append(cur)

    # 注記
    if not breakdown:
        notes.append("勘定科目内訳明細書が未アップロードのため、借入返済は空欄です。")
    if not tax:
        notes.append("法人税申告書が未アップロードのため、税金は空欄です。")
    notes.append("月次試算表が未アップロードのため、年次サマリーで出力しています。")

    return CashFlowResult(
        periods=periods,
        mode="annual",
        company_name=company_name,
        fiscal_year_end=fye,
        notes=notes,
    )


# ---- 月次モード -------------------------------------------------------------


def _build_monthly(
    financial: dict[str, Any],
    breakdown: dict[str, Any] | None,
    tax: dict[str, Any] | None,
    monthly_trial: dict[str, Any],
    company_name: str | None,
    fye: str | None,
) -> CashFlowResult:
    periods: list[PeriodRow] = []
    notes: list[str] = []

    for mt in monthly_trial.get("months", []):
        row = PeriodRow(period=mt.get("month", ""), period_type="monthly", label="実績")
        row.sales = mt.get("sales")
        row.cogs = mt.get("cost_of_sales")
        row.gross_profit = mt.get("gross_profit")
        row.sga_cash = mt.get("sga")
        row.operating_income = mt.get("operating_income")
        row.ending_cash = mt.get("cash_balance")
        periods.append(row)

    # 借入返済(月額) — breakdown があれば月次で按分
    if breakdown and breakdown.get("loans_payable"):
        monthly_repay = 0.0
        for loan in breakdown["loans_payable"]:
            mr = loan.get("monthly_repayment")
            if mr is not None:
                try:
                    monthly_repay += float(mr)
                except (TypeError, ValueError):
                    pass
        if monthly_repay > 0:
            for r in periods:
                r.debt_repayment = monthly_repay
    else:
        notes.append("勘定科目内訳明細書が未アップロードのため、借入返済は空欄です。")

    # 税金 — tax PDFがあれば期末月に計上(中間納付の月特定が難しいため)
    if tax and periods:
        parts = [
            _opt(tax, "corporate_tax_current") or 0,
            _opt(tax, "local_tax_current") or 0,
            _opt(tax, "consumption_tax_current") or 0,
        ]
        total = sum(parts)
        if total > 0:
            periods[-1].tax_paid = total
            periods[-1].notes.append("税金は当期合計を期末月に計上")
    else:
        notes.append("法人税申告書が未アップロードのため、税金は空欄です。")

    # 各月の純増減 = 売上 - 売上原価 - 販管費 - 税金 - 借入返済 + 新規借入 - 支払利息
    for r in periods:
        comps = [r.sales, r.cogs, r.sga_cash, r.interest_paid, r.tax_paid, r.debt_repayment, r.new_borrowing]
        if any(v is not None for v in comps):
            r.net_change = (
                (r.sales or 0)
                - (r.cogs or 0)
                - (r.sga_cash or 0)
                - (r.interest_paid or 0)
                - (r.tax_paid or 0)
                - (r.debt_repayment or 0)
                + (r.new_borrowing or 0)
            )

    return CashFlowResult(
        periods=periods,
        mode="monthly",
        company_name=company_name,
        fiscal_year_end=fye,
        notes=notes,
    )
