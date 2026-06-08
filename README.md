# ShikinKuri_AI

士業向けの資金繰り表 自動生成ツール。
決算書PDFをアップロードするだけで、経営者向けに分かりやすい資金繰り表（Excel/PDF）を出力します。

## できること

- 決算書PDF（B/S・P/L・C/F・製造原価明細）を Claude API で読み取り、構造化
- 勘定科目内訳明細書・法人税申告書（別表）・月次試算表もあれば併せて読込
- 過去12ヶ月の月次キャッシュフローを再構成（推定値はセル色で明示）
- 将来3〜12ヶ月を「悲観・標準・楽観」の3シナリオで予測
- 経営者向けの自然言語アドバイス（AI生成）
- 月末現預金推移グラフ・月次入出金グラフ
- Excel と PDF の両方で出力

## セットアップ手順

### 1. Anthropic APIキーを取得

1. https://console.anthropic.com にアクセスしてアカウント作成
2. ログイン後、左メニューの **API Keys** → **Create Key**
3. 表示されたキー（`sk-ant-...`）をコピー
   - ※ キーは一度しか表示されません。安全な場所に保存
4. 初回登録で $5 の無料クレジットが付きます。1決算書あたり概算 $0.10〜0.30 程度

### 2. Python環境を整える

PowerShellで以下を実行：

```powershell
cd C:\Users\aiacq\Projects\ShikinKuri_AI

# 仮想環境を作る（推奨）
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# パッケージをインストール
pip install -r requirements.txt
```

### 3. APIキーを設定

`.env.example` をコピーして `.env` を作成：

```powershell
Copy-Item .env.example .env
notepad .env
```

`.env` を開いて、`ANTHROPIC_API_KEY=` の右に取得したキーを貼り付けて保存。

### 4. 起動

```powershell
streamlit run app.py
```

ブラウザが自動で開きます（http://localhost:8501）。
PDFをアップロード → 解析 → ダウンロード、の流れで使えます。

## Streamlit Community Cloud にデプロイ

公開せず自分だけで使う場合はローカル起動だけでOKです。
公開する場合：

1. このフォルダを GitHub のプライベートリポジトリにpush
2. https://share.streamlit.io にログイン
3. **New app** → リポジトリと `app.py` を選択
4. **Advanced settings** → **Secrets** に以下を貼り付け：
   ```
   ANTHROPIC_API_KEY = "sk-ant-xxxx"
   ```
5. **Deploy**

数分でURLが発行され、ブラウザから誰でも使える状態になります。

## ディレクトリ構成

```
ShikinKuri_AI\
├─ app.py                      Streamlit UI
├─ requirements.txt
├─ .env.example                APIキー設定の雛形
├─ src\
│  ├─ pdf_reader.py            PDF→Claude APIで構造化
│  ├─ extractor_prompts.py     各書類の抽出プロンプト
│  ├─ financial_model.py       年次→月次キャッシュフロー再構成
│  ├─ forecaster.py            将来予測（3シナリオ）
│  ├─ advisor.py               AI経営アドバイス生成
│  ├─ excel_writer.py          Excel出力
│  ├─ pdf_writer.py            PDF出力
│  └─ charts.py                グラフ生成
├─ samples\                    テスト用PDF置き場
└─ tests\                      動作確認スクリプト
```

## テスト用のサンプル決算書

公開されている上場企業の決算書は **EDINET** から取得できます：

- https://disclosure2.edinet-fsa.go.jp/
- 「書類検索」で会社名を入れて、有価証券報告書をダウンロード
- 取得したPDFを `samples\` フォルダに置いて試してください

## コスト目安（月）

| 項目 | 月額 |
|------|------|
| Streamlit Community Cloud | 0円（無料） |
| Claude API（claude-sonnet-4-6） | 1決算書 $0.10〜0.30。月20件処理でも数百円程度 |

## 注意事項

- 月次試算表がない場合、売上・仕入は年額÷12で按分しています（季節性は考慮されません）
- 借入返済額は内訳明細から取得します。明細がない場合は短期÷12+長期÷60で粗く推定します
- AIアドバイスは参考情報です。最終判断は税理士・経営者にご確認ください
- 入力PDFに個人情報が含まれる場合、扱いに十分ご注意ください（Claude APIに送信されます）
