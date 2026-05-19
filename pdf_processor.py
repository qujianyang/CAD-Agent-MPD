import pymupdf4llm
import fitz
from pathlib import Path
from typing import Dict, Any
import hashlib
import time


class PDFProcessor:
    def __init__(self):
        self.stats = {}

    def process_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Process PDF using pymupdf4llm for optimal markdown extraction.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Dictionary containing document info and markdown content
        """
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        # Generate document ID from file content hash
        doc_id = hashlib.md5(pdf_path.read_bytes()).hexdigest()

        # Extract content as markdown
        print(f"Processing PDF: {pdf_path.name}")
        start_time = time.time()

        try:
            # Use pymupdf4llm for markdown extraction
            markdown_content = pymupdf4llm.to_markdown(
                str(pdf_path),
                page_chunks=False,  # Get full document
                write_images=False,  # Skip images for now
                show_progress=False  # No progress bar
            )
        except Exception as e:
            print(f"Error processing PDF with pymupdf4llm: {e}")
            # Fallback to basic extraction
            markdown_content = self._fallback_extraction(pdf_path)

        processing_time = time.time() - start_time

        # Get page count and metadata
        with fitz.open(str(pdf_path)) as doc:
            page_count = len(doc)

            # Extract basic metadata if available
            metadata = doc.metadata
            title = metadata.get('title', pdf_path.stem)
            author = metadata.get('author', '')

        return {
            'doc_id': doc_id,
            'filename': pdf_path.name,
            'filepath': str(pdf_path.absolute()),
            'content': markdown_content,
            'page_count': page_count,
            'processing_time': processing_time,
            'title': title,
            'author': author,
            'method': 'pymupdf4llm'
        }

    def _fallback_extraction(self, pdf_path: Path) -> str:
        """Fallback method for PDF text extraction using PyMuPDF."""
        markdown_content = []

        with fitz.open(str(pdf_path)) as doc:
            for page_num, page in enumerate(doc, 1):
                # Add page header
                markdown_content.append(f"\n## Page {page_num}\n")

                # Extract text
                text = page.get_text()
                if text.strip():
                    markdown_content.append(text)
                else:
                    markdown_content.append("[No text content on this page]")

        return "\n".join(markdown_content)