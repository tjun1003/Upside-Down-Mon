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
from typing import Optional, List, AsyncGenerator, Dict, Any
from datetime import datetime
from dotenv import load_dotenv

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

from langchain.memory import ConversationBufferWindowMemory
from langchain.schema import HumanMessage, AIMessage
from langdetect import detect, DetectorFactory
from huggingface_hub import InferenceClient

load_dotenv()
DetectorFactory.seed = 42  # deterministic language detection

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


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

# HuggingFace model IDs for each language pair (cloud inference)
SEA_HF_MODELS = {
    # General SEA — best all-rounder (8B fits free HF API)
    "default":    "sail/Sailor2-8B-Chat",
    # Thai specialist
    "th":         "scb10x/typhoon2-qwen2.5-7b-instruct",
    # Vietnamese specialist
    "vi":         "vilm/vinallama-7b-chat",
    # Indonesian / Malay specialist
    "id":         "sail/Sailor2-8B-Chat",
    "ms":         "sail/Sailor2-8B-Chat",
    # Broad SEA (low-resource languages)
    "my":         "aisingapore/Qwen-SEA-LION-v4-32B-IT",
    "km":         "aisingapore/Qwen-SEA-LION-v4-32B-IT",
    "lo":         "aisingapore/Qwen-SEA-LION-v4-32B-IT",
}


class LanguageDetector:
    """Auto-detect language from text, with SEA-aware fallback."""

    @staticmethod
    def detect(text: str) -> str:
        """Returns normalised language code e.g. 'ms', 'th', 'en'."""
        try:
            raw = detect(text)
            return LANG_MAP.get(raw, raw)
        except Exception:
            return "en"

    @staticmethod
    def detect_with_confidence(text: str) -> Dict[str, Any]:
        from langdetect import detect_langs
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
        "You are an expert multilingual translator specializing in Southeast Asian languages. "
        "Translate the given text from {src_name} to {tgt_name} accurately and naturally. "
        "Preserve tone, formality, and cultural nuance. "
        "Output ONLY the translation — no explanations, no notes.\n"
        "<|im_end|>\n"
        "<|im_start|>user\n{text}\n<|im_end|>\n"
        "<|im_start|>assistant\n"
    ),
    # LLaMA format (Sahabat-AI, VinaLLaMA)
    "llama": (
        "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n"
        "You are an expert {src_name}–{tgt_name} translator. "
        "Output only the translation, no explanation.\n"
        "<|eot_id|><|start_header_id|>user<|end_header_id|>\n"
        "{text}\n<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n"
    ),
}


class TranslationEngine:
    """
    Translation via HuggingFace Inference API (streaming supported).
    Falls back to local transformers pipeline if HF_TOKEN is missing.
    """

    def __init__(self):
        self.hf_token = os.getenv("HF_TOKEN")
        self._local_pipe = None
        if self.hf_token:
            self.client = InferenceClient(token=self.hf_token)
            logger.info("✅ Using HuggingFace Inference API (cloud)")
        else:
            logger.warning("⚠️  HF_TOKEN not set — falling back to local model")
            self._load_local()

    def _load_local(self):
        """Load a small local model as fallback."""
        try:
            from transformers import pipeline
            self._local_pipe = pipeline(
                "text-generation",
                model="sail/Sailor2-1B-Chat",   # 1B — CPU friendly
                max_new_tokens=512,
                do_sample=False,
            )
            logger.info("✅ Local Sailor2-1B loaded as fallback")
        except Exception as e:
            logger.error(f"Local model load failed: {e}")

    def _select_model(self, src_lang: str, tgt_lang: str) -> str:
        # Pick best model based on target language (most need the target side)
        return SEA_HF_MODELS.get(tgt_lang,
               SEA_HF_MODELS.get(src_lang, SEA_HF_MODELS["default"]))

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

    def translate(self, text: str, src_lang: str, tgt_lang: str,
                  context: str = "") -> str:
        """Blocking translation."""
        model_id = self._select_model(src_lang, tgt_lang)
        prompt = self._build_prompt(text, src_lang, tgt_lang, context)

        if self.hf_token:
            response = self.client.text_generation(
                prompt,
                model=model_id,
                max_new_tokens=512,
                temperature=0.1,
                repetition_penalty=1.05,
                stop_sequences=["<|im_end|>", "<|eot_id|>", "\n\n\n"],
            )
            return response.strip()
        elif self._local_pipe:
            out = self._local_pipe(prompt, return_full_text=False)
            return out[0]["generated_text"].strip()
        else:
            return f"[Translation unavailable — no model loaded]"

    async def translate_stream(
        self, text: str, src_lang: str, tgt_lang: str, context: str = ""
    ) -> AsyncGenerator[str, None]:
        """Streaming translation via SSE — yields tokens one by one."""
        model_id = self._select_model(src_lang, tgt_lang)
        prompt = self._build_prompt(text, src_lang, tgt_lang, context)

        if not self.hf_token:
            # Fallback: simulate streaming from blocking call
            result = self.translate(text, src_lang, tgt_lang, context)
            for word in result.split(" "):
                yield word + " "
                await asyncio.sleep(0.03)
            return

        # Real streaming from HF API
        for token in self.client.text_generation(
            prompt,
            model=model_id,
            max_new_tokens=512,
            temperature=0.1,
            repetition_penalty=1.05,
            stream=True,
            stop_sequences=["<|im_end|>", "<|eot_id|>"],
        ):
            yield token
            await asyncio.sleep(0)  # yield control


# ═══════════════════════════════════════════════════════════════════
# 3. Conversation Memory (LangChain)
# ═══════════════════════════════════════════════════════════════════

class ConversationStore:
    """
    Per-session conversation memory using LangChain's
    ConversationBufferWindowMemory. Keeps last N turns.
    """

    def __init__(self, window: int = 10):
        self._sessions: Dict[str, ConversationBufferWindowMemory] = {}
        self.window = window

    def get(self, session_id: str) -> ConversationBufferWindowMemory:
        if session_id not in self._sessions:
            self._sessions[session_id] = ConversationBufferWindowMemory(
                k=self.window, return_messages=True
            )
        return self._sessions[session_id]

    def add(self, session_id: str, human: str, ai: str):
        mem = self.get(session_id)
        mem.save_context({"input": human}, {"output": ai})

    def history(self, session_id: str) -> List[Dict]:
        mem = self.get(session_id)
        messages = mem.chat_memory.messages
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
        self._setup()

    def _setup(self):
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
        if self._index is None:
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
        Returns full string (stream=False) or async generator (stream=True).
        """
        # 1. Detect source language
        detection = self.detector.detect_with_confidence(message)
        src_lang   = detection["lang"]

        # If already in target language, no translation needed
        if src_lang == target_lang:
            reply = f"[Already in {LANG_NAMES.get(target_lang, target_lang)}] {message}"
            self.memory.add(session_id, message, reply)
            if stream:
                async def _passthrough():
                    yield reply
                return _passthrough()
            return reply

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
        "endpoints": ["/chat", "/chat/stream", "/detect", "/history",
                      "/kb/add", "/health"],
    }


@app.post("/detect")
def detect_language(req: DetectRequest):
    """Detect language of input text."""
    return chatbot.detector.detect_with_confidence(req.text)


@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Non-streaming translation endpoint.
    Returns full translation with metadata.
    """
    if not req.message.strip():
        raise HTTPException(400, "Message cannot be empty")

    result = await chatbot.respond(
        req.session_id, req.message, req.target_lang, stream=False
    )
    return {
        **result,
        "session_id": req.session_id,
        "timestamp":  datetime.utcnow().isoformat(),
    }


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

    # Send metadata header first, then stream tokens
    async def event_generator():
        # First event: metadata
        meta = json.dumps({
            "type":       "meta",
            "src_lang":   src_lang,
            "src_name":   detection["name"],
            "confidence": detection["confidence"],
            "tgt_lang":   req.target_lang,
        })
        yield f"data: {meta}\n\n"

        # Stream translation tokens
        if src_lang == req.target_lang:
            yield f"data: {json.dumps({'type': 'token', 'text': req.message})}\n\n"
        else:
            context = chatbot.kb.retrieve(req.message) if chatbot.kb.ready else ""
            async for token in chatbot.engine.translate_stream(
                req.message, src_lang, req.target_lang, context
            ):
                payload = json.dumps({"type": "token", "text": token})
                yield f"data: {payload}\n\n"
                await asyncio.sleep(0)

        # Done event
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
        "kb_ready":        chatbot.kb.ready,
        "hf_api":          bool(os.getenv("HF_TOKEN")),
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
    # Start Telegram bot in background if token provided
    asyncio.create_task(setup_telegram())


if __name__ == "__main__":
    uvicorn.run("chatbot_backend:app", host="0.0.0.0", port=8000, reload=True)