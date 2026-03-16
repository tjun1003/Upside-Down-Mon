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

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from app_models import ChatRequest, ClearRequest, DetectRequest, KBAddRequest
from chatbot_core import SEAChatbot, log_cache_status, setup_telegram
from language_tools import (
    build_assistant_reply,
    infer_lang_by_script,
    is_off_topic_message,
    needs_language_correction,
    resolve_response_lang,
    sanitize_assistant_output,
)
from translation_config import (
    ATLAS_COLLECTION_NAME,
    ATLAS_DB_NAME,
    LANG_NAMES,
    STARTUP_CHECK_CACHE,
    STREAM_CHUNK_DELAY,
    SYSTEM_SCOPE_REDIRECT_EN,
    USE_ATLAS_KB,
    UVICORN_RELOAD,
    logger,
)


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

    detection = chatbot.detector.detect_with_confidence(req.message)
    src_lang = detection["lang"]
    script_lang = infer_lang_by_script(req.message)
    if script_lang is not None:
        src_lang = script_lang

    # In auto mode, prioritize the visible script in user input to keep language aligned.
    auto_mode = (req.target_lang or "auto").strip().lower() == "auto"
    if auto_mode and script_lang is not None:
        response_lang = script_lang
    elif auto_mode and src_lang == "en" and float(detection.get("confidence", 0.0)) < 0.2:
        # If detection is very uncertain and input contains non-ASCII chars, prefer Chinese for UX.
        has_non_ascii = any(ord(ch) > 127 for ch in req.message)
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

        context = chatbot.kb.retrieve(req.message) if chatbot.kb.ready else ""

        if req.assistant_mode:
            if is_off_topic_message(req.message):
                if response_lang == "en":
                    final_reply = SYSTEM_SCOPE_REDIRECT_EN
                else:
                    final_reply = chatbot.engine.translate(
                        SYSTEM_SCOPE_REDIRECT_EN,
                        "en",
                        response_lang,
                        "",
                    )
                final_reply = sanitize_assistant_output(final_reply)

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
                    final_reply = sanitize_assistant_output(final_reply)
                    if not final_reply.strip():
                        final_reply = EMPTY_ASSISTANT_FALLBACK_EN

                async for event in emit_text_as_tokens(final_reply):
                    yield event
                chatbot.memory.add(req.session_id, req.message, final_reply)
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return

            rule_reply_en = build_assistant_reply(req.message)
            if rule_reply_en is not None:
                if response_lang == "en":
                    final_reply = rule_reply_en
                else:
                    final_reply = chatbot.engine.translate(
                        rule_reply_en,
                        "en",
                        response_lang,
                        "",
                    )
            else:
                final_reply = chatbot.engine.generate_assistant_reply(
                    req.message,
                    response_lang,
                    context,
                )

            final_reply = sanitize_assistant_output(final_reply)
            out_lang = chatbot.detector.detect(final_reply)
            if out_lang != response_lang and final_reply.strip():
                final_reply = chatbot.engine.translate(
                    final_reply,
                    out_lang,
                    response_lang,
                    "",
                )
                final_reply = sanitize_assistant_output(final_reply)

            if needs_language_correction(final_reply, response_lang):
                final_reply = chatbot.engine.translate(
                    final_reply,
                    chatbot.detector.detect(final_reply),
                    response_lang,
                    "",
                )
                final_reply = sanitize_assistant_output(final_reply)

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
                final_reply = sanitize_assistant_output(final_reply)
                if not final_reply.strip():
                    final_reply = EMPTY_ASSISTANT_FALLBACK_EN

            async for event in emit_text_as_tokens(final_reply):
                yield event
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

        chatbot.memory.add(req.session_id, req.message, final_reply)
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/history/{session_id}")
def get_history(session_id: str):
    return {"session_id": session_id, "history": chatbot.memory.history(session_id)}


@app.post("/history/clear")
def clear_history(req: ClearRequest):
    chatbot.memory.clear(req.session_id)
    return {"cleared": True, "session_id": req.session_id}


@app.post("/kb/add")
def add_to_kb(req: KBAddRequest):
    chatbot.kb.add_documents(req.documents)
    return {"added": len(req.documents), "kb_ready": chatbot.kb.ready}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "active_sessions": chatbot.memory.active_sessions(),
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
    logger.info("SEA Translation Chatbot starting...")
    if STARTUP_CHECK_CACHE:
        log_cache_status()
    else:
        logger.info("Skipping cache status scan (set STARTUP_CHECK_CACHE=1 to enable)")
    asyncio.create_task(setup_telegram(chatbot))


if __name__ == "__main__":
    uvicorn.run("translation:app", host="0.0.0.0", port=8000, reload=UVICORN_RELOAD)