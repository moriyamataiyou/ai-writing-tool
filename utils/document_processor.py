import io
import logging
import streamlit as st
import PyPDF2

logger = logging.getLogger(__name__)

MAX_CHARS = 50_000      # API へ送る最大文字数
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _read_pdf(uploaded_file) -> str:
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(uploaded_file.read()))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return "\n".join(pages)
    except Exception:
        logger.error("PDF read error", exc_info=True)
        st.error("PDF の読み込みに失敗しました。ファイルが壊れていないか確認してください。")
        return ""


def _read_txt(uploaded_file) -> str:
    raw = uploaded_file.read()
    for encoding in ("utf-8", "shift-jis", "cp932", "utf-16"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    st.error("テキストファイルのエンコーディングを判定できませんでした。UTF-8 で保存し直してください。")
    return ""


def _read_docx(uploaded_file) -> str:
    try:
        import docx  # python-docx
        doc = docx.Document(io.BytesIO(uploaded_file.read()))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except ImportError:
        st.error("DOCX の読み込みには python-docx が必要です: pip install python-docx")
        return ""
    except Exception:
        logger.error("DOCX read error", exc_info=True)
        st.error("DOCX の読み込みに失敗しました。ファイルが壊れていないか確認してください。")
        return ""


def extract_text(uploaded_file) -> str:
    if uploaded_file is None:
        return ""

    if hasattr(uploaded_file, "size") and uploaded_file.size > MAX_FILE_SIZE:
        st.error(f"ファイルが大きすぎます（上限: {MAX_FILE_SIZE // 1024 // 1024} MB）")
        return ""

    mime = uploaded_file.type
    name = uploaded_file.name.lower()

    if mime == "application/pdf" or name.endswith(".pdf"):
        text = _read_pdf(uploaded_file)
    elif mime in ("text/plain", "text/markdown") or name.endswith((".txt", ".md")):
        text = _read_txt(uploaded_file)
    elif name.endswith(".docx"):
        text = _read_docx(uploaded_file)
    else:
        st.warning("未対応のファイル形式です。PDF / TXT / DOCX をアップロードしてください。")
        return ""

    if len(text) > MAX_CHARS:
        st.info(f"文章が長いため、先頭 {MAX_CHARS:,} 文字を使用します（全体: {len(text):,} 文字）")
        return text[:MAX_CHARS]
    return text
