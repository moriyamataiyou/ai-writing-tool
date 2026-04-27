# Streamlit × Gemini で作る AI ライティングツール — app.py 完全解説

> このブログ記事は `app.py` のコードを読んで「何をしているか・なぜそう書いたか」を理解するための解説です。

---

## 目次

1. [全体像を把握する](#1-全体像を把握する)
2. [ページ設定と CSS カスタマイズ](#2-ページ設定と-css-カスタマイズ)
3. [サイドバー — API キーとモデル選択](#3-サイドバー--api-キーとモデル選択)
4. [3 つのヘルパー関数](#4-3-つのヘルパー関数)
5. [7 タブの構造パターン](#5-7-タブの構造パターン)
6. [TAB 1: 資料 Q&A（チャット機能）](#6-tab-1-資料-qa-チャット機能)
7. [TAB 2: レポート・感想文生成](#7-tab-2-レポート感想文生成)
8. [TAB 3〜7 の共通パターン](#8-tab-37-の共通パターン)
9. [コード全体のデータフロー図](#9-コード全体のデータフロー図)
10. [まとめ](#10-まとめ)

---

## 1. 全体像を把握する

`app.py` は **Streamlit のシングルページアプリ**です。
ファイルは上から下へ 1 度だけ実行されます。
ユーザーがボタンを押したり入力するたびに、Streamlit がスクリプト全体を再実行します。

```
app.py（約 780 行）
│
├── インポート & 環境変数の読み込み
├── ページ設定・CSS
├── サイドバー（API キー入力 / モデル選択）
├── ヘルパー関数 3 つ
├── ページヘッダー
└── タブ 7 つ（with tab_xxx: ブロック）
```

`app.py` は UI とプロンプトの組み立てを担当し、
実際の API 呼び出しとファイル読み込みは `utils/` に委譲しています。

```python
from utils.document_processor import extract_text        # ファイル読み込み
from utils.gemini_client import generate_text, chat_with_history  # API呼び出し
```

---

## 2. ページ設定と CSS カスタマイズ

```python
st.set_page_config(
    page_title="AI ライティングツール",
    page_icon="✍️",
    layout="wide",                    # 画面幅いっぱいに広げる
    initial_sidebar_state="expanded", # サイドバーを最初から開いておく
)
```

`layout="wide"` を指定することで、後で使う 2 カラムレイアウトが画面幅を活かせるようになります。

続いて `st.markdown()` で独自 CSS を注入しています。

```python
st.markdown("""
<style>
    [data-testid="stSidebar"] { min-width: 260px; max-width: 320px; }
    .block-container { padding-top: 1.5rem; }
    .stTabs [data-baseweb="tab"] { font-size: 0.9rem; padding: 6px 14px; }
    .result-header { color: #444; font-size: 0.85rem; margin-bottom: 4px; }
    div[data-testid="stCodeBlock"] pre { max-height: 520px; overflow-y: auto; }
</style>
""", unsafe_allow_html=True)
```

| セレクタ | 効果 |
|---|---|
| `[data-testid="stSidebar"]` | サイドバーの幅を固定 |
| `.block-container` | メインエリア上部の余白を削減 |
| `.stTabs [data-baseweb="tab"]` | タブのフォントサイズ調整 |
| `div[data-testid="stCodeBlock"] pre` | 生成結果ボックスのスクロール高さ制限 |

> **ポイント:** Streamlit のコンポーネントは HTML の `data-testid` 属性を持っているので、
> それを CSS セレクタとして狙い撃ちできます。

---

## 3. サイドバー — API キーとモデル選択

```python
with st.sidebar:
    api_key = st.text_input(
        "Gemini API キー",
        value=os.getenv("GEMINI_API_KEY", ""),  # .env があれば自動入力
        type="password",                          # マスク表示
    )

    if api_key:
        genai.configure(api_key=api_key)      # Gemini SDK にキーを渡す
        st.session_state["api_ok"] = True
        st.success("✅ API 接続済み")
    else:
        st.session_state["api_ok"] = False
```

### なぜ `st.session_state` に保存するのか

Streamlit はボタンを押すたびにスクリプト全体を再実行します。
`st.session_state` はその再実行をまたいで値を保持できる**唯一の仕組み**です。

`api_ok` フラグをセッション状態に入れることで、
どのタブからでも「API キーが設定されているか」を確認できます。

### モデル選択

```python
MODEL_MAP = {
    "Gemini 2.0 Flash（推奨・高速）": "gemini-2.0-flash",
    "Gemini 1.5 Pro（高精度）":       "gemini-1.5-pro",
    "Gemini 1.5 Flash（超高速）":     "gemini-1.5-flash",
}
label = st.selectbox("🤖 モデル", list(MODEL_MAP.keys()))
st.session_state["model"] = MODEL_MAP[label]
```

ユーザーには日本語のラベルを見せ、内部では API に渡すモデル ID だけを保持します。
辞書でラベル → ID のマッピングを管理するパターンはこのアプリ全体で多用されています。

---

## 4. 3 つのヘルパー関数

アプリ全体で繰り返し使う処理を 3 つの小さな関数にまとめています。

### `api_ok()` — API チェックゲート

```python
def api_ok() -> bool:
    if not st.session_state.get("api_ok"):
        st.warning("⚠️ サイドバーで Gemini API キーを設定してください。")
        return False
    return True
```

各タブの生成ボタン処理の先頭で必ず呼び出します。
`False` が返ったら処理を打ち切るゲートとして機能します。

```python
if gen_btn:
    if not api_ok():   # ← ここで止める
        pass
    elif not report_src.strip():
        st.warning("入力してください")
    else:
        # ← ここからが本処理
```

### `model()` — モデル ID の取得

```python
def model() -> str:
    return st.session_state.get("model", "gemini-2.0-flash")
```

デフォルト値を持たせているので、初回実行時（セッション状態が空）でも安全に動きます。

### `show_output()` — 結果の統一表示

```python
def show_output(text: str, label: str = "生成結果"):
    st.markdown(f'<p class="result-header">📄 {label}</p>', unsafe_allow_html=True)
    st.code(text, language=None)   # コピーボタン付きのブロック
    st.caption(f"文字数: {len(text):,} 字")
```

`st.code(text, language=None)` が重要です。
`language=None` にすることでシンタックスハイライトなしの**コピーボタン付きブロック**になります。
生成した文章をそのままコピーして使いたい用途に最適です。

---

## 5. 7 タブの構造パターン

```python
(
    tab_qa, tab_report, tab_summary,
    tab_proof, tab_outline, tab_style, tab_translate,
) = st.tabs([
    "📄 資料Q&A", "✍️ レポート・感想", "📝 要約",
    "🔍 文章校正", "📋 アウトライン", "🔄 文体変換", "🌐 翻訳",
])
```

`st.tabs()` はタブオブジェクトのリストを返すので、
タプルアンパックで 7 変数に一気に受け取っています。

各タブは `with tab_xxx:` ブロックの中に UI を書きます。
ほぼすべてのタブが同じ構造を持っています。

```
with tab_xxx:
    st.header(...)
    st.caption(...)

    col_左, col_右 = st.columns([比率, 比率], gap="large")

    with col_左:        # 設定パネル
        # ウィジェット（selectbox, text_area など）
        実行ボタン = st.button("...", type="primary")

    with col_右:        # 結果パネル
        if 実行ボタン:
            if not api_ok(): pass
            elif not 入力.strip(): st.warning(...)
            else:
                prompt = f"""..."""   # プロンプト組み立て
                with st.spinner("..."):
                    result = generate_text(prompt, model_name=model())
                if result:
                    show_output(result, "ラベル")
        else:
            st.info("使い方ガイド")
```

---

## 6. TAB 1: 資料 Q&A（チャット機能）

Q&A タブだけが他と違う仕組みを使っています。
**会話の継続（チャット）** を実現するためです。

### セッション状態の初期化

```python
if "qa_history" not in st.session_state:
    st.session_state.qa_history = []
if "qa_doc" not in st.session_state:
    st.session_state.qa_doc = ""
```

`if "key" not in st.session_state` というパターンが重要です。
これを `st.session_state["key"] = []` と書いてしまうと、
ボタンを押すたびにリセットされてしまいます。

### チャット表示と入力

```python
# ① 過去の履歴を上から表示
for msg in st.session_state.qa_history:
    with st.chat_message(msg["role"]):  # "user" or "assistant"
        st.write(msg["content"])

# ② 新しい入力を受け付ける（画面下部に固定される）
if question := st.chat_input("質問してください…"):
    # ③ ユーザーメッセージをその場で表示
    with st.chat_message("user"):
        st.write(question)

    # ④ API を呼んでアシスタントの返答を表示
    with st.chat_message("assistant"):
        with st.spinner("回答を生成中…"):
            answer = chat_with_history(
                question=question,
                document=st.session_state.qa_doc,
                history=st.session_state.qa_history,  # ← 履歴を渡す
                model_name=model(),
            )
        if answer:
            st.write(answer)

    # ⑤ セッション状態の履歴に追加（次回のスクリプト実行時に①で表示される）
    if answer:
        st.session_state.qa_history.append({"role": "user",      "content": question})
        st.session_state.qa_history.append({"role": "assistant", "content": answer})
```

### なぜ `st.rerun()` を呼ばないのか

`st.chat_input` が入力を受け取ると Streamlit が自動で再実行します。
その再実行中に ③④ で入力内容を直接表示し、⑤ で履歴に追加します。
次回の再実行では ① のループが更新された履歴を表示してくれるので、
明示的な `st.rerun()` は不要です。

### ロール名の変換（app.py ↔ Gemini API）

| 場所 | ロール名 |
|---|---|
| `st.session_state.qa_history` | `"user"` / `"assistant"` |
| Gemini API が要求する形式 | `"user"` / `"model"` |

この変換は `utils/gemini_client.py` の `chat_with_history()` の中でやっています。
`app.py` 側は `"assistant"` で統一して、変換処理を外に隠しています。

---

## 7. TAB 2: レポート・感想文生成

このタブが最もオプションが多い機能です。

### 動的な入力 UI

```python
input_type = st.radio("入力の種類", ["📄 資料・記事の本文", "💡 テーマ・題目のみ"])

if input_type == "📄 資料・記事の本文":
    report_src = st.text_area("資料を貼り付け", height=220, key="report_src")
else:
    report_src = st.text_input("テーマ・題目", key="report_topic")
```

`st.radio` の選択値によって表示するウィジェットを切り替えています。
どちらのウィジェットの値も同じ変数 `report_src` に入るので、
後のプロンプト組み立てでは分岐が不要になります。

### f-string でプロンプトを組み立て

```python
prompt = f"""あなたは大学生のレポート・感想文作成を支援するAIです。

【入力内容 / テーマ】
{report_src}

【作成条件】
- 種類: {doc_type}
- 文字数: 約{target_len}字（±10%）
- 文体: {style}
...
"""
```

Python の f-string（`f"""..."""`）でウィジェットの値をそのままプロンプトに埋め込んでいます。
ユーザーが画面で選んだ設定が、そのまま AI への指示文になる仕組みです。

### 文字数のプリセット管理

```python
LENGTH_MAP = {
    "400字（短め）": 400, "800字": 800, "1200字": 1200,
    "2000字": 2000, "4000字": 4000,
}
if length_preset == "カスタム":
    target_len = st.number_input("文字数", min_value=100, max_value=10000)
else:
    target_len = LENGTH_MAP[length_preset]
```

選択肢 → 数値 のマッピングを辞書で管理し、
「カスタム」選択時だけ数値入力欄を表示しています。

---

## 8. TAB 3〜7 の共通パターン

残り 5 タブはすべて「**ワンショット生成**」です。
チャット形式ではなく、入力→ボタン→結果の 1 往復のみです。

各タブのポイントだけ抜粋します。

### TAB 3: 要約 — `select_slider` で直感的な長さ指定

```python
sum_len = st.select_slider(
    "要約の長さ",
    options=["超短め（〜3行）", "短め（5〜7行）", "中程度", "詳しめ", "長め"],
    value="中程度",
)
```

数値スライダーではなく文字列のスライダーにすることで、
ユーザーが「何字にするか」を考えなくてよくなっています。

### TAB 4: 文章校正 — temperature を低く設定

```python
result = generate_text(prompt, model_name=model(), temperature=0.3)
```

校正・翻訳のように「正確さ」が求められる機能は `temperature=0.3` にしています。
temperature が低いほど AI の出力がブレにくくなります。
逆にレポート生成はデフォルトの `0.75` で創造性を持たせています。

### TAB 5: アウトライン — 構造化出力をプロンプトで指示

```python
prompt = f"""...
# アウトライン：「{topic}」

## Ⅰ. 序論（目安：○○字）
### 1.1 問題の背景・導入
...
"""
```

出力してほしい Markdown の**見出し構造をプロンプトに直接書いています**。
AI はこのテンプレートを参考にして構造化された出力を返してくれます。

### TAB 6: 文体変換 — 変換の種類を 8 種類用意

```python
conversion = st.selectbox("🔄 変換の種類", [
    "です・ます体 → だ・である体（学術体）",
    "わかりやすく書き直す（リライト）",
    "より簡潔に（要点を残して短縮）",
    ...
])
```

選択した文字列がそのままプロンプトに入ります。

```python
prompt = f"""以下の文章に「{conversion}」の変換を行ってください。"""
```

### TAB 7: 翻訳 — 方向によって src/tgt を切り替え

```python
src, tgt = ("日本語", "英語") if "日本語 →" in direction else ("英語", "日本語")
```

`in` でラジオボタンの選択値を部分一致チェックして変数を振り分けています。

---

## 9. コード全体のデータフロー図

```
ユーザー操作（ボタン押下・入力）
        │
        ▼
  Streamlit が app.py を再実行
        │
        ├─ サイドバー処理
        │     └─ genai.configure(api_key) → st.session_state["api_ok"] = True
        │
        ├─ タブの with ブロックを実行
        │     ├─ ウィジェットの現在値を読み取る
        │     ├─ ボタンが押されているか確認
        │     │
        │     └─ [ボタンが押されていれば]
        │           ├─ api_ok() チェック
        │           ├─ 入力バリデーション
        │           ├─ f-string でプロンプト組み立て
        │           ├─ generate_text() または chat_with_history() を呼び出し
        │           │       └─ utils/gemini_client.py が Gemini API へリクエスト
        │           └─ show_output() で st.code() に結果表示
        │
        └─ セッション状態の更新（Q&A タブのみ qa_history に追加）
```

---

## 10. まとめ

| 要素 | 使っているもの | 役割 |
|---|---|---|
| UI フレームワーク | Streamlit | ウィジェット・レイアウト・状態管理 |
| AI API | Google Gemini (`google-generativeai`) | テキスト生成・チャット |
| 状態管理 | `st.session_state` | タブをまたいだデータ保持 |
| 設定管理 | `.env` + `python-dotenv` | API キーの環境変数読み込み |
| ファイル処理 | PyPDF2 / python-docx | PDF・DOCX のテキスト抽出 |

このアプリの核心は「**ユーザーが画面で選んだ設定を f-string でプロンプトに変換し、Gemini API に投げる**」という非常にシンプルなパターンです。
複雑に見える 780 行も、この 1 パターンを 7 タブ分繰り返しているだけです。

新しい機能を追加したいときは、既存のタブを 1 つコピーしてプロンプト文字列と設定ウィジェットを書き換えるだけで実現できます。
