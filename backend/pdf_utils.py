#!/usr/bin/env python3
"""
PDF text extraction utilities for essay ranking experiments
"""

import io
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

def extract_text_from_pdf(pdf_file) -> Optional[str]:
    """
    Extract text content from a PDF file.
    
    Args:
        pdf_file: File-like object or bytes containing PDF data
        
    Returns:
        Extracted text content or None if extraction fails
    """
    try:
        import PyPDF2
        
        # Handle different input types
        if hasattr(pdf_file, 'read'):
            # File-like object
            pdf_file.seek(0)  # Reset file pointer to beginning
            pdf_reader = PyPDF2.PdfReader(pdf_file)
        elif isinstance(pdf_file, bytes):
            # Bytes data
            pdf_stream = io.BytesIO(pdf_file)
            pdf_reader = PyPDF2.PdfReader(pdf_stream)
        else:
            logger.error(f"Unsupported PDF file type: {type(pdf_file)}")
            return None
        
        # Extract text from all pages
        text_content = []
        for page_num, page in enumerate(pdf_reader.pages):
            try:
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    # Handle Unicode encoding issues
                    try:
                        # Try to encode as UTF-8 and handle surrogates
                        page_text = page_text.encode('utf-8', errors='replace').decode('utf-8')
                    except UnicodeError:
                        # If that fails, use a more aggressive approach
                        page_text = page_text.encode('utf-8', errors='ignore').decode('utf-8')
                    
                    text_content.append(f"--- Page {page_num + 1} ---\n{page_text}")
            except Exception as e:
                logger.warning(f"Failed to extract text from page {page_num + 1}: {e}")
                continue
        
        if not text_content:
            logger.warning("No text content found in PDF")
            return None
        
        full_text = "\n\n".join(text_content)
        
        # Clean up the text and handle any remaining Unicode issues
        try:
            full_text = full_text.encode('utf-8', errors='replace').decode('utf-8')
        except UnicodeError:
            full_text = full_text.encode('utf-8', errors='ignore').decode('utf-8')
        
        full_text = full_text.strip()
        
        # Log extraction success
        logger.info(f"Successfully extracted {len(full_text)} characters from PDF")
        
        return full_text
        
    except Exception as e:
        logger.error(f"Failed to extract text from PDF: {e}")
        return None

def extract_text_from_pdf_file_path(file_path: str) -> Optional[str]:
    """
    Extract text content from a PDF file given its file path.
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        Extracted text content or None if extraction fails
    """
    try:
        with open(file_path, 'rb') as pdf_file:
            return extract_text_from_pdf(pdf_file)
    except Exception as e:
        logger.error(f"Failed to read PDF file {file_path}: {e}")
        return None

def validate_essay_content(essay_text: str) -> Dict[str, Any]:
    """
    Validate and analyze essay content.
    
    Args:
        essay_text: The extracted essay text
        
    Returns:
        Dictionary with validation results and metadata
    """
    if not essay_text or not essay_text.strip():
        return {
            "valid": False,
            "error": "Empty essay content",
            "word_count": 0,
            "character_count": 0
        }
    
    # Basic validation
    word_count = len(essay_text.split())
    character_count = len(essay_text)
    
    # Check for minimum content requirements
    if word_count < 10:
        return {
            "valid": False,
            "error": f"Essay too short: {word_count} words (minimum 10 required)",
            "word_count": word_count,
            "character_count": character_count
        }
    
    if character_count < 50:
        return {
            "valid": False,
            "error": f"Essay too short: {character_count} characters (minimum 50 required)",
            "word_count": word_count,
            "character_count": character_count
        }
    
    return {
        "valid": True,
        "word_count": word_count,
        "character_count": character_count,
        "estimated_reading_time_minutes": max(1, word_count // 200)  # Assume 200 words per minute
    }
