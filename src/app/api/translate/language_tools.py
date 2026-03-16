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


def looks_like_gibberish(text: str) -> bool:
    """Heuristic detector for random/garbled input."""
    content = re.sub(r"\s+", "", text)
    if len(content) < 6:
        return False

    valid_chars = re.findall(
        r"[A-Za-z0-9\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF\u0E00-\u0E7F\u1000-\u109F\u0E80-\u0EFF\u1780-\u17FF\u0600-\u06FF\u0B80-\u0BFF]",
        content,
    )
    valid_ratio = (len(valid_chars) / len(content)) if content else 1.0

    if valid_ratio < 0.35:
        return True

    if re.search(r"([~!@#$%^&*_=+\\/\\|<>?`.,;:'\"-])\1{4,}", content):
        return True

    return False


def is_off_topic_message(message: str) -> bool:
    lower = message.lower().strip()
    if not lower:
        return False

    if looks_like_gibberish(message):
        return True

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


def sanitize_assistant_output(text: str) -> str:
    """Remove bilingual/meta tails and keep primary conversational reply."""
    cleaned = text.strip()
    marker_pattern = re.compile(
        r"\s*(translation|translated\s*text|翻译|翻譯|terjemahan|explanation|explain|解释|解釋|说明|說明|설명)\s*[:：].*$",
        re.IGNORECASE | re.DOTALL,
    )
    cleaned = marker_pattern.sub("", cleaned).strip()

    analysis_pattern = re.compile(
        r"\s*(意思是|意思為|可以表达为|可以表達為|in\s+other\s+words|this\s+means)\b.*$",
        re.IGNORECASE | re.DOTALL,
    )
    cleaned = analysis_pattern.sub("", cleaned).strip()

    cleaned = re.sub(r"^\s*(question|问题)\s*[:：].*$", "", cleaned, flags=re.IGNORECASE | re.MULTILINE).strip()
    cleaned = re.sub(r"^\s*(answer|回答|答案)\s*[:：]\s*", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\[(\d{1,3})\]\s*", "", cleaned)

    cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"__([^_]+)__", r"\1", cleaned)
    cleaned = re.sub(r"^\s*#{1,6}\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*[-*]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*\d+\.\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()

    cleaned = re.sub(r"^(你问的是|你是在问|您问的是|you asked|you are asking)[^。.!?\n]*[。.!?]\s*", "", cleaned, flags=re.IGNORECASE).strip()

    # Guard against prompt echo / RAG reference leakage.
    if re.search(r"\[Reference\]|\[Text to translate\]|Translate the following", cleaned, flags=re.IGNORECASE):
        return ""
    if re.search(r"\b(Bahasa\s+Indonesia\s*-\s*English\s*Translation|formal\s+Chinese)\b", cleaned, flags=re.IGNORECASE):
        return ""

    # Drop retrieval-style numbered dump output and let caller trigger a fallback.
    if len(re.findall(r"\b(Application|Eligibility|deadline|cutoff)\b", cleaned, flags=re.IGNORECASE)) >= 8:
        return ""

    return cleaned


def needs_language_correction(text: str, target_lang: str) -> bool:
    """Generic hard guard for output language drift."""
    content = text.strip()
    if not content:
        return False

    script_lang = infer_lang_by_script(content)
    if script_lang is not None and script_lang != target_lang:
        if {script_lang, target_lang} != {"zh", "ja"}:
            return True

    latin_count = len(re.findall(r"[A-Za-z]", content))
    han_count = len(re.findall(r"[\u4E00-\u9FFF]", content))
    hangul_count = len(re.findall(r"[\uAC00-\uD7AF]", content))
    kana_count = len(re.findall(r"[\u3040-\u30FF]", content))
    thai_count = len(re.findall(r"[\u0E00-\u0E7F]", content))
    myanmar_count = len(re.findall(r"[\u1000-\u109F]", content))
    lao_count = len(re.findall(r"[\u0E80-\u0EFF]", content))
    khmer_count = len(re.findall(r"[\u1780-\u17FF]", content))
    arabic_count = len(re.findall(r"[\u0600-\u06FF]", content))
    tamil_count = len(re.findall(r"[\u0B80-\u0BFF]", content))

    non_latin_targets = {"zh", "ja", "ko", "th", "my", "lo", "km", "ar", "ta"}
    if target_lang in non_latin_targets and latin_count >= 24:
        expected_counts = {
            "zh": han_count,
            "ja": han_count + kana_count,
            "ko": hangul_count,
            "th": thai_count,
            "my": myanmar_count,
            "lo": lao_count,
            "km": khmer_count,
            "ar": arabic_count,
            "ta": tamil_count,
        }
        if latin_count > expected_counts.get(target_lang, 0):
            return True

    detected = LanguageDetector.detect(content)
    if detected != target_lang:
        if {detected, target_lang} in ({"ms", "id"}, {"zh", "ja"}):
            return False
        return True
    return False


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
