"""SEA Translation Chatbot - Optimized streamlined version"""

import asyncio
import json
import base64

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response

from db.models import ChatRequest, ClearRequest, DetectRequest, KBAddRequest, KBAddPDFRequest
from core.chatbot_core import SEAChatbot
from libs.language_tools import resolve_response_lang
from services.rag_service import RAGService
from config.settings import (
    ATLAS_RAG_TOP_K,
    ATLAS_TEXT_FIELD,
    PDF_DEFAULT_CHUNK_SIZE,
    PDF_DEFAULT_CHUNK_OVERLAP,
    PDF_MAX_FILE_SIZE_MB,
    logger,
)

try:
    from db.connection import MongoConversationStore, MongoKnowledgeBase, close_mongo, init_mongo
    from libs.pdf_processor import PDFProcessor as create_pdf_processor
    DB_AVAILABLE = True
except Exception as exc:
    MongoConversationStore = None
    MongoKnowledgeBase = None
    close_mongo = None
    init_mongo = None
    DB_AVAILABLE = False
    logger.warning(f"DB integration disabled: {exc}")


app = FastAPI(title="SEA Translation Chatbot API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
chatbot = SEAChatbot()
mongo_store = None
gridfs_storage = None
rag_service = RAGService(chatbot.kb, logger, ATLAS_RAG_TOP_K, ATLAS_TEXT_FIELD)


@app.get("/")
def root():
    return {
        "service": "SEA Translation Chatbot",
        "version": "2.0.0",
        "endpoints": ["/chat/stream", "/detect", "/kb/add-pdf", "/health"],
    }


@app.post("/detect")
def detect_language(req: DetectRequest):
    """Language detection"""
    return chatbot.detector.detect_with_confidence(req.text)


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """Core chat API - RAG-enhanced translation"""
    if not req.message.strip():
        raise HTTPException(400, "Message cannot be empty")

    message = req.message
    detection = chatbot.detector.detect_with_confidence(message)
    src_lang = detection["lang"]  # e.g., en
    response_lang = resolve_response_lang(src_lang, req.target_lang)

    async def event_generator():
        # 1. Translate to English
        pivot_en = message if src_lang == "en" else chatbot.engine.translate(message, src_lang, "en", "")
        
        # 2. Generate retrieval summary
        summary = chatbot.engine.summarize_for_retrieval_en(pivot_en)
        
        # 3. RAG retrieval
        context = await rag_service.retrieve_context(summary)
        
        # 4. Translate context to target language
        if context.strip():
            context_lang = chatbot.detector.detect(context)
            if context_lang != response_lang:
                reply = chatbot.engine.translate(context, context_lang, response_lang, "")
            else:
                reply = context
        else:
            reply = "I can help with this. Please share more details." if response_lang == "en" else message

        # 5. Stream output
        for chunk in reply.split(" "):
            if chunk:
                yield f"data: {json.dumps({'type': 'token', 'text': chunk + ' '})}\n\n"
                await asyncio.sleep(0.01)

        # 6. Save conversation
        if mongo_store:
            try:
                await mongo_store.add(req.session_id, message, reply)
            except:
                chatbot.memory.add(req.session_id, message, reply)
        else:
            chatbot.memory.add(req.session_id, message, reply)

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/history/{session_id}")
async def get_history(session_id: str):
    """Get conversation history"""
    if mongo_store:
        try:
            docs = await mongo_store.history(session_id)
            return {"session_id": session_id, "history": [
                {"role": "assistant" if d.get("role") == "ai" else d.get("role"), "content": d.get("text", "")}
                for d in docs
            ]}
        except:
            pass
    return {"session_id": session_id, "history": chatbot.memory.history(session_id)}


@app.post("/history/clear")
async def clear_history(req: ClearRequest):
    """Clear conversation history"""
    if mongo_store:
        try:
            await mongo_store.clear(req.session_id)
        except:
            pass
    chatbot.memory.clear(req.session_id)
    return {"cleared": True, "session_id": req.session_id}


@app.post("/kb/add")
async def add_to_kb(req: KBAddRequest):
    """Add documents to knowledge base"""
    added = await rag_service.add_documents(req.documents)
    return {"added": len(req.documents), "mongo_added": added}


@app.post("/kb/add-pdf")
async def add_pdf_to_kb(req: KBAddPDFRequest):
    """PDF upload - extract text and store chunks"""
    try:
        pdf_bytes = base64.b64decode(req.pdf_content)
    except:
        raise HTTPException(400, "Invalid base64 content")

    file_size_mb = len(pdf_bytes) / (1024 * 1024)
    if file_size_mb > PDF_MAX_FILE_SIZE_MB:
        raise HTTPException(400, f"File too large: {file_size_mb:.2f}MB")

    # Process PDF
    processor = create_pdf_processor(
        chunk_size=req.chunk_size or PDF_DEFAULT_CHUNK_SIZE,
        chunk_overlap=req.chunk_overlap or PDF_DEFAULT_CHUNK_OVERLAP
    )

    metadata = req.additional_metadata or {}
    if req.filename:
        metadata["filename"] = req.filename
    if req.lang:
        metadata["lang"] = req.lang
    if req.entity:
        metadata["entity"] = req.entity

    chunks = processor.process_pdf_to_chunks(pdf_bytes, metadata)
    if not chunks:
        raise HTTPException(400, "No text extracted from PDF")

    # Store to GridFS (optional)
    gridfs_file_id = None
    if req.store_original and gridfs_storage:
        try:
            gridfs_file_id = await gridfs_storage.upload_pdf(
                pdf_bytes,
                req.filename or "unnamed.pdf",
                {"lang": req.lang, "entity": req.entity, "num_chunks": len(chunks)}
            )
            for chunk in chunks:
                chunk["metadata"]["gridfs_file_id"] = gridfs_file_id
        except Exception as e:
            logger.warning(f"GridFS upload failed: {e}")

    # Add to knowledge base
    added = await rag_service.add_documents(chunks)

    return {
        "success": True,
        "filename": req.filename,
        "file_size_mb": round(file_size_mb, 2),
        "chunks_created": len(chunks),
        "chunks_added": added,
        "gridfs_file_id": gridfs_file_id,
        "pdf_metadata": chunks[0]["metadata"] if chunks else {}
    }


@app.get("/kb/pdf/{file_id}")
async def download_pdf(file_id: str):
    """Download PDF from GridFS"""
    if not gridfs_storage:
        raise HTTPException(503, "GridFS not available")

    file_info = await gridfs_storage.get_file_info(file_id)
    if not file_info:
        raise HTTPException(404, "PDF not found")

    pdf_content = await gridfs_storage.download_pdf(file_id)
    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{file_info.get("filename", "doc.pdf")}"'}
    )


@app.get("/kb/pdfs")
async def list_pdfs(limit: int = 100):
    """List PDFs in GridFS"""
    if not gridfs_storage:
        raise HTTPException(503, "GridFS not available")

    files = await gridfs_storage.list_files(limit=limit)
    total_size = await gridfs_storage.get_total_size()
    return {
        "total_files": len(files),
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "files": files
    }


@app.delete("/kb/pdf/{file_id}")
async def delete_pdf(file_id: str):
    """Delete PDF from GridFS"""
    if not gridfs_storage:
        raise HTTPException(503, "GridFS not available")

    success = await gridfs_storage.delete_pdf(file_id)
    if not success:
        raise HTTPException(404, "PDF not found")

    return {"success": True, "file_id": file_id}


@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "ok",
        "model_loaded": chatbot.engine._model is not None,
        "kb_ready": chatbot.kb.ready,
        "mongo_connected": mongo_store is not None,
        "gridfs_available": gridfs_storage is not None,
    }


@app.on_event("startup")
async def on_startup():
    global mongo_store, gridfs_storage

    if DB_AVAILABLE and init_mongo:
        try:
            await init_mongo(app)
            db = getattr(app.state, "mongodb", None)
            if db:
                mongo_store = MongoConversationStore(db)
                mongo_kb = MongoKnowledgeBase(db)
                rag_service.set_mongo_store(mongo_kb)

                try:
                    from db.gridfs_storage import create_gridfs_storage
                    gridfs_storage = create_gridfs_storage(db)
                except Exception as e:
                    logger.warning(f"GridFS init failed: {e}")
        except Exception as e:
            logger.warning(f"MongoDB init failed: {e}")


@app.on_event("shutdown")
async def on_shutdown():
    global mongo_store, gridfs_storage
    mongo_store = None
    gridfs_storage = None
    if DB_AVAILABLE and close_mongo:
        close_mongo(app)


if __name__ == "__main__":
    uvicorn.run("translation:app", host="0.0.0.0", port=8000, reload=True)
