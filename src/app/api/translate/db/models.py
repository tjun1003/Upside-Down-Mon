from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    session_id: str = "default"
    message: str
    target_lang: str = "auto"
    assistant_mode: bool = True
    independent_langs: Optional[List[str]] = None


class DetectRequest(BaseModel):
    text: str


class KBAddRequest(BaseModel):
    documents: List[Dict[str, Any]]


class KBAddPDFRequest(BaseModel):
    """PDF upload request - supports Base64 or binary content"""
    pdf_content: str = Field(..., description="Base64-encoded PDF file content")
    filename: Optional[str] = Field(None, description="PDF filename (optional)")
    lang: Optional[str] = Field(None, description="Document language (optional, for classification)")
    entity: Optional[str] = Field(None, description="Entity/topic tag (optional)")
    chunk_size: Optional[int] = Field(1000, description="Chunk size (number of characters)")
    chunk_overlap: Optional[int] = Field(200, description="Chunk overlap size (number of characters)")
    additional_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    store_original: Optional[bool] = Field(True, description="Whether to store original PDF to GridFS (default True)")


class PDFDownloadRequest(BaseModel):
    """PDF download request"""
    file_id: str = Field(..., description="GridFS file ID")


class ClearRequest(BaseModel):
    session_id: str = "default"
