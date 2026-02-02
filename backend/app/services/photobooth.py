"""Photobooth pipeline: orchestrates dimension extraction, barcode reading, and OCR.

Workflow:
1. User places book on calibration mat
2. Takes 3 photos: front cover, back cover, spine
3. This pipeline processes all 3 and returns merged results
4. User confirms/edits the extracted data
5. Book is created in the database
"""

import logging
from dataclasses import dataclass, field
from io import BytesIO

import cv2
import numpy as np
from pyzbar import pyzbar
from pyzbar.pyzbar import ZBarSymbol

from app.services.dimension_extractor import extract_dimensions, measure_spine_depth
from app.services.ocr_service import (
    analyze_front_cover, analyze_back_cover, analyze_spine,
    preprocess_for_ocr, CoverOCRResult,
)

logger = logging.getLogger(__name__)


@dataclass
class PhotoboothResult:
    """Combined result from processing all book photos."""
    # Extracted data
    isbn: str | None = None
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    publisher: str | None = None

    # Physical dimensions (mm)
    height_mm: float | None = None
    width_mm: float | None = None
    depth_mm: float | None = None

    # Confidence scores
    isbn_confidence: float = 0.0
    title_confidence: float = 0.0
    dimension_confidence: float = 0.0

    # Raw OCR data for manual review
    front_ocr: CoverOCRResult | None = None
    back_ocr: CoverOCRResult | None = None
    spine_ocr: CoverOCRResult | None = None

    # Cover image (front) for storage
    cover_image: bytes | None = None

    # Debug/metadata
    warnings: list[str] = field(default_factory=list)
    markers_found: int = 0


def decode_image(data: bytes) -> np.ndarray:
    """Decode image bytes to OpenCV BGR array."""
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image data")
    return img


def encode_image_jpeg(image: np.ndarray, quality: int = 85) -> bytes:
    """Encode OpenCV image to JPEG bytes."""
    _, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return buf.tobytes()


def extract_isbn_barcode(image: np.ndarray) -> tuple[str | None, float]:
    """Extract ISBN from barcode in the image using pyzbar.

    Tries multiple preprocessing approaches for robustness.
    Returns (isbn_string, confidence).
    """
    attempts = [
        ("original", image),
        ("gray", cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)),
    ]

    # Add sharpened version
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    sharpened = cv2.filter2D(gray, -1, np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]]))
    attempts.append(("sharpened", sharpened))

    # Add thresholded version
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    attempts.append(("binary", binary))

    for name, img in attempts:
        barcodes = pyzbar.decode(img, symbols=[ZBarSymbol.EAN13, ZBarSymbol.EAN8])
        for barcode in barcodes:
            isbn = barcode.data.decode("utf-8")
            # ISBN-13 starts with 978 or 979
            if isbn.startswith(("978", "979")) and len(isbn) == 13:
                logger.info("ISBN found via %s: %s", name, isbn)
                return isbn, 1.0
            # EAN-8 or other - less likely to be ISBN but record it
            if len(isbn) >= 8:
                logger.info("Barcode found via %s (non-ISBN): %s", name, isbn)

    # Try cropping to bottom half (where barcodes typically are)
    h = image.shape[0]
    bottom_half = image[h // 2:, :]
    barcodes = pyzbar.decode(bottom_half, symbols=[ZBarSymbol.EAN13])
    for barcode in barcodes:
        isbn = barcode.data.decode("utf-8")
        if isbn.startswith(("978", "979")) and len(isbn) == 13:
            logger.info("ISBN found in bottom crop: %s", isbn)
            return isbn, 0.9

    return None, 0.0


def process_front_cover(
    image_data: bytes
) -> tuple[CoverOCRResult, float | None, float | None, float, bytes]:
    """Process front cover photo.

    Returns: (ocr_result, height_mm, width_mm, dim_confidence, cover_jpeg)
    """
    image = decode_image(image_data)

    # Extract dimensions from calibration mat
    dim_result = extract_dimensions(image)
    height_mm = dim_result.dimensions.height_mm if dim_result.dimensions else None
    width_mm = dim_result.dimensions.width_mm if dim_result.dimensions else None
    dim_confidence = dim_result.dimensions.confidence if dim_result.dimensions else 0.0

    # OCR on the rectified image (better quality) or original
    ocr_target = dim_result.rectified_image if dim_result.rectified_image is not None else image
    ocr_target = preprocess_for_ocr(ocr_target)
    ocr_result = analyze_front_cover(ocr_target)

    # Save a clean cover image (original, not rectified)
    cover_jpeg = encode_image_jpeg(image)

    return ocr_result, height_mm, width_mm, dim_confidence, cover_jpeg


def process_back_cover(image_data: bytes) -> tuple[CoverOCRResult, str | None, float]:
    """Process back cover photo.

    Returns: (ocr_result, isbn, isbn_confidence)
    """
    image = decode_image(image_data)

    # Try barcode first (most reliable)
    isbn, isbn_conf = extract_isbn_barcode(image)

    # OCR for additional data and ISBN fallback
    preprocessed = preprocess_for_ocr(image)
    ocr_result = analyze_back_cover(preprocessed)

    # If barcode failed, try OCR-extracted ISBN
    if isbn is None and ocr_result.isbn_candidates:
        isbn = ocr_result.isbn_candidates[0]
        isbn_conf = 0.6  # lower confidence for OCR-extracted ISBN

    return ocr_result, isbn, isbn_conf


def process_spine(image_data: bytes) -> tuple[CoverOCRResult, float | None, float]:
    """Process spine photo.

    Returns: (ocr_result, depth_mm, dim_confidence)
    """
    image = decode_image(image_data)

    # Measure spine depth
    depth_result = measure_spine_depth(image)
    depth_mm = depth_result.dimensions.height_mm if depth_result.dimensions else None
    dim_confidence = depth_result.dimensions.confidence if depth_result.dimensions else 0.0

    # OCR the spine
    ocr_target = depth_result.rectified_image if depth_result.rectified_image is not None else image
    ocr_target = preprocess_for_ocr(ocr_target)
    ocr_result = analyze_spine(ocr_target)

    return ocr_result, depth_mm, dim_confidence


def process_book(
    front_image: bytes | None = None,
    back_image: bytes | None = None,
    spine_image: bytes | None = None,
) -> PhotoboothResult:
    """Process all available photos of a book and merge results.

    At minimum, the back cover (for ISBN) should be provided.
    All three photos give the best results.
    """
    result = PhotoboothResult()

    # Process each available image
    if back_image:
        try:
            back_ocr, isbn, isbn_conf = process_back_cover(back_image)
            result.back_ocr = back_ocr
            result.isbn = isbn
            result.isbn_confidence = isbn_conf
        except Exception as e:
            logger.error("Back cover processing failed: %s", e)
            result.warnings.append(f"Back cover processing error: {e}")

    if front_image:
        try:
            front_ocr, h, w, dim_conf, cover = process_front_cover(front_image)
            result.front_ocr = front_ocr
            result.height_mm = h
            result.width_mm = w
            result.dimension_confidence = dim_conf
            result.cover_image = cover
        except Exception as e:
            logger.error("Front cover processing failed: %s", e)
            result.warnings.append(f"Front cover processing error: {e}")

    if spine_image:
        try:
            spine_ocr, depth, spine_dim_conf = process_spine(spine_image)
            result.spine_ocr = spine_ocr
            result.depth_mm = depth
            # Average dimension confidence if we have both
            if result.dimension_confidence > 0 and spine_dim_conf > 0:
                result.dimension_confidence = (result.dimension_confidence + spine_dim_conf) / 2
            elif spine_dim_conf > 0:
                result.dimension_confidence = spine_dim_conf
        except Exception as e:
            logger.error("Spine processing failed: %s", e)
            result.warnings.append(f"Spine processing error: {e}")

    # --- Merge OCR results ---
    _merge_ocr_results(result)

    return result


def _merge_ocr_results(result: PhotoboothResult):
    """Merge OCR results from all three photos into best-guess fields."""
    title_candidates = []
    author_candidates = []
    publisher_candidates = []

    for ocr in [result.front_ocr, result.spine_ocr]:
        if ocr is None:
            continue
        title_candidates.extend(ocr.title_candidates)
        author_candidates.extend(ocr.author_candidates)
        publisher_candidates.extend(ocr.publisher_candidates)

    if result.back_ocr:
        publisher_candidates.extend(result.back_ocr.publisher_candidates)
        # Back cover ISBN as fallback
        if result.isbn is None and result.back_ocr.isbn_candidates:
            result.isbn = result.back_ocr.isbn_candidates[0]
            result.isbn_confidence = 0.5

    # Pick best title (longest candidate from front cover, confirmed by spine)
    if title_candidates:
        # Prefer front cover titles (first in list), pick longest
        result.title = max(title_candidates[:3], key=len) if title_candidates else None
        result.title_confidence = 0.7 if result.title else 0.0

        # Boost confidence if spine confirms
        if result.spine_ocr and result.spine_ocr.title_candidates:
            spine_title = result.spine_ocr.title_candidates[0].lower()
            if result.title and spine_title in result.title.lower():
                result.title_confidence = 0.9

    # Pick authors
    if author_candidates:
        # Deduplicate (case-insensitive)
        seen = set()
        unique_authors = []
        for a in author_candidates:
            key = a.lower().strip()
            if key not in seen and len(key) > 2:
                seen.add(key)
                unique_authors.append(a.strip())
        result.authors = unique_authors

    # Pick publisher
    if publisher_candidates:
        result.publisher = publisher_candidates[0]

    # Add warnings for low-confidence fields
    if result.isbn is None:
        result.warnings.append("No ISBN barcode detected - manual entry needed")
    if result.title is None:
        result.warnings.append("Could not determine title from OCR - manual entry needed")
    if result.height_mm is None:
        result.warnings.append("Could not measure dimensions - check calibration mat visibility")
