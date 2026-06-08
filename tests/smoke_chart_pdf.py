"""グラフ・PDF出力のスモーク確認(Claude API不要)。"""
from src.advisor import AdviceItem
from src.charts import plot_cash_balance, plot_in_out
from src.financial_model import reconstruct_cashflow
from src.forecaster import forecast
from src.pdf_writer import build_pdf

fin = {
    "balance_sheet": {
        "current": {"cash": 30_000_000},
        "prior": {"cash": 25_000_000},
    },
    "profit_loss": {
        "current": {
            "sales": 120_000_000, "cost_of_sales": 72_000_000,
            "gross_profit": 48_000_000, "sga": 36_000_000, "depreciation": 3_000_000,
            "operating_income": 12_000_000, "interest_expense": 600_000,
        },
        "prior": {"sales": 110_000_000, "cost_of_sales": 66_000_000},
    },
    "cash_flow_statement": {
        "current": {"operating_cf": 15_000_000, "investing_cf": -5_000_000, "financing_cf": -8_000_000},
    },
    "company_name": "テスト株式会社",
    "fiscal_year_end": "2026-03-31",
}
bd = {"loans_payable": [{"lender": "A銀行", "balance": 30_000_000, "monthly_repayment": 250_000}]}

cf = reconstruct_cashflow(fin, breakdown=bd)
fcs = forecast(cf, financial=fin)
print(f"mode: {cf.mode}, periods: {len(cf.periods)}, forecasts: {len(fcs)}")

cc = plot_cash_balance(cf.periods, fcs)
io_chart = plot_in_out(list(cf.periods) + list(fcs))
print("cash chart:", len(cc), "bytes")
print("in_out chart:", len(io_chart), "bytes")

advice = [
    AdviceItem(category="資金繰り", headline="テストアドバイス", detail="これはテスト用の説明文です。", action="やってみる", priority="high"),
    AdviceItem(category="安全性", headline="借入の見直し", detail="返済負担が高めです。", action="銀行と協議する", priority="medium"),
]
pdf = build_pdf(
    cf, fcs, advice,
    cash_chart_png=cc, in_out_chart_png=io_chart,
    company_name="テスト株式会社",
    user_notes="6月に大型設備投資3,000万円を予定。\n年末に新規借入1,000万円調達予定。",
)
print("PDF:", len(pdf), "bytes, header:", pdf[:4])
assert pdf[:4] == b"%PDF"
print("OK")
