"""Claude APIに渡す抽出プロンプト集。"""

COMBINED_PROMPT = """\
あなたは日本の会計・税務に精通した専門家です。
添付された書類の種別を判定し、対応する構造化データを抽出してください。

【書類種別】
- financial_statements: 貸借対照表/損益計算書/キャッシュフロー計算書/製造原価明細書を含む決算書(決算短信、有価証券報告書、計算書類等)
- account_breakdown   : 勘定科目内訳明細書(売掛金・買掛金・借入金などの取引先別明細)
- tax_return          : 法人税申告書の別表
- monthly_trial       : 月次試算表
- unknown             : 上記いずれにも該当しない

【返答形式(JSON)】
{
  "document_type": "<種別>",
  "confidence": 0.0-1.0,
  "reason": "判定理由を1文",
  "data": <種別ごとのデータ。unknownなら null>
}

【data の構造(種別ごと)】

financial_statements:
{
  "company_name": "会社名",
  "fiscal_year_end": "YYYY-MM-DD",
  "balance_sheet": {
    "current": {
      "cash": <現金及び預金>, "accounts_receivable": <売掛金>, "inventory": <棚卸資産>,
      "total_current_assets": <流動資産合計>, "fixed_assets": <固定資産合計>, "total_assets": <資産合計>,
      "accounts_payable": <買掛金>, "short_term_debt": <短期借入金>,
      "total_current_liabilities": <流動負債合計>, "long_term_debt": <長期借入金>,
      "total_liabilities": <負債合計>, "net_assets": <純資産合計>
    },
    "prior": { 同じ構造 or null }
  },
  "profit_loss": {
    "current": {
      "sales": <売上高>, "cost_of_sales": <売上原価>, "gross_profit": <売上総利益>,
      "sga": <販管費合計>, "operating_income": <営業利益>,
      "ordinary_income": <経常利益>, "pretax_income": <税引前当期純利益>,
      "income_tax": <法人税等>, "net_income": <当期純利益>,
      "depreciation": <減価償却費>, "interest_expense": <支払利息>
    },
    "prior": { 同じ構造 or null }
  },
  "cash_flow_statement": {
    "current": {
      "operating_cf": <営業CF or null>, "investing_cf": <投資CF or null>,
      "financing_cf": <財務CF or null>, "ending_cash": <期末現金及び現金同等物 or null>
    },
    "prior": { 同じ構造 or null }
  },
  "notes": "気付いた事項を1〜2文"
}

account_breakdown:
{
  "accounts_receivable": [{"name": "...", "amount": <残高>, "note": "..."}],
  "accounts_payable": [{"name": "...", "amount": <残高>, "note": "..."}],
  "loans_payable": [{"lender": "...", "balance": <残高>, "interest_rate": <%>, "monthly_repayment": <月次返済額>, "maturity": "YYYY-MM-DD", "note": "..."}],
  "notes": "..."
}

tax_return:
{
  "corporate_tax_current": <当期法人税額 or null>,
  "local_tax_current": <地方法人税・住民税・事業税の合計 or null>,
  "consumption_tax_current": <当期消費税額 or null>,
  "loss_carryforward": <繰越欠損金残高 or null>,
  "interim_payment_made": <中間納付額 or null>,
  "notes": "..."
}

monthly_trial:
{
  "company_name": "...",
  "months": [{"month": "YYYY-MM", "sales": <売上高>, "cost_of_sales": <売上原価>, "sga": <販管費>, "operating_income": <営業利益>, "cash_balance": <月末現預金>}],
  "notes": "..."
}

【ルール】
- 金額は円単位の整数(千円・百万円表記は円に換算)
- 該当データがない項目は null
- 当期と前期があれば両方抽出
- 説明文不要、JSONのみ出力
"""


CLASSIFY_PROMPT = """\
あなたは日本の会計・税務に精通した専門家です。
添付されたPDFが次のどの書類に該当するか1語で答えてください。

選択肢:
- financial_statements : 貸借対照表/損益計算書/キャッシュフロー計算書/製造原価明細書を含む決算書
- account_breakdown    : 勘定科目内訳明細書(売掛金・買掛金・借入金などの取引先別明細)
- tax_return           : 法人税申告書の別表
- monthly_trial        : 月次試算表
- unknown              : 判別不能

JSONで返してください。形式:
{"document_type": "<上記から1つ>", "confidence": 0.0-1.0, "reason": "判定理由を1文で"}
"""


FINANCIAL_STATEMENTS_PROMPT = """\
添付PDFは日本の決算書です。次の構造で全データをJSONで抽出してください。

ルール:
- 金額は円単位の整数(千円・百万円単位の場合は円に換算)
- 当期と前期の両方があれば両方抽出
- 該当データがない項目は null
- 数値は会計上の符号で(マイナス計上はマイナス値で)

形式:
{
  "company_name": "会社名",
  "fiscal_year_end": "YYYY-MM-DD",
  "prior_year_end": "YYYY-MM-DD or null",
  "balance_sheet": {
    "current": {
      "cash": <現金及び預金>,
      "accounts_receivable": <売掛金>,
      "inventory": <棚卸資産>,
      "other_current_assets": <その他流動資産>,
      "total_current_assets": <流動資産合計>,
      "fixed_assets": <固定資産合計>,
      "total_assets": <資産合計>,
      "accounts_payable": <買掛金>,
      "short_term_debt": <短期借入金>,
      "other_current_liabilities": <その他流動負債>,
      "total_current_liabilities": <流動負債合計>,
      "long_term_debt": <長期借入金>,
      "other_long_term_liabilities": <その他固定負債>,
      "total_liabilities": <負債合計>,
      "net_assets": <純資産合計>
    },
    "prior": { 同じ構造 or null }
  },
  "profit_loss": {
    "current": {
      "sales": <売上高>,
      "cost_of_sales": <売上原価>,
      "gross_profit": <売上総利益>,
      "sga": <販管費合計>,
      "operating_income": <営業利益>,
      "non_operating_income": <営業外収益>,
      "non_operating_expense": <営業外費用>,
      "ordinary_income": <経常利益>,
      "extraordinary_income": <特別利益>,
      "extraordinary_loss": <特別損失>,
      "pretax_income": <税引前当期純利益>,
      "income_tax": <法人税等>,
      "net_income": <当期純利益>,
      "depreciation": <減価償却費 (販管費内+製造原価内の合計、わからなければ販管費内のみ)>,
      "interest_expense": <支払利息>
    },
    "prior": { 同じ構造 or null }
  },
  "cash_flow_statement": {
    "current": {
      "operating_cf": <営業活動によるCF or null>,
      "investing_cf": <投資活動によるCF or null>,
      "financing_cf": <財務活動によるCF or null>,
      "ending_cash": <期末現金及び現金同等物 or null>
    },
    "prior": { 同じ構造 or null }
  },
  "manufacturing_cost": {
    "current": {
      "materials": <材料費 or null>,
      "labor": <労務費 or null>,
      "expenses": <経費 or null>,
      "depreciation_in_cogs": <製造原価内の減価償却費 or null>,
      "total": <当期製品製造原価 or null>
    },
    "prior": { 同じ構造 or null }
  },
  "notes": "抽出時に気付いた事項(数値の単位、特殊な勘定科目など)を1〜3文で"
}

説明文は不要。JSONのみ出力してください。
"""


ACCOUNT_BREAKDOWN_PROMPT = """\
添付PDFは日本の勘定科目内訳明細書です。次の構造でJSONで抽出してください。

ルール:
- 金額は円単位の整数
- 該当データがない項目は空配列または null
- 取引先名は記載通り(個人名・法人名)

形式:
{
  "accounts_receivable": [
    {"name": "取引先名", "amount": <残高>, "note": "備考があれば"}
  ],
  "accounts_payable": [
    {"name": "取引先名", "amount": <残高>, "note": "備考があれば"}
  ],
  "loans_payable": [
    {
      "lender": "借入先名",
      "balance": <期末残高>,
      "interest_rate": <年利率% or null>,
      "monthly_repayment": <月次返済額 or null>,
      "maturity": "YYYY-MM-DD or null",
      "note": "備考があれば"
    }
  ],
  "inventory_detail": [
    {"name": "品目", "amount": <残高>}
  ],
  "notes": "気付いた事項を1〜2文"
}

説明文は不要。JSONのみ出力してください。
"""


TAX_RETURN_PROMPT = """\
添付PDFは日本の法人税申告書(別表)です。資金繰りに影響する項目を抽出してJSONで返してください。

形式:
{
  "corporate_tax_current": <当期法人税額 or null>,
  "local_tax_current": <地方法人税・住民税・事業税の合計 or null>,
  "consumption_tax_current": <当期消費税額 or null>,
  "loss_carryforward": <繰越欠損金残高 or null>,
  "interim_payment_made": <中間納付額 or null>,
  "notes": "気付いた事項を1〜2文"
}

説明文は不要。JSONのみ出力してください。
"""


MONTHLY_TRIAL_PROMPT = """\
添付PDFは月次試算表です。月別の主要数値をJSONで抽出してください。

形式:
{
  "company_name": "会社名 or null",
  "months": [
    {
      "month": "YYYY-MM",
      "sales": <売上高>,
      "cost_of_sales": <売上原価 or null>,
      "gross_profit": <売上総利益 or null>,
      "sga": <販管費 or null>,
      "operating_income": <営業利益 or null>,
      "cash_balance": <月末現預金残高 or null>
    }
  ],
  "notes": "気付いた事項を1〜2文"
}

説明文は不要。JSONのみ出力してください。
"""
