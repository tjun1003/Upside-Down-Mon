"""
╔══════════════════════════════════════════════════════════════════════╗
║  🌏 SEA Translation Chatbot — Backend (FastAPI)                     ║
║                                                                      ║
║  Features:                                                           ║
║  • Auto language detection (langdetect)                              ║
║  • Streaming translation (Server-Sent Events)                        ║
║  • Conversation memory (LangChain ConversationBufferMemory)          ║
║  • RAG knowledge base (LlamaIndex)                                   ║
║  • Multi-platform webhooks (Telegram, WhatsApp)                      ║
║  • HuggingFace Inference API (cloud) + local model fallback          ║
╚══════════════════════════════════════════════════════════════════════╝

Install:
    pip install fastapi uvicorn python-telegram-bot langchain \
                langchain-community llama-index \
                llama-index-embeddings-huggingface \
                sentence-transformers huggingface_hub \
                langdetect chromadb sse-starlette \
                python-dotenv pydantic requests
"""

import os
import json
import asyncio
import logging
import re
from collections import OrderedDict
from threading import Thread
from typing import Optional, List, AsyncGenerator, Dict, Any
from datetime import datetime
from dotenv import load_dotenv

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage
from langdetect import detect, DetectorFactory
# Note: transformers and torch are loaded dynamically in TranslationEngine

load_dotenv()
DetectorFactory.seed = 42  # deterministic language detection

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

USE_KB = os.getenv("USE_KB", "0") == "1"
# 0 means no hard cap (unlimited at app layer).
MAX_TRANSLATION_TOKENS = int(os.getenv("MAX_TRANSLATION_TOKENS", "0"))
ASSISTANT_MAX_NEW_TOKENS = int(os.getenv("ASSISTANT_MAX_NEW_TOKENS", "0"))
# Soft caps protect against pathological long generations; set 0 to disable.
SOFT_MAX_TRANSLATION_TOKENS = int(os.getenv("SOFT_MAX_TRANSLATION_TOKENS", "2048"))
SOFT_MAX_ASSISTANT_TOKENS = int(os.getenv("SOFT_MAX_ASSISTANT_TOKENS", "3072"))
STREAM_CHUNK_DELAY = float(os.getenv("STREAM_CHUNK_DELAY", "0.01"))
TRANSLATION_CACHE_SIZE = int(os.getenv("TRANSLATION_CACHE_SIZE", "128"))
MODEL_QUANTIZATION = os.getenv("MODEL_QUANTIZATION", "dynamic").lower()
LAZY_LOAD_MODEL = os.getenv("LAZY_LOAD_MODEL", "1") == "1"
STARTUP_CHECK_CACHE = os.getenv("STARTUP_CHECK_CACHE", "0") == "1"
UVICORN_RELOAD = os.getenv("UVICORN_RELOAD", "0") == "1"


# ═══════════════════════════════════════════════════════════════════
# 0. Model Cache Helper
# ═══════════════════════════════════════════════════════════════════

def check_model_cache(model_name: str) -> bool:
    """
    Check if a HuggingFace model is already cached locally.
    Returns True if cached, False otherwise.
    """
    from pathlib import Path
    
    # HuggingFace cache directory
    cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
    
    # Model folder name format: models--{org}--{model}
    model_folder = "models--" + model_name.replace("/", "--")
    model_path = cache_dir / model_folder
    
    if model_path.exists():
        # Calculate size
        total_size = sum(f.stat().st_size for f in model_path.rglob("*") if f.is_file())
        size_str = f"{total_size / (1024**3):.2f} GB" if total_size > 1024**3 else f"{total_size / (1024**2):.0f} MB"
        logger.info(f"✅ Cache found: {model_name} ({size_str})")
        return True
    else:
        logger.info(f"⏳ Will download: {model_name}")
        return False


def log_cache_status():
    """Log cache status for all models used in this app."""
    logger.info("═" * 50)
    logger.info("📦 Checking model cache...")
    
    models = [
        "sail/Sailor2-1B-Chat",
        "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    ]
    
    cached = sum(1 for m in models if check_model_cache(m))
    logger.info(f"📊 {cached}/{len(models)} models cached")
    logger.info("═" * 50)


# ═══════════════════════════════════════════════════════════════════
# 1. Language Detection
# ═══════════════════════════════════════════════════════════════════

# Map langdetect codes → our SEA codes
LANG_MAP = {
    "zh-cn": "zh", "zh-tw": "zh", "zh": "zh",
    "ms": "ms", "id": "id", "th": "th",
    "vi": "vi", "tl": "tl", "my": "my",
    "ta": "ta", "km": "km", "lo": "lo",
    "en": "en", "ja": "ja", "ko": "ko",
    "fr": "fr", "de": "de", "es": "es",
    "ar": "ar",
}

LANG_NAMES = {
    "en": "English",         "ms": "Bahasa Melayu",
    "id": "Bahasa Indonesia", "th": "Thai",
    "vi": "Vietnamese",      "zh": "Chinese",
    "ta": "Tamil",           "tl": "Filipino",
    "my": "Burmese",         "km": "Khmer",
    "lo": "Lao",             "ja": "Japanese",
    "ko": "Korean",
}

ASSISTANT_RESPONSES = {
    "greeting": (
        "Hello. I am doing well, thank you for asking. "
        "How may I assist you today?"
    ),
    "affection": (
        "Thank you for saying that. That is very kind of you. "
        "I am here with you. What would you like to talk about next?"
    ),
    "subsidy": (
        "Hospital subsidies are available under the Skim Peduli Kesihatan programme. "
        "To apply: (1) Register at MySejahtera portal, (2) Upload your IC and income documents, "
        "(3) Visit any government clinic for assessment. The process takes 5 to 7 working days."
    ),
    "scholarship": (
        "Several scholarships are available: JPA Scholarship (full tuition), MARA Loans "
        "(low-interest), and State Education Bursaries. Eligibility depends on household "
        "income and academic results. Which education level is your child in?"
    ),
    "housing": (
        "Affordable housing programmes include PR1MA for middle income, PPR Rental for low "
        "income, and MyDeposit for first-home buyers. Apply online at ehome.kpkt.gov.my. "
        "What is your household income range?"
    ),
    "legal": (
        "As a migrant worker you have the right to fair wages, safe working conditions, "
        "healthcare access, and the right to file complaints with JTKSM. "
        "Call the Labour Hotline: 1800-88-8088 (free). Would you like this in another language?"
    ),
}

SYSTEM_SCOPE_REDIRECT_EN = (
    "I can only assist with government service topics: public health support, education and scholarships, "
    "housing assistance, and basic worker/legal rights. "
    "Please ask a related question so I can help you directly."
)

DOMAIN_KEYWORDS = [
    "health", "hospital", "subsidy", "clinic", "医保", "医疗", "医院", "补助", "补贴",
    "education", "school", "scholarship", "study", "学历", "教育", "奖学金",
    "housing", "rent", "home", "house", "房屋", "住房", "租房", "买房",
    "legal", "right", "rights", "contract", "labour", "labor", "worker", "migrant",
    "法律", "权益", "合同", "工人", "劳工", "勞工", "签证", "簽證",
]

OFF_TOPIC_KEYWORDS = [
    "i love you", "i like you", "do you love me", "you love who", "kiss", "date", "girlfriend", "boyfriend",
    "我爱你", "我愛你", "我喜欢你", "你爱谁", "你愛誰", "谈恋爱", "談戀愛",
    "cook", "make food", "make me dinner", "做饭", "做飯", "煮饭", "煮飯",
]


def build_assistant_reply(message: str) -> Optional[str]:
    lower = message.lower()
    if any(k in lower for k in ["hi", "hello", "hey", "how are you", "你好", "您好", "你好吗", "你還好嗎", "你还好吗"]):
        return ASSISTANT_RESPONSES["greeting"]
    if any(k in lower for k in ["i like you", "i love you", "我喜欢你", "我愛你", "我爱你", "saya suka kamu", "aku suka kamu"]):
        return ASSISTANT_RESPONSES["affection"]
    if any(k in lower for k in ["subsidi", "hospital", "health"]):
        return ASSISTANT_RESPONSES["subsidy"]
    if any(k in lower for k in ["scholarship", "education", "school"]):
        return ASSISTANT_RESPONSES["scholarship"]
    if any(k in lower for k in ["hous", "rumah"]):
        return ASSISTANT_RESPONSES["housing"]
    if any(k in lower for k in ["legal", "right", "migrant"]):
        return ASSISTANT_RESPONSES["legal"]
    return None


def resolve_response_lang(detected_lang: str, requested_lang: str) -> str:
    """
    Resolve assistant reply language for the current turn.
    Prefer the language detected from the current user input; fall back to requested language.
    """
    if detected_lang in LANG_NAMES:
        return detected_lang
    return requested_lang


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

    # Mostly symbols/noise.
    if valid_ratio < 0.35:
        return True

    # Repeated random punctuation chunks.
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

    # Very short non-domain social prompts are treated as off-topic for this assistant scope.
    token_count = len(re.findall(r"\w+", lower, flags=re.UNICODE))
    if token_count <= 4 and not any(k in lower for k in DOMAIN_KEYWORDS):
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
    # Chinese/Japanese share Han characters; if no kana/hangul are present, default to zh.
    if re.search(r"[\u4E00-\u9FFF]", text):
        return "zh"
    return None


def sanitize_assistant_output(text: str) -> str:
    """
    Remove bilingual/meta tails like "Translation: ..." from assistant output.
    Keep only the primary conversational reply.
    """
    cleaned = text.strip()
    marker_pattern = re.compile(
        r"\s*(translation|translated\s*text|翻译|翻譯|terjemahan|explanation|explain|解释|解釋|说明|說明|설명)\s*[:：].*$",
        re.IGNORECASE | re.DOTALL,
    )
    cleaned = marker_pattern.sub("", cleaned).strip()

    # Remove common "sentence analysis" style continuations in Chinese/English.
    analysis_pattern = re.compile(
        r"\s*(意思是|意思為|可以表达为|可以表達為|in\s+other\s+words|this\s+means)\b.*$",
        re.IGNORECASE | re.DOTALL,
    )
    cleaned = analysis_pattern.sub("", cleaned).strip()

    # Remove common Q/A wrappers so we keep only the direct answer.
    cleaned = re.sub(r"^\s*(question|问题)\s*[:：].*$", "", cleaned, flags=re.IGNORECASE | re.MULTILINE).strip()
    cleaned = re.sub(r"^\s*(answer|回答|答案)\s*[:：]\s*", "", cleaned, flags=re.IGNORECASE).strip()

    # Remove markdown formatting markers when model outputs markdown in plain-text channel.
    cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"__([^_]+)__", r"\1", cleaned)
    cleaned = re.sub(r"^\s*#{1,6}\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*[-*]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*\d+\.\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()

    # If the response still starts by rephrasing user intent, trim that lead-in.
    cleaned = re.sub(r"^(你问的是|你是在问|您问的是|you asked|you are asking)[^。.!?\n]*[。.!?]\s*", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


def needs_language_correction(text: str, target_lang: str) -> bool:
    """
    Generic hard guard for output language drift.
    Uses script hints + detector fallback to decide whether to auto-correct.
    """
    content = text.strip()
    if not content:
        return False

    # Quick script inference for obvious drift.
    script_lang = infer_lang_by_script(content)
    if script_lang is not None and script_lang != target_lang:
        # Allow zh<->ja script overlap to pass; detector handles deeper correction.
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
        # Allow closely related/overlapping outputs for Malay/Indonesian and zh/ja.
        if {detected, target_lang} in ({"ms", "id"}, {"zh", "ja"}):
            return False
        return True
    return False

# Local Sailor2 models for SEA languages
# Sailor2 excels at Southeast Asian languages
LOCAL_MODELS = {
    # Use 1B for CPU, 8B for GPU (set USE_LARGE_MODEL=1 in .env)
    "small": "sail/Sailor2-1B-Chat",   # ~2GB VRAM / CPU friendly
    "large": "sail/Sailor2-8B-Chat",   # ~16GB VRAM
}


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
        from langdetect import detect_langs
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
                "all": [{"lang": LANG_MAP.get(str(l.lang), str(l.lang)),
                          "prob": round(l.prob, 3)} for l in langs[:3]]
            }
        except Exception:
            return {"lang": "en", "confidence": 0.0, "name": "English", "all": []}


# ═══════════════════════════════════════════════════════════════════
# 2. Translation Engine (HF Inference API + local fallback)
# ═══════════════════════════════════════════════════════════════════

CHAT_PROMPTS = {
    # ChatML format (Sailor2, SEA-LION, Typhoon)
    "chatml": (
        "<|im_start|>system\n"
        "You are a professional translator. Translate the given {src_name} text into formal, standard {tgt_name}. "
        "Always use proper grammar, punctuation, and formal register regardless of the style of the input. "
        "Output ONLY the translated text with no explanations, notes, or extra content.\n"
        "<|im_end|>\n"
        "<|im_start|>user\n"
        "Translate the following {src_name} text into formal {tgt_name}:\n\n{text}\n"
        "<|im_end|>\n"
        "<|im_start|>assistant\n"
    ),
    # LLaMA format (Sahabat-AI, VinaLLaMA)
    "llama": (
        "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n"
        "You are a professional {src_name}–{tgt_name} translator. "
        "Always produce formal, grammatically correct {tgt_name} regardless of the register of the source text. "
        "Output only the translation, no explanation.\n"
        "<|eot_id|><|start_header_id|>user<|end_header_id|>\n"
        "{text}\n<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n"
    ),
    # Mistral format
    "mistral": (
        "<s>[INST] You are a professional multilingual translator. "
        "Translate the following text from {src_name} to {tgt_name} using formal, standard language. "
        "Always use proper grammar and formal register regardless of how the source text is written. "
        "Output ONLY the translation, nothing else.\n\n"
        "{text} [/INST]"
    ),
}


class TranslationEngine:
    """
    Translation using local Sailor2 model.
    Sailor2 is optimized for Southeast Asian languages.
    """

    def __init__(self):
        self._tokenizer = None
        self._model = None
        self._model_name = None
        self._device = "cpu"
        self._quantization = "none"
        self._cache: OrderedDict[tuple[str, str, str, str], str] = OrderedDict()
        if LAZY_LOAD_MODEL:
            logger.info("⏭️ Lazy model loading enabled; model will load on first translation request")
        else:
            self._load_local()

    def ensure_model_loaded(self):
        if self._model is None or self._tokenizer is None:
            self._load_local()

    def _load_local(self):
        """Load Sailor2 model locally."""
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            
            # Check if GPU available and if user wants large model
            use_large = os.getenv("USE_LARGE_MODEL", "0") == "1"
            has_gpu = torch.cuda.is_available()
            
            if use_large and has_gpu:
                self._model_name = LOCAL_MODELS["large"]
                logger.info(f"🚀 Loading large model: {self._model_name} (GPU)")
            else:
                self._model_name = LOCAL_MODELS["small"]
                logger.info(f"💻 Loading small model: {self._model_name} (CPU/GPU)")
            
            # Determine device
            self._device = "cuda" if has_gpu else "cpu"
            logger.info(f"🖥️  Device: {self._device}")

            self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)
            if self._tokenizer.pad_token is None:
                self._tokenizer.pad_token = self._tokenizer.eos_token

            model_kwargs: Dict[str, Any] = {}
            requested_quantization = MODEL_QUANTIZATION

            if has_gpu:
                if requested_quantization in {"4bit", "8bit"}:
                    try:
                        from transformers import BitsAndBytesConfig

                        if requested_quantization == "4bit":
                            model_kwargs["quantization_config"] = BitsAndBytesConfig(
                                load_in_4bit=True,
                                bnb_4bit_compute_dtype=torch.float16,
                                bnb_4bit_use_double_quant=True,
                                bnb_4bit_quant_type="nf4",
                            )
                        else:
                            model_kwargs["quantization_config"] = BitsAndBytesConfig(
                                load_in_8bit=True,
                            )
                        model_kwargs["device_map"] = "auto"
                        self._quantization = requested_quantization
                    except Exception as exc:
                        logger.warning(f"Quantization setup failed, falling back to fp16: {exc}")
                        model_kwargs["torch_dtype"] = torch.float16
                        model_kwargs["device_map"] = "auto"
                        self._quantization = "fp16"
                else:
                    model_kwargs["torch_dtype"] = torch.float16
                    model_kwargs["device_map"] = "auto"
                    self._quantization = "fp16"
            else:
                model_kwargs["torch_dtype"] = torch.float32
                self._quantization = "none"

            self._model = AutoModelForCausalLM.from_pretrained(
                self._model_name,
                **model_kwargs,
            )

            if not has_gpu and requested_quantization in {"dynamic", "8bit"}:
                self._model = torch.quantization.quantize_dynamic(
                    self._model,
                    {torch.nn.Linear},
                    dtype=torch.qint8,
                )
                self._quantization = "dynamic-int8"

            if not has_gpu:
                self._model.to(self._device)

            self._model.eval()
            logger.info(f"✅ Sailor2 loaded successfully: {self._model_name}")
            logger.info(f"⚙️ Quantization mode: {self._quantization}")
        except Exception as e:
            logger.error(f"Local model load failed: {e}")

    def _estimate_max_new_tokens(self, text: str) -> int:
        estimated = max(32, len(text) * 2)
        if MAX_TRANSLATION_TOKENS > 0:
            estimated = min(MAX_TRANSLATION_TOKENS, estimated)
        elif SOFT_MAX_TRANSLATION_TOKENS > 0:
            estimated = min(SOFT_MAX_TRANSLATION_TOKENS, estimated)
        return estimated

    def _build_generation_kwargs(self, max_new_tokens: int, streamer: Any = None) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {
            "max_new_tokens": max_new_tokens,
            "do_sample": False,
            "use_cache": True,
            "pad_token_id": self._tokenizer.pad_token_id if self._tokenizer else None,
            "eos_token_id": self._tokenizer.eos_token_id if self._tokenizer else None,
        }
        if streamer is not None:
            kwargs["streamer"] = streamer
        return kwargs

    def _generate_text(self, prompt: str, max_new_tokens: int) -> str:
        import torch

        if self._tokenizer is None or self._model is None:
            return "[Translation unavailable — model not loaded]"

        inputs = self._tokenizer(prompt, return_tensors="pt")
        if self._device == "cpu":
            inputs = {key: value.to(self._device) for key, value in inputs.items()}

        with torch.inference_mode():
            output = self._model.generate(
                **inputs,
                **self._build_generation_kwargs(max_new_tokens),
            )

        generated_tokens = output[0][inputs["input_ids"].shape[1]:]
        return self._tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()

    def _clean_translation(self, text: str) -> str:
        cleaned = text.strip()
        for stop in ["<|im_end|>", "<|im_start|>", "\n\n\n"]:
            if stop in cleaned:
                cleaned = cleaned.split(stop)[0].strip()
        return cleaned

    def _get_cached_translation(
        self, text: str, src_lang: str, tgt_lang: str, context: str
    ) -> Optional[str]:
        cache_key = (text, src_lang, tgt_lang, context)
        cached = self._cache.get(cache_key)
        if cached is not None:
            self._cache.move_to_end(cache_key)
        return cached

    def _set_cached_translation(
        self, text: str, src_lang: str, tgt_lang: str, context: str, translation: str
    ) -> None:
        cache_key = (text, src_lang, tgt_lang, context)
        self._cache[cache_key] = translation
        self._cache.move_to_end(cache_key)
        if len(self._cache) > TRANSLATION_CACHE_SIZE:
            self._cache.popitem(last=False)

    def _select_model(self, src_lang: str, tgt_lang: str) -> str:
        # Always use local Sailor2 model
        return self._model_name or LOCAL_MODELS["small"]

    def _build_prompt(self, text: str, src_lang: str, tgt_lang: str,
                      context: str = "", fmt: str = "chatml") -> str:
        src_name = LANG_NAMES.get(src_lang, src_lang)
        tgt_name = LANG_NAMES.get(tgt_lang, tgt_lang)
        full_text = text
        if context:
            full_text = f"[Reference]\n{context}\n\n[Text to translate]\n{text}"
        return CHAT_PROMPTS[fmt].format(
            src_name=src_name, tgt_name=tgt_name, text=full_text
        )

    def _build_assistant_prompt(self, message: str, target_lang: str, context: str = "") -> str:
        tgt_name = LANG_NAMES.get(target_lang, target_lang)
        context_block = ""
        if context:
            context_block = f"<official_context>\n{context}\n</official_context>\n\n"

        return (
            "<|im_start|>system\n"
            "You are CitizenAI, a warm and knowledgeable government services assistant — like a helpful friend who works in the civil service. "
            f"Always respond in {tgt_name}, matching the user's register (formal if they are formal, casual if they are casual).\n\n"

            "## Conversation Style\n"
            "- Speak directly to the user in a natural, human tone — not like a FAQ page or official document.\n"
            "- For greetings, small talk, or emotional messages: respond conversationally, warmly, and briefly.\n"
            "- Never give robotic, bullet-point-only responses unless the user explicitly asks for a list.\n"
            "- Never analyze or paraphrase the user's message back to them.\n\n"
            "- Do not repeat or restate the user's question before answering.\n\n"

            "## When Answering Government / Service Questions\n"
            "- Lead with the most useful, direct answer first — then add context if needed.\n"
            "- Break complex processes into simple numbered steps when there are multiple actions required.\n"
            "- If a relevant official link, portal, or hotline exists, include it naturally in the response "
            "(e.g. 'You can apply directly at [MyEG portal](https://www.myeg.com.my) — it usually takes about 10 minutes.').\n"
            "- Acknowledge if something varies by state, citizenship status, or situation, and ask a clarifying question if needed.\n"
            "- Never hallucinate links, fees, deadlines, or policy details. If unsure, say so and point to the right authority.\n\n"

            "## Proactive Guidance\n"
            "- After answering, anticipate what the user likely needs to know next and offer it naturally "
            "(e.g. 'While you're at it, you'll probably also need to...', or 'One thing people often miss is...').\n"
            "- End with ONE short follow-up question or suggestion that moves the user forward "
            "(e.g. 'Would you like to know what documents you need to bring?', or 'Are you applying as a first-time applicant?').\n"
            "- Do not ask multiple questions at once. Pick the single most useful one.\n\n"

            "## Boundaries\n"
            "- Do not give legal advice — refer to a lawyer or legal aid if needed.\n"
            "- Do not speculate on politically sensitive matters.\n"
            "- If a question is completely outside government services scope, acknowledge it briefly and redirect.\n"
            "<|im_end|>\n"
            "<|im_start|>user\n"
            f"{context_block}"
            f"{message}\n"
            "<|im_end|>\n"
            "<|im_start|>assistant\n"
        )

    def generate_assistant_reply(self, message: str, target_lang: str, context: str = "") -> str:
        self.ensure_model_loaded()
        prompt = self._build_assistant_prompt(message, target_lang, context)
        max_new_tokens = max(96, len(message) * 4)
        if ASSISTANT_MAX_NEW_TOKENS > 0:
            max_new_tokens = min(ASSISTANT_MAX_NEW_TOKENS, max_new_tokens)
        elif SOFT_MAX_ASSISTANT_TOKENS > 0:
            max_new_tokens = min(SOFT_MAX_ASSISTANT_TOKENS, max_new_tokens)
        try:
            return self._clean_translation(self._generate_text(prompt, max_new_tokens))
        except Exception as e:
            logger.error(f"Assistant generation error: {e}")
            return "I can help, but I hit an internal generation error. Please try again."

    def translate(self, text: str, src_lang: str, tgt_lang: str,
                  context: str = "") -> str:
        """Blocking translation using local Sailor2 model."""
        self.ensure_model_loaded()

        cached = self._get_cached_translation(text, src_lang, tgt_lang, context)
        if cached is not None:
            return cached

        prompt = self._build_prompt(text, src_lang, tgt_lang, context, fmt="chatml")
        max_new_tokens = self._estimate_max_new_tokens(text)

        if self._model and self._tokenizer:
            try:
                result = self._clean_translation(
                    self._generate_text(prompt, max_new_tokens)
                )
                self._set_cached_translation(text, src_lang, tgt_lang, context, result)
                return result
            except Exception as e:
                logger.error(f"Translation error: {e}")
                return f"[Translation error: {str(e)}]"
        else:
            return "[Translation unavailable — model not loaded]"

    async def translate_stream(
        self, text: str, src_lang: str, tgt_lang: str, context: str = ""
    ) -> AsyncGenerator[str, None]:
        """True streaming translation using TextIteratorStreamer."""
        self.ensure_model_loaded()

        cached = self._get_cached_translation(text, src_lang, tgt_lang, context)
        if cached is not None:
            for chunk in cached.split(" "):
                if chunk:
                    yield chunk + " "
                    await asyncio.sleep(STREAM_CHUNK_DELAY)
            return

        if self._tokenizer is None or self._model is None:
            yield "[Translation unavailable — model not loaded]"
            return

        try:
            import torch
            from transformers import TextIteratorStreamer

            prompt = self._build_prompt(text, src_lang, tgt_lang, context, fmt="chatml")
            max_new_tokens = self._estimate_max_new_tokens(text)
            inputs = self._tokenizer(prompt, return_tensors="pt")
            if self._device == "cpu":
                inputs = {key: value.to(self._device) for key, value in inputs.items()}

            streamer = TextIteratorStreamer(
                self._tokenizer,
                skip_prompt=True,
                skip_special_tokens=True,
            )

            generation_thread = Thread(
                target=self._model.generate,
                kwargs={
                    **inputs,
                    **self._build_generation_kwargs(max_new_tokens, streamer=streamer),
                },
                daemon=True,
            )
            generation_thread.start()

            chunks: List[str] = []
            for chunk in streamer:
                cleaned = self._clean_translation(chunk)
                if cleaned:
                    chunks.append(cleaned)
                    yield cleaned
                    await asyncio.sleep(STREAM_CHUNK_DELAY)

            final_text = self._clean_translation("".join(chunks))
            if final_text:
                self._set_cached_translation(text, src_lang, tgt_lang, context, final_text)
        except Exception as e:
            logger.error(f"Streaming translation error: {e}")
            yield f"[Translation error: {str(e)}]"


# ═══════════════════════════════════════════════════════════════════
# 3. Conversation Memory (LangChain)
# ═══════════════════════════════════════════════════════════════════

class ConversationStore:
    """
    Per-session conversation memory using ChatMessageHistory.
    Keeps last N turns.
    """

    def __init__(self, window: int = 10):
        self._sessions: Dict[str, ChatMessageHistory] = {}
        self.window = window

    def get(self, session_id: str) -> ChatMessageHistory:
        if session_id not in self._sessions:
            self._sessions[session_id] = ChatMessageHistory()
        return self._sessions[session_id]

    def add(self, session_id: str, human: str, ai: str):
        mem = self.get(session_id)
        mem.add_user_message(human)
        mem.add_ai_message(ai)
        # Keep only last N*2 messages (N turns = N human + N ai)
        if len(mem.messages) > self.window * 2:
            mem.messages = mem.messages[-(self.window * 2):]

    def history(self, session_id: str) -> List[Dict]:
        mem = self.get(session_id)
        messages = mem.messages
        result = []
        for m in messages:
            role = "user" if isinstance(m, HumanMessage) else "assistant"
            result.append({"role": role, "content": m.content})
        return result

    def clear(self, session_id: str):
        if session_id in self._sessions:
            self._sessions[session_id].clear()

    def active_sessions(self) -> int:
        return len(self._sessions)


# ═══════════════════════════════════════════════════════════════════
# 4. RAG Knowledge Base (LlamaIndex)
# ═══════════════════════════════════════════════════════════════════

class KnowledgeBase:
    """
    LlamaIndex-powered RAG store for domain glossaries,
    FAQ documents, and translation memory.
    """

    def __init__(self, index_path: str = "./kb_index",
                 embed_model: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"):
        self.index_path = index_path
        self.embed_model_id = embed_model
        self._index = None
        self.enabled = USE_KB
        if self.enabled:
            self._setup()
        else:
            logger.info("ℹ️ Knowledge base disabled (USE_KB=0)")

    def _setup(self):
        if not self.enabled:
            return
        try:
            from llama_index.core import Settings
            from llama_index.embeddings.huggingface import HuggingFaceEmbedding
            Settings.embed_model = HuggingFaceEmbedding(model_name=self.embed_model_id)
            Settings.llm = None  # We use our own SEA LLM

            # Try loading existing index
            if os.path.exists(self.index_path):
                from llama_index.core import StorageContext, load_index_from_storage
                ctx = StorageContext.from_defaults(persist_dir=self.index_path)
                self._index = load_index_from_storage(ctx)
                logger.info("✅ Knowledge base loaded from disk")
        except Exception as e:
            logger.warning(f"KB setup: {e}")

    def add_documents(self, docs: List[Dict]):
        """
        Add documents to the knowledge base.
        docs: [{"text": "...", "metadata": {"lang": "ms", "domain": "..."}}]
        """
        if not self.enabled:
            raise RuntimeError("Knowledge base is disabled. Set USE_KB=1 to enable it.")
        from llama_index.core import VectorStoreIndex, Document
        os.makedirs(self.index_path, exist_ok=True)
        llama_docs = [Document(text=d["text"], metadata=d.get("metadata", {}))
                      for d in docs]
        if self._index is None:
            self._index = VectorStoreIndex.from_documents(llama_docs)
        else:
            for doc in llama_docs:
                self._index.insert(doc)
        self._index.storage_context.persist(persist_dir=self.index_path)
        logger.info(f"✅ Added {len(docs)} documents to knowledge base")

    def retrieve(self, query: str, top_k: int = 3) -> str:
        """Retrieve relevant context for RAG."""
        if not self.enabled or self._index is None:
            return ""
        try:
            retriever = self._index.as_retriever(similarity_top_k=top_k)
            nodes = retriever.retrieve(query)
            return "\n---\n".join(n.text for n in nodes)
        except Exception:
            return ""

    @property
    def ready(self) -> bool:
        return self._index is not None


# ═══════════════════════════════════════════════════════════════════
# 5. Chatbot Core
# ═══════════════════════════════════════════════════════════════════

class SEAChatbot:
    """
    Unified chatbot that combines:
    - Language detection
    - RAG context retrieval
    - Streaming translation
    - Conversation memory
    """

    def __init__(self):
        self.detector   = LanguageDetector()
        self.engine     = TranslationEngine()
        self.memory     = ConversationStore(window=10)
        self.kb         = KnowledgeBase()

    async def respond(
        self,
        session_id: str,
        message: str,
        target_lang: str = "en",
        stream: bool = False,
    ) -> Any:
        """
        Main entry: detect language, retrieve context, translate.
        Returns dict (stream=False) or async generator (stream=True).
        """
        # 1. Detect source language
        detection = self.detector.detect_with_confidence(message)
        src_lang   = detection["lang"]

        # If already in target language, no translation needed
        if src_lang == target_lang:
            reply = message  # Just return original message
            self.memory.add(session_id, message, reply)
            if stream:
                async def _passthrough():
                    yield reply
                return _passthrough()
            return {
                "translation": reply,
                "src_lang":    src_lang,
                "src_name":    detection["name"],
                "confidence":  detection["confidence"],
                "tgt_lang":    target_lang,
                "tgt_name":    LANG_NAMES.get(target_lang, target_lang),
                "same_lang":   True,
            }

        # 2. RAG context
        context = self.kb.retrieve(message) if self.kb.ready else ""

        # 3. Translate
        if stream:
            async def _stream_and_save():
                full = []
                async for token in self.engine.translate_stream(
                    message, src_lang, target_lang, context
                ):
                    full.append(token)
                    yield token
                # Save complete response to memory after stream ends
                self.memory.add(session_id, message, "".join(full))

            return _stream_and_save()
        else:
            translation = self.engine.translate(message, src_lang, target_lang, context)
            self.memory.add(session_id, message, translation)
            return {
                "translation": translation,
                "src_lang":    src_lang,
                "src_name":    detection["name"],
                "confidence":  detection["confidence"],
                "tgt_lang":    target_lang,
                "tgt_name":    LANG_NAMES.get(target_lang, target_lang),
            }


# ═══════════════════════════════════════════════════════════════════
# 6. FastAPI App
# ═══════════════════════════════════════════════════════════════════

app = FastAPI(
    title="🌏 SEA Translation Chatbot API",
    description="Real-time multilingual translation for SEA languages",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Singleton chatbot
chatbot = SEAChatbot()


# ── Pydantic models ───────────────────────────────────────────────
class ChatRequest(BaseModel):
    session_id: str = "default"
    message: str
    target_lang: str = "en"
    assistant_mode: bool = True

class DetectRequest(BaseModel):
    text: str

class KBAddRequest(BaseModel):
    documents: List[Dict[str, Any]]

class ClearRequest(BaseModel):
    session_id: str


# ── Endpoints ─────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "service": "SEA Translation Chatbot",
        "version": "1.0.0",
        "endpoints": ["/chat/stream", "/detect", "/history",
                      "/kb/add", "/health"],
    }


@app.post("/detect")
def detect_language(req: DetectRequest):
    """Detect language of input text."""
    return chatbot.detector.detect_with_confidence(req.text)


@app.post("/chat")
async def chat(req: ChatRequest):
    """Non-streaming endpoint is intentionally disabled; use /chat/stream."""
    raise HTTPException(410, "Non-streaming chat is disabled. Use /chat/stream.")


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    Streaming translation via Server-Sent Events (SSE).
    Frontend receives tokens as they are generated.
    """
    if not req.message.strip():
        raise HTTPException(400, "Message cannot be empty")

    # Detect language first (fast, non-streaming)
    detection = chatbot.detector.detect_with_confidence(req.message)
    src_lang = detection["lang"]
    response_lang = resolve_response_lang(src_lang, req.target_lang)

    # Send metadata header first, then stream tokens
    async def event_generator():
        # First event: metadata
        meta = json.dumps({
            "type":       "meta",
            "src_lang":   src_lang,
            "src_name":   detection["name"],
            "confidence": detection["confidence"],
            "tgt_lang":   response_lang,
        })
        yield f"data: {meta}\n\n"

        context = chatbot.kb.retrieve(req.message) if chatbot.kb.ready else ""

        if req.assistant_mode:
            if is_off_topic_message(req.message):
                if response_lang == "en":
                    final_reply = SYSTEM_SCOPE_REDIRECT_EN
                else:
                    final_reply = chatbot.engine.translate(
                        SYSTEM_SCOPE_REDIRECT_EN, "en", response_lang, context
                    )
                final_reply = sanitize_assistant_output(final_reply)
                for chunk in final_reply.split(" "):
                    if chunk:
                        yield f"data: {json.dumps({'type': 'token', 'text': chunk + ' '})}\n\n"
                        await asyncio.sleep(STREAM_CHUNK_DELAY)
                chatbot.memory.add(req.session_id, req.message, final_reply)
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return

            # Hybrid mode: rule-based template when matched, otherwise model-generated answer.
            rule_reply_en = build_assistant_reply(req.message)
            if rule_reply_en is not None:
                if response_lang == "en":
                    final_reply = rule_reply_en
                else:
                    final_reply = chatbot.engine.translate(
                        rule_reply_en, "en", response_lang, context
                    )
            else:
                final_reply = chatbot.engine.generate_assistant_reply(
                    req.message, response_lang, context
                )

            final_reply = sanitize_assistant_output(final_reply)
            out_lang = chatbot.detector.detect(final_reply)
            if out_lang != response_lang and final_reply.strip():
                final_reply = chatbot.engine.translate(
                    final_reply, out_lang, response_lang, context
                )
                final_reply = sanitize_assistant_output(final_reply)

            if needs_language_correction(final_reply, response_lang):
                final_reply = chatbot.engine.translate(
                    final_reply, chatbot.detector.detect(final_reply), response_lang, context
                )
                final_reply = sanitize_assistant_output(final_reply)

            for chunk in final_reply.split(" "):
                if chunk:
                    yield f"data: {json.dumps({'type': 'token', 'text': chunk + ' '})}\n\n"
                    await asyncio.sleep(STREAM_CHUNK_DELAY)
        else:
            async for token in chatbot.engine.translate_stream(
                req.message,
                src_lang,
                req.target_lang,
                context,
            ):
                payload = json.dumps({"type": "token", "text": token})
                yield f"data: {payload}\n\n"
                await asyncio.sleep(0)
            final_reply = chatbot.engine.translate(req.message, src_lang, req.target_lang, context)

        # Done event
        chatbot.memory.add(req.session_id, req.message, final_reply)

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/history/{session_id}")
def get_history(session_id: str):
    """Return conversation history for a session."""
    return {
        "session_id": session_id,
        "history":    chatbot.memory.history(session_id),
    }


@app.post("/history/clear")
def clear_history(req: ClearRequest):
    """Clear conversation history for a session."""
    chatbot.memory.clear(req.session_id)
    return {"cleared": True, "session_id": req.session_id}


@app.post("/kb/add")
def add_to_kb(req: KBAddRequest):
    """Add documents/glossaries to the RAG knowledge base."""
    chatbot.kb.add_documents(req.documents)
    return {"added": len(req.documents), "kb_ready": chatbot.kb.ready}


@app.get("/health")
def health():
    return {
        "status":          "ok",
        "active_sessions": chatbot.memory.active_sessions(),
        "kb_enabled":      chatbot.kb.enabled,
        "kb_ready":        chatbot.kb.ready,
        "model":           chatbot.engine._model_name,
        "model_loaded":    chatbot.engine._model is not None,
        "streaming":       True,
        "quantization":    chatbot.engine._quantization,
        "max_tokens":      MAX_TRANSLATION_TOKENS,
        "soft_max_translation_tokens": SOFT_MAX_TRANSLATION_TOKENS,
        "soft_max_assistant_tokens": SOFT_MAX_ASSISTANT_TOKENS,
    }


# ═══════════════════════════════════════════════════════════════════
# 7. Telegram Bot Integration
# ═══════════════════════════════════════════════════════════════════

async def setup_telegram():
    """
    Telegram bot that uses the same chatbot core.
    Set TELEGRAM_TOKEN in .env to activate.
    """
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.info("ℹ️  TELEGRAM_TOKEN not set — Telegram bot disabled")
        return

    try:
        from telegram import Update
        from telegram.ext import (
            Application, CommandHandler, MessageHandler,
            filters, ContextTypes
        )
    except ImportError:
        logger.warning("python-telegram-bot not installed. "
                       "Run: pip install python-telegram-bot")
        return

    tg_app = Application.builder().token(token).build()

    async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🌏 *SEA Translation Bot*\n\n"
            "Send me any text in a SEA language and I'll translate it to English.\n"
            "Use /lang <code> to change target language (e.g. /lang ms)\n\n"
            "Supported: en, ms, id, th, vi, zh, ta, tl, my, km, lo",
            parse_mode="Markdown",
        )

    async def set_lang(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if ctx.args:
            ctx.user_data["target_lang"] = ctx.args[0]
            name = LANG_NAMES.get(ctx.args[0], ctx.args[0])
            await update.message.reply_text(f"✅ Target language set to: {name}")
        else:
            await update.message.reply_text("Usage: /lang <code>  e.g. /lang ms")

    async def translate_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        session_id = f"tg_{update.effective_user.id}"
        target_lang = ctx.user_data.get("target_lang", "en")

        # Show typing indicator
        await update.message.chat.send_action("typing")

        result = await chatbot.respond(session_id, text, target_lang, stream=False)

        if isinstance(result, dict):
            reply = (
                f"🔤 *{result['src_name']}* → *{result['tgt_name']}*\n\n"
                f"{result['translation']}\n\n"
                f"_Confidence: {result['confidence']:.0%}_"
            )
        else:
            reply = str(result)

        await update.message.reply_text(reply, parse_mode="Markdown")

    async def clear_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        session_id = f"tg_{update.effective_user.id}"
        chatbot.memory.clear(session_id)
        await update.message.reply_text("✅ Conversation history cleared.")

    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CommandHandler("lang", set_lang))
    tg_app.add_handler(CommandHandler("clear", clear_cmd))
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, translate_msg))

    logger.info("🤖 Telegram bot starting (polling)...")
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling()
    logger.info("✅ Telegram bot is running")
    return tg_app


# ═══════════════════════════════════════════════════════════════════
# 8. WhatsApp (Meta Cloud API) webhook
# ═══════════════════════════════════════════════════════════════════

@app.get("/webhook/whatsapp")
async def whatsapp_verify(request: Request):
    """WhatsApp webhook verification handshake."""
    params   = dict(request.query_params)
    verify   = os.getenv("WHATSAPP_VERIFY_TOKEN", "sea_translate_token")
    mode     = params.get("hub.mode")
    token    = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    if mode == "subscribe" and token == verify:
        return JSONResponse(content=int(challenge))
    raise HTTPException(403, "Verification failed")


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request, background: BackgroundTasks):
    """Receive WhatsApp messages and translate them."""
    import httpx
    body = await request.json()

    async def process():
        try:
            entry = body["entry"][0]
            change = entry["changes"][0]["value"]
            msg = change["messages"][0]
            if msg["type"] != "text":
                return
            text       = msg["text"]["body"]
            phone      = msg["from"]
            session_id = f"wa_{phone}"

            result = await chatbot.respond(session_id, text, "en", stream=False)
            if isinstance(result, dict):
                reply = (
                    f"[{result['src_name']} → {result['tgt_name']}]\n"
                    f"{result['translation']}"
                )
            else:
                reply = str(result)

            # Send reply via WhatsApp Cloud API
            wa_token = os.getenv("WHATSAPP_TOKEN")
            phone_id  = os.getenv("WHATSAPP_PHONE_ID")
            if wa_token and phone_id:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        f"https://graph.facebook.com/v18.0/{phone_id}/messages",
                        headers={"Authorization": f"Bearer {wa_token}"},
                        json={
                            "messaging_product": "whatsapp",
                            "to": phone,
                            "type": "text",
                            "text": {"body": reply},
                        },
                    )
        except Exception as e:
            logger.error(f"WhatsApp webhook error: {e}")

    background.add_task(process)
    return {"status": "ok"}


# ═══════════════════════════════════════════════════════════════════
# 9. Startup
# ═══════════════════════════════════════════════════════════════════

@app.on_event("startup")
async def on_startup():
    logger.info("🌏 SEA Translation Chatbot starting…")
    if STARTUP_CHECK_CACHE:
        log_cache_status()
    else:
        logger.info("⏩ Skipping cache status scan (set STARTUP_CHECK_CACHE=1 to enable)")
    # Start Telegram bot in background if token provided
    asyncio.create_task(setup_telegram())


if __name__ == "__main__":
    uvicorn.run("translation:app", host="0.0.0.0", port=8000, reload=UVICORN_RELOAD)