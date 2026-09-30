"""
GridFS storage module for original PDF files

Provides:
- Upload PDF to GridFS
- Download PDF from GridFS
- Manage PDF metadata
- Integration with chunking system
"""
import hashlib
import logging
from typing import Any, Dict, Optional, BinaryIO
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)


class GridFSPDFStorage:
    """GridFS PDF storage manager"""

    def __init__(self, db: Any, bucket_name: str = "pdfs"):
        """
        Initialize GridFS storage
        
        Args:
            db: AsyncIOMotorDatabase instance
            bucket_name: GridFS bucket name (default "pdfs")
        """
        if db is None:
            raise ValueError("db cannot be None; MongoDB must be initialized")
        
        self.db = db
        self.bucket = AsyncIOMotorGridFSBucket(db, bucket_name=bucket_name)
        self.logger = logger

    async def upload_pdf(
        self,
        pdf_content: bytes,
        filename: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Upload PDF to GridFS
        
        Args:
            pdf_content: PDF binary content
            filename: File name
            metadata: Optional metadata dictionary
            
        Returns:
            GridFS file_id (string)
            
        Raises:
            ValueError: If input is invalid
            Exception: MongoDB operation error
        """
        if not pdf_content:
            raise ValueError("PDF content cannot be empty")
        if not filename:
            raise ValueError("Filename cannot be empty")

        try:
            # Calculate file hash
            content_hash = hashlib.sha256(pdf_content).hexdigest()
            
            # Prepare metadata
            file_metadata = {
                "filename": filename,
                "content_hash": content_hash,
                "file_size": len(pdf_content),
                "upload_date": datetime.utcnow(),
                "content_type": "application/pdf",
            }
            
            # Merge custom metadata
            if metadata:
                file_metadata.update(metadata)
            
            # Check if file already exists (deduplication by hash)
            existing = await self._find_by_hash(content_hash)
            if existing:
                self.logger.info(
                    f"PDF already exists with hash {content_hash[:8]}, "
                    f"returning existing file_id: {existing}"
                )
                return str(existing)
            
            # Upload to GridFS
            file_id = await self.bucket.upload_from_stream(
                filename,
                pdf_content,
                metadata=file_metadata,
            )
            
            self.logger.info(
                f"Uploaded PDF to GridFS: {filename} "
                f"(size: {len(pdf_content)} bytes, file_id: {file_id})"
            )
            
            return str(file_id)
            
        except PyMongoError as e:
            self.logger.error(f"Failed to upload PDF to GridFS: {e}", exc_info=True)
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error uploading PDF: {e}", exc_info=True)
            raise

    async def download_pdf(self, file_id: str) -> bytes:
        """
        Download PDF from GridFS
        
        Args:
            file_id: GridFS file ID
            
        Returns:
            PDF binary content
            
        Raises:
            ValueError: If file_id is invalid
            FileNotFoundError: If file does not exist
            Exception: MongoDB operation error
        """
        if not file_id:
            raise ValueError("file_id cannot be empty")

        try:
            from bson import ObjectId
            
            # Convert to ObjectId
            try:
                oid = ObjectId(file_id)
            except Exception:
                raise ValueError(f"Invalid file_id format: {file_id}")
            
            # Check if file exists
            file_info = await self.get_file_info(file_id)
            if not file_info:
                raise FileNotFoundError(f"File not found: {file_id}")
            
            # Download file
            grid_out = await self.bucket.open_download_stream(oid)
            content = await grid_out.read()
            
            self.logger.info(
                f"Downloaded PDF from GridFS: {file_info.get('filename')} "
                f"(file_id: {file_id}, size: {len(content)} bytes)"
            )
            
            return content
            
        except FileNotFoundError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to download PDF from GridFS: {e}", exc_info=True)
            raise

    async def get_file_info(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Get file information (without downloading content)
        
        Args:
            file_id: GridFS file ID
            
        Returns:
            File metadata dictionary, or None if not found
        """
        if not file_id:
            return None

        try:
            from bson import ObjectId
            
            try:
                oid = ObjectId(file_id)
            except Exception:
                self.logger.warning(f"Invalid file_id format: {file_id}")
                return None
            
            # Query file metadata
            cursor = self.db.fs.files.find({"_id": oid})
            file_doc = await cursor.to_list(length=1)
            
            if not file_doc:
                return None
            
            doc = file_doc[0]
            
            return {
                "file_id": str(doc["_id"]),
                "filename": doc.get("filename"),
                "length": doc.get("length"),
                "upload_date": doc.get("uploadDate"),
                "content_type": doc.get("metadata", {}).get("content_type"),
                "metadata": doc.get("metadata", {}),
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get file info: {e}", exc_info=True)
            return None

    async def delete_pdf(self, file_id: str) -> bool:
        """
        Delete PDF from GridFS
        
        Args:
            file_id: GridFS file ID
            
        Returns:
            True if deleted, False otherwise
        """
        if not file_id:
            return False

        try:
            from bson import ObjectId
            
            try:
                oid = ObjectId(file_id)
            except Exception:
                self.logger.warning(f"Invalid file_id format: {file_id}")
                return False
            
            await self.bucket.delete(oid)
            self.logger.info(f"Deleted PDF from GridFS: {file_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete PDF from GridFS: {e}", exc_info=True)
            return False

    async def list_files(
        self,
        filter_query: Optional[Dict[str, Any]] = None,
        limit: int = 100,
    ) -> list[Dict[str, Any]]:
        """
        List files in GridFS
        
        Args:
            filter_query: Optional MongoDB query filter
            limit: Result limit
            
        Returns:
            List of file information
        """
        try:
            query = filter_query or {}
            cursor = self.db.fs.files.find(query).limit(limit)
            files = await cursor.to_list(length=limit)
            
            result = []
            for doc in files:
                result.append({
                    "file_id": str(doc["_id"]),
                    "filename": doc.get("filename"),
                    "length": doc.get("length"),
                    "upload_date": doc.get("uploadDate"),
                    "metadata": doc.get("metadata", {}),
                })
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to list files: {e}", exc_info=True)
            return []

    async def _find_by_hash(self, content_hash: str) -> Optional[str]:
        """
        Find existing file by content hash (for deduplication)
        
        Args:
            content_hash: Content SHA256 hash value
            
        Returns:
            File ID if found, otherwise None
        """
        try:
            cursor = self.db.fs.files.find(
                {"metadata.content_hash": content_hash}
            ).limit(1)
            
            files = await cursor.to_list(length=1)
            if files:
                return str(files[0]["_id"])
            return None
            
        except Exception as e:
            self.logger.warning(f"Hash lookup failed: {e}")
            return None

    async def count_files(self, filter_query: Optional[Dict[str, Any]] = None) -> int:
        """
        Count files
        
        Args:
            filter_query: Optional MongoDB query filter
            
        Returns:
            Number of files
        """
        try:
            query = filter_query or {}
            count = await self.db.fs.files.count_documents(query)
            return count
        except Exception as e:
            self.logger.error(f"Failed to count files: {e}", exc_info=True)
            return 0

    async def get_total_size(self) -> int:
        """
        Get total size of all stored files
        
        Returns:
            Total size in bytes
        """
        try:
            pipeline = [
                {"$group": {"_id": None, "total": {"$sum": "$length"}}}
            ]
            cursor = self.db.fs.files.aggregate(pipeline)
            result = await cursor.to_list(length=1)
            
            if result:
                return result[0].get("total", 0)
            return 0
            
        except Exception as e:
            self.logger.error(f"Failed to calculate total size: {e}", exc_info=True)
            return 0


def create_gridfs_storage(db: Any, bucket_name: str = "pdfs") -> GridFSPDFStorage:
    """
    Factory function: create GridFS storage instance
    
    Args:
        db: AsyncIOMotorDatabase instance
        bucket_name: GridFS bucket name
        
    Returns:
        GridFSPDFStorage instance
    """
    return GridFSPDFStorage(db, bucket_name)
