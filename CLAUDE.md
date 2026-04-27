# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 起動・開発コマンド

```bash
# 依存関係インストール
pip install -r requirements.txt

# アプリ起動
streamlit run app.py

# ポート指定して起動
streamlit run app.py --server.port 8502
```

APIキーは `.env` ファイル（`.env.example` を参照）か、サイドバーの入力欄から設定する。

## アーキテクチャ

### 全体構成

```
app.py                    ← Streamlit シングルページアプリ（全 UI + プロンプト組み立て）
utils/
  gemini_client.py        ← Gemini API 呼び出し（generate_text / chat_with_history）
  document_processor.py  ← ファイル読み込み（PDF / TXT / DOCX）
```

`app.py` がすべての UI とプロンプト文字列を持つ。ビジネスロジックは `utils/` に分離されている。

### データフロー

1. ユーザーがファイルをアップロードまたはテキストを貼り付け
2. `document_processor.extract_text()` でテキスト抽出（上限 50,000 文字で切り捨て）
3. プロンプトを `app.py` 内で組み立て
4. `gemini_client.generate_text()` または `chat_with_history()` に渡す
5. 結果を `show_output()` ヘルパーで `st.code(text, language=None)` に表示（コピーボタン付き）

### セッション状態

Q&A タブのみ `st.session_state` で状態を保持する。

| キー | 型 | 用途 |
|---|---|---|
| `api_ok` | bool | API キー設定済みフラグ |
| `model` | str | 選択中のモデル ID |
| `qa_doc` | str | Q&A タブで設定した資料テキスト |
| `qa_history` | list[dict] | Q&A の会話履歴（role: "user"\|"assistant"） |

### Gemini ロール変換

`st.session_state` の会話履歴は `role: "user"/"assistant"` で保持する。`chat_with_history()` が Gemini API へ渡す際に `"assistant" → "model"` へ変換する。

### temperature 設定の使い分け

| 機能 | temperature | 理由 |
|---|---|---|
| 翻訳・文章校正 | 0.3 | 再現性・正確性優先 |
| 要約・文体変換 | 0.5 | バランス |
| アウトライン | 0.6 | 構造の一貫性を保ちつつ多様性 |
| レポート・感想生成 | 0.75（デフォルト） | 創造性優先 |

## 新機能を追加するときのパターン

1. `st.tabs([...])` のリストに新しいタブ名を追加
2. 対応する `with tab_xxx:` ブロックを `app.py` 末尾に追加
3. 設定列（左）と結果列（右）の 2 カラム構成を踏襲する
4. 生成ボタン押下時に `api_ok()` チェック → 入力バリデーション → プロンプト組み立て → `generate_text()` 呼び出し → `show_output()` の順で実装
5. 各 Streamlit ウィジェットに一意の `key=` を付ける（同名ウィジェットが複数タブにある場合は必須）
