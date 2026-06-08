"""Claude APIを呼ばないスモークテスト。"""
from __future__ import annotations

from src.advisor import AdviceItem
from src.excel_writer import build_workbook
from src.financial_model import reconstruct_cashflow
from src.forecaster import forecast


def _dummy_financial(with_prior: bool = True):
    cur = {
        "balance_sheet": {
            "current": {"cash": 30_000_000, "accounts_receivable": 20_000_000},
            "prior": {"cash": 25_000_000} if with_prior else None,
        },
        "profit_loss": {
            "current": {
                "sales": 120_000_000, "cost_of_sales": 72_000_000,
                "gross_profit": 48_000_000, "sga": 36_000_000, "depreciation": 3_000_000,
                "operating_income": 12_000_000, "interest_expense": 600_000,
            },
            "prior": {"sales": 110_000_000, "cost_of_sales": 66_000_000} if with_prior else None,
        },
        "cash_flow_statement": {
            "current": {"operating_cf": 15_000_000, "investing_cf": -5_000_000, "financing_cf": -8_000_000},
            "prior": None,
        },
        "company_name": "テスト株式会社",
        "fiscal_year_end": "2026-03-31",
    }
    return cur


def _dummy_breakdown():
    return {"loans_payable": [{"lender": "A銀行", "balance": 30_000_000, "monthly_repayment": 250_000}]}


def test_annual_mode_no_fabrication():
    """月次試算表なし → 年次サマリーで出力。借入返済・税金は空欄。"""
    cf = reconstruct_cashflow(_dummy_financial(), breakdown=None, tax=None)
    assert cf.mode == "annual"
    assert len(cf.periods) == 2  # 前期 + 当期
    cur = cf.periods[-1]
    assert cur.sales == 120_000_000
    assert cur.tax_paid is None  # ソースなし
    assert cur.debt_repayment is None  # ソースなし


def test_annual_mode_with_breakdown():
    """内訳明細あり → 借入返済が入る。"""
    cf = reconstruct_cashflow(_dummy_financial(), breakdown=_dummy_breakdown())
    cur = cf.periods[-1]
    assert cur.debt_repayment == 250_000 * 12


def test_forecast_annual_auto():
    """予測パラメータなし、決算書から自動算出。"""
    fin = _dummy_financial(with_prior=True)
    cf = reconstruct_cashflow(fin)
    fcs = forecast(cf, financial=fin)
    assert len(fcs) == 2  # デフォルト2期
    # 売上成長率は (120 - 110) / 110 = 9.09%
    assert fcs[0].sales is not None
    assert fcs[0].sales > cf.periods[-1].sales  # 成長してる
    assert all(p.is_forecast for p in fcs)


def test_forecast_no_prior():
    """前期データなし → 成長率0%でフラット予測。"""
    fin = _dummy_financial(with_prior=False)
    cf = reconstruct_cashflow(fin)
    fcs = forecast(cf, financial=fin)
    assert len(fcs) == 2
    if cf.periods[-1].sales is not None and fcs[0].sales is not None:
        assert abs(fcs[0].sales - cf.periods[-1].sales) < 1


def test_build_workbook_annual():
    fin = _dummy_financial()
    cf = reconstruct_cashflow(fin, breakdown=_dummy_breakdown())
    fcs = forecast(cf, financial=fin)
    advice = [
        AdviceItem(category="資金繰り", headline="テスト", detail="詳細", action="やる", priority="high")
    ]
    data = build_workbook(
        cf, fcs, advice,
        company_name="テスト株式会社",
        user_notes="来月から新規取引先\n設備投資3,000万円予定",
    )
    assert data[:2] == b"PK"
    assert len(data) > 2000


def test_monthly_mode():
    """月次試算表あり → 月次モード。"""
    monthly = {"months": [
        {"month": "2025-04", "sales": 10_000_000, "cost_of_sales": 6_000_000, "sga": 3_000_000, "cash_balance": 26_000_000},
        {"month": "2025-05", "sales": 11_000_000, "cost_of_sales": 6_500_000, "sga": 3_000_000, "cash_balance": 27_500_000},
    ]}
    cf = reconstruct_cashflow(_dummy_financial(), monthly_trial=monthly)
    assert cf.mode == "monthly"
    assert len(cf.periods) == 2
    assert cf.periods[0].sales == 10_000_000
