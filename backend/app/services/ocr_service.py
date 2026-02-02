"""OCR service for extracting text from book covers and spines.

Uses EasyOCR for French text detection and recognition.
Includes heuristics to identify title, author, and publisher
from extracted text blocks.
"""

import logging
import re
from dataclasses import dataclass, field

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Lazy-loaded EasyOCR reader (models are large, load once)
_reader = None


def _get_reader():
    """Lazy-initialize EasyOCR reader with French + English support."""
    global _reader
    if _reader is None:
        import easyocr
        _reader = easyocr.Reader(["fr", "en"], gpu=False)
        logger.info("EasyOCR reader initialized (fr + en)")
    return _reader


@dataclass
class TextBlock:
    """A detected text block with position and confidence."""
    text: str
    bbox: list[list[int]]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
    confidence: float
    y_center: float  # vertical center for layout analysis
    height: float  # text height in pixels
    area: float  # bounding box area


@dataclass
class CoverOCRResult:
    """Extracted information from a book cover."""
    title_candidates: list[str] = field(default_factory=list)
    author_candidates: list[str] = field(default_factory=list)
    publisher_candidates: list[str] = field(default_factory=list)
    isbn_candidates: list[str] = field(default_factory=list)
    all_text_blocks: list[TextBlock] = field(default_factory=list)
    raw_text: str = ""


def extract_text_blocks(image: np.ndarray) -> list[TextBlock]:
    """Run EasyOCR on the image and return structured text blocks."""
    reader = _get_reader()

    # EasyOCR returns list of (bbox, text, confidence)
    results = reader.readtext(image, paragraph=False)

    blocks = []
    for bbox, text, conf in results:
        text = text.strip()
        if not text or conf < 0.15:
            continue

        # Compute metrics for layout analysis
        ys = [p[1] for p in bbox]
        xs = [p[0] for p in bbox]
        y_center = sum(ys) / len(ys)
        text_height = max(ys) - min(ys)
        area = (max(xs) - min(xs)) * text_height

        blocks.append(TextBlock(
            text=text,
            bbox=bbox,
            confidence=conf,
            y_center=y_center,
            height=text_height,
            area=area,
        ))

    # Sort by vertical position (top to bottom)
    blocks.sort(key=lambda b: b.y_center)
    return blocks


def analyze_front_cover(image: np.ndarray) -> CoverOCRResult:
    """Extract title, author, publisher from a front cover image.

    Layout heuristics for typical French book covers:
    - Publisher logo/name is often at the very top or bottom
    - Title is the largest text, usually in the upper 60%
    - Author name is typically above or below the title, in smaller font
    - Collection/series name may appear near the publisher
    """
    blocks = extract_text_blocks(image)
    result = CoverOCRResult(all_text_blocks=blocks)
    result.raw_text = " | ".join(b.text for b in blocks)

    if not blocks:
        return result

    img_height = image.shape[0]

    # --- Identify title: largest text block(s) ---
    # Title is typically the tallest text on the cover
    max_height = max(b.height for b in blocks)

    # Blocks with height >= 50% of max are title candidates
    title_threshold = max_height * 0.50
    title_blocks = [b for b in blocks if b.height >= title_threshold]

    # Merge adjacent title blocks (multi-line titles)
    title_blocks.sort(key=lambda b: b.y_center)
    title_parts = []
    for b in title_blocks:
        title_parts.append(b.text)
    if title_parts:
        result.title_candidates.append(" ".join(title_parts))

    # --- Identify author: typically a name pattern ---
    non_title_blocks = [b for b in blocks if b.height < title_threshold]

    # Common French name patterns
    name_pattern = re.compile(
        r"^[A-ZÀ-ÿ][a-zà-ÿ]+(?:\s+[A-ZÀ-ÿ][a-zà-ÿ]+)+$"  # "Jean Dupont"
        r"|^[A-ZÀ-ÿ\s.'-]{3,}$"  # "J. K. ROWLING" or "VICTOR HUGO"
    )

    for b in non_title_blocks:
        cleaned = b.text.strip()
        if name_pattern.match(cleaned) and len(cleaned) > 3:
            result.author_candidates.append(cleaned)

    # If no name pattern matched, use position heuristic:
    # Author is often the first non-title text at the top
    if not result.author_candidates and non_title_blocks:
        top_blocks = [b for b in non_title_blocks if b.y_center < img_height * 0.35]
        if top_blocks:
            result.author_candidates.append(top_blocks[0].text)

    # --- Identify publisher: usually at bottom or top, small text ---
    known_publishers = [
        "gallimard", "folio", "seuil", "flammarion", "grasset", "albin michel",
        "hachette", "larousse", "robert laffont", "plon", "stock", "calmann-lévy",
        "actes sud", "minuit", "pocket", "le livre de poche", "j'ai lu",
        "10/18", "points", "rivages", "denoël", "mercure de france",
        "editions du seuil", "éditions du seuil", "livre de poche",
        "fayard", "dunod", "eyrolles", "odile jacob", "la découverte",
        "puf", "lgf", "casterman", "dargaud", "dupuis", "glénat",
        "delcourt", "soleil", "ankama", "kana", "pika",
    ]

    for b in blocks:
        text_lower = b.text.lower().strip()
        for pub in known_publishers:
            if pub in text_lower:
                result.publisher_candidates.append(b.text.strip())
                break

    return result


def analyze_back_cover(image: np.ndarray) -> CoverOCRResult:
    """Extract ISBN and blurb from back cover.

    The ISBN barcode is handled separately by pyzbar.
    This extracts the printed ISBN text and any other useful text.
    """
    blocks = extract_text_blocks(image)
    result = CoverOCRResult(all_text_blocks=blocks)
    result.raw_text = " | ".join(b.text for b in blocks)

    # Look for ISBN patterns in text
    isbn_pattern = re.compile(r"(?:ISBN[:\s-]*)?(\d[\d\s-]{9,16}[\dXx])")

    for b in blocks:
        match = isbn_pattern.search(b.text)
        if match:
            # Clean the ISBN
            isbn_raw = match.group(1)
            isbn_clean = re.sub(r"[\s-]", "", isbn_raw)
            if len(isbn_clean) in (10, 13):
                result.isbn_candidates.append(isbn_clean)

    return result


def analyze_spine(image: np.ndarray) -> CoverOCRResult:
    """Extract title and author from spine.

    Spine text is typically rotated 90° (or 270°). We try both orientations
    and pick the one with higher total OCR confidence.
    """
    # Try original orientation
    blocks_orig = extract_text_blocks(image)
    conf_orig = sum(b.confidence for b in blocks_orig)

    # Try rotated 90° clockwise
    rotated_cw = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    blocks_cw = extract_text_blocks(rotated_cw)
    conf_cw = sum(b.confidence for b in blocks_cw)

    # Try rotated 90° counter-clockwise
    rotated_ccw = cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
    blocks_ccw = extract_text_blocks(rotated_ccw)
    conf_ccw = sum(b.confidence for b in blocks_ccw)

    # Use the orientation with highest total confidence
    if conf_cw >= conf_orig and conf_cw >= conf_ccw:
        blocks = blocks_cw
    elif conf_ccw >= conf_orig:
        blocks = blocks_ccw
    else:
        blocks = blocks_orig

    result = CoverOCRResult(all_text_blocks=blocks)
    result.raw_text = " | ".join(b.text for b in blocks)

    if not blocks:
        return result

    # Spine typically has: Author - Title - Publisher (or reverse)
    # The largest text is usually the title
    if blocks:
        max_height = max(b.height for b in blocks)
        for b in blocks:
            if b.height >= max_height * 0.7:
                result.title_candidates.append(b.text)
            else:
                result.author_candidates.append(b.text)

    return result


def preprocess_for_ocr(image: np.ndarray) -> np.ndarray:
    """Preprocess image to improve OCR accuracy.

    Applies contrast enhancement and sharpening.
    """
    # Convert to LAB and equalize L channel for contrast
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    enhanced = cv2.merge([l, a, b])
    enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

    # Sharpen
    kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
    sharpened = cv2.filter2D(enhanced, -1, kernel)

    return sharpened
