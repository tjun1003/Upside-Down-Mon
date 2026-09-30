"""
PDF processing and document chunking module

Provides:
- PDF file content extraction
- Intelligent document chunking
- Metadata extraction
"""
import hashlib
import io
from typing import Any, Dict, List, Optional
import logging

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

logger = logging.getLogger(__name__)


class PDFProcessor:
    """PDF processor - extracts content and performs intelligent chunking"""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        min_chunk_size: int = 100,
    ):
        """
        Initialize PDF processor
        
        Args:
            chunk_size: Target characters per chunk (default 1000)
            chunk_overlap: Overlapping characters between chunks (default 200)
            min_chunk_size: Minimum chunk size, smaller chunks will be merged (default 100)
        """
        if PdfReader is None:
            raise ImportError(
                "pypdf is required for PDF processing. "
                "Install it with: pip install pypdf"
            )
        
        self.chunk_size = max(100, chunk_size)
        self.chunk_overlap = max(0, min(chunk_overlap, chunk_size // 2))
        self.min_chunk_size = max(50, min_chunk_size)
        self.logger = logger

    def extract_text_from_pdf(self, pdf_content: bytes) -> tuple[str, Dict[str, Any]]:
        """
        Extract text from PDF binary content
        
        Args:
            pdf_content: PDF file binary content
            
        Returns:
            (extracted text, metadata dictionary)
            
        Raises:
            ValueError: If PDF is invalid or cannot be read
        """
        if not pdf_content:
            raise ValueError("PDF content cannot be empty")

        try:
            pdf_file = io.BytesIO(pdf_content)
            reader = PdfReader(pdf_file)
            
            # Extract metadata
            metadata = {}
            if reader.metadata:
                metadata = {
                    "title": reader.metadata.get("/Title", ""),
                    "author": reader.metadata.get("/Author", ""),
                    "subject": reader.metadata.get("/Subject", ""),
                    "creator": reader.metadata.get("/Creator", ""),
                }
            
            metadata["num_pages"] = len(reader.pages)
            
            # Extract text from all pages
            text_parts = []
            for page_num, page in enumerate(reader.pages, 1):
                try:
                    page_text = page.extract_text()
                    if page_text.strip():
                        text_parts.append(page_text)
                except Exception as e:
                    self.logger.warning(f"Failed to extract text from page {page_num}: {e}")
                    continue
            
            full_text = "\n\n".join(text_parts)
            
            if not full_text.strip():
                raise ValueError("No text could be extracted from PDF")
            
            # Add text length to metadata
            metadata["text_length"] = len(full_text)
            
            # Generate content hash (for deduplication)
            content_hash = hashlib.sha256(full_text.encode("utf-8")).hexdigest()[:16]
            metadata["content_hash"] = content_hash
            
            self.logger.info(
                f"Extracted {len(full_text)} chars from {metadata['num_pages']} pages"
            )
            
            return full_text, metadata
            
        except Exception as e:
            self.logger.error(f"Failed to process PDF: {e}", exc_info=True)
            raise ValueError(f"Failed to process PDF: {str(e)}")

    def chunk_text(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Intelligently chunk text
        
        Uses sliding window method, splitting at paragraph boundaries to maintain context coherence
        
        Args:
            text: Text to chunk
            metadata: Optional metadata (will be added to each chunk)
            
        Returns:
            List of chunk documents, each with "text" and "metadata" fields
        """
        if not text or not text.strip():
            return []

        metadata = metadata or {}
        
        # Split by paragraphs (preserve double newlines)
        paragraphs = text.split("\n\n")
        
        chunks = []
        current_chunk = ""
        current_length = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            para_length = len(para)
            
            # If current paragraph exceeds chunk_size, need to split further
            if para_length > self.chunk_size:
                # Save current chunk first (if any)
                if current_chunk:
                    chunks.append(self._create_chunk_doc(current_chunk, metadata, len(chunks)))
                    current_chunk = ""
                    current_length = 0
                
                # Split long paragraph
                sub_chunks = self._split_long_paragraph(para)
                for sub_chunk in sub_chunks:
                    chunks.append(self._create_chunk_doc(sub_chunk, metadata, len(chunks)))
                
                continue
            
            # If adding this paragraph would exceed chunk_size
            if current_length + para_length + 2 > self.chunk_size:
                # Save current chunk
                if current_chunk:
                    chunks.append(self._create_chunk_doc(current_chunk, metadata, len(chunks)))
                
                # Start new chunk, possibly including overlap
                if self.chunk_overlap > 0 and current_chunk:
                    overlap_text = current_chunk[-self.chunk_overlap:]
                    current_chunk = overlap_text + "\n\n" + para
                    current_length = len(overlap_text) + 2 + para_length
                else:
                    current_chunk = para
                    current_length = para_length
            else:
                # Add paragraph to current chunk
                if current_chunk:
                    current_chunk += "\n\n" + para
                    current_length += 2 + para_length
                else:
                    current_chunk = para
                    current_length = para_length
        
        # Save last chunk
        if current_chunk and len(current_chunk) >= self.min_chunk_size:
            chunks.append(self._create_chunk_doc(current_chunk, metadata, len(chunks)))
        elif current_chunk and chunks:
            # If last chunk is too small, merge into previous chunk
            chunks[-1]["text"] += "\n\n" + current_chunk
        
        self.logger.info(f"Created {len(chunks)} chunks from text of length {len(text)}")
        
        return chunks

    def _split_long_paragraph(self, paragraph: str) -> List[str]:
        """
        Split overly long paragraphs (at sentence boundaries)
        
        Args:
            paragraph: Long paragraph to split
            
        Returns:
            List of split text blocks
        """
        # Try to split by sentences (simple method: by period, question mark, exclamation mark)
        import re
        sentences = re.split(r'([.!?。！？]+[\s\n]+)', paragraph)
        
        chunks = []
        current_chunk = ""
        
        # Recombine sentences (preserving punctuation)
        for i in range(0, len(sentences) - 1, 2):
            sentence = sentences[i]
            if i + 1 < len(sentences):
                sentence += sentences[i + 1]
            
            if len(current_chunk) + len(sentence) > self.chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                current_chunk += sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks if chunks else [paragraph]

    def _create_chunk_doc(
        self,
        text: str,
        metadata: Dict[str, Any],
        chunk_index: int,
    ) -> Dict[str, Any]:
        """
        Create chunk document structure
        
        Args:
            text: Chunk text
            metadata: Original document metadata
            chunk_index: Chunk index number
            
        Returns:
            Formatted chunk document
        """
        chunk_metadata = metadata.copy()
        chunk_metadata["chunk_index"] = chunk_index
        chunk_metadata["chunk_length"] = len(text)
        
        return {
            "text": text.strip(),
            "metadata": chunk_metadata,
        }

    def process_pdf_to_chunks(
        self,
        pdf_content: bytes,
        additional_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Complete workflow: extract text from PDF and chunk it
        
        Args:
            pdf_content: PDF binary content
            additional_metadata: Additional metadata (such as language, entity, etc.)
            
        Returns:
            List of chunk documents ready for database storage
            
        Raises:
            ValueError: If PDF processing fails
        """
        # Extract text and metadata
        text, pdf_metadata = self.extract_text_from_pdf(pdf_content)
        
        # Merge metadata
        final_metadata = pdf_metadata.copy()
        if additional_metadata:
            final_metadata.update(additional_metadata)
        
        # Chunk
        chunks = self.chunk_text(text, final_metadata)
        
        self.logger.info(
            f"Processed PDF into {len(chunks)} chunks "
            f"(size={self.chunk_size}, overlap={self.chunk_overlap})"
        )
        
        return chunks


def create_pdf_processor(
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> PDFProcessor:
    """
    Factory function: create PDF processor instance
    
    Args:
        chunk_size: Optional chunk size (default 1000)
        chunk_overlap: Optional overlap size (default 200)
        
    Returns:
        Configured PDFProcessor instance
    """
    kwargs = {}
    if chunk_size is not None:
        kwargs["chunk_size"] = chunk_size
    if chunk_overlap is not None:
        kwargs["chunk_overlap"] = chunk_overlap
    
    return PDFProcessor(**kwargs)
