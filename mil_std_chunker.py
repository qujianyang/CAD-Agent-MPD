"""
Document chunking and ingestion for MIL-STD documents.
"""
import pymupdf4llm
import fitz
from pathlib import Path
from typing import List, Dict, Any
import json
import re


class DocumentChunker:
    def __init__(self, chunk_size: int = 500, overlap: int = 100):
        """
        Initialize chunker with configurable chunk size and overlap.
        
        Args:
            chunk_size: Characters per chunk
            overlap: Character overlap between chunks for context preservation
        """
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Split text into overlapping chunks with metadata.
        
        Args:
            text: Full document text
            
        Returns:
            List of chunk dicts with content and metadata
        """
        chunks = []
        sentences = re.split(r'(?<=[.!?])\s+', text)
        current_chunk = ""
        chunk_id = 0
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) < self.chunk_size:
                current_chunk += " " + sentence
            else:
                if current_chunk.strip():
                    chunks.append({
                        "id": chunk_id,
                        "content": current_chunk.strip(),
                        "length": len(current_chunk)
                    })
                    chunk_id += 1
                # Start new chunk with overlap from previous
                overlap_text = current_chunk[-self.overlap:] if len(current_chunk) > self.overlap else current_chunk
                current_chunk = overlap_text + " " + sentence
        
        # Add final chunk
        if current_chunk.strip():
            chunks.append({
                "id": chunk_id,
                "content": current_chunk.strip(),
                "length": len(current_chunk)
            })
        
        return chunks

    def ingest_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Ingest PDF and return chunked content with metadata.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dictionary with document metadata and chunks
        """
        pdf_path = Path(pdf_path)
        
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        
        print(f"Ingesting: {pdf_path.name}")
        
        # Extract markdown content
        try:
            markdown_content = pymupdf4llm.to_markdown(
                str(pdf_path),
                page_chunks=False,
                write_images=False,
                show_progress=False
            )
        except Exception as e:
            print(f"pymupdf4llm error: {e}, using fallback")
            markdown_content = self._fallback_extraction(pdf_path)
        
        # Get PDF metadata
        with fitz.open(str(pdf_path)) as doc:
            page_count = len(doc)
            metadata = doc.metadata
            title = metadata.get('title', pdf_path.stem)
            author = metadata.get('author', 'Unknown')
        
        # Chunk the content
        chunks = self.chunk_text(markdown_content)
        
        return {
            "filename": pdf_path.name,
            "filepath": str(pdf_path.absolute()),
            "title": title,
            "author": author,
            "page_count": page_count,
            "chunk_count": len(chunks),
            "chunks": chunks,
            "raw_content": markdown_content[:500]  # First 500 chars for preview
        }

    def _fallback_extraction(self, pdf_path: Path) -> str:
        """Fallback text extraction using PyMuPDF."""
        text_parts = []
        with fitz.open(str(pdf_path)) as doc:
            for page_num, page in enumerate(doc, 1):
                text_parts.append(f"\n## Page {page_num}\n")
                text = page.get_text()
                text_parts.append(text if text.strip() else "[Empty page]")
        return "\n".join(text_parts)
