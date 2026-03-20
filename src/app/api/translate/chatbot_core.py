import asyncio
import importlib
import os
import re
from collections import OrderedDict
from pathlib import Path
from threading import Thread
from typing import Any, AsyncGenerator, Dict, List, Optional

from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import HumanMessage

from language_tools import LANG_NAMES, LanguageDetector
from translation_config import (
    ASSISTANT_PROMPT_TEMPLATE,
    ASSISTANT_MAX_NEW_TOKENS,
    ATLAS_COLLECTION_NAME,
    ATLAS_DB_NAME,
    ATLAS_EMBEDDING_FIELD,
    ATLAS_METADATA_FIELD,
    ATLAS_RAG_NUM_CANDIDATES,
    ATLAS_RAG_TOP_K,
    ATLAS_SOURCE_FIELD,
    ATLAS_TEXT_FIELD,
    ATLAS_URI,
    ATLAS_USE_VECTOR_SEARCH,
    ATLAS_VECTOR_INDEX,
    LAZY_LOAD_MODEL,
    LOCAL_MODELS,
    MAX_TRANSLATION_TOKENS,
    MODEL_QUANTIZATION,
    SOFT_MAX_ASSISTANT_TOKENS,
    SOFT_MAX_TRANSLATION_TOKENS,
    STREAM_CHUNK_DELAY,
    TRANSLATION_PROMPT_TEMPLATE,
    TRANSLATION_PROMPT_TEMPLATES,
    TRANSLATION_CACHE_SIZE,
    USE_ATLAS_KB,
    USE_KB,
    logger,
)


def check_model_cache(model_name: str) -> bool:
    """Check if a HuggingFace model is already cached locally."""
    cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
    model_folder = "models--" + model_name.replace("/", "--")
    model_path = cache_dir / model_folder

    if model_path.exists():
        total_size = sum(f.stat().st_size for f in model_path.rglob("*") if f.is_file())
        size_str = (
            f"{total_size / (1024**3):.2f} GB"
            if total_size > 1024**3
            else f"{total_size / (1024**2):.0f} MB"
        )
        logger.info(f"Cache found: {model_name} ({size_str})")
        return True

    logger.info(f"Will download: {model_name}")
    return False


def log_cache_status() -> None:
    """Log cache status for all models used in this app."""
    logger.info("=" * 50)
    logger.info("Checking model cache...")

    models = [
        "sail/Sailor2-1B-Chat",
        "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    ]

    cached = sum(1 for m in models if check_model_cache(m))
    logger.info(f"{cached}/{len(models)} models cached")
    logger.info("=" * 50)


class TranslationEngine:
    """Translation using local Sailor2 model."""

    def __init__(self):
        self._tokenizer = None
        self._model = None
        self._model_name = None
        self._device = "cpu"
        self._quantization = "none"
        self._cache: OrderedDict[tuple[str, str, str, str], str] = OrderedDict()
        if LAZY_LOAD_MODEL:
            logger.info("Lazy model loading enabled; model will load on first request")
        else:
            self._load_local()

    def ensure_model_loaded(self) -> None:
        if self._model is None or self._tokenizer is None:
            self._load_local()

    def _load_local(self) -> None:
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer

            use_large = os.getenv("USE_LARGE_MODEL", "0") == "1"
            has_gpu = torch.cuda.is_available()

            if use_large and has_gpu:
                self._model_name = LOCAL_MODELS["large"]
                logger.info(f"Loading large model: {self._model_name} (GPU)")
            else:
                self._model_name = LOCAL_MODELS["small"]
                logger.info(f"Loading small model: {self._model_name} (CPU/GPU)")

            self._device = "cuda" if has_gpu else "cpu"
            logger.info(f"Device: {self._device}")

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
            logger.info(f"Sailor2 loaded successfully: {self._model_name}")
            logger.info(f"Quantization mode: {self._quantization}")
        except Exception as exc:
            logger.error(f"Local model load failed: {exc}")

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
            return "[Translation unavailable - model not loaded]"

        inputs = self._tokenizer(prompt, return_tensors="pt")
        if self._device == "cpu":
            inputs = {key: value.to(self._device) for key, value in inputs.items()}

        with torch.inference_mode():
            output = self._model.generate(
                **inputs,
                **self._build_generation_kwargs(max_new_tokens),
            )

        generated_tokens = output[0][inputs["input_ids"].shape[1] :]
        return self._tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()

    def _clean_translation(self, text: str) -> str:
        cleaned = text.strip()
        for stop in ["<|im_end|>", "<|im_start|>", "\n\n\n"]:
            if stop in cleaned:
                cleaned = cleaned.split(stop)[0].strip()
        return cleaned

    def _get_cached_translation(self, text: str, src_lang: str, tgt_lang: str, context: str) -> Optional[str]:
        cache_key = (text, src_lang, tgt_lang, context)
        cached = self._cache.get(cache_key)
        if cached is not None:
            self._cache.move_to_end(cache_key)
        return cached

    def _set_cached_translation(self, text: str, src_lang: str, tgt_lang: str, context: str, translation: str) -> None:
        cache_key = (text, src_lang, tgt_lang, context)
        self._cache[cache_key] = translation
        self._cache.move_to_end(cache_key)
        if len(self._cache) > TRANSLATION_CACHE_SIZE:
            self._cache.popitem(last=False)

    def _build_prompt(self, text: str, src_lang: str, tgt_lang: str, context: str = "") -> str:
        src_name = LANG_NAMES.get(src_lang, src_lang)
        tgt_name = LANG_NAMES.get(tgt_lang, tgt_lang)
        full_text = text
        if context:
            full_text = f"[Reference]\n{context}\n\n[Text to translate]\n{text}"
        pair_template = TRANSLATION_PROMPT_TEMPLATES.get((src_lang, tgt_lang))
        if pair_template is not None:
            return pair_template.format(text=full_text)
        return TRANSLATION_PROMPT_TEMPLATE.format(src_name=src_name, tgt_name=tgt_name, text=full_text)

    def _build_assistant_prompt(self, message: str, target_lang: str, context: str = "") -> str:
        _ = target_lang  # kept for backward compatibility with existing call sites
        context_block = ""
        if context:
            context_block = f"<official_context>\n{context}\n</official_context>\n\n"
        return ASSISTANT_PROMPT_TEMPLATE.format(context_block=context_block, message=message)

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
        except Exception as exc:
            logger.error(f"Assistant generation error: {exc}")
            return "I can help, but I hit an internal generation error. Please try again."

    def translate(self, text: str, src_lang: str, tgt_lang: str, context: str = "") -> str:
        self.ensure_model_loaded()

        cached = self._get_cached_translation(text, src_lang, tgt_lang, context)
        if cached is not None:
            return cached

        prompt = self._build_prompt(text, src_lang, tgt_lang, context)
        max_new_tokens = self._estimate_max_new_tokens(text)

        if self._model and self._tokenizer:
            try:
                result = self._clean_translation(self._generate_text(prompt, max_new_tokens))
                self._set_cached_translation(text, src_lang, tgt_lang, context, result)
                return result
            except Exception as exc:
                logger.error(f"Translation error: {exc}")
                return f"[Translation error: {str(exc)}]"

        return "[Translation unavailable - model not loaded]"

    async def translate_stream(self, text: str, src_lang: str, tgt_lang: str, context: str = "") -> AsyncGenerator[str, None]:
        self.ensure_model_loaded()

        cached = self._get_cached_translation(text, src_lang, tgt_lang, context)
        if cached is not None:
            for chunk in cached.split(" "):
                if chunk:
                    yield chunk + " "
                    await asyncio.sleep(STREAM_CHUNK_DELAY)
            return

        if self._tokenizer is None or self._model is None:
            yield "[Translation unavailable - model not loaded]"
            return

        try:
            from transformers import TextIteratorStreamer

            prompt = self._build_prompt(text, src_lang, tgt_lang, context)
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
        except Exception as exc:
            logger.error(f"Streaming translation error: {exc}")
            yield f"[Translation error: {str(exc)}]"


class ConversationStore:
    """Per-session conversation memory using ChatMessageHistory."""

    def __init__(self, window: int = 10):
        self._sessions: Dict[str, ChatMessageHistory] = {}
        self.window = window

    def get(self, session_id: str) -> ChatMessageHistory:
        if session_id not in self._sessions:
            self._sessions[session_id] = ChatMessageHistory()
        return self._sessions[session_id]

    def add(self, session_id: str, human: str, ai: str) -> None:
        mem = self.get(session_id)
        mem.add_user_message(human)
        mem.add_ai_message(ai)
        if len(mem.messages) > self.window * 2:
            mem.messages = mem.messages[-(self.window * 2) :]

    def history(self, session_id: str) -> List[Dict[str, str]]:
        mem = self.get(session_id)
        result: List[Dict[str, str]] = []
        for m in mem.messages:
            role = "user" if isinstance(m, HumanMessage) else "assistant"
            result.append({"role": role, "content": m.content})
        return result

    def clear(self, session_id: str) -> None:
        if session_id in self._sessions:
            self._sessions[session_id].clear()

    def active_sessions(self) -> int:
        return len(self._sessions)


class KnowledgeBase:
    """LlamaIndex-powered RAG store for domain glossaries and FAQ docs."""

    def __init__(
        self,
        index_path: str = "./kb_index",
        embed_model: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    ):
        self.index_path = index_path
        self.embed_model_id = embed_model
        self._index = None
        self._atlas_client = None
        self._atlas_collection = None
        self._atlas_embedder = None
        self._atlas_enabled = USE_ATLAS_KB
        self._atlas_ready = False
        self._atlas_use_vector = ATLAS_USE_VECTOR_SEARCH
        self.enabled = USE_KB
        self._setup_atlas()
        if self.enabled:
            self._setup()
        else:
            logger.info("Knowledge base disabled (USE_KB=0)")

    def _setup_atlas(self) -> None:
        if not self._atlas_enabled:
            logger.info("MongoDB Atlas KB disabled (USE_ATLAS_KB=0)")
            return

        if not ATLAS_URI or not ATLAS_DB_NAME:
            logger.warning("MongoDB Atlas KB enabled but MONGODB_ATLAS_URI / MONGODB_ATLAS_DB missing")
            return

        try:
            pymongo = importlib.import_module("pymongo")
            mongo_client = pymongo.MongoClient

            self._atlas_client = mongo_client(ATLAS_URI, appname="sea-translation-rag")
            self._atlas_client.admin.command("ping")
            db = self._atlas_client[ATLAS_DB_NAME]
            self._atlas_collection = db[ATLAS_COLLECTION_NAME]
            self._atlas_ready = True
            logger.info(f"MongoDB Atlas KB connected: {ATLAS_DB_NAME}.{ATLAS_COLLECTION_NAME}")

            if self._atlas_use_vector:
                try:
                    from llama_index.embeddings.huggingface import HuggingFaceEmbedding

                    self._atlas_embedder = HuggingFaceEmbedding(model_name=self.embed_model_id)
                    logger.info("Atlas query embedder ready")
                except Exception as exc:
                    self._atlas_use_vector = False
                    logger.warning(f"Atlas vector embedder unavailable, fallback to keyword search: {exc}")
        except Exception as exc:
            self._atlas_ready = False
            logger.warning(f"Atlas setup failed: {exc}")

    def _atlas_format_context(self, docs: List[Dict[str, Any]]) -> str:
        chunks: List[str] = []
        logger.info(f"📚 RAG: Found {len(docs)} document(s) from Atlas KB")
        
        for idx, doc in enumerate(docs, 1):
            text = str(doc.get(ATLAS_TEXT_FIELD, "")).strip()
            if not text:
                continue

            source = str(doc.get(ATLAS_SOURCE_FIELD, "")).strip()
            score_raw = doc.get("score")
            score = ""
            if isinstance(score_raw, (float, int)):
                score = f" (score: {score_raw:.4f})"

            # Log each document's information
            text_preview = text[:100].replace('\n', ' ') + ('...' if len(text) > 100 else '')
            logger.info(f"  [{idx}] {source}{score}")
            logger.info(f"       Content: {text_preview}")

            prefix = f"[{idx}]"
            if source:
                prefix += f" {source}"
            chunks.append(f"{prefix}{score}\n{text}")

        return "\n---\n".join(chunks)

    def _atlas_keyword_query(self, query: str) -> Dict[str, Any]:
        tokens = [t for t in re.findall(r"\w+", query.lower(), flags=re.UNICODE) if len(t) >= 3][:6]

        if tokens:
            return {
                "$or": [
                    {ATLAS_TEXT_FIELD: {"$regex": re.escape(t), "$options": "i"}}
                    for t in tokens
                ]
            }

        fallback = query.strip()[:80]
        if not fallback:
            return {}
        return {ATLAS_TEXT_FIELD: {"$regex": re.escape(fallback), "$options": "i"}}

    def _atlas_retrieve(self, query: str, top_k: int = 3) -> str:
        if not self._atlas_ready or self._atlas_collection is None:
            return ""

        limit = max(1, min(top_k, 10))
        logger.info(f"🔍 RAG: Query: '{query}' (limit={limit})")

        # Try vector search first
        if self._atlas_use_vector and self._atlas_embedder is not None:
            try:
                logger.info(f"🔍 RAG: Attempting vector search using index '{ATLAS_VECTOR_INDEX}'...")
                query_vector = self._atlas_embedder.get_text_embedding(query)
                pipeline = [
                    {
                        "$vectorSearch": {
                            "index": ATLAS_VECTOR_INDEX,
                            "path": ATLAS_EMBEDDING_FIELD,
                            "queryVector": query_vector,
                            "numCandidates": max(limit, ATLAS_RAG_NUM_CANDIDATES),
                            "limit": limit,
                        }
                    },
                    {
                        "$project": {
                            "_id": 0,
                            ATLAS_TEXT_FIELD: 1,
                            ATLAS_SOURCE_FIELD: 1,
                            "score": {"$meta": "vectorSearchScore"},
                        }
                    },
                ]
                docs = list(self._atlas_collection.aggregate(pipeline))
                if docs:
                    logger.info(f"✅ RAG: Vector search successful! Retrieved {len(docs)} document(s)")
                    return self._atlas_format_context(docs)
                else:
                    logger.info(f"❌ RAG: Vector search returned no results")
            except Exception as exc:
                logger.warning(f"⚠️  RAG: Vector retrieval failed, fallback to keyword search: {exc}")

        # Fallback to keyword search
        try:
            logger.info(f"🔍 RAG: Attempting keyword search...")
            projection = {"_id": 0, ATLAS_TEXT_FIELD: 1, ATLAS_SOURCE_FIELD: 1}
            query_obj = self._atlas_keyword_query(query)
            docs = list(self._atlas_collection.find(query_obj, projection).limit(limit))
            if docs:
                logger.info(f"✅ RAG: Keyword search successful! Retrieved {len(docs)} document(s)")
                return self._atlas_format_context(docs)
            else:
                logger.info(f"❌ RAG: Keyword search returned no results")
        except Exception as exc:
            logger.warning(f"⚠️  RAG: Keyword retrieval failed: {exc}")

        logger.info(f"❌ RAG: No documents found for query")
        return ""

    def _setup(self) -> None:
        if not self.enabled:
            return

        try:
            from llama_index.core import Settings
            from llama_index.embeddings.huggingface import HuggingFaceEmbedding

            settings = Settings
            settings.embed_model = HuggingFaceEmbedding(model_name=self.embed_model_id)
            settings.llm = None

            if os.path.exists(self.index_path):
                from llama_index.core import StorageContext, load_index_from_storage

                ctx = StorageContext.from_defaults(persist_dir=self.index_path)
                self._index = load_index_from_storage(ctx)
                logger.info("Knowledge base loaded from disk")
        except Exception as exc:
            logger.warning(f"KB setup: {exc}")

    def add_documents(self, docs: List[Dict[str, Any]]) -> None:
        atlas_added = 0
        if self._atlas_ready and self._atlas_collection is not None:
            atlas_docs: List[Dict[str, Any]] = []
            for doc in docs:
                text = str(doc.get("text", "")).strip()
                if not text:
                    continue

                metadata = doc.get("metadata", {}) if isinstance(doc.get("metadata", {}), dict) else {}
                atlas_doc: Dict[str, Any] = {
                    ATLAS_TEXT_FIELD: text,
                    ATLAS_METADATA_FIELD: metadata,
                    ATLAS_SOURCE_FIELD: metadata.get("source") or metadata.get("title") or "kb_document",
                }
                if self._atlas_use_vector and self._atlas_embedder is not None:
                    try:
                        atlas_doc[ATLAS_EMBEDDING_FIELD] = self._atlas_embedder.get_text_embedding(text)
                    except Exception as exc:
                        logger.warning(f"Atlas embedding failed for one document: {exc}")
                atlas_docs.append(atlas_doc)

            if atlas_docs:
                self._atlas_collection.insert_many(atlas_docs, ordered=False)
                atlas_added = len(atlas_docs)
                logger.info(f"Added {len(atlas_docs)} documents to MongoDB Atlas knowledge base")

        if not self.enabled:
            if self._atlas_ready:
                if atlas_added == 0:
                    logger.info("Atlas KB connected but no valid documents were provided")
                return
            raise RuntimeError("Knowledge base is disabled. Set USE_KB=1 or USE_ATLAS_KB=1 to enable it.")

        from llama_index.core import Document, VectorStoreIndex

        os.makedirs(self.index_path, exist_ok=True)
        llama_docs = [Document(text=d["text"], metadata=d.get("metadata", {})) for d in docs]
        if self._index is None:
            self._index = VectorStoreIndex.from_documents(llama_docs)
        else:
            for doc in llama_docs:
                self._index.insert(doc)
        self._index.storage_context.persist(persist_dir=self.index_path)
        logger.info(f"Added {len(docs)} documents to knowledge base")

    def retrieve(self, query: str, top_k: int = ATLAS_RAG_TOP_K) -> str:
        if not query.strip():
            return ""
        
        logger.info(f"\n{'='*60}")
        logger.info(f"RAG RETRIEVAL STARTED")
        logger.info(f"{'='*60}")
        logger.info(f"Query: '{query}'")
        
        atlas_context = self._atlas_retrieve(query, top_k=top_k)
        if atlas_context:
            logger.info(f"\n✅ RAG Context prepared successfully")
            logger.info(f"{'='*60}\n")
            return atlas_context
        
        logger.info(f"\n⚠️  Falling back to local knowledge base...")
        if not self.enabled or self._index is None:
            logger.info(f"❌ Local KB not available")
            logger.info(f"{'='*60}\n")
            return ""

        try:
            retriever = self._index.as_retriever(similarity_top_k=top_k)
            nodes = retriever.retrieve(query)
            if nodes:
                logger.info(f"✅ Local KB: Found {len(nodes)} document(s)")
                context = "\n---\n".join(n.text for n in nodes)
                logger.info(f"{'='*60}\n")
                return context
            else:
                logger.info(f"❌ Local KB: No documents found")
                logger.info(f"{'='*60}\n")
                return ""
        except Exception as exc:
            logger.warning(f"Local KB retrieval error: {exc}")
            logger.info(f"{'='*60}\n")
            return ""

    @property
    def ready(self) -> bool:
        return self._atlas_ready or (self._index is not None)


class SEAChatbot:
    """Unified chatbot that combines detection, RAG, translation, and memory."""

    def __init__(self):
        self.detector = LanguageDetector()
        self.engine = TranslationEngine()
        self.memory = ConversationStore(window=10)
        self.kb = KnowledgeBase()

    async def respond(
        self,
        session_id: str,
        message: str,
        target_lang: str = "en",
        stream: bool = False,
    ) -> Any:
        detection = self.detector.detect_with_confidence(message)
        src_lang = detection["lang"]

        if src_lang == target_lang:
            reply = message
            self.memory.add(session_id, message, reply)
            if stream:

                async def _passthrough():
                    yield reply

                return _passthrough()
            return {
                "translation": reply,
                "src_lang": src_lang,
                "src_name": detection["name"],
                "confidence": detection["confidence"],
                "tgt_lang": target_lang,
                "tgt_name": LANG_NAMES.get(target_lang, target_lang),
                "same_lang": True,
            }

        context = self.kb.retrieve(message) if self.kb.ready else ""

        if stream:

            async def _stream_and_save():
                full = []
                async for token in self.engine.translate_stream(message, src_lang, target_lang, context):
                    full.append(token)
                    yield token
                self.memory.add(session_id, message, "".join(full))

            return _stream_and_save()

        translation = self.engine.translate(message, src_lang, target_lang, context)
        self.memory.add(session_id, message, translation)
        return {
            "translation": translation,
            "src_lang": src_lang,
            "src_name": detection["name"],
            "confidence": detection["confidence"],
            "tgt_lang": target_lang,
            "tgt_name": LANG_NAMES.get(target_lang, target_lang),
        }


async def setup_telegram(chatbot: SEAChatbot) -> Any:
    """Telegram bot that uses the same chatbot core."""
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.info("TELEGRAM_TOKEN not set - Telegram bot disabled")
        return None

    try:
        from telegram import Update
        from telegram.ext import (
            Application,
            CommandHandler,
            ContextTypes,
            MessageHandler,
            filters,
        )
    except ImportError:
        logger.warning("python-telegram-bot not installed. Run: pip install python-telegram-bot")
        return None

    tg_app = Application.builder().token(token).build()

    async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "SEA Translation Bot\n\n"
            "Send me any text in a SEA language and I'll translate it to English.\n"
            "Use /lang <code> to change target language (e.g. /lang ms)\n\n"
            "Supported: en, ms, id, th, vi, zh, ta, tl, my, km, lo",
        )

    async def set_lang(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if ctx.args:
            ctx.user_data["target_lang"] = ctx.args[0]
            name = LANG_NAMES.get(ctx.args[0], ctx.args[0])
            await update.message.reply_text(f"Target language set to: {name}")
        else:
            await update.message.reply_text("Usage: /lang <code>  e.g. /lang ms")

    async def translate_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        session_id = f"tg_{update.effective_user.id}"
        target_lang = ctx.user_data.get("target_lang", "en")

        await update.message.chat.send_action("typing")

        result = await chatbot.respond(session_id, text, target_lang, stream=False)

        if isinstance(result, dict):
            reply = (
                f"{result['src_name']} -> {result['tgt_name']}\n\n"
                f"{result['translation']}\n\n"
                f"Confidence: {result['confidence']:.0%}"
            )
        else:
            reply = str(result)

        await update.message.reply_text(reply)

    async def clear_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        session_id = f"tg_{update.effective_user.id}"
        chatbot.memory.clear(session_id)
        await update.message.reply_text("Conversation history cleared.")

    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CommandHandler("lang", set_lang))
    tg_app.add_handler(CommandHandler("clear", clear_cmd))
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, translate_msg))

    logger.info("Telegram bot starting (polling)...")
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling()
    logger.info("Telegram bot is running")
    return tg_app
