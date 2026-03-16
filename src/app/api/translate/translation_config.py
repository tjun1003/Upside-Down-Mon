import logging
import os

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
    "en": "English", "ms": "Bahasa Melayu",
    "id": "Bahasa Indonesia", "th": "Thai",
    "vi": "Vietnamese", "zh": "Chinese",
    "ta": "Tamil", "tl": "Filipino",
    "my": "Burmese", "km": "Khmer",
    "lo": "Lao", "ja": "Japanese",
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
    "grant": (
        "Great question. For most government grant applications, the fastest path is to prepare these first: "
        "(1) company profile and registration documents, (2) latest financial statements, "
        "(3) project proposal with budget and timeline, and (4) expected outcomes (jobs, productivity, digital adoption). "
        "Then check eligibility criteria on the official portal and submit before the closing date. "
        "If you tell me your sector and company size, I can narrow this down to the most relevant scheme and checklist for you."
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
    "grant", "fund", "funding", "基金", "资助", "補助金", "拨款", "撥款", "申请", "申請",
    "housing", "rent", "home", "house", "房屋", "住房", "租房", "买房",
    "legal", "right", "rights", "contract", "labour", "labor", "worker", "migrant",
    "法律", "权益", "合同", "工人", "劳工", "勞工", "签证", "簽證",
]

OFF_TOPIC_KEYWORDS = [
    "i love you", "i like you", "do you love me", "you love who", "kiss", "date", "girlfriend", "boyfriend",
    "我爱你", "我愛你", "我喜欢你", "你爱谁", "你愛誰", "谈恋爱", "談戀愛",
    "cook", "make food", "make me dinner", "做饭", "做飯", "煮饭", "煮飯",
]

CHAT_PROMPTS = {
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
    "llama": (
        "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n"
        "You are a professional {src_name}–{tgt_name} translator. "
        "Always produce formal, grammatically correct {tgt_name} regardless of the register of the source text. "
        "Output only the translation, no explanation.\n"
        "<|eot_id|><|start_header_id|>user<|end_header_id|>\n"
        "{text}\n<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n"
    ),
    "mistral": (
        "<s>[INST] You are a professional multilingual translator. "
        "Translate the following text from {src_name} to {tgt_name} using formal, standard language. "
        "Always use proper grammar and formal register regardless of how the source text is written. "
        "Output ONLY the translation, nothing else.\n\n"
        "{text} [/INST]"
    ),
}

LOCAL_MODELS = {
    "small": "sail/Sailor2-1B-Chat",
    "large": "sail/Sailor2-8B-Chat",
}
