import html
import os
import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv

from utils.document_processor import extract_text
from utils.gemini_client import generate_text, chat_with_history

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# ページ設定
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI ライティングツール",
    page_icon="✍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    [data-testid="stSidebar"] { min-width: 260px; max-width: 320px; }
    .block-container { padding-top: 1.5rem; }
    .stTabs [data-baseweb="tab"] { font-size: 0.9rem; padding: 6px 14px; }
    .result-header { color: #444; font-size: 0.85rem; margin-bottom: 4px; }
    div[data-testid="stCodeBlock"] pre { max-height: 520px; overflow-y: auto; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# サイドバー
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("✍️ AI Writing Tool")
    st.caption("大学課題・ライティング全般サポート")
    st.divider()

    st.subheader("⚙️ 設定")
    api_key = st.text_input(
        "Gemini API キー",
        value=os.getenv("GEMINI_API_KEY", ""),
        type="password",
        help="Google AI Studio (aistudio.google.com) で無料取得できます",
    )

    if api_key:
        genai.configure(api_key=api_key)
        st.session_state["api_ok"] = True
        st.success("✅ API 接続済み")
    else:
        st.session_state["api_ok"] = False
        st.info("🔑 API キーを入力してください\nhttps://aistudio.google.com")

    st.divider()

    MODEL_MAP = {
        "Gemini 2.0 Flash（推奨・高速）": "gemini-2.0-flash",
        "Gemini 1.5 Pro（高精度）": "gemini-1.5-pro",
        "Gemini 1.5 Flash（超高速）": "gemini-1.5-flash",
    }
    label = st.selectbox("🤖 モデル", list(MODEL_MAP.keys()))
    st.session_state["model"] = MODEL_MAP[label]

    st.divider()
    st.markdown("""
**機能一覧**
- 📄 資料Q&A — 論文・記事に質問
- ✍️ レポート・感想生成
- 📝 要約・要点整理
- 🔍 文章校正・添削
- 📋 アウトライン作成
- 🔄 文体変換・リライト
- 🌐 翻訳（日↔英）
""")
    st.divider()
    st.caption("個人利用向け | 認証なし")
    st.caption("Powered by Google Gemini")


# ─────────────────────────────────────────────────────────────────────────────
# ヘルパー
# ─────────────────────────────────────────────────────────────────────────────
def api_ok() -> bool:
    if not st.session_state.get("api_ok"):
        st.warning("⚠️ サイドバーで Gemini API キーを設定してください。")
        return False
    return True


def model() -> str:
    return st.session_state.get("model", "gemini-2.0-flash")


MAX_INPUT_CHARS = 30_000  # テキストエリアからの入力上限

def show_output(text: str, label: str = "生成結果"):
    """結果をコピーボタン付きのコードブロックで表示する。"""
    safe_label = html.escape(label)
    st.markdown(f'<p class="result-header">📄 {safe_label}</p>', unsafe_allow_html=True)
    st.code(text, language=None)
    st.caption(f"文字数: {len(text):,} 字")


# ─────────────────────────────────────────────────────────────────────────────
# ヘッダー
# ─────────────────────────────────────────────────────────────────────────────
st.title("✍️ AI ライティングツール")
st.caption("大学レポート・課題作成を AI がトータルサポート")
st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# タブ定義
# ─────────────────────────────────────────────────────────────────────────────
(
    tab_qa,
    tab_report,
    tab_summary,
    tab_proof,
    tab_outline,
    tab_style,
    tab_translate,
) = st.tabs([
    "📄 資料Q&A",
    "✍️ レポート・感想",
    "📝 要約",
    "🔍 文章校正",
    "📋 アウトライン",
    "🔄 文体変換",
    "🌐 翻訳",
])


# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — 資料 Q&A
# ═════════════════════════════════════════════════════════════════════════════
with tab_qa:
    st.header("📄 資料・論文 Q&A")
    st.caption("資料をアップロードまたは貼り付けて、内容について自由に質問できます。")

    if "qa_history" not in st.session_state:
        st.session_state.qa_history = []
    if "qa_doc" not in st.session_state:
        st.session_state.qa_doc = ""

    col_doc, col_chat = st.columns([1, 2], gap="large")

    with col_doc:
        st.subheader("📁 資料の設定")

        input_mode = st.radio(
            "入力方法",
            ["📎 ファイルアップロード", "📝 テキスト貼り付け"],
            horizontal=True,
        )

        if input_mode == "📎 ファイルアップロード":
            uploaded = st.file_uploader(
                "PDF / TXT / DOCX",
                type=["pdf", "txt", "docx"],
            )
            if uploaded:
                with st.spinner("読み込み中..."):
                    doc_text = extract_text(uploaded)
                if doc_text:
                    st.session_state.qa_doc = doc_text
                    st.success(f"✅ {uploaded.name}  ({len(doc_text):,} 文字)")
                    with st.expander("プレビュー（先頭 600 文字）"):
                        st.text(doc_text[:600] + ("…" if len(doc_text) > 600 else ""))
        else:
            pasted = st.text_area(
                "テキストを貼り付け",
                height=220,
                placeholder="資料・記事の本文を貼り付けてください…",
                key="qa_paste",
                max_chars=MAX_INPUT_CHARS,
            )
            if st.button("📌 資料として設定", key="qa_set"):
                if pasted.strip():
                    st.session_state.qa_doc = pasted
                    st.success(f"✅ 設定済み ({len(pasted):,} 文字)")
                else:
                    st.warning("テキストを入力してください")

        if st.session_state.qa_doc:
            st.info(f"📄 資料設定済み: {len(st.session_state.qa_doc):,} 文字")

        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🗑️ 会話クリア", use_container_width=True):
                st.session_state.qa_history = []
                st.rerun()
        with c2:
            if st.button("📄 資料クリア", use_container_width=True):
                st.session_state.qa_doc = ""
                st.session_state.qa_history = []
                st.rerun()

    with col_chat:
        st.subheader("💬 会話")

        if not st.session_state.qa_doc:
            st.info("👈 左側で資料を設定してから質問してください")

        # 過去の会話を表示
        for msg in st.session_state.qa_history:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        # 入力受付
        if question := st.chat_input("資料について質問してください…"):
            if not api_ok():
                pass
            elif not st.session_state.qa_doc:
                st.warning("先に資料を設定してください")
            else:
                with st.chat_message("user"):
                    st.write(question)
                with st.chat_message("assistant"):
                    with st.spinner("回答を生成中…"):
                        answer = chat_with_history(
                            question=question,
                            document=st.session_state.qa_doc,
                            history=st.session_state.qa_history,
                            model_name=model(),
                        )
                    if answer:
                        st.write(answer)
                if answer:
                    st.session_state.qa_history.append({"role": "user", "content": question})
                    st.session_state.qa_history.append({"role": "assistant", "content": answer})


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — レポート・感想生成
# ═════════════════════════════════════════════════════════════════════════════
with tab_report:
    st.header("✍️ レポート・感想文生成")
    st.caption("資料やテーマを元に、大学生レベルのレポート・感想文を生成します。")

    col_r1, col_r2 = st.columns([1, 2], gap="large")

    with col_r1:
        st.subheader("⚙️ 設定")

        doc_type = st.selectbox(
            "📄 種類",
            ["感想文", "レポート", "小論文", "論考・考察", "課題レポート"],
        )

        length_preset = st.selectbox(
            "📏 文字数",
            ["400字（短め）", "800字", "1200字", "2000字", "4000字", "カスタム"],
            index=2,
        )
        LENGTH_MAP = {
            "400字（短め）": 400, "800字": 800, "1200字": 1200,
            "2000字": 2000, "4000字": 4000,
        }
        if length_preset == "カスタム":
            target_len = st.number_input("文字数", min_value=100, max_value=10000, value=1000, step=100)
        else:
            target_len = LENGTH_MAP[length_preset]

        style = st.selectbox(
            "✏️ 文体",
            ["です・ます体", "だ・である体（学術体）"],
        )

        st.divider()

        input_type = st.radio(
            "入力の種類",
            ["📄 資料・記事の本文", "💡 テーマ・題目のみ"],
            horizontal=True,
        )
        if input_type == "📄 資料・記事の本文":
            report_src = st.text_area(
                "資料・記事の本文を貼り付け",
                height=220,
                placeholder="資料の本文を貼り付けてください…",
                key="report_src",
                max_chars=MAX_INPUT_CHARS,
            )
        else:
            report_src = st.text_input(
                "テーマ・題目",
                placeholder="例：AIの発展と社会への影響",
                key="report_topic",
            )

        notes = st.text_area(
            "💡 追加指示（任意）",
            height=80,
            placeholder="例：第3章を中心に倫理的視点から論じてください",
            key="report_notes",
            max_chars=500,
        )

        gen_btn = st.button("🚀 生成する", type="primary", use_container_width=True, key="report_gen")

    with col_r2:
        st.subheader("📄 生成結果")

        if gen_btn:
            if not api_ok():
                pass
            elif not report_src.strip():
                st.warning("資料またはテーマを入力してください")
            else:
                prompt = f"""あなたは日本の大学で高評価を得てきた優秀な学生のライティングを支援する専門AIです。
以下の条件・要件に従い、教授が「よく考えられている」と評価する水準の{doc_type}を作成してください。

【入力内容 / テーマ — ここから】
{report_src}
【入力内容 / テーマ — ここまで】

【作成条件】
- 種類: {doc_type}
- 文字数: 約{target_len}字（±10%）
- 文体: {style}
- 追加指示: {notes if notes.strip() else "なし"}

【構成の要件】
- 序論: 問いを明確に設定し、本稿の目的・立場・構成を1〜2段落で示す
- 本論: 複数の視点から論拠を展開し、主張を段階的に積み上げる
- 結論: 序論で立てた問いへの答えを明示し、考察の意義と今後の課題を述べる

【論述の質に関する要件（ここが評価を左右する）】
- 「〜と思う」だけで終わらず、必ず「なぜなら〜」「その根拠として〜」と論証する
- 主張 → 根拠 → 具体例（事実・データ・事例）→ 考察 の流れを意識する
- 内容を表面的に要約するだけでなく、背景・意義・問題点・限界を分析する
- 複数の立場・観点を比較した上で、自分の立場を明確に述べる
- 一般論にとどまらず、具体的なケースや自分の経験・観察を織り交ぜる

【文章表現の要件】
- 一人称は「私」を使用
- 「〜と思われる」「〜と考えられる」「〜といえよう」など学術的な表現を使う
- 段落の冒頭文で段落全体の主張を明示する（トピックセンテンス）
- 接続詞（しかし・したがって・つまり・一方で）を効果的に使い論理の流れを明確にする

{doc_type}を作成してください："""

                with st.spinner(f"{doc_type}を生成中…"):
                    result = generate_text(prompt, model_name=model())
                if result:
                    st.success(f"✅ 生成完了")
                    show_output(result, doc_type)
                    with st.expander("📊 生成情報"):
                        st.write(f"- 生成文字数: **{len(result):,} 字**")
                        st.write(f"- 目標文字数: **{target_len:,} 字**")
                        diff = len(result) - target_len
                        st.write(f"- 差分: {'＋' if diff >= 0 else ''}{diff:,} 字")
        else:
            st.info("👈 左側で設定して「生成する」を押してください")
            st.markdown("""
**使い方**
1. 種類・文字数・文体を選択
2. 資料本文またはテーマを入力
3. 必要に応じて追加指示を記入
4. 「生成する」をクリック
5. 結果をコピーして使用
""")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 3 — 要約・要点整理
# ═════════════════════════════════════════════════════════════════════════════
with tab_summary:
    st.header("📝 要約・要点整理")
    st.caption("長文を素早く要約します。箇条書き・段落形式を選べます。")

    col_s1, col_s2 = st.columns([1, 1], gap="large")

    with col_s1:
        st.subheader("📥 入力")

        s_input_mode = st.radio(
            "入力方法",
            ["テキスト入力", "ファイルアップロード"],
            horizontal=True,
            key="sum_mode",
        )
        sum_text = ""
        if s_input_mode == "テキスト入力":
            sum_text = st.text_area(
                "要約する文章",
                height=280,
                placeholder="要約したい文章を貼り付けてください…",
                key="sum_input",
                max_chars=MAX_INPUT_CHARS,
            )
        else:
            s_file = st.file_uploader(
                "PDF / TXT / DOCX",
                type=["pdf", "txt", "docx"],
                key="sum_file",
            )
            if s_file:
                with st.spinner("読み込み中…"):
                    sum_text = extract_text(s_file)
                st.success(f"✅ {s_file.name}  ({len(sum_text):,} 文字)")

        st.divider()

        sum_format = st.radio(
            "出力形式",
            ["📋 箇条書き", "📄 段落形式", "📊 箇条書き＋段落"],
            horizontal=True,
        )

        sum_len = st.select_slider(
            "要約の長さ",
            options=["超短め（〜3行）", "短め（5〜7行）", "中程度", "詳しめ", "長め"],
            value="中程度",
        )

        focus = st.text_input(
            "🎯 重点ポイント（任意）",
            placeholder="例：経済的影響について重点的に",
            key="sum_focus",
        )

        sum_btn = st.button("📝 要約する", type="primary", use_container_width=True, key="sum_gen")

    with col_s2:
        st.subheader("📤 要約結果")

        if sum_btn:
            if not api_ok():
                pass
            elif not sum_text.strip():
                st.warning("テキストを入力してください")
            else:
                LEN_MAP = {
                    "超短め（〜3行）": "3行以内・約150字",
                    "短め（5〜7行）": "5〜7行・約300字",
                    "中程度": "10〜15行・約500字",
                    "詳しめ": "約800字",
                    "長め": "約1200字",
                }
                FORMAT_MAP = {
                    "📋 箇条書き": "箇条書き（・）形式で出力してください",
                    "📄 段落形式": "段落形式（連続した文章）で出力してください",
                    "📊 箇条書き＋段落": "まず段落形式で要約し、続けてキーポイントを箇条書きでまとめてください",
                }

                prompt = f"""以下の文章を要約してください。

【条件】
- 長さ: {LEN_MAP[sum_len]}
- 形式: {FORMAT_MAP[sum_format]}
- 重点: {focus if focus.strip() else "特になし"}

【原文 — ここから】
{sum_text}
【原文 — ここまで】

要約："""

                with st.spinner("要約中…"):
                    result = generate_text(prompt, model_name=model(), temperature=0.5)
                if result:
                    st.success("✅ 要約完了")
                    show_output(result, "要約")
                    st.caption(f"原文 {len(sum_text):,} 字 → 要約 {len(result):,} 字（約 {len(result)/max(len(sum_text),1)*100:.0f}%）")
        else:
            st.info("👈 文章を入力して「要約する」を押してください")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 4 — 文章校正・添削
# ═════════════════════════════════════════════════════════════════════════════
with tab_proof:
    st.header("🔍 文章校正・添削")
    st.caption("誤字脱字・文法ミス・不自然な表現を検出して修正案を提示します。")

    col_p1, col_p2 = st.columns([1, 1], gap="large")

    with col_p1:
        st.subheader("📥 校正する文章")

        proof_text = st.text_area(
            "文章を入力",
            height=320,
            placeholder="校正したい文章を貼り付けてください…",
            key="proof_input",
            max_chars=MAX_INPUT_CHARS,
        )

        st.divider()

        proof_level = st.select_slider(
            "校正の厳しさ",
            options=["軽め（誤字・脱字のみ）", "標準", "厳しめ（表現・構成も）"],
            value="標準",
        )
        purpose = st.selectbox(
            "文章の用途",
            ["大学レポート", "小論文・論文", "感想文", "メール・ビジネス文書", "その他"],
        )

        proof_btn = st.button("🔍 校正する", type="primary", use_container_width=True, key="proof_gen")

    with col_p2:
        st.subheader("📤 校正結果")

        if proof_btn:
            if not api_ok():
                pass
            elif not proof_text.strip():
                st.warning("文章を入力してください")
            else:
                LEVEL_MAP = {
                    "軽め（誤字・脱字のみ）": "誤字・脱字の修正のみ行い、表現や構成には触れないでください",
                    "標準": "誤字・脱字、文法ミス、不自然な表現を修正してください",
                    "厳しめ（表現・構成も）": "誤字・脱字・文法ミスに加え、表現の改善・論理構成の問題もすべて指摘・修正してください",
                }

                prompt = f"""以下の文章を{purpose}として校正してください。

【校正方針】
{LEVEL_MAP[proof_level]}

【原文 — ここから】
{proof_text}
【原文 — ここまで】

以下の形式で出力してください：

## ✅ 校正済み文章

（修正した文章全文をここに記載）

## 📋 主な修正点

（修正箇所と理由を箇条書きで記載。修正なければ「修正点はありませんでした。」と記載）"""

                with st.spinner("校正中…"):
                    result = generate_text(prompt, model_name=model(), temperature=0.3)
                if result:
                    st.success("✅ 校正完了")
                    show_output(result, "校正結果")
        else:
            st.info("👈 文章を入力して「校正する」を押してください")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 5 — アウトライン作成
# ═════════════════════════════════════════════════════════════════════════════
with tab_outline:
    st.header("📋 アウトライン・構成案作成")
    st.caption("レポートや論文の構成（アウトライン）を作成します。")

    col_o1, col_o2 = st.columns([1, 2], gap="large")

    with col_o1:
        st.subheader("⚙️ 設定")

        topic = st.text_input(
            "📌 テーマ・タイトル",
            placeholder="例：SNSが若者のメンタルヘルスに与える影響",
        )

        essay_type = st.selectbox(
            "📄 レポートの種類",
            ["大学レポート", "小論文", "卒業論文", "調査レポート", "実験レポート"],
        )

        o_len = st.selectbox(
            "📏 目標文字数",
            ["2000字", "4000字", "8000字", "12000字（卒論レベル）", "カスタム"],
            index=1,
        )
        if o_len == "カスタム":
            o_len_val = str(st.number_input("文字数", min_value=500, max_value=50000, value=3000))
        else:
            o_len_val = o_len

        sections = st.slider("本論のセクション数", min_value=2, max_value=6, value=3)

        o_ref = st.text_area(
            "📚 参考資料・メモ（任意）",
            height=110,
            placeholder="参考にしたい資料の内容やキーワードがあれば入力…",
            key="outline_ref",
        )

        outline_btn = st.button(
            "📋 アウトラインを作成",
            type="primary",
            use_container_width=True,
            key="outline_gen",
        )

    with col_o2:
        st.subheader("📄 アウトライン")

        if outline_btn:
            if not api_ok():
                pass
            elif not topic.strip():
                st.warning("テーマを入力してください")
            else:
                prompt = f"""「{topic}」についての{essay_type}の詳細なアウトラインを作成してください。

【条件】
- 目標文字数: {o_len_val}
- 本論セクション数: {sections}章
- 参考資料・メモ: {o_ref.strip() if o_ref.strip() else "なし"}

【出力形式】
各セクションに「主な論点（箇条書き）」「目安文字数」「使えそな根拠・事例のヒント」を含めてください。

# アウトライン：「{topic}」

## Ⅰ. 序論（目安：○○字）
### 1.1 問題の背景・導入
### 1.2 本稿の目的と問い
### 1.3 本稿の構成

## Ⅱ. 本論
（{sections}つのセクションに分け、各セクションに小見出しと要点を記載）

## Ⅲ. 結論（目安：○○字）
### まとめ
### 今後の課題・展望

## 参考文献（形式例）
"""

                with st.spinner("アウトラインを作成中…"):
                    result = generate_text(prompt, model_name=model(), temperature=0.6)
                if result:
                    st.success("✅ アウトライン作成完了")
                    show_output(result, "アウトライン")
        else:
            st.info("👈 テーマを入力して「アウトラインを作成」を押してください")
            st.markdown("""
**作れるもの**
- 大学レポートの構成案
- 卒業論文のアウトライン
- 小論文の骨子
- 各セクションの要点・文字数配分
""")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 6 — 文体変換・リライト
# ═════════════════════════════════════════════════════════════════════════════
with tab_style:
    st.header("🔄 文体変換・リライト")
    st.caption("文章の文体を変換したり、わかりやすくリライトします。")

    col_st1, col_st2 = st.columns([1, 1], gap="large")

    with col_st1:
        st.subheader("📥 入力")

        style_text = st.text_area(
            "変換する文章",
            height=300,
            placeholder="変換したい文章を入力してください…",
            key="style_input",
            max_chars=MAX_INPUT_CHARS,
        )

        st.divider()

        conversion = st.selectbox(
            "🔄 変換の種類",
            [
                "です・ます体 → だ・である体（学術体）",
                "だ・である体 → です・ます体",
                "口語体・話し言葉 → 文語体（フォーマル）",
                "文語体 → 口語体（カジュアル）",
                "わかりやすく書き直す（リライト）",
                "より簡潔に（要点を残して短縮）",
                "より詳しく（肉付け・補足追加）",
                "英語的・硬い表現 → 自然な日本語",
            ],
        )

        style_notes = st.text_input(
            "📝 追加指示（任意）",
            placeholder="例：専門用語はそのまま残してください",
            key="style_notes",
        )

        style_btn = st.button("🔄 変換する", type="primary", use_container_width=True, key="style_gen")

    with col_st2:
        st.subheader("📤 変換結果")

        if style_btn:
            if not api_ok():
                pass
            elif not style_text.strip():
                st.warning("文章を入力してください")
            else:
                prompt = f"""以下の文章に「{conversion}」の変換を行ってください。

【注意】
- 内容・意味はそのまま保持する
- 指定された文体・スタイルに変換する
- 追加指示: {style_notes.strip() if style_notes.strip() else "なし"}

【原文 — ここから】
{style_text}
【原文 — ここまで】

【変換後の文章のみを出力してください（説明・補足は不要）】"""

                with st.spinner("変換中…"):
                    result = generate_text(prompt, model_name=model(), temperature=0.5)
                if result:
                    st.success("✅ 変換完了")
                    show_output(result, "変換後")
                    st.caption(f"原文 {len(style_text):,} 字 → 変換後 {len(result):,} 字")
        else:
            st.info("👈 文章を入力して「変換する」を押してください")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 7 — 翻訳（日↔英）
# ═════════════════════════════════════════════════════════════════════════════
with tab_translate:
    st.header("🌐 翻訳（日本語 ↔ 英語）")
    st.caption("学術論文・レポートにも対応した高品質な翻訳を行います。")

    col_t1, col_t2 = st.columns([1, 1], gap="large")

    with col_t1:
        st.subheader("📥 翻訳元")

        direction = st.radio(
            "翻訳の方向",
            ["🇯🇵 日本語 → 🇺🇸 英語", "🇺🇸 英語 → 🇯🇵 日本語"],
            horizontal=True,
        )

        trans_text = st.text_area(
            "翻訳する文章",
            height=280,
            placeholder="翻訳したい文章を入力してください…",
            key="trans_input",
            max_chars=MAX_INPUT_CHARS,
        )

        st.divider()

        trans_style = st.selectbox(
            "✏️ 翻訳スタイル",
            ["標準（自然な翻訳）", "学術的（論文・レポート向け）", "平易（わかりやすく）", "直訳"],
        )

        trans_field = st.selectbox(
            "🎓 専門分野（任意）",
            ["指定なし", "人文・社会科学", "理工学", "医学・生命科学", "経済・経営", "法学", "教育学"],
        )

        trans_btn = st.button("🌐 翻訳する", type="primary", use_container_width=True, key="trans_gen")

    with col_t2:
        st.subheader("📤 翻訳結果")

        if trans_btn:
            if not api_ok():
                pass
            elif not trans_text.strip():
                st.warning("文章を入力してください")
            else:
                src, tgt = ("日本語", "英語") if "日本語 →" in direction else ("英語", "日本語")

                STYLE_MAP = {
                    "標準（自然な翻訳）": "自然で読みやすい翻訳",
                    "学術的（論文・レポート向け）": "学術論文で使われる正式な表現",
                    "平易（わかりやすく）": "できるだけ平易でわかりやすい表現",
                    "直訳": "原文にできるだけ忠実な直訳",
                }
                field_note = f"（専門分野: {trans_field}）" if trans_field != "指定なし" else ""

                prompt = f"""以下の{src}を{tgt}に翻訳してください。

【スタイル】{STYLE_MAP[trans_style]}{field_note}
【注意】専門用語を適切に訳し、原文の意味を正確に伝えてください。

【原文（{src}）— ここから】
{trans_text}
【原文（{src}）— ここまで】

【翻訳（{tgt}）— 翻訳文のみを出力してください】"""

                with st.spinner("翻訳中…"):
                    result = generate_text(prompt, model_name=model(), temperature=0.3)
                if result:
                    st.success("✅ 翻訳完了")
                    show_output(result, f"翻訳結果（{tgt}）")
                    st.caption(f"原文 {len(trans_text):,} 字 → 翻訳 {len(result):,} 字")
        else:
            st.info("👈 文章を入力して「翻訳する」を押してください")
