"""過去実績から将来予測を自動生成する。

ユーザー入力は不要。決算書の前期/当期比較から成長率を自動算出する。

- 年次モード: 当期 → 予測(+1期), 予測(+2期) ...
- 月次モード: 直近平均 + 年次成長率(月率に変換) で先 N ヶ月を予測
"""
from __future__ import annotations

from dataclasses import dataclass

from .financial_model import CashFlowResult, PeriodRow, _fy_label, _opt


@dataclass
class ForecastConfig:
    """予測設定。デフォルトで使えるよう全てに既定値を持たせる。"""

    annual_horizon_years: int = 2  # 年次モード時の予測年数
    monthly_horizon: int = 6  # 月次モード時の予測月数


def derive_growth_rate(financial: dict | None) -> float | None:
    """前期/当期の売上比較から年成長率を算出する。

    どちらか欠ければ None。極端値(±50%超)はノイズの可能性として None。
    """
    if not financial:
        return None
    cur = _opt(financial, "profit_loss", "current", "sales")
    prior = _opt(financial, "profit_loss", "prior", "sales")
    if cur is None or prior is None or prior <= 0:
        return None
    g = (cur - prior) / prior
    if abs(g) > 0.5:
        return None  # 異常値
    return g


def _scaled_row(base: PeriodRow, factor: float) -> PeriodRow:
    """base行を factor 倍して新Rowを返す。Noneは引き継ぐ。"""
    def _m(v: float | None) -> float | None:
        return None if v is None else v * factor

    return PeriodRow(
        period="",
        period_type=base.period_type,
        is_forecast=True,
        sales=_m(base.sales),
        cogs=_m(base.cogs),
        gross_profit=_m(base.gross_profit),
        sga_cash=_m(base.sga_cash),
        operating_income=_m(base.operating_income),
        interest_paid=_m(base.interest_paid),
        tax_paid=_m(base.tax_paid),
        new_borrowing=None,  # 予測なし(ソースなし)
        debt_repayment=_m(base.debt_repayment),
        operating_cf=_m(base.operating_cf),
        investing_cf=_m(base.investing_cf),
        financing_cf=_m(base.financing_cf),
    )


def _recompute_net_change_and_cash(rows: list[PeriodRow], opening: float | None) -> None:
    """純増減と期末現預金を上書き計算する。"""
    cur_cash = opening
    for r in rows:
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
        if cur_cash is not None and r.net_change is not None:
            r.opening_cash = cur_cash
            r.ending_cash = cur_cash + r.net_change
            cur_cash = r.ending_cash


def forecast(
    actual: CashFlowResult,
    financial: dict | None = None,
    config: ForecastConfig | None = None,
) -> list[PeriodRow]:
    """過去実績から将来予測を自動生成する。"""
    cfg = config or ForecastConfig()
    if not actual.periods:
        return []

    growth = derive_growth_rate(financial)

    if actual.mode == "annual":
        # 当期(最後の実績)を基準に、年次で複利成長
        base = actual.periods[-1]
        forecasts: list[PeriodRow] = []
        g = growth if growth is not None else 0.0
        for i in range(1, cfg.annual_horizon_years + 1):
            row = _scaled_row(base, (1.0 + g) ** i)
            row.period = _fy_label(actual.fiscal_year_end, offset=i)
            row.label = f"予測(+{i}期)"
            forecasts.append(row)

        # 期首現預金 = 直近実績の期末
        _recompute_net_change_and_cash(forecasts, base.ending_cash)
        return forecasts

    # 月次モード
    # 直近3ヶ月の平均を基準値に、年次成長率→月率変換
    g_annual = growth if growth is not None else 0.0
    g_monthly = (1.0 + g_annual) ** (1 / 12) - 1.0

    n = min(3, len(actual.periods))
    tail = actual.periods[-n:]

    def _avg(attr: str) -> float | None:
        vals = [getattr(r, attr) for r in tail if getattr(r, attr) is not None]
        return sum(vals) / len(vals) if vals else None

    base_avg = PeriodRow(
        period="",
        period_type="monthly",
        sales=_avg("sales"),
        cogs=_avg("cogs"),
        sga_cash=_avg("sga_cash"),
        interest_paid=_avg("interest_paid"),
        tax_paid=None,  # 月次予測では税金は引き継がない(期末月に発生するため)
        debt_repayment=_avg("debt_repayment"),
    )

    last_period = actual.periods[-1].period  # "YYYY-MM"
    forecasts = []
    for i in range(1, cfg.monthly_horizon + 1):
        ym = _add_months_str(last_period, i)
        row = _scaled_row(base_avg, (1.0 + g_monthly) ** i)
        row.period = ym
        row.label = f"予測(+{i}ヶ月)"
        forecasts.append(row)

    _recompute_net_change_and_cash(forecasts, actual.periods[-1].ending_cash)
    return forecasts


def _add_months_str(ym: str, n: int) -> str:
    """'2026-03' + 1 → '2026-04'。フォーマット不正なら元のまま。"""
    try:
        y, m = int(ym[:4]), int(ym[5:7])
        total = (y * 12 + m - 1) + n
        ny, nm = divmod(total, 12)
        return f"{ny:04d}-{nm + 1:02d}"
    except (ValueError, IndexError):
        return ym
