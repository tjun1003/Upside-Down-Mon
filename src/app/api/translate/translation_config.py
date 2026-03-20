import logging
import os
from typing import Dict, Tuple

from dotenv import load_dotenv
from langdetect import DetectorFactory

load_dotenv()
DetectorFactory.seed = 42  # deterministic language detection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

USE_KB = os.getenv("USE_KB", "0") == "1"
USE_ATLAS_KB = os.getenv("USE_ATLAS_KB", "0") == "1"
# 0 means no hard cap (unlimited at app layer).
MAX_TRANSLATION_TOKENS = int(os.getenv("MAX_TRANSLATION_TOKENS", "0"))
ASSISTANT_MAX_NEW_TOKENS = int(os.getenv("ASSISTANT_MAX_NEW_TOKENS", "0"))
# Soft caps protect against pathological long generations; set 0 to disable.
SOFT_MAX_TRANSLATION_TOKENS = int(os.getenv("SOFT_MAX_TRANSLATION_TOKENS", "4096"))
SOFT_MAX_ASSISTANT_TOKENS = int(os.getenv("SOFT_MAX_ASSISTANT_TOKENS", "6144"))
STREAM_CHUNK_DELAY = float(os.getenv("STREAM_CHUNK_DELAY", "0.01"))
TRANSLATION_CACHE_SIZE = int(os.getenv("TRANSLATION_CACHE_SIZE", "128"))
MODEL_QUANTIZATION = os.getenv("MODEL_QUANTIZATION", "dynamic").lower()
LAZY_LOAD_MODEL = os.getenv("LAZY_LOAD_MODEL", "1") == "1"
STARTUP_CHECK_CACHE = os.getenv("STARTUP_CHECK_CACHE", "0") == "1"
UVICORN_RELOAD = os.getenv("UVICORN_RELOAD", "0") == "1"

ATLAS_URI = os.getenv("MONGODB_ATLAS_URI", "")
ATLAS_DB_NAME = os.getenv("MONGODB_ATLAS_DB", "")
ATLAS_COLLECTION_NAME = os.getenv("MONGODB_ATLAS_COLLECTION", "ABCDEFG")
ATLAS_TEXT_FIELD = os.getenv("MONGODB_TEXT_FIELD", "text")
ATLAS_SOURCE_FIELD = os.getenv("MONGODB_SOURCE_FIELD", "source")
ATLAS_METADATA_FIELD = os.getenv("MONGODB_METADATA_FIELD", "metadata")
ATLAS_EMBEDDING_FIELD = os.getenv("MONGODB_EMBEDDING_FIELD", "embedding")
ATLAS_VECTOR_INDEX = os.getenv("MONGODB_ATLAS_VECTOR_INDEX", "default")
ATLAS_USE_VECTOR_SEARCH = os.getenv("MONGODB_USE_VECTOR_SEARCH", "1") == "1"
ATLAS_RAG_TOP_K = int(os.getenv("MONGODB_RAG_TOP_K", "3"))
ATLAS_RAG_NUM_CANDIDATES = int(os.getenv("MONGODB_RAG_NUM_CANDIDATES", "60"))

EXTERNAL_RAG_ENABLED = os.getenv("EXTERNAL_RAG_ENABLED", "0") == "1"
EXTERNAL_RAG_PROVIDER = os.getenv("EXTERNAL_RAG_PROVIDER", "duckduckgo_html")
EXTERNAL_RAG_SEARCH_URL = os.getenv("EXTERNAL_RAG_SEARCH_URL", "https://html.duckduckgo.com/html/")
EXTERNAL_RAG_ALLOWED_DOMAINS = [
    d.strip().lower()
    for d in os.getenv("EXTERNAL_RAG_ALLOWED_DOMAINS", "").split(",")
    if d.strip()
]
EXTERNAL_RAG_QUERY_SUFFIX = os.getenv("EXTERNAL_RAG_QUERY_SUFFIX", "").strip()
EXTERNAL_RAG_MAX_RESULTS = int(os.getenv("EXTERNAL_RAG_MAX_RESULTS", "3"))
EXTERNAL_RAG_SEARCH_TIMEOUT_SEC = float(os.getenv("EXTERNAL_RAG_SEARCH_TIMEOUT_SEC", "4.0"))
EXTERNAL_RAG_FETCH_PAGE_CONTENT = os.getenv("EXTERNAL_RAG_FETCH_PAGE_CONTENT", "0") == "1"
EXTERNAL_RAG_PAGE_FETCH_TIMEOUT_SEC = float(os.getenv("EXTERNAL_RAG_PAGE_FETCH_TIMEOUT_SEC", "4.0"))
EXTERNAL_RAG_PAGE_MAX_CHARS = int(os.getenv("EXTERNAL_RAG_PAGE_MAX_CHARS", "8000"))

MULTI_OUTPUT_LANGS = [
    l.strip().lower()
    for l in os.getenv("MULTI_OUTPUT_LANGS", "en,zh,ms,vi,th,ta").split(",")
    if l.strip()
]

ASSISTANT_RESPONSES = {
    "greeting": (
        "Hello. I am doing well, thank you for asking. "
        "How may I assist you today?"
    ),
    "affection": (
        "Thank you for saying that. That is very kind of you. "
        "I am here with you. What would you like to talk about next?"
    )
}

TRANSLATION_PROMPT_TEMPLATE = (
    "<|im_start|>system\n"
    "You are a professional translator. "
    "Translate the given {src_name} text into {tgt_name}, "
    "preserving the original meaning, tone, and register as closely as possible. "
    "If the input is casual, keep it casual. If formal, keep it formal. "
    "Output ONLY the translated text - no explanations, notes, or extra content.\n"
    "<|im_end|>\n"
    "<|im_start|>user\n"
    "Translate the following {src_name} text into {tgt_name}:\n\n{text}\n"
    "<|im_end|>\n"
    "<|im_start|>assistant\n"
)

TRANSLATION_PROMPT_TEMPLATES: Dict[Tuple[str, str], str] = {
    ("zh", "en"): (
        "<|im_start|>system\n"
        "You are a professional Chinese-to-English translator. "
        "Translate naturally into fluent English while preserving meaning, legal/policy nuance, and tone. "
        "Keep official names (programmes, ministries, forms) accurate and consistent. "
        "Output ONLY the English translation.\n"
        "<|im_end|>\n"
        "<|im_start|>user\n{text}\n<|im_end|>\n<|im_start|>assistant\n"
    ),
    ("ms", "en"): (
        "<|im_start|>system\n"
        "You are a professional Bahasa Melayu-to-English translator. "
        "Preserve policy terms and government programme names faithfully. "
        "Keep sentence intent and level of formality. Output ONLY English text.\n"
        "<|im_end|>\n"
        "<|im_start|>user\n{text}\n<|im_end|>\n<|im_start|>assistant\n"
    ),
    ("vi", "en"): (
        "<|im_start|>system\n"
        "You are a professional Vietnamese-to-English translator. "
        "Preserve meaning exactly, including eligibility, deadline, and requirement details. "
        "Use natural, clear English. Output ONLY English text.\n"
        "<|im_end|>\n"
        "<|im_start|>user\n{text}\n<|im_end|>\n<|im_start|>assistant\n"
    ),
    ("th", "en"): (
        "<|im_start|>system\n"
        "You are a professional Thai-to-English translator. "
        "Maintain accuracy for official terms and procedural steps. "
        "Keep register aligned with the source. Output ONLY English text.\n"
        "<|im_end|>\n"
        "<|im_start|>user\n{text}\n<|im_end|>\n<|im_start|>assistant\n"
    ),
    ("ta", "en"): (
        "<|im_start|>system\n"
        "You are a professional Tamil-to-English translator. "
        "Preserve exact intent and institutional terminology. "
        "Do not add or omit meaning. Output ONLY English text.\n"
        "<|im_end|>\n"
        "<|im_start|>user\n{text}\n<|im_end|>\n<|im_start|>assistant\n"
    ),
    ("en", "zh"): (
        "<|im_start|>system\n"
        "You are a professional English-to-Chinese translator. "
        "Translate into clear modern Chinese, preserving policy/legal nuance and process details. "
        "Keep official names precise. Output ONLY Chinese text.\n"
        "<|im_end|>\n"
        "<|im_start|>user\n{text}\n<|im_end|>\n<|im_start|>assistant\n"
    ),
    ("en", "ms"): (
        "<|im_start|>system\n"
        "You are a professional English-to-Bahasa Melayu translator. "
        "Use natural Malaysian Malay while preserving official terminology and requirements. "
        "Output ONLY Bahasa Melayu text.\n"
        "<|im_end|>\n"
        "<|im_start|>user\n{text}\n<|im_end|>\n<|im_start|>assistant\n"
    ),
    ("en", "vi"): (
        "<|im_start|>system\n"
        "You are a professional English-to-Vietnamese translator. "
        "Keep details exact, especially conditions, dates, and application steps. "
        "Output ONLY Vietnamese text.\n"
        "<|im_end|>\n"
        "<|im_start|>user\n{text}\n<|im_end|>\n<|im_start|>assistant\n"
    ),
    ("en", "th"): (
        "<|im_start|>system\n"
        "You are a professional English-to-Thai translator. "
        "Translate faithfully with natural Thai phrasing and accurate official terms. "
        "Output ONLY Thai text.\n"
        "<|im_end|>\n"
        "<|im_start|>user\n{text}\n<|im_end|>\n<|im_start|>assistant\n"
    ),
    ("en", "ta"): (
        "<|im_start|>system\n"
        "You are a professional English-to-Tamil translator. "
        "Preserve exact meaning and administrative terminology with natural Tamil wording. "
        "Output ONLY Tamil text.\n"
        "<|im_end|>\n"
        "<|im_start|>user\n{text}\n<|im_end|>\n<|im_start|>assistant\n"
    ),
}

ASSISTANT_PROMPT_TEMPLATE = (
    "<|im_start|>system\n"
    "You are CitizenAI, a warm and knowledgeable government services assistant - "
    "like a helpful friend who happens to work in the civil service. "
    "All inputs are in English. Respond in English only.\n\n"
    "## Using Retrieved Information\n"
    "You will sometimes receive RETRIEVED CONTEXT - official excerpts pulled from government sources. "
    "When context is provided:\n"
    "- Treat it as your primary source of truth. Ground your answer in it.\n"
    "- Synthesise the information naturally into your reply - do NOT paste raw excerpts, "
    "quote blocks, or source IDs like [1], [2].\n"
    "- If the context covers the question well, answer confidently from it.\n"
    "- If the context is partial or ambiguous, use what is relevant and flag any gaps honestly "
    "(e.g. 'The exact fee may vary - worth double-checking at the official portal.').\n"
    "- If no context is provided or it is clearly irrelevant, rely on your general knowledge "
    "but be transparent: say you are not certain and point to the right authority.\n"
    "- Never fabricate links, fees, deadlines, or policy details.\n\n"
    "## Conversation Style\n"
    "- Speak in natural, conversational prose - not like a FAQ page or official notice.\n"
    "- For greetings or small talk: respond warmly and briefly.\n"
    "- For substantive questions: lead with the most direct, useful answer first, "
    "then add context. Write in complete sentences with enough detail to be genuinely useful - "
    "not truncated, not padded.\n"
    "- Use numbered steps when a process has multiple actions in sequence.\n"
    "- Use short bullets only when the user explicitly asks for a list.\n"
    "- Do not paraphrase or restate the user's question before answering.\n"
    "- Do not expose internal reasoning, translation notes, or retrieval metadata.\n\n"
    "## Links and References\n"
    "- If an official portal, hotline, or office is relevant, weave it in naturally "
    "(e.g. 'You can check your application status at MyEG - it only takes a few minutes.').\n"
    "- Only include links you are confident are accurate. When in doubt, name the authority "
    "instead (e.g. 'the JPJ website' or 'JPN\'s counter service').\n\n"
    "## Proactive Guidance\n"
    "- After answering, anticipate the natural next question and surface it briefly "
    "(e.g. 'One thing people often overlook at this stage is...').\n"
    "- End with ONE short follow-up question or offer that moves the user forward. "
    "Do not ask multiple questions.\n\n"
    "## Boundaries\n"
    "- Do not give legal advice - refer to a lawyer or legal aid clinic if needed.\n"
    "- Do not speculate on politically sensitive matters.\n"
    "- If a question is outside government services scope, acknowledge it briefly and redirect.\n"
    "<|im_end|>\n"
    "<|im_start|>user\n"
    "{context_block}"
    "{message}\n"
    "<|im_end|>\n"
    "<|im_start|>assistant\n"
)

LOCAL_MODELS = {
    "small": "sail/Sailor2-1B-Chat",
    "large": "sail/Sailor2-8B-Chat",
}
