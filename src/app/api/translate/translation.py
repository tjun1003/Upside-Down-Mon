"""
SEA Translation Chatbot backend entrypoint.

This file now focuses on FastAPI routing and startup wiring.
Core logic is split into smaller modules:
- translation_config.py
- language_tools.py
- chatbot_core.py
- app_models.py
"""

import asyncio
import json
import os
import re

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from app_models import ChatRequest, ClearRequest, DetectRequest, KBAddRequest
from chatbot_core import SEAChatbot, log_cache_status, setup_telegram
from language_tools import (
    build_assistant_reply,
    infer_lang_by_script,
    resolve_response_lang,
)
from rag_service import RAGService
from translation_config import (
    ATLAS_COLLECTION_NAME,
    ATLAS_DB_NAME,
    ATLAS_RAG_TOP_K,
    ATLAS_TEXT_FIELD,
    LANG_NAMES,
    MULTI_OUTPUT_LANGS,
    STARTUP_CHECK_CACHE,
    STREAM_CHUNK_DELAY,
    USE_ATLAS_KB,
    UVICORN_RELOAD,
    logger,
)

try:
    from db import (
        MongoConversationStore,
        MongoKnowledgeBase,
        close_mongo,
        init_mongo,
    )

    DB_INTEGRATION_AVAILABLE = True
except Exception as exc:  # pragma: no cover - optional dependency at runtime
    MongoConversationStore = None  # type: ignore[assignment]
    MongoKnowledgeBase = None  # type: ignore[assignment]
    close_mongo = None  # type: ignore[assignment]
    init_mongo = None  # type: ignore[assignment]
    DB_INTEGRATION_AVAILABLE = False
    logger.warning(f"Mongo integration disabled: {exc}")


EMPTY_ASSISTANT_FALLBACK_EN = (
    "I can help with this. Please share a bit more detail so I can guide you accurately."
)
EMPTY_ASSISTANT_FALLBACK_ZH = "我可以帮你。你可以再告诉我你的申请对象、行业和预算范围吗？我会给你一份更具体的申请步骤。"


app = FastAPI(
    title="SEA Translation Chatbot API",
    description="Real-time multilingual translation for SEA languages",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

chatbot = SEAChatbot()
mongo_conversation_store = None
mongo_kb_store = None
rag_service = RAGService(
    default_kb=chatbot.kb,
    logger=logger,
    top_k=ATLAS_RAG_TOP_K,
    text_field=ATLAS_TEXT_FIELD,
)


def summarize_for_rag(english_text: str, max_chars: int = 420) -> str:
    """Build a compact English retrieval query from long user text."""
    text = re.sub(r"\s+", " ", english_text or "").strip()
    if not text:
        return ""

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if not sentences:
        return text[:max_chars]

    # Keep the lead sentence and one informative sentence for better recall.
    lead = sentences[0]
    best = ""
    for s in sentences[1:]:
        if len(s) > len(best):
            best = s

    summary = lead if not best else f"{lead} {best}"
    summary = re.sub(r"\s+", " ", summary).strip()
    if len(summary) > max_chars:
        summary = summary[:max_chars].rsplit(" ", 1)[0].strip()

    return summary or text[:max_chars]


def build_independent_translations(
    base_text: str,
    base_lang: str = "en",
    target_langs_override: list[str] | None = None,
) -> dict[str, str]:
    """Translate one source text into multiple target languages independently."""
    results: dict[str, str] = {}
    source = (base_text or "").strip()
    if not source:
        return results

    target_langs = [lang for lang in (target_langs_override or MULTI_OUTPUT_LANGS) if lang]
    if not target_langs:
        target_langs = ["en", "zh", "ms", "id"]

    for lang in target_langs:
        try:
            if lang == base_lang:
                results[lang] = source
            else:
                translated = chatbot.engine.translate(source, base_lang, lang, "")
                results[lang] = translated
        except Exception as exc:
            logger.warning(f"Independent translation failed for {lang}: {exc}")

    return results


async def persist_conversation(session_id: str, message: str, reply: str) -> None:
    """Persist chat messages to Mongo when available; fallback to in-memory store."""
    global mongo_conversation_store

    if mongo_conversation_store is not None:
        try:
            await mongo_conversation_store.add(session_id, message, reply)
            return
        except Exception as exc:
            logger.warning(f"Mongo conversation write failed, using memory fallback: {exc}")

    chatbot.memory.add(session_id, message, reply)


@app.get("/")
def root():
    return {
        "service": "SEA Translation Chatbot",
        "version": "1.0.0",
        "endpoints": ["/chat/stream", "/detect", "/history", "/kb/add", "/health"],
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
    """Streaming translation via Server-Sent Events (SSE)."""
    if not req.message.strip():
        raise HTTPException(400, "Message cannot be empty")

    message = req.message
    logger.info(f"chat_stream: session={req.session_id}, assistant_mode={req.assistant_mode}")

    detection = chatbot.detector.detect_with_confidence(message)
    src_lang = detection["lang"]
    script_lang = infer_lang_by_script(message)
    if script_lang is not None:
        src_lang = script_lang

    # In auto mode, prioritize the visible script in user input to keep language aligned.
    auto_mode = (req.target_lang or "auto").strip().lower() == "auto"
    if auto_mode and script_lang is not None:
        response_lang = script_lang
    elif auto_mode and src_lang == "en" and float(detection.get("confidence", 0.0)) < 0.2:
        has_non_ascii = any(ord(ch) > 127 for ch in message)
        response_lang = "zh" if has_non_ascii else "en"
    else:
        response_lang = resolve_response_lang(src_lang, req.target_lang)

    async def emit_text_as_tokens(text: str):
        for chunk in text.split(" "):
            if not chunk:
                continue
            payload = json.dumps({"type": "token", "text": chunk + " "})
            yield f"data: {payload}\n\n"
            await asyncio.sleep(STREAM_CHUNK_DELAY)

    async def event_generator():
        meta = json.dumps(
            {
                "type": "meta",
                "src_lang": src_lang,
                "src_name": LANG_NAMES.get(src_lang, detection["name"]),
                "confidence": detection["confidence"],
                "tgt_lang": response_lang,
            }
        )
        yield f"data: {meta}\n\n"

        if req.assistant_mode:
            rule_reply_en = build_assistant_reply(message)
            if rule_reply_en is not None:
                english_reply = rule_reply_en
            else:
                pivot_en = message
                if src_lang != "en":
                    logger.info(f"Assistant pipeline: translating source {src_lang} -> en")
                    pivot_en = chatbot.engine.translate(message, src_lang, "en", "")
                    if not pivot_en.strip() or pivot_en.startswith("["):
                        pivot_en = message

                summary_en = summarize_for_rag(pivot_en)
                rag_query_en = summary_en or pivot_en

                logger.info("Assistant pipeline: retrieving RAG context")
                raw_context = await rag_service.retrieve_context(rag_query_en)
                context_en = raw_context
                if raw_context.strip():
                    context_lang = chatbot.detector.detect(raw_context)
                    if context_lang != "en":
                        logger.info(f"Assistant pipeline: translating context {context_lang} -> en")
                        translated_context = chatbot.engine.translate(raw_context, context_lang, "en", "")
                        if translated_context.strip() and not translated_context.startswith("["):
                            context_en = translated_context

                generation_prompt_en = (
                    f"User request (English normalized):\n{pivot_en}\n\n"
                    f"Retrieval summary for search:\n{rag_query_en}\n\n"
                    "Please answer in English using clean Markdown (headings/lists/table when useful). "
                    "Give direct guidance first, then practical next steps."
                )
                english_reply = chatbot.engine.generate_assistant_reply(
                    generation_prompt_en,
                    "en",
                    context_en,
                )

            if not english_reply.strip():
                english_reply = EMPTY_ASSISTANT_FALLBACK_EN

            override_langs = req.independent_langs if req.independent_langs else None
            translations = build_independent_translations(
                english_reply,
                base_lang="en",
                target_langs_override=override_langs,
            )
            translations_event = json.dumps({"type": "translations", "data": translations})
            yield f"data: {translations_event}\n\n"

            final_output_lang = src_lang if src_lang in LANG_NAMES else response_lang
            if final_output_lang == "en":
                final_reply = english_reply
            else:
                final_reply = chatbot.engine.translate(
                    english_reply,
                    "en",
                    final_output_lang,
                    "",
                )
            logger.info(
                "Assistant pipeline: final output translated to user language, "
                f"lang={final_output_lang}"
            )

            if not final_reply.strip():
                if response_lang == "zh":
                    final_reply = EMPTY_ASSISTANT_FALLBACK_ZH
                elif response_lang == "en":
                    final_reply = EMPTY_ASSISTANT_FALLBACK_EN
                else:
                    final_reply = chatbot.engine.translate(
                        EMPTY_ASSISTANT_FALLBACK_EN,
                        "en",
                        response_lang,
                        "",
                    )
                if not final_reply.strip():
                    final_reply = EMPTY_ASSISTANT_FALLBACK_EN

            async for event in emit_text_as_tokens(final_reply):
                yield event
        else:
            async for token in chatbot.engine.translate_stream(
                message,
                src_lang,
                req.target_lang,
                "",
            ):
                payload = json.dumps({"type": "token", "text": token})
                yield f"data: {payload}\n\n"
                await asyncio.sleep(0)
            final_reply = chatbot.engine.translate(message, src_lang, req.target_lang, "")

        await persist_conversation(req.session_id, message, final_reply)
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/history/{session_id}")
async def get_history(session_id: str):
    if mongo_conversation_store is not None:
        try:
            docs = await mongo_conversation_store.history(session_id)
            history = [
                {
                    "role": "assistant" if d.get("role") == "ai" else d.get("role", "assistant"),
                    "content": d.get("text", ""),
                }
                for d in docs
            ]
            return {"session_id": session_id, "history": history}
        except Exception as exc:
            logger.warning(f"Mongo history read failed, using memory fallback: {exc}")

    return {"session_id": session_id, "history": chatbot.memory.history(session_id)}


@app.post("/history/clear")
async def clear_history(req: ClearRequest):
    if mongo_conversation_store is not None:
        try:
            await mongo_conversation_store.clear(req.session_id)
        except Exception as exc:
            logger.warning(f"Mongo history clear failed: {exc}")

    chatbot.memory.clear(req.session_id)
    return {"cleared": True, "session_id": req.session_id}


@app.post("/kb/add")
async def add_to_kb(req: KBAddRequest):
    await rag_service.add_documents(req.documents)
    return {"added": len(req.documents), "kb_ready": chatbot.kb.ready}


@app.get("/health")
async def health():
    active_sessions = chatbot.memory.active_sessions()
    if mongo_conversation_store is not None:
        try:
            active_sessions = await mongo_conversation_store.active_sessions()
        except Exception as exc:
            logger.warning(f"Mongo active session count failed, using memory fallback: {exc}")

    return {
        "status": "ok",
        "active_sessions": active_sessions,
        "kb_enabled": chatbot.kb.enabled,
        "kb_ready": chatbot.kb.ready,
        "atlas_kb_enabled": USE_ATLAS_KB,
        "atlas_kb_ready": chatbot.kb._atlas_ready,
        "atlas_db": ATLAS_DB_NAME,
        "atlas_collection": ATLAS_COLLECTION_NAME,
        "atlas_vector_search": chatbot.kb._atlas_use_vector,
        "model": chatbot.engine._model_name,
        "model_loaded": chatbot.engine._model is not None,
        "streaming": True,
        "quantization": chatbot.engine._quantization,
        "mongo_integration_available": DB_INTEGRATION_AVAILABLE,
        "mongo_connected": mongo_conversation_store is not None,
    }


@app.get("/webhook/whatsapp")
async def whatsapp_verify(request: Request):
    """WhatsApp webhook verification handshake."""
    params = dict(request.query_params)
    verify = os.getenv("WHATSAPP_VERIFY_TOKEN", "sea_translate_token")
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
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
            text = msg["text"]["body"]
            phone = msg["from"]
            session_id = f"wa_{phone}"

            result = await chatbot.respond(session_id, text, "en", stream=False)
            if isinstance(result, dict):
                reply = f"[{result['src_name']} -> {result['tgt_name']}]\n{result['translation']}"
            else:
                reply = str(result)

            wa_token = os.getenv("WHATSAPP_TOKEN")
            phone_id = os.getenv("WHATSAPP_PHONE_ID")
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
        except Exception as exc:
            logger.error(f"WhatsApp webhook error: {exc}")

    background.add_task(process)
    return {"status": "ok"}


@app.on_event("startup")
async def on_startup():
    global mongo_conversation_store, mongo_kb_store

    logger.info("SEA Translation Chatbot starting...")
    if STARTUP_CHECK_CACHE:
        log_cache_status()
    else:
        logger.info("Skipping cache status scan (set STARTUP_CHECK_CACHE=1 to enable)")

    if DB_INTEGRATION_AVAILABLE and init_mongo is not None:
        try:
            await init_mongo(app)
            db = getattr(app.state, "mongodb", None)
            if db is not None and MongoConversationStore is not None and MongoKnowledgeBase is not None:
                mongo_conversation_store = MongoConversationStore(db)
                mongo_kb_store = MongoKnowledgeBase(db)
                rag_service.set_mongo_store(mongo_kb_store)
                logger.info("Mongo stores initialized (conversation + KB)")
            else:
                logger.info("Mongo URI not configured; using in-memory stores")
        except Exception as exc:
            mongo_conversation_store = None
            mongo_kb_store = None
            logger.warning(f"Mongo startup init failed, using in-memory stores: {exc}")

    asyncio.create_task(setup_telegram(chatbot))


@app.on_event("shutdown")
async def on_shutdown():
    global mongo_conversation_store, mongo_kb_store

    mongo_conversation_store = None
    mongo_kb_store = None
    rag_service.set_mongo_store(None)

    if DB_INTEGRATION_AVAILABLE and close_mongo is not None:
        try:
            close_mongo(app)
            logger.info("Mongo connection closed")
        except Exception as exc:
            logger.warning(f"Mongo shutdown failed: {exc}")


if __name__ == "__main__":
    uvicorn.run("translation:app", host="0.0.0.0", port=8000, reload=UVICORN_RELOAD)