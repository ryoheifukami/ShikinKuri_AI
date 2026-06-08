"""matplotlib で資金繰り表のグラフ画像を生成する。

実績(実線)と予測(点線)を1つのグラフに描画する。
Noneは欠損として扱い、線をつなげず欠損部分は描画しない。
"""
from __future__ import annotations

import io
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

from .financial_model import PeriodRow


def _setup_japanese_font() -> None:
    """OS横断で日本語フォントを設定する。

    優先順:
    1. matplotlib に既にインデックス済みのフォント名で検索
    2. Linuxでフォントが最近インストールされた場合、ファイルパスを直接探して登録
    """
    # OS毎の日本語フォント候補(順序が優先順)
    candidates = [
        "Noto Sans CJK JP",  # Linux (fonts-noto-cjk)
        "Noto Sans JP",
        "Noto Serif CJK JP",
        "IPAexGothic",
        "TakaoGothic",
        "Yu Gothic",  # Windows
        "Meiryo",     # Windows
        "MS Gothic",  # Windows
        "Hiragino Sans",  # macOS
    ]
    installed = {f.name for f in font_manager.fontManager.ttflist}
    for c in candidates:
        if c in installed:
            plt.rcParams["font.family"] = c
            plt.rcParams["axes.unicode_minus"] = False
            return

    # 既知の場所にあるフォントファイルを直接登録(Linuxで apt install 直後など)
    candidate_paths = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
    ]
    for p in candidate_paths:
        if os.path.exists(p):
            try:
                font_manager.fontManager.addfont(p)
                prop = font_manager.FontProperties(fname=p)
                plt.rcParams["font.family"] = prop.get_name()
                plt.rcParams["axes.unicode_minus"] = False
                return
            except Exception:
                continue

    # システム全体を走査して CJK フォントを探す
    for path in font_manager.findSystemFonts():
        lower = path.lower()
        if "notosanscjk" in lower or "notosansjp" in lower or "cjk" in lower:
            try:
                font_manager.fontManager.addfont(path)
                prop = font_manager.FontProperties(fname=path)
                plt.rcParams["font.family"] = prop.get_name()
                plt.rcParams["axes.unicode_minus"] = False
                return
            except Exception:
                continue

    # フォールバック
    plt.rcParams["axes.unicode_minus"] = False


_setup_japanese_font()


# 表示単位
UNIT_DIVISOR = 1_000_000  # 円 → 百万円
UNIT_LABEL = "百万円"


def _to_unit(value: float | None) -> float | None:
    return None if value is None else value / UNIT_DIVISOR


def plot_cash_balance(
    actual: list[PeriodRow],
    forecasts: list[PeriodRow] | None = None,
) -> bytes:
    """期末現預金残高の推移(実績+予測)を1本のグラフに描画。"""
    fig, ax = plt.subplots(figsize=(10, 5))

    has_data = False

    if actual:
        x = [r.period for r in actual]
        y = [_to_unit(r.ending_cash) for r in actual]
        if any(v is not None for v in y):
            ax.plot(x, y, marker="o", linewidth=2.5, label="実績", color="#1f77b4")
            has_data = True

    if forecasts and actual:
        x = [actual[-1].period] + [r.period for r in forecasts]
        y = [_to_unit(actual[-1].ending_cash)] + [_to_unit(r.ending_cash) for r in forecasts]
        if any(v is not None for v in y):
            ax.plot(x, y, marker="s", linewidth=2, linestyle="--", label="予測", color="#ff7f0e")
            has_data = True

    if not has_data:
        ax.text(0.5, 0.5, "期末現預金データなし", ha="center", va="center", transform=ax.transAxes)

    ax.set_title(f"期末現預金残高の推移(単位:{UNIT_LABEL})", fontsize=14, pad=15, fontweight="bold")
    ax.set_ylabel(f"金額 [{UNIT_LABEL}]", fontsize=11)
    ax.set_xlabel("期間", fontsize=11)
    ax.axhline(0, color="red", linewidth=0.8, linestyle=":", alpha=0.6)
    ax.grid(True, alpha=0.3)
    if has_data:
        ax.legend(loc="best", framealpha=0.95)
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


def plot_in_out(actual: list[PeriodRow]) -> bytes:
    """売上(入金) vs 支出 vs 純増減 の棒+折れ線グラフ。"""
    fig, ax = plt.subplots(figsize=(10, 5))

    periods = [r.period for r in actual]
    cash_in = [_to_unit(r.sales) if r.sales is not None else 0 for r in actual]
    cash_out = []
    for r in actual:
        out = sum(filter(None, [r.cogs, r.sga_cash, r.interest_paid, r.tax_paid, r.debt_repayment]))
        cash_out.append(_to_unit(out))
    net = [_to_unit(r.net_change) if r.net_change is not None else None for r in actual]

    x_idx = list(range(len(periods)))
    width = 0.35

    if any(v for v in cash_in):
        ax.bar([i - width / 2 for i in x_idx], cash_in, width=width, label="売上(入金)", color="#2ca02c")
    if any(v for v in cash_out):
        ax.bar([i + width / 2 for i in x_idx], cash_out, width=width, label="支出", color="#d62728")
    if any(v is not None for v in net):
        ax.plot(x_idx, net, marker="o", linewidth=2.5, color="#1f77b4", label="差引(純増減)")

    ax.set_title(f"売上と支出(単位:{UNIT_LABEL})", fontsize=14, pad=15, fontweight="bold")
    ax.set_ylabel(f"金額 [{UNIT_LABEL}]", fontsize=11)
    ax.set_xlabel("期間", fontsize=11)
    ax.set_xticks(x_idx)
    ax.set_xticklabels(periods, rotation=45, ha="right")
    ax.axhline(0, color="black", linewidth=0.5)
    ax.grid(True, alpha=0.3, axis="y")
    ax.legend(loc="best", framealpha=0.95)
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


# 後方互換
plot_monthly_in_out = plot_in_out
