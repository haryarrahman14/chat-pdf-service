"""PDF processing service"""
import hashlib
from typing import List, Tuple
from pypdf import PdfReader
import re


class PDFService:
    """Service for PDF processing and text extraction"""

    @staticmethod
    def compute_sha256(file_content: bytes) -> str:
        """Compute SHA256 hash of file content"""
        return hashlib.sha256(file_content).hexdigest()

    @staticmethod
    def extract_text_from_pdf(file_path: str) -> Tuple[str, int]:
        """
        Extract text from PDF file

        Returns:
            Tuple of (full_text, page_count)
        """
        reader = PdfReader(file_path)
        page_count = len(reader.pages)

        # Extract text with page markers
        text_parts = []
        for i, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text()
            if page_text.strip():
                text_parts.append(f"<!-- Page {i} -->\n{page_text}")

        full_text = "\n\n".join(text_parts)
        return full_text, page_count

    @staticmethod
    def chunk_text(
        text: str,
        chunk_size: int = 800,
        overlap: int = 150,
        min_chunk_size: int = 100
    ) -> List[dict]:
        """
        Split text into overlapping chunks

        Args:
            text: Full document text (with page markers)
            chunk_size: Target chunk size in tokens (approximated by chars/4)
            overlap: Number of tokens to overlap between chunks
            min_chunk_size: Minimum chunk size in tokens

        Returns:
            List of chunk dictionaries with content, page info, etc.
        """
        # Convert token sizes to character sizes (rough approximation: 1 token ≈ 4 chars)
        char_chunk_size = chunk_size * 4
        char_overlap = overlap * 4
        char_min_size = min_chunk_size * 4

        chunks = []
        current_page = None

        # Split text into segments by page markers
        page_pattern = r'<!-- Page (\d+) -->\n'
        segments = re.split(page_pattern, text)

        # Process segments (format is: ['', '1', 'text', '2', 'text', ...])
        full_text_no_markers = ""
        page_boundaries = []  # Track where each page starts

        for i in range(1, len(segments), 2):
            if i < len(segments):
                page_num = int(segments[i])
                page_text = segments[i + 1] if i + 1 < len(segments) else ""

                page_boundaries.append({
                    'page': page_num,
                    'start_char': len(full_text_no_markers)
                })
                full_text_no_markers += page_text + "\n\n"

        # Chunk the text with sliding window
        start = 0
        chunk_id = 0

        while start < len(full_text_no_markers):
            end = min(start + char_chunk_size, len(full_text_no_markers))

            # Try to break at sentence boundary
            if end < len(full_text_no_markers):
                # Look for sentence endings within last 20% of chunk
                search_start = int(end * 0.8)
                sentence_endings = ['.', '!', '?', '\n']

                best_break = end
                for char in sentence_endings:
                    pos = full_text_no_markers.rfind(char, search_start, end)
                    if pos != -1 and pos > start:
                        best_break = pos + 1
                        break

                end = best_break

            chunk_text = full_text_no_markers[start:end].strip()

            if len(chunk_text) >= char_min_size:
                # Determine page range for this chunk
                page_start = None
                page_end = None

                for j, boundary in enumerate(page_boundaries):
                    if boundary['start_char'] <= start:
                        page_start = boundary['page']
                    if boundary['start_char'] <= end:
                        page_end = boundary['page']
                    else:
                        break

                # Estimate token count (rough: chars / 4)
                token_count = len(chunk_text) // 4

                chunks.append({
                    'content': chunk_text,
                    'page_start': page_start,
                    'page_end': page_end,
                    'token_count': token_count,
                    'section': None  # Can be enhanced with section detection
                })

                chunk_id += 1

            # Move start forward, with overlap
            start = end - char_overlap
            if start <= 0 or end >= len(full_text_no_markers):
                break

        return chunks
