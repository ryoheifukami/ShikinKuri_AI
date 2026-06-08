"""資金繰り自動出力ツール (Streamlit)"""
from __future__ import annotations

import os
from datetime import date

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

if "ANTHROPIC_API_KEY" not in os.environ:
    try:
        if "ANTHROPIC_API_KEY" in st.secrets:
            os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        pass

from src.advisor import CATEGORY_ICONS, CATEGORY_NAMES, generate_advice
from src.charts import plot_cash_balance, plot_in_out
from src.excel_writer import build_workbook
from src.financial_model import reconstruct_cashflow
from src.forecaster import derive_growth_rate, forecast
from src.pdf_reader import merge_documents, read_pdf
from src.pdf_writer import build_pdf


APP_TITLE = "資金繰り自動出力ツール"

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --------------------------------------------------------------------------
# Custom CSS — 白ベース、抑制された配色、明快なヒエラルキー
# --------------------------------------------------------------------------
st.markdown("""
<style>
/* ===== Base ===== */
.stApp {
    background: #FFFFFF;
    color: #0F172A;
}

.block-container {
    padding-top: 2.5rem !important;
    padding-bottom: 4rem !important;
    max-width: 1280px;
}

/* ===== Typography ===== */
h1 {
    font-weight: 700 !important;
    letter-spacing: -0.025em;
    color: #0F172A !important;
    font-size: 2.25rem !important;
    line-height: 1.2 !important;
    margin-bottom: 0.4rem !important;
}

h2 {
    font-weight: 600 !important;
    color: #0F172A !important;
    font-size: 1.4rem !important;
    letter-spacing: -0.01em;
    border-bottom: 1px solid #E5E7EB;
    padding-bottom: 0.6rem;
    margin-top: 2.5rem !important;
    margin-bottom: 1rem !important;
}

h3 {
    font-weight: 600 !important;
    color: #0F172A !important;
    font-size: 1.05rem !important;
    margin-top: 1rem !important;
}

h4 {
    font-weight: 600 !important;
    color: #334155 !important;
    font-size: 0.95rem !important;
}

p, .stMarkdown, .stText {
    color: #334155;
    line-height: 1.65;
}

/* ===== Hero ===== */
.hero-subtitle {
    color: #64748B;
    font-size: 1.0rem;
    margin-bottom: 2rem;
    margin-top: 0;
    font-weight: 400;
}

/* ===== Step indicator ===== */
.step-label {
    display: inline-flex;
    align-items: center;
    gap: 0.6rem;
    color: #1E40AF;
    font-weight: 600;
    font-size: 0.825rem;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin-bottom: 0.3rem;
}
.step-num {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    background: #1E40AF;
    color: white;
    border-radius: 50%;
    font-weight: 700;
    font-size: 0.75rem;
}

/* ===== Cards (bordered containers) ===== */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 12px !important;
    border: 1px solid #E5E7EB !important;
    background: #FFFFFF;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    transition: box-shadow 0.2s ease;
}

[data-testid="stVerticalBlockBorderWrapper"]:hover {
    box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06);
}

/* ===== Buttons ===== */
.stButton > button[kind="primary"],
.stDownloadButton > button {
    background: #1E40AF !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    padding: 0.6rem 1.4rem !important;
    box-shadow: 0 1px 2px rgba(30, 64, 175, 0.18) !important;
    transition: all 0.15s ease !important;
    color: #FFFFFF !important;
}

/* ボタン内のあらゆる文字を白に強制 */
.stButton > button[kind="primary"] *,
.stButton > button[kind="primary"] p,
.stButton > button[kind="primary"] span,
.stButton > button[kind="primary"] div,
.stDownloadButton > button *,
.stDownloadButton > button p,
.stDownloadButton > button span,
.stDownloadButton > button div {
    color: #FFFFFF !important;
}

.stButton > button[kind="primary"]:hover,
.stDownloadButton > button:hover {
    background: #1E3A8A !important;
    box-shadow: 0 4px 12px rgba(30, 64, 175, 0.22) !important;
    transform: translateY(-1px);
}

.stButton > button[kind="primary"]:hover *,
.stDownloadButton > button:hover * {
    color: #FFFFFF !important;
}

.stButton > button[kind="secondary"] {
    background: #FFFFFF !important;
    border: 1px solid #CBD5E1 !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    color: #334155 !important;
}

/* ===== File uploader ===== */
[data-testid="stFileUploaderDropzone"] {
    background: #F8FAFC !important;
    border: 2px dashed #CBD5E1 !important;
    border-radius: 12px !important;
    padding: 2rem !important;
    transition: all 0.2s ease;
}

[data-testid="stFileUploaderDropzone"]:hover {
    background: #F1F5F9 !important;
    border-color: #94A3B8 !important;
}

/* ===== Text input / area ===== */
.stTextArea textarea,
.stTextInput input {
    border-radius: 8px !important;
    border: 1px solid #E5E7EB !important;
    font-family: "Inter", "Yu Gothic", "Hiragino Sans", sans-serif !important;
    color: #0F172A !important;
}

.stTextArea textarea:focus,
.stTextInput input:focus {
    border-color: #1E40AF !important;
    box-shadow: 0 0 0 3px rgba(30, 64, 175, 0.1) !important;
}

/* ===== Sidebar ===== */
[data-testid="stSidebar"] {
    background: #F8FAFC !important;
    border-right: 1px solid #E5E7EB;
}

[data-testid="stSidebar"] h2 {
    border: none !important;
    margin-top: 0.5rem !important;
    font-size: 0.85rem !important;
    color: #64748B !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 600 !important;
}

[data-testid="stSidebar"] hr {
    margin: 1.5rem 0 !important;
    border-color: #E5E7EB !important;
}

/* ===== Alerts ===== */
[data-testid="stAlert"] {
    border-radius: 8px !important;
    border: 1px solid;
    border-left-width: 4px !important;
    padding: 0.85rem 1rem !important;
}

/* ===== Images (charts) ===== */
.stImage {
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid #E5E7EB;
    background: white;
}

.stImage img {
    border-radius: 12px;
}

/* ===== Dataframe ===== */
[data-testid="stDataFrame"] {
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    overflow: hidden;
}

/* ===== Status pill ===== */
.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.3rem 0.7rem;
    border-radius: 999px;
    font-size: 0.8rem;
    font-weight: 600;
}
.status-pill.ok {
    background: #DCFCE7;
    color: #166534;
}
.status-pill.warn {
    background: #FEF3C7;
    color: #92400E;
}
.status-pill.err {
    background: #FEE2E2;
    color: #991B1B;
}

/* ===== Category section ===== */
.category-header {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin-top: 1.5rem;
    margin-bottom: 0.6rem;
    padding-bottom: 0.4rem;
    border-bottom: 2px solid #E5E7EB;
}
.category-header .cat-icon {
    font-size: 1.25rem;
}
.category-header .cat-name {
    font-weight: 700;
    color: #0F172A;
    font-size: 1.05rem;
}

/* ===== Advice card body styling ===== */
.advice-priority {
    display: inline-block;
    padding: 0.15rem 0.6rem;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
    margin-left: 0.5rem;
}
.advice-priority.high {
    background: #FEE2E2;
    color: #991B1B;
}
.advice-priority.medium {
    background: #FEF3C7;
    color: #92400E;
}
.advice-priority.low {
    background: #DCFCE7;
    color: #166534;
}
.advice-action {
    margin-top: 0.5rem;
    padding: 0.6rem 0.85rem;
    background: #EFF6FF;
    border-left: 3px solid #1E40AF;
    border-radius: 4px;
    font-size: 0.92rem;
    color: #1E3A8A;
}

/* ===== Hide Streamlit defaults ===== */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header[data-testid="stHeader"] {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Hero
# --------------------------------------------------------------------------
st.markdown(f"<h1>{APP_TITLE}</h1>", unsafe_allow_html=True)
st.markdown(
    '<p class="hero-subtitle">決算書PDFをアップロードするだけで、経営者向けの資金繰り表を自動生成します。</p>',
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------
with st.sidebar:
    api_key_set = bool(os.environ.get("ANTHROPIC_API_KEY"))

    st.markdown("## システム状態")
    if api_key_set:
        st.markdown('<span class="status-pill ok">●  Claude API 接続済み</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-pill err">●  APIキー未設定</span>', unsafe_allow_html=True)
        st.caption("`.env` に `ANTHROPIC_API_KEY=...` を記述してください。")

    st.divider()

    st.markdown("## 使い方")
    st.markdown(
        "**1.**  決算書PDFをアップロード  \n"
        "**2.**  必要に応じて補足資料も追加  \n"
        "**3.**  解析開始  \n"
        "**4.**  追記情報を入力(任意)  \n"
        "**5.**  資金繰り表を生成  \n"
        "**6.**  Excel / PDF をダウンロード"
    )

    st.divider()

    st.markdown("## 設計方針")
    st.caption(
        "・アップロード資料の数字のみ使用\n"
        "\n・ソースのない項目は空欄"
        "\n\n・予測は前期比較から自動算出"
    )


# --------------------------------------------------------------------------
# Session state init
# --------------------------------------------------------------------------
for key, default in [
    ("extracted_docs", []),
    ("merged", None),
    ("cashflow", None),
    ("forecasts", None),
    ("advice", None),
    ("user_notes", ""),
    ("company_name", ""),
]:
    if key not in st.session_state:
        st.session_state[key] = default


def _step(num: int, title: str) -> None:
    """ステップ番号付きの見出しを表示する。"""
    st.markdown(
        f'<div class="step-label"><span class="step-num">{num}</span> STEP {num}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(f"## {title}")


# --------------------------------------------------------------------------
# STEP 1 — Upload
# --------------------------------------------------------------------------
_step(1, "決算書PDFをアップロード")
st.caption("決算書(必須)、勘定科目内訳明細書、法人税申告書、月次試算表など、複数選択可。種別は自動判定します。")

uploaded_files = st.file_uploader(
    "ファイルを選択またはドラッグ&ドロップ",
    type=["pdf"],
    accept_multiple_files=True,
    label_visibility="collapsed",
)

if uploaded_files and st.button("解析を開始する", type="primary", disabled=not api_key_set):
    st.session_state.extracted_docs = []
    progress = st.progress(0.0, text="PDFを解析中...")
    rate_limit_placeholder = st.empty()

    def _on_wait(seconds: float):
        rate_limit_placeholder.warning(
            f"APIレート制限に達したため {int(seconds)} 秒待機して再試行します..."
        )

    for i, f in enumerate(uploaded_files):
        progress.progress(i / len(uploaded_files), text=f"解析中: {f.name}")
        try:
            ext = read_pdf(f.name, f.read(), on_rate_limit_wait=_on_wait)
            st.session_state.extracted_docs.append(ext)
            rate_limit_placeholder.empty()
        except Exception as e:
            st.error(f"{f.name} の解析に失敗: {e}")
    progress.progress(1.0, text="完了")
    st.session_state.merged = merge_documents(st.session_state.extracted_docs)
    st.session_state.cashflow = None


# --------------------------------------------------------------------------
# STEP 2 — Extraction results
# --------------------------------------------------------------------------
if st.session_state.extracted_docs:
    _step(2, "抽出結果")

    cols = st.columns(min(3, len(st.session_state.extracted_docs)))
    for i, doc in enumerate(st.session_state.extracted_docs):
        with cols[i % len(cols)]:
            with st.container(border=True):
                if doc.error:
                    st.markdown('<span class="status-pill err">●  解析失敗</span>', unsafe_allow_html=True)
                else:
                    st.markdown(
                        f'<span class="status-pill ok">●  {doc.label_ja}</span>',
                        unsafe_allow_html=True,
                    )
                st.markdown(f"**{doc.filename}**")
                if doc.error:
                    st.caption(doc.error)
                else:
                    st.caption(f"確度: {doc.confidence:.0%} — {doc.classify_reason}")

    with st.expander("抽出データの詳細(JSON)"):
        st.json(st.session_state.merged)


# --------------------------------------------------------------------------
# STEP 3 — Generation form
# --------------------------------------------------------------------------
if st.session_state.merged and st.session_state.merged.get("financial_statements"):
    _step(3, "資金繰り表を生成")

    merged = st.session_state.merged
    fin = merged["financial_statements"]
    default_company = fin.get("company_name", "") if fin else ""

    g = derive_growth_rate(fin)
    if g is not None:
        st.info(f"前期比較から自動算出した年成長率は **{g*100:+.1f}%** です(売上ベース)。予測に利用します。")
    else:
        st.info("前期データが見つからないため、成長率は 0% で予測します。")

    with st.container(border=True):
        company_name = st.text_input("会社名", value=default_company, help="自動取得した値が入力されています。必要に応じて編集してください。")

        st.markdown("**追記情報** (任意)")
        st.caption("決算書からは読み取れない情報を、AIアドバイスに反映させたい場合に記入してください。")
        user_notes = st.text_area(
            "追記情報",
            value=st.session_state.get("user_notes", ""),
            placeholder=(
                "例:\n"
                "・来月から大口取引先A社との契約が終了予定\n"
                "・8月に設備投資2,000万円を予定\n"
                "・来期から金利が1.5%上昇する見込み\n"
                "・代表者個人からの借入1,000万円を返済予定"
            ),
            height=140,
            label_visibility="collapsed",
        )

    if st.button("資金繰り表を生成する", type="primary"):
        with st.spinner("資金繰り表を生成中..."):
            cashflow = reconstruct_cashflow(
                financial=merged.get("financial_statements"),
                breakdown=merged.get("account_breakdown"),
                tax=merged.get("tax_return"),
                monthly_trial=merged.get("monthly_trial"),
            )
            forecasts = forecast(cashflow, financial=merged.get("financial_statements"))
            try:
                advice = generate_advice(
                    cashflow, forecasts,
                    company_name=company_name,
                    user_notes=user_notes,
                )
            except Exception as e:
                st.warning(f"アドバイス生成に失敗: {e}")
                advice = []

        st.session_state.cashflow = cashflow
        st.session_state.forecasts = forecasts
        st.session_state.advice = advice
        st.session_state.company_name = company_name
        st.session_state.user_notes = user_notes


# --------------------------------------------------------------------------
# STEP 4 — Results
# --------------------------------------------------------------------------
if st.session_state.get("cashflow"):
    cashflow = st.session_state.cashflow
    forecasts = st.session_state.get("forecasts") or []
    advice = st.session_state.get("advice") or []
    company_name = st.session_state.get("company_name", "")
    user_notes_saved = st.session_state.get("user_notes", "")

    _step(4, "資金繰り表(結果)")

    mode_label = "月次モード" if cashflow.mode == "monthly" else "年次モード"
    st.caption(f"出力モード: {mode_label}")

    if cashflow.notes:
        for n in cashflow.notes:
            st.info(n)
    if cashflow.warnings:
        for w in cashflow.warnings:
            st.warning(w)

    combined = list(cashflow.periods) + list(forecasts)
    cash_chart = plot_cash_balance(cashflow.periods, forecasts)
    in_out_chart = plot_in_out(combined)

    # グラフ
    st.markdown("### 期末現預金残高の推移")
    st.image(cash_chart)
    st.markdown("### 売上と支出")
    st.image(in_out_chart)

    # アドバイス(観点別)
    if advice:
        st.markdown("### 経営アドバイス(観点別)")

        priority_label = {
            "high": '<span class="advice-priority high">重要度 高</span>',
            "medium": '<span class="advice-priority medium">重要度 中</span>',
            "low": '<span class="advice-priority low">重要度 低</span>',
        }

        grouped: dict[str, list] = {c: [] for c in CATEGORY_NAMES}
        for a in advice:
            grouped.setdefault(a.category, []).append(a)

        for cat in CATEGORY_NAMES:
            items = grouped.get(cat, [])
            if not items:
                continue
            icon = CATEGORY_ICONS.get(cat, "")
            st.markdown(
                f'<div class="category-header"><span class="cat-icon">{icon}</span>'
                f'<span class="cat-name">{cat}</span></div>',
                unsafe_allow_html=True,
            )
            for a in items:
                with st.container(border=True):
                    st.markdown(
                        f"**{a.headline}** {priority_label.get(a.priority, '')}",
                        unsafe_allow_html=True,
                    )
                    st.write(a.detail)
                    if a.action:
                        st.markdown(
                            f'<div class="advice-action">推奨アクション: {a.action}</div>',
                            unsafe_allow_html=True,
                        )

    # 数値表
    with st.expander("数値表 (全期間、単位: 千円)", expanded=False):
        import pandas as pd

        def _scale(v):
            return None if v is None else int(round(v / 1000))

        rows = []
        for r in combined:
            rows.append({
                "ラベル": (r.label or "") + ("(予測)" if r.is_forecast else ""),
                "期間": r.period,
                "売上高": _scale(r.sales),
                "売上原価": _scale(r.cogs),
                "売上総利益": _scale(r.gross_profit),
                "販管費(現金)": _scale(r.sga_cash),
                "営業利益": _scale(r.operating_income),
                "支払利息": _scale(r.interest_paid),
                "税金": _scale(r.tax_paid),
                "新規借入": _scale(r.new_borrowing),
                "借入返済": _scale(r.debt_repayment),
                "期首現預金": _scale(r.opening_cash),
                "期間中増減": _scale(r.net_change),
                "期末現預金": _scale(r.ending_cash),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # --------------------------------------------------------------------
    # STEP 5 — Download
    # --------------------------------------------------------------------
    _step(5, "ダウンロード")

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.markdown("**Excel ファイル**")
            st.caption("資金繰り表 / 経営アドバイス / 前提・注意事項")
            xlsx_bytes = build_workbook(
                cashflow, forecasts, advice,
                company_name=company_name,
                user_notes=user_notes_saved,
            )
            st.download_button(
                "Excel(.xlsx) をダウンロード",
                data=xlsx_bytes,
                file_name=f"shikin_kuri_{company_name or 'company'}_{date.today().isoformat()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True,
            )
    with col2:
        with st.container(border=True):
            st.markdown("**PDF ファイル**")
            st.caption("配布・印刷用にレイアウト済み")
            pdf_bytes = build_pdf(
                cashflow, forecasts, advice,
                cash_chart_png=cash_chart, in_out_chart_png=in_out_chart,
                company_name=company_name,
                user_notes=user_notes_saved,
            )
            st.download_button(
                "PDF をダウンロード",
                data=pdf_bytes,
                file_name=f"shikin_kuri_{company_name or 'company'}_{date.today().isoformat()}.pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True,
            )
