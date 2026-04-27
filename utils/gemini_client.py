import logging
from typing import Optional
import google.generativeai as genai
import streamlit as st

logger = logging.getLogger(__name__)


def generate_text(
    prompt: str,
    model_name: str = "gemini-2.0-flash",
    system_instruction: Optional[str] = None,
    temperature: float = 0.75,
) -> str:
    try:
        config = genai.GenerationConfig(temperature=temperature, max_output_tokens=8192)
        kwargs: dict = {"model_name": model_name, "generation_config": config}
        if system_instruction:
            kwargs["system_instruction"] = system_instruction
        model = genai.GenerativeModel(**kwargs)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error("Gemini generate_text error", exc_info=True)
        st.error("テキストの生成中にエラーが発生しました。しばらくしてから再試行してください。")
        return ""


def chat_with_history(
    question: str,
    document: str,
    history: list[dict],
    model_name: str = "gemini-2.0-flash",
) -> str:
    try:
        system_instruction = (
            "あなたは大学生の学習をサポートするAIアシスタントです。\n"
            "以下の資料を参照して質問に丁寧かつ正確に答えてください。\n"
            "資料に記載がない場合は「資料には記載されていません」と伝えた上で"
            "一般知識から補足してください。\n\n"
            f"【参照資料】\n{document}"
        )
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_instruction,
        )
        # Gemini uses "user" / "model" roles
        gemini_history = [
            {"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]}
            for m in history
        ]
        chat = model.start_chat(history=gemini_history)
        response = chat.send_message(question)
        return response.text
    except Exception as e:
        logger.error("Gemini chat_with_history error", exc_info=True)
        st.error("回答の生成中にエラーが発生しました。しばらくしてから再試行してください。")
        return ""
