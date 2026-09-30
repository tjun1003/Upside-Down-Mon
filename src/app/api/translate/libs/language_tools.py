import re
from typing import Any, Dict, Optional

from langdetect import detect, detect_langs
from translation_config import logger

from translation_config import (
    ASSISTANT_RESPONSES,
)

LANG_MAP = {
    "zh-cn": "zh",
    "zh-tw": "zh",
    "zh": "zh",
    "ms": "ms",
    "id": "ms",
    "in": "ms",
    "th": "th",
    "vi": "vi",
    "ta": "ta",
    "en": "en",
}

LANG_NAMES = {
    "en": "English",
    "ms": "Bahasa Melayu",
    "th": "Thai",
    "vi": "Vietnamese",
    "zh": "Chinese",
    "ta": "Tamil",
}

SUPPORTED_LANGS = {"en", "zh", "ms", "vi", "th", "ta"}

MS_HINT_WORDS = {
    "yang", "dan", "untuk", "dengan", "dalam", "kepada", "adalah", "tidak",
    "ini", "itu", "sekolah", "kementerian", "permohonan", "kerajaan", "rakyat",
}

VI_DIACRITIC_RE = re.compile(r"[ăâđêôơưàáảãạầấẩẫậằắẳẵặèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ]", re.IGNORECASE)
TH_CHAR_RE = re.compile(r"[\u0E00-\u0E7F]")
TA_CHAR_RE = re.compile(r"[\u0B80-\u0BFF]")


def _normalize_for_detection(text: str) -> str:
    normalized = text or ""
    normalized = re.sub(r"https?://\S+", " ", normalized)
    normalized = re.sub(r"www\.\S+", " ", normalized)
    normalized = re.sub(r"```[\s\S]*?```", " ", normalized)
    normalized = re.sub(r"`[^`]*`", " ", normalized)
    normalized = re.sub(r"\*\*|__|~~|#+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _heuristic_detect(text: str) -> Optional[str]:
    if not text:
        return None

    # Fast path: Thai block characters are distinctive enough for reliable detection.
    if len(TH_CHAR_RE.findall(text)) >= 2:
        logger.info("LanguageDetect heuristic: th (script signal)")
        return "th"

    # Fast path: Tamil block characters are distinctive enough for reliable detection.
    if len(TA_CHAR_RE.findall(text)) >= 2:
        logger.info("LanguageDetect heuristic: ta (script signal)")
        return "ta"

    script_lang = infer_lang_by_script(text)
    if script_lang in SUPPORTED_LANGS:
        return script_lang

    lower = text.lower()

    # Fast path: Vietnamese diacritics are distinctive enough for reliable detection.
    if VI_DIACRITIC_RE.search(lower):
        logger.info("LanguageDetect heuristic: vi (diacritic signal)")
        return "vi"

    tokens = re.findall(r"[a-zA-Z\u00C0-\u024F]+", lower)
    if not tokens:
        return None

    ms_hits = sum(1 for t in tokens if t in MS_HINT_WORDS)
    if ms_hits >= 2:
        logger.info("LanguageDetect heuristic: ms (keyword signal)")
        return "ms"

    return None


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


def infer_lang_by_script(text: str) -> Optional[str]:
    """Infer language from script for short messages where langdetect may be unstable."""
    if re.search(r"[\u0E00-\u0E7F]", text):
        return "th"
    if re.search(r"[\u0B80-\u0BFF]", text):
        return "ta"
    if re.search(r"[\u4E00-\u9FFF]", text):
        return "zh"
    return None


class LanguageDetector:
    """Auto-detect language from text, with SEA-aware fallback."""

    @staticmethod
    def detect(text: str) -> str:
        """Returns normalised language code e.g. 'ms', 'th', 'en'."""
        normalized = _normalize_for_detection(text)
        heuristic_lang = _heuristic_detect(normalized)
        if heuristic_lang is not None:  # If heuristic detection is valid, return directly
            return heuristic_lang
        try:
            raw = detect(normalized or text)  # Otherwise use built-in library function

            mapped = LANG_MAP.get(raw, raw)
            logger.info(f"LanguageDetect detect: raw={raw}, mapped={mapped}")
            if mapped in SUPPORTED_LANGS:
                return mapped
            return "en"
        except Exception:
            return "en"

    @staticmethod
    def detect_with_confidence(text: str) -> Dict[str, Any]:
        normalized = _normalize_for_detection(text)
        heuristic_lang = _heuristic_detect(normalized)
        if heuristic_lang is not None:
            return {
                "lang": heuristic_lang,
                "confidence": 0.99,
                "name": LANG_NAMES.get(heuristic_lang, heuristic_lang),
                "all": [{"lang": heuristic_lang, "prob": 0.99}],
            }
        try:
            langs = detect_langs(normalized or text)
            candidates = [
                (LANG_MAP.get(str(l.lang), str(l.lang)), round(l.prob, 3))
                for l in langs[:5]
            ]
            logger.info(f"LanguageDetect candidates: {candidates}")
            code = "en"
            confidence = 0.0
            for lang_code, prob in candidates:
                if lang_code in SUPPORTED_LANGS:
                    code = lang_code
                    confidence = prob
                    break
            return {
                "lang": code,
                "confidence": confidence,
                "name": LANG_NAMES.get(code, code),
                "all": [
                    {
                        "lang": lang_code,
                        "prob": prob,
                    }
                    for lang_code, prob in candidates
                ],
            }
        except Exception:
            return {"lang": "en", "confidence": 0.0, "name": "English", "all": []}
