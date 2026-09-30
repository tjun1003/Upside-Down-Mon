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

# PDF processing configuration
PDF_DEFAULT_CHUNK_SIZE = int(os.getenv("PDF_DEFAULT_CHUNK_SIZE", "1000"))
PDF_DEFAULT_CHUNK_OVERLAP = int(os.getenv("PDF_DEFAULT_CHUNK_OVERLAP", "200"))
PDF_MIN_CHUNK_SIZE = int(os.getenv("PDF_MIN_CHUNK_SIZE", "100"))
PDF_MAX_FILE_SIZE_MB = int(os.getenv("PDF_MAX_FILE_SIZE_MB", "10"))

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


TRANSLATION_PROMPT_TEMPLATES: Dict[Tuple[str, str], str] = {
    ("zh", "en"): (
        "<|im_start|>system\n"
        "You are a professional Chinese-to-English translator. Always output ONLY English. If the input is not English, translate it to English first.\n"
        "You MUST NOT output any explanations, labels, or phrases like 'Translation:', 'If you need assistance...', or similar. Output ONLY the translated text, nothing else.\n"
        "<|im_end|>\n"
        "<|im_start|>user\n输入：教育局最新公告：本周起所有学生需佩戴校徽。\n<|im_end|>\n<|im_start|>assistant\nThe Education Bureau announced that starting this week, all students are required to wear school badges.\n<|im_end|>\n"
        "<|im_start|>user\n{text}\n<|im_end|>\n<|im_start|>assistant\n"
    ),
    ("ms", "en"): (
        "<|im_start|>system\n"
        "You are a professional Bahasa Melayu-to-English translator. Preserve policy terms and government programme names faithfully. Keep sentence intent and level of formality. Output ONLY English text.\n"
        "You MUST NOT output any explanations, labels, or phrases like 'Translation:', 'If you need assistance...', or similar. Output ONLY the translated text, nothing else.\n"
        "<|im_end|>\n"
        "<|im_start|>user\nInput: Sekolah Berasrama Penuh (SBP) dan Kolej Vokasional (KV) adalah program pendidikan tinggi di Malaysia yang memberi peluang kepada calon mahasiswa untuk memilih antara dua pilihan:\n\nUniversiti - Program Sarjana Muda (Bachelor's Degree)\nLembaga - Program Diploma (Diploma)\nCalon mahasiswa dapat memilih salah satu dari kedua-dua pilihan ini untuk melanjutkan studinya ke jenjang sarjana atau diploma di institusi yang dituju.\n<|im_end|>\n<|im_start|>assistant\nFully Residential Schools (SBP) and Vocational Colleges (KV) are higher education programmes in Malaysia that offer prospective students the opportunity to choose between two options:\n\nUniversity - Bachelor's Degree Programme\nBoard - Diploma Programme\nStudents can choose either option to further their studies at the bachelor's or diploma level at their chosen institution.\n<|im_end|>\n"
        "<|im_start|>user\n{text}\n<|im_end|>\n<|im_start|>assistant\n"
    ),
    ("vi", "en"): (
        "<|im_start|>system\n"
        "You are a professional Vietnamese-to-English translator. Preserve meaning exactly, including eligibility, deadline, and requirement details. Use natural, clear English. Output ONLY English text.\n"
        "You MUST NOT output any explanations, labels, or phrases like 'Translation:', 'If you need assistance...', or similar. Output ONLY the translated text, nothing else.\n"
        "<|im_end|>\n"
        "<|im_start|>user\nInput: Trường nội trú và trường cao đẳng nghề là các chương trình giáo dục đại học tại Malaysia, cung cấp cho sinh viên cơ hội lựa chọn giữa hai lựa chọn:\n\nĐại học - Chương trình Cử nhân\nHội đồng - Chương trình Cao đẳng\nSinh viên có thể chọn một trong hai lựa chọn này để tiếp tục học lên trình độ cử nhân hoặc cao đẳng tại cơ sở mong muốn.\n<|im_end|>\n<|im_start|>assistant\nBoarding schools and vocational colleges are higher education programmes in Malaysia that provide students with the opportunity to choose between two options:\n\nUniversity - Bachelor's Degree Programme\nBoard - Diploma Programme\nStudents can choose either option to pursue a bachelor's or diploma degree at their desired institution.\n<|im_end|>\n"
        "<|im_start|>user\n{text}\n<|im_end|>\n<|im_start|>assistant\n"
    ),
    ("th", "en"): (
        "<|im_start|>system\n"
        "You are a professional Thai-to-English translator. Maintain accuracy for official terms and procedural steps. Keep register aligned with the source. Output ONLY English text.\n"
        "You MUST NOT output any explanations, labels, or phrases like 'Translation:', 'If you need assistance...', or similar. Output ONLY the translated text, nothing else.\n"
        "<|im_end|>\n"
        "<|im_start|>user\nInput: โรงเรียนประจำ (SBP) และวิทยาลัยอาชีวศึกษา (KV) เป็นโปรแกรมการศึกษาระดับอุดมศึกษาในมาเลเซียที่เปิดโอกาสให้นักศึกษาเลือกได้สองทางเลือก:\n\nมหาวิทยาลัย - โปรแกรมปริญญาตรี\nคณะกรรมการ - โปรแกรมอนุปริญญา\nนักศึกษาสามารถเลือกหนึ่งในสองทางเลือกนี้เพื่อศึกษาต่อในระดับปริญญาตรีหรืออนุปริญญาในสถาบันที่ต้องการ\n<|im_end|>\n<|im_start|>assistant\nBoarding Schools (SBP) and Vocational Colleges (KV) are higher education programmes in Malaysia that give students the opportunity to choose between two options:\n\nUniversity - Bachelor's Degree Programme\nBoard - Diploma Programme\nStudents can choose either option to further their studies at the bachelor's or diploma level at their chosen institution.\n<|im_end|>\n"
        "<|im_start|>user\n{text}\n<|im_end|>\n<|im_start|>assistant\n"
    ),
    ("ta", "en"): (
        "<|im_start|>system\n"
        "You are a professional Tamil-to-English translator. Preserve exact intent and institutional terminology. Do not add or omit meaning. Output ONLY English text.\n"
        "You MUST NOT output any explanations, labels, or phrases like 'Translation:', 'If you need assistance...', or similar. Output ONLY the translated text, nothing else.\n"
        "<|im_end|>\n"
        "<|im_start|>user\nInput: மலேசியாவில் உள்ள குடியிருப்பு பள்ளிகள் (SBP) மற்றும் தொழில்நுட்பக் கல்லூரிகள் (KV) உயர்கல்வி திட்டங்கள் ஆகும், அவை மாணவர்களுக்கு இரண்டு விருப்பங்களை தேர்வு செய்ய வாய்ப்பு வழங்குகின்றன:\n\nபல்கலைக்கழகம் - பட்டப்படிப்பு திட்டம்\nபலகை - டிப்ளோமா திட்டம்\nமாணவர்கள் இந்த இரண்டு விருப்பங்களில் ஒன்றைத் தேர்வு செய்து, தாங்கள் விரும்பும் நிறுவனத்தில் பட்டப்படிப்பு அல்லது டிப்ளோமா படிப்பை தொடரலாம்.\n<|im_end|>\n<|im_start|>assistant\nBoarding Schools (SBP) and Vocational Colleges (KV) are higher education programmes in Malaysia that provide students with the opportunity to choose between two options:\n\nUniversity - Bachelor's Degree Programme\nBoard - Diploma Programme\nStudents can choose either option to continue their studies at the bachelor's or diploma level at their preferred institution.\n<|im_end|>\n"
        "<|im_start|>user\n{text}\n<|im_end|>\n<|im_start|>assistant\n"
    ),
    ("en", "zh"): (
        "<|im_start|>system\n"
        "You are a professional English-to-Chinese translator. Translate into clear modern Chinese, preserving policy/legal nuance and process details. Keep official names precise. Output ONLY Chinese text.\n"
        "You MUST NOT output any explanations, labels, or phrases like 'Translation:', 'If you need assistance...', or similar. Output ONLY the translated text, nothing else.\n"
        "<|im_end|>\n"
        "<|im_start|>user\nInput: Fully Residential Schools (SBP) and Vocational Colleges (KV) are higher education programmes in Malaysia that offer prospective students the opportunity to choose between two options:\n\nUniversity - Bachelor's Degree Programme\nBoard - Diploma Programme\nStudents can choose either option to further their studies at the bachelor's or diploma level at their chosen institution.\n<|im_end|>\n<|im_start|>assistant\n马来西亚的寄宿中学（SBP）和职业学院（KV）是高等教育项目，为学生提供两种选择：\n\n大学——学士学位课程\n理事会——文凭课程\n学生可以选择其中之一，在所选院校攻读学士或文凭课程。\n<|im_end|>\n"
        "<|im_start|>user\n{text}\n<|im_end|>\n<|im_start|>assistant\n"
    ),
    ("en", "ms"): (
        "<|im_start|>system\n"
        "You are a professional English-to-Bahasa Melayu translator. Use natural Malaysian Malay while preserving official terminology and requirements. Output ONLY Bahasa Melayu text.\n"
        "You MUST NOT output any explanations, labels, or phrases like 'Translation:', 'If you need assistance...', or similar. Output ONLY the translated text, nothing else.\n"
        "<|im_end|>\n"
        "<|im_start|>user\nInput: Fully Residential Schools (SBP) and Vocational Colleges (KV) are higher education programmes in Malaysia that offer prospective students the opportunity to choose between two options:\n\nUniversity - Bachelor's Degree Programme\nBoard - Diploma Programme\nStudents can choose either option to further their studies at the bachelor's or diploma level at their chosen institution.\n<|im_end|>\n<|im_start|>assistant\nSekolah Berasrama Penuh (SBP) dan Kolej Vokasional (KV) ialah program pendidikan tinggi di Malaysia yang menawarkan peluang kepada pelajar untuk memilih antara dua pilihan:\n\nUniversiti - Program Ijazah Sarjana Muda\nLembaga - Program Diploma\nPelajar boleh memilih salah satu pilihan ini untuk melanjutkan pengajian ke peringkat ijazah sarjana muda atau diploma di institusi pilihan mereka.\n<|im_end|>\n"
        "<|im_start|>user\n{text}\n<|im_end|>\n<|im_start|>assistant\n"
    ),
    ("en", "vi"): (
        "<|im_start|>system\n"
        "You are a professional English-to-Vietnamese translator. Keep details exact, especially conditions, dates, and application steps. Output ONLY Vietnamese text.\n"
        "You MUST NOT output any explanations, labels, or phrases like 'Translation:', 'If you need assistance...', or similar. Output ONLY the translated text, nothing else.\n"
        "<|im_end|>\n"
        "<|im_start|>user\nInput: Fully Residential Schools (SBP) and Vocational Colleges (KV) are higher education programmes in Malaysia that offer prospective students the opportunity to choose between two options:\n\nUniversity - Bachelor's Degree Programme\nBoard - Diploma Programme\nStudents can choose either option to further their studies at the bachelor's or diploma level at their chosen institution.\n<|im_end|>\n<|im_start|>assistant\nTrường nội trú (SBP) và trường cao đẳng nghề (KV) là các chương trình giáo dục đại học tại Malaysia, cung cấp cho sinh viên cơ hội lựa chọn giữa hai lựa chọn:\n\nĐại học - Chương trình Cử nhân\nHội đồng - Chương trình Cao đẳng\nSinh viên có thể chọn một trong hai lựa chọn này để tiếp tục học lên trình độ cử nhân hoặc cao đẳng tại cơ sở mong muốn.\n<|im_end|>\n"
        "<|im_start|>user\n{text}\n<|im_end|>\n<|im_start|>assistant\n"
    ),
    ("en", "th"): (
        "<|im_start|>system\n"
        "You are a professional English-to-Thai translator. Translate faithfully with natural Thai phrasing and accurate official terms. Output ONLY Thai text.\n"
        "You MUST NOT output any explanations, labels, or phrases like 'Translation:', 'If you need assistance...', or similar. Output ONLY the translated text, nothing else.\n"
        "<|im_end|>\n"
        "<|im_start|>user\nInput: Fully Residential Schools (SBP) and Vocational Colleges (KV) are higher education programmes in Malaysia that offer prospective students the opportunity to choose between two options:\n\nUniversity - Bachelor's Degree Programme\nBoard - Diploma Programme\nStudents can choose either option to further their studies at the bachelor's or diploma level at their chosen institution.\n<|im_end|>\n<|im_start|>assistant\nโรงเรียนประจำ (SBP) และวิทยาลัยอาชีวศึกษา (KV) เป็นโปรแกรมการศึกษาระดับอุดมศึกษาในมาเลเซียที่เปิดโอกาสให้นักศึกษาเลือกได้สองทางเลือก:\n\nมหาวิทยาลัย - โปรแกรมปริญญาตรี\nคณะกรรมการ - โปรแกรมอนุปริญญา\nนักศึกษาสามารถเลือกหนึ่งในสองทางเลือกนี้เพื่อศึกษาต่อในระดับปริญญาตรีหรืออนุปริญญาในสถาบันที่ต้องการ\n<|im_end|>\n"
        "<|im_start|>user\n{text}\n<|im_end|>\n<|im_start|>assistant\n"
    ),
    ("en", "ta"): (
        "<|im_start|>system\n"
        "You are a professional English-to-Tamil translator. Preserve exact meaning and administrative terminology with natural Tamil wording. Output ONLY Tamil text.\n"
        "You MUST NOT output any explanations, labels, or phrases like 'Translation:', 'If you need assistance...', or similar. Output ONLY the translated text, nothing else.\n"
        "<|im_end|>\n"
        "<|im_start|>user\nInput: Fully Residential Schools (SBP) and Vocational Colleges (KV) are higher education programmes in Malaysia that offer prospective students the opportunity to choose between two options:\n\nUniversity - Bachelor's Degree Programme\nBoard - Diploma Programme\nStudents can choose either option to further their studies at the bachelor's or diploma level at their chosen institution.\n<|im_end|>\n<|im_start|>assistant\nமுழு நேர விடுதி பள்ளிகள் (SBP) மற்றும் தொழில்நுட்பக் கல்லூரிகள் (KV) மலேசியாவில் உள்ள உயர்கல்வி திட்டங்கள் ஆகும், அவை மாணவர்களுக்கு இரண்டு விருப்பங்களைத் தேர்வு செய்ய வாய்ப்பு வழங்குகின்றன:\n\nபல்கலைக்கழகம் - பட்டப்படிப்பு திட்டம்\nபலகை - டிப்ளோமா திட்டம்\nமாணவர்கள் இந்த இரண்டு விருப்பங்களில் ஒன்றைத் தேர்வு செய்து, தாங்கள் விரும்பும் நிறுவனத்தில் பட்டப்படிப்பு அல்லது டிப்ளோமா படிப்பை தொடரலாம்.\n<|im_end|>\n"
        "<|im_start|>user\n{text}\n<|im_end|>\n<|im_start|>assistant\n"
    ),
}

SUMMARY_PROMPT_TEMPLATE = (
    "<|im_start|>system\n"
    "You are a retrieval summarizer for search engines. Your job is to extract and output only the shortest possible English summary: key facts, entities, policies, deadlines, or intent, in a single compact sentence or a few keywords. "
    "Do NOT expand, explain, answer, or add any extra information. Do NOT output full sentences unless necessary. Prefer keywords, phrases, or a very short summary. "
    "Do NOT include phrases like 'Explanation', 'Answer', 'Correct option', or similar. "
    "If the input is not English, translate it to English first, then summarize.\n"
    "<|im_end|>\n"
    "<|im_start|>user\n输入：教育局最新公告：本周起所有学生需佩戴校徽。\n<|im_end|>\n<|im_start|>assistant\nMOE: mandatory school badges, all students, next week\n<|im_end|>\n"
    "<|im_start|>user\n{text}\n<|im_end|>\n<|im_start|>assistant\n"
)

SUMMARY_EN_TO_MS_PROMPT_TEMPLATE = (
    "<|im_start|>system\n"
    "You are a professional English-to-Bahasa Melayu translator for retrieval queries. "
    "Translate faithfully and keep important entities/official terms unchanged when needed. "
    "Output ONLY Bahasa Melayu text with no extra explanation.\n"
    "<|im_end|>\n"
    "<|im_start|>user\n{text}\n<|im_end|>\n<|im_start|>assistant\n"
)

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
    "- If context is present, ALWAYS use it as the basis of your answer, even when it seems only partially related.\n"
    "- If the context is partial or ambiguous, still proceed using it and clearly label uncertain parts.\n"
    "- If no context is provided, do NOT rely on general knowledge. "
    "State that you do not have sufficient retrieved information and ask a short follow-up "
    "question to narrow scope or request an official source/authority.\n"
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
