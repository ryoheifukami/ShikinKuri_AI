"""matplotlib で資金繰り表のグラフ画像を生成する。

実績(実線)と予測(点線)を1つのグラフに描画する。
Noneは欠損として扱い、線をつなげず欠損部分は描画しない。
"""
from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

from .financial_model import PeriodRow


def _setup_japanese_font() -> None:
    candidates = ["Yu Gothic", "Meiryo", "MS Gothic", "Hiragino Sans", "Noto Sans CJK JP", "IPAexGothic", "TakaoGothic"]
    installed = {f.name for f in font_manager.fontManager.ttflist}
    for c in candidates:
        if c in installed:
            plt.rcParams["font.family"] = c
            break
    plt.rcParams["axes.unicode_minus"] = False


_setup_japanese_font()


def _to_million(value: float | None) -> float | None:
    return None if value is None else value / 1_000_000


def plot_cash_balance(
    actual: list[PeriodRow],
    forecasts: list[PeriodRow] | None = None,
) -> bytes:
    """期末現預金残高の推移(実績+予測)を1本のグラフに描画。"""
    fig, ax = plt.subplots(figsize=(10, 5))

    has_data = False

    if actual:
        x = [r.period for r in actual]
        y = [_to_million(r.ending_cash) for r in actual]
        if any(v is not None for v in y):
            ax.plot(x, y, marker="o", linewidth=2, label="実績", color="#1f77b4")
            has_data = True

    if forecasts and actual:
        # 接続点として実績の最終を追加
        x = [actual[-1].period] + [r.period for r in forecasts]
        y = [_to_million(actual[-1].ending_cash)] + [_to_million(r.ending_cash) for r in forecasts]
        if any(v is not None for v in y):
            ax.plot(x, y, marker="s", linewidth=1.5, linestyle="--", label="予測", color="#ff7f0e")
            has_data = True

    if not has_data:
        ax.text(0.5, 0.5, "期末現預金データなし", ha="center", va="center", transform=ax.transAxes)

    ax.set_title("期末現預金残高の推移", fontsize=14, pad=15)
    ax.set_ylabel("百万円")
    ax.axhline(0, color="red", linewidth=0.8, linestyle=":", alpha=0.6)
    ax.grid(True, alpha=0.3)
    if has_data:
        ax.legend(loc="best")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def plot_in_out(actual: list[PeriodRow]) -> bytes:
    """売上(入金) vs 支出 vs 純増減 の棒+折れ線グラフ。"""
    fig, ax = plt.subplots(figsize=(10, 5))

    periods = [r.period for r in actual]
    cash_in = [_to_million(r.sales) if r.sales is not None else 0 for r in actual]
    cash_out = []
    for r in actual:
        out = sum(filter(None, [r.cogs, r.sga_cash, r.interest_paid, r.tax_paid, r.debt_repayment]))
        cash_out.append(_to_million(out))
    net = [_to_million(r.net_change) if r.net_change is not None else None for r in actual]

    x_idx = list(range(len(periods)))
    width = 0.35

    if any(v for v in cash_in):
        ax.bar([i - width / 2 for i in x_idx], cash_in, width=width, label="売上", color="#2ca02c")
    if any(v for v in cash_out):
        ax.bar([i + width / 2 for i in x_idx], cash_out, width=width, label="支出", color="#d62728")
    if any(v is not None for v in net):
        ax.plot(x_idx, net, marker="o", color="#1f77b4", label="差引")

    ax.set_title("売上と支出", fontsize=14, pad=15)
    ax.set_ylabel("百万円")
    ax.set_xticks(x_idx)
    ax.set_xticklabels(periods, rotation=45, ha="right")
    ax.axhline(0, color="black", linewidth=0.5)
    ax.grid(True, alpha=0.3, axis="y")
    ax.legend(loc="best")
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


# 後方互換
plot_monthly_in_out = plot_in_out
