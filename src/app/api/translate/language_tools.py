import re
from typing import Any, Dict, Optional

from langdetect import detect, detect_langs

from translation_config import (
    ASSISTANT_RESPONSES,
    DOMAIN_KEYWORDS,
    LANG_MAP,
    LANG_NAMES,
    OFF_TOPIC_KEYWORDS,
)


def build_assistant_reply(message: str) -> Optional[str]:
    lower = message.lower()

    # Treat greeting as a standalone small-talk turn only.
    normalized = re.sub(r"[\s,，.。!?！？~～:：;；\-_/\\]+", "", lower)
    greeting_only = {
        "hi",
        "hello",
        "hey",
        "howareyou",
        "你好",
        "您好",
        "你好吗",
        "你還好嗎",
        "你还好吗",
    }
    if normalized in greeting_only:
        return ASSISTANT_RESPONSES["greeting"]
    if any(k in lower for k in ["i like you", "i love you", "我喜欢你", "我愛你", "我爱你", "saya suka kamu", "aku suka kamu"]):
        return ASSISTANT_RESPONSES["affection"]
    if any(k in lower for k in ["grant", "fund", "funding", "基金", "资助", "補助金", "拨款", "撥款", "申请基金", "申請基金"]):
        return ASSISTANT_RESPONSES["grant"]
    return None


def resolve_response_lang(detected_lang: str, requested_lang: str) -> str:
    """Prefer latest input language, then explicit request, then English fallback."""
    if detected_lang in LANG_NAMES:
        return detected_lang

    requested = (requested_lang or "").strip().lower()
    if requested in LANG_NAMES:
        return requested

    return "en"


def is_off_topic_message(message: str) -> bool:
    lower = message.lower().strip()
    if not lower:
        return False

    if any(k in lower for k in DOMAIN_KEYWORDS):
        return False

    if any(k in lower for k in OFF_TOPIC_KEYWORDS):
        return True

    token_count = len(re.findall(r"\w+", lower, flags=re.UNICODE))
    has_cjk = bool(re.search(r"[\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF]", lower))

    # Keep this short-message off-topic heuristic for latin-script chatty prompts only.
    if token_count <= 4 and not has_cjk and not any(k in lower for k in DOMAIN_KEYWORDS):
        return True

    return False


def infer_lang_by_script(text: str) -> Optional[str]:
    """Infer language from script for short messages where langdetect may be unstable."""
    if re.search(r"[\uAC00-\uD7AF]", text):
        return "ko"
    if re.search(r"[\u3040-\u30FF]", text):
        return "ja"
    if re.search(r"[\u0E00-\u0E7F]", text):
        return "th"
    if re.search(r"[\u1000-\u109F]", text):
        return "my"
    if re.search(r"[\u0E80-\u0EFF]", text):
        return "lo"
    if re.search(r"[\u1780-\u17FF]", text):
        return "km"
    if re.search(r"[\u4E00-\u9FFF]", text):
        return "zh"
    return None


class LanguageDetector:
    """Auto-detect language from text, with SEA-aware fallback."""

    @staticmethod
    def detect(text: str) -> str:
        """Returns normalised language code e.g. 'ms', 'th', 'en'."""
        script_lang = infer_lang_by_script(text)
        if script_lang is not None:
            return script_lang
        try:
            raw = detect(text)
            return LANG_MAP.get(raw, raw)
        except Exception:
            return "en"

    @staticmethod
    def detect_with_confidence(text: str) -> Dict[str, Any]:
        script_lang = infer_lang_by_script(text)
        if script_lang is not None:
            return {
                "lang": script_lang,
                "confidence": 0.99,
                "name": LANG_NAMES.get(script_lang, script_lang),
                "all": [{"lang": script_lang, "prob": 0.99}],
            }
        try:
            langs = detect_langs(text)
            best = langs[0]
            code = LANG_MAP.get(str(best.lang), str(best.lang))
            return {
                "lang": code,
                "confidence": round(best.prob, 3),
                "name": LANG_NAMES.get(code, code),
                "all": [
                    {
                        "lang": LANG_MAP.get(str(l.lang), str(l.lang)),
                        "prob": round(l.prob, 3),
                    }
                    for l in langs[:3]
                ],
            }
        except Exception:
            return {"lang": "en", "confidence": 0.0, "name": "English", "all": []}
