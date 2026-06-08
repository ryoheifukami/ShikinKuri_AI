"""PDF → Claude API で構造化データを抽出するモジュール。

レート制限対策:
- pdfplumber でローカルでテキスト抽出 → Claude にはテキストだけ送る(トークン削減)
- 書類種別判定と抽出を1回のAPI呼び出しで実施
"""
from __future__ import annotations

import base64
import json
import os
import re
import time
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import anthropic
import pdfplumber
from anthropic import Anthropic

from .extractor_prompts import COMBINED_PROMPT

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# Tier 1の入力トークン上限近くまで使わないよう、テキストを安全に切る
MAX_TEXT_CHARS = 60_000


DOCUMENT_LABELS_JA = {
    "financial_statements": "決算書(財務諸表)",
    "account_breakdown": "勘定科目内訳明細書",
    "tax_return": "法人税申告書(別表)",
    "monthly_trial": "月次試算表",
    "unknown": "不明",
}


@dataclass
class ExtractedDocument:
    filename: str
    document_type: str
    confidence: float
    classify_reason: str
    data: dict[str, Any] | None
    error: str | None = None

    @property
    def label_ja(self) -> str:
        return DOCUMENT_LABELS_JA.get(self.document_type, self.document_type)


def _client() -> Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY が設定されていません。")
    return Anthropic(api_key=api_key)


def _pdf_block(pdf_bytes: bytes) -> dict[str, Any]:
    return {
        "type": "document",
        "source": {
            "type": "base64",
            "media_type": "application/pdf",
            "data": base64.standard_b64encode(pdf_bytes).decode("ascii"),
        },
    }


def _extract_text_local(pdf_bytes: bytes, max_chars: int = MAX_TEXT_CHARS) -> str | None:
    """pdfplumber でローカルにテキストを抜き出す。失敗または短すぎる場合は None。"""
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            chunks = []
            total = 0
            for page in pdf.pages:
                t = page.extract_text() or ""
                if not t.strip():
                    continue
                if total + len(t) > max_chars:
                    chunks.append(t[: max_chars - total])
                    chunks.append("\n... (以降省略) ...")
                    break
                chunks.append(t)
                total += len(t)
            text = "\n\n".join(chunks).strip()
            return text if len(text) >= 200 else None
    except Exception:
        return None


def _extract_json(text: str) -> dict[str, Any]:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"JSONが見つかりません: {text[:200]}")
    return json.loads(text[start : end + 1])


def _call_with_retry(
    cli: Anthropic,
    *,
    model: str,
    content: list,
    max_tokens: int = 8000,
    max_retries: int = 1,
    retry_wait: float = 65.0,
    on_wait=None,
) -> Any:
    """RateLimitError が出たら指定秒待ってリトライする。"""
    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return cli.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": content}],
            )
        except anthropic.RateLimitError as e:
            last_err = e
            if attempt < max_retries:
                if on_wait:
                    on_wait(retry_wait)
                time.sleep(retry_wait)
            else:
                raise
    raise last_err if last_err else RuntimeError("call failed")


def read_pdf(
    filename: str,
    pdf_bytes: bytes,
    *,
    forced_type: str | None = None,
    client: Anthropic | None = None,
    model: str = DEFAULT_MODEL,
    on_rate_limit_wait=None,
) -> ExtractedDocument:
    """PDFを1回のAPI呼び出しで分類+抽出する。

    pdfplumberでテキスト抽出できればテキストを送信(トークン少)。
    抽出失敗(スキャンPDF等)はPDF本体を送信。
    """
    cli = client or _client()

    text = _extract_text_local(pdf_bytes)
    if text:
        # テキストモード(トークン削減)
        user_content = [{
            "type": "text",
            "text": f"{COMBINED_PROMPT}\n\n【書類の内容(ファイル名: {filename})】\n{text}",
        }]
    else:
        # フォールバック: PDF本体を送る(画像PDFの場合)
        user_content = [_pdf_block(pdf_bytes), {"type": "text", "text": COMBINED_PROMPT}]

    try:
        resp = _call_with_retry(
            cli, model=model, content=user_content,
            max_tokens=8000, max_retries=1, retry_wait=65.0,
            on_wait=on_rate_limit_wait,
        )
    except anthropic.RateLimitError:
        return ExtractedDocument(
            filename=filename, document_type="unknown", confidence=0.0,
            classify_reason="", data=None,
            error="レート制限(無料枠)に達しました。1〜2分待ってから再実行してください。"
                  " または https://console.anthropic.com/settings/billing でクレジット購入し上位プランへ。",
        )
    except anthropic.APIStatusError as e:
        return ExtractedDocument(
            filename=filename, document_type="unknown", confidence=0.0,
            classify_reason="", data=None, error=f"API エラー: {e}",
        )

    raw_text = "".join(b.text for b in resp.content if b.type == "text")
    try:
        parsed = _extract_json(raw_text)
    except (ValueError, json.JSONDecodeError) as e:
        return ExtractedDocument(
            filename=filename, document_type="unknown", confidence=0.0,
            classify_reason="", data=None, error=f"応答のJSON解析に失敗: {e}",
        )

    doc_type = forced_type or parsed.get("document_type", "unknown")
    confidence = float(parsed.get("confidence", 0.0) or 0.0)
    reason = parsed.get("reason", "") or ""
    data = parsed.get("data")

    if doc_type == "unknown" or data is None:
        return ExtractedDocument(
            filename=filename, document_type=doc_type, confidence=confidence,
            classify_reason=reason, data=None,
            error="書類種別を判定できなかった、または抽出データがありません。",
        )

    return ExtractedDocument(
        filename=filename, document_type=doc_type, confidence=confidence,
        classify_reason=reason, data=data,
    )


def read_pdf_file(path: str | Path, **kwargs: Any) -> ExtractedDocument:
    p = Path(path)
    return read_pdf(p.name, p.read_bytes(), **kwargs)


def merge_documents(docs: list[ExtractedDocument]) -> dict[str, Any]:
    """複数の抽出結果を1つの会社データにまとめる。"""
    merged: dict[str, Any] = {
        "financial_statements": None,
        "account_breakdown": None,
        "tax_return": None,
        "monthly_trial": None,
    }
    for d in docs:
        if d.error or not d.data:
            continue
        if d.document_type in merged:
            merged[d.document_type] = d.data
    return merged
