"""Dimension extractor using ArUco markers and homography.

Places a book on an A3 calibration mat with 4 ArUco markers at known positions.
Detects markers, computes homography to map pixels to real-world mm,
then finds the book contour and measures its dimensions.
"""

import logging
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# --- Calibration Mat Configuration ---
# A3 mat (297 x 420 mm) with 4 ArUco markers (DICT_4X4_50)
# Markers are 40mm squares, inset 20mm from edges.
# Coordinates are the CENTER of each marker in mm.
MARKER_SIZE_MM = 40.0
MARKER_HALF = MARKER_SIZE_MM / 2.0

# Marker centers on the A3 mat (origin = top-left corner of mat)
MARKER_CENTERS_MM = {
    0: (40.0, 40.0),      # top-left
    1: (380.0, 40.0),     # top-right
    2: (380.0, 257.0),    # bottom-right
    3: (40.0, 257.0),     # bottom-left
}

# Corner points of each marker (top-left, top-right, bottom-right, bottom-left)
MARKER_CORNERS_MM = {}
for mid, (cx, cy) in MARKER_CENTERS_MM.items():
    MARKER_CORNERS_MM[mid] = np.array([
        [cx - MARKER_HALF, cy - MARKER_HALF],
        [cx + MARKER_HALF, cy - MARKER_HALF],
        [cx + MARKER_HALF, cy + MARKER_HALF],
        [cx - MARKER_HALF, cy + MARKER_HALF],
    ], dtype=np.float32)

ARUCO_DICT = cv2.aruco.DICT_4X4_50


@dataclass
class Dimensions:
    """Measured book dimensions in mm."""
    height_mm: float
    width_mm: float
    confidence: float  # 0.0 to 1.0 based on marker detection quality


@dataclass
class ExtractionResult:
    """Full result of dimension extraction."""
    dimensions: Dimensions | None
    rectified_image: np.ndarray | None  # perspective-corrected image
    book_contour: np.ndarray | None  # contour points in mm coordinates
    markers_found: int
    debug_image: np.ndarray | None  # annotated image for debugging


def detect_aruco_markers(image: np.ndarray) -> tuple[list, list, list]:
    """Detect ArUco markers in the image.

    Returns (corners, ids, rejected) from OpenCV ArUco detection.
    """
    aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICT)
    params = cv2.aruco.DetectorParameters()

    # Tune for better detection
    params.adaptiveThreshWinSizeMin = 3
    params.adaptiveThreshWinSizeMax = 23
    params.adaptiveThreshWinSizeStep = 10
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX

    detector = cv2.aruco.ArucoDetector(aruco_dict, params)
    corners, ids, rejected = detector.detectMarkers(image)
    return corners, ids, rejected


def compute_homography(
    corners: list, ids: np.ndarray
) -> tuple[np.ndarray | None, float]:
    """Compute homography from detected markers to real-world mm coordinates.

    Returns (homography_matrix, reprojection_error).
    Needs at least 3 markers for a good homography; 4 is ideal.
    """
    src_points = []  # pixel coordinates
    dst_points = []  # mm coordinates

    for i, marker_id in enumerate(ids.flatten()):
        if marker_id in MARKER_CORNERS_MM:
            # corners[i][0] has shape (4, 2) - the 4 corners in pixel coords
            pixel_corners = corners[i][0]
            mm_corners = MARKER_CORNERS_MM[marker_id]

            for pc, mc in zip(pixel_corners, mm_corners):
                src_points.append(pc)
                dst_points.append(mc)

    if len(src_points) < 8:  # need at least 2 markers (8 points)
        logger.warning("Not enough markers detected for homography: %d points", len(src_points))
        return None, 0.0

    src = np.array(src_points, dtype=np.float32)
    dst = np.array(dst_points, dtype=np.float32)

    H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 3.0)

    if H is None:
        return None, 0.0

    # Compute reprojection error
    projected = cv2.perspectiveTransform(src.reshape(-1, 1, 2), H)
    errors = np.linalg.norm(projected.reshape(-1, 2) - dst, axis=1)
    mean_error = float(np.mean(errors))

    return H, mean_error


def rectify_image(image: np.ndarray, H: np.ndarray) -> np.ndarray:
    """Warp image to top-down view using homography.

    Output is in mm coordinate space at 5 pixels per mm (high resolution).
    """
    # Output: A3 mat at 5 px/mm = 2100 x 1485 pixels
    px_per_mm = 5
    out_w = int(420 * px_per_mm)
    out_h = int(297 * px_per_mm)

    # Scale homography to output in pixels (not mm)
    S = np.array([
        [px_per_mm, 0, 0],
        [0, px_per_mm, 0],
        [0, 0, 1],
    ], dtype=np.float64)

    H_scaled = S @ H
    rectified = cv2.warpPerspective(image, H_scaled, (out_w, out_h))
    return rectified


def detect_book_contour(
    rectified: np.ndarray, px_per_mm: float = 5.0
) -> tuple[np.ndarray | None, Dimensions | None]:
    """Detect the book as the largest rectangular contour in the rectified image.

    The rectified image is in mm-scaled pixel space, so dimensions
    can be directly converted.
    """
    gray = cv2.cvtColor(rectified, cv2.COLOR_BGR2GRAY)

    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)

    # Adaptive threshold to handle varying book cover colors
    thresh = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 21, 5
    )

    # Morphological closing to fill gaps in the book outline
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    # Find contours
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return None, None

    # Filter: find the largest contour that approximates to a quadrilateral
    # Exclude very small contours and very large ones (the mat itself)
    mat_area = rectified.shape[0] * rectified.shape[1]
    min_area = mat_area * 0.02  # book should be at least 2% of mat
    max_area = mat_area * 0.70  # and at most 70%

    best_contour = None
    best_area = 0

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area or area > max_area:
            continue

        # Approximate to polygon
        epsilon = 0.02 * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)

        # Accept quadrilaterals (4 vertices) or close approximations
        if 4 <= len(approx) <= 8 and area > best_area:
            best_contour = approx
            best_area = area

    if best_contour is None:
        # Fallback: use the largest contour regardless of shape
        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)
        if area < min_area:
            return None, None
        best_contour = largest

    # Get rotated bounding rectangle
    rect = cv2.minAreaRect(best_contour)
    (cx, cy), (w, h), angle = rect

    # Convert pixels to mm
    w_mm = w / px_per_mm
    h_mm = h / px_per_mm

    # Ensure height > width (books are taller than wide)
    height_mm = round(max(w_mm, h_mm), 1)
    width_mm = round(min(w_mm, h_mm), 1)

    dims = Dimensions(
        height_mm=height_mm,
        width_mm=width_mm,
        confidence=0.0,  # will be set by caller based on marker count
    )

    return best_contour, dims


def extract_dimensions(image: np.ndarray) -> ExtractionResult:
    """Main entry point: extract book dimensions from a photo of the calibration mat.

    Args:
        image: BGR image (from cv2.imread or decoded from upload)

    Returns:
        ExtractionResult with dimensions, rectified image, and debug info.
    """
    # Step 1: Detect ArUco markers
    corners, ids, _ = detect_aruco_markers(image)

    if ids is None or len(ids) == 0:
        logger.warning("No ArUco markers detected")
        return ExtractionResult(
            dimensions=None,
            rectified_image=None,
            book_contour=None,
            markers_found=0,
            debug_image=_draw_debug(image, [], None, None),
        )

    markers_found = len(ids)
    logger.info("Detected %d ArUco markers: %s", markers_found, ids.flatten().tolist())

    # Step 2: Compute homography
    H, reproj_error = compute_homography(corners, ids)

    if H is None:
        logger.warning("Failed to compute homography")
        return ExtractionResult(
            dimensions=None,
            rectified_image=None,
            book_contour=None,
            markers_found=markers_found,
            debug_image=_draw_debug(image, corners, None, None),
        )

    logger.info("Homography reprojection error: %.2f mm", reproj_error)

    # Step 3: Rectify image
    px_per_mm = 5.0
    rectified = rectify_image(image, H)

    # Step 4: Detect book contour and measure
    contour, dims = detect_book_contour(rectified, px_per_mm)

    if dims is not None:
        # Confidence based on markers found and reprojection error
        marker_conf = min(markers_found / 4.0, 1.0)
        error_conf = max(0.0, 1.0 - reproj_error / 5.0)
        dims.confidence = round(marker_conf * error_conf, 2)

        logger.info(
            "Book dimensions: %.1f x %.1f mm (confidence: %.0f%%)",
            dims.height_mm, dims.width_mm, dims.confidence * 100,
        )

    return ExtractionResult(
        dimensions=dims,
        rectified_image=rectified,
        book_contour=contour,
        markers_found=markers_found,
        debug_image=_draw_debug(image, corners, contour, dims),
    )


def measure_spine_depth(image: np.ndarray) -> ExtractionResult:
    """Measure spine depth from a photo of the book lying on its side.

    Same pipeline as extract_dimensions, but interprets the shorter
    dimension as the spine depth.
    """
    result = extract_dimensions(image)

    if result.dimensions is not None:
        # For spine measurement, the shorter dimension is the depth
        result.dimensions = Dimensions(
            height_mm=result.dimensions.width_mm,  # spine "width" = book depth
            width_mm=result.dimensions.height_mm,
            confidence=result.dimensions.confidence,
        )

    return result


def _draw_debug(
    image: np.ndarray,
    corners: list,
    book_contour: np.ndarray | None,
    dims: Dimensions | None,
) -> np.ndarray:
    """Draw debug annotations on the image."""
    debug = image.copy()

    # Draw detected markers
    if corners:
        cv2.aruco.drawDetectedMarkers(debug, corners)

    # Draw book contour
    if book_contour is not None:
        cv2.drawContours(debug, [book_contour], -1, (0, 255, 0), 3)

    # Draw dimensions text
    if dims is not None:
        text = f"{dims.height_mm:.0f} x {dims.width_mm:.0f} mm ({dims.confidence:.0%})"
        cv2.putText(
            debug, text, (20, 60),
            cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3,
        )

    return debug
