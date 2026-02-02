#!/usr/bin/env python3
"""Generate a printable A3 calibration mat with ArUco markers.

Outputs an SVG file that can be printed at exact scale on A3 paper.
The mat uses DICT_4X4_50 markers at the four corners.

Usage:
    python generate_calibration_mat.py [output_path]

The SVG preserves real-world mm dimensions, so print at 100% scale.
After printing, verify marker size with a ruler (should be 40mm).
"""

import sys
import base64
from pathlib import Path

# --- Mat Configuration (must match dimension_extractor.py) ---
MAT_WIDTH_MM = 420   # A3 landscape width
MAT_HEIGHT_MM = 297  # A3 landscape height
MARKER_SIZE_MM = 40
MARKER_IDS = [0, 1, 2, 3]

# Marker centers (mm from top-left)
MARKER_CENTERS = {
    0: (40, 40),      # top-left
    1: (380, 40),     # top-right
    2: (380, 257),    # bottom-right
    3: (40, 257),     # bottom-left
}

# Background color - dark green (good contrast with most book covers)
BG_COLOR = "#1a3a2a"
MARKER_BLACK = "#000000"
MARKER_WHITE = "#ffffff"
TEXT_COLOR = "#4a7a5a"
GUIDE_COLOR = "#2a5a3a"

# ArUco 4x4_50 marker patterns (6x6 grid including border)
# Each marker is a 6x6 binary matrix where 1=black, 0=white
# The outer ring is always black (border)
ARUCO_4X4_50 = {
    0: [
        [1, 1, 1, 1, 1, 1],
        [1, 0, 0, 0, 1, 1],
        [1, 0, 1, 0, 0, 1],
        [1, 1, 0, 1, 0, 1],
        [1, 0, 1, 1, 0, 1],
        [1, 1, 1, 1, 1, 1],
    ],
    1: [
        [1, 1, 1, 1, 1, 1],
        [1, 0, 0, 1, 0, 1],
        [1, 1, 0, 0, 1, 1],
        [1, 0, 1, 1, 0, 1],
        [1, 1, 0, 0, 0, 1],
        [1, 1, 1, 1, 1, 1],
    ],
    2: [
        [1, 1, 1, 1, 1, 1],
        [1, 1, 0, 0, 0, 1],
        [1, 0, 0, 0, 0, 1],
        [1, 0, 1, 1, 1, 1],
        [1, 1, 0, 1, 0, 1],
        [1, 1, 1, 1, 1, 1],
    ],
    3: [
        [1, 1, 1, 1, 1, 1],
        [1, 1, 0, 1, 1, 1],
        [1, 1, 0, 0, 0, 1],
        [1, 0, 0, 0, 1, 1],
        [1, 0, 0, 1, 1, 1],
        [1, 1, 1, 1, 1, 1],
    ],
}


def marker_to_svg_rects(marker_id: int, cx_mm: float, cy_mm: float, size_mm: float) -> str:
    """Generate SVG rectangles for a single ArUco marker."""
    pattern = ARUCO_4X4_50[marker_id]
    cell_size = size_mm / 6  # 6x6 grid
    x_origin = cx_mm - size_mm / 2
    y_origin = cy_mm - size_mm / 2

    rects = []

    # White background for the entire marker area
    rects.append(
        f'  <rect x="{x_origin}" y="{y_origin}" '
        f'width="{size_mm}" height="{size_mm}" fill="{MARKER_WHITE}"/>'
    )

    # Draw black cells
    for row in range(6):
        for col in range(6):
            if pattern[row][col] == 1:
                x = x_origin + col * cell_size
                y = y_origin + row * cell_size
                rects.append(
                    f'  <rect x="{x:.2f}" y="{y:.2f}" '
                    f'width="{cell_size:.2f}" height="{cell_size:.2f}" fill="{MARKER_BLACK}"/>'
                )

    # Marker ID label
    rects.append(
        f'  <text x="{cx_mm}" y="{cy_mm + size_mm / 2 + 8}" '
        f'text-anchor="middle" fill="{TEXT_COLOR}" font-size="5" font-family="monospace">'
        f'ID:{marker_id}</text>'
    )

    return "\n".join(rects)


def generate_svg() -> str:
    """Generate the full calibration mat SVG."""
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{MAT_WIDTH_MM}mm" height="{MAT_HEIGHT_MM}mm" '
        f'viewBox="0 0 {MAT_WIDTH_MM} {MAT_HEIGHT_MM}">',
        f'  <!-- Bibliotheque Calibration Mat - Print at 100% on A3 -->',
        f'  <!-- Markers: DICT_4X4_50, Size: {MARKER_SIZE_MM}mm -->',
        f'  <!-- VERIFY: Each marker should measure exactly {MARKER_SIZE_MM}mm with a ruler -->',
        "",
        f'  <!-- Background -->',
        f'  <rect width="{MAT_WIDTH_MM}" height="{MAT_HEIGHT_MM}" fill="{BG_COLOR}"/>',
        "",
    ]

    # Book placement guide (centered rectangle)
    guide_x = 80
    guide_y = 60
    guide_w = MAT_WIDTH_MM - 160
    guide_h = MAT_HEIGHT_MM - 120
    parts.extend([
        f'  <!-- Book placement guide -->',
        f'  <rect x="{guide_x}" y="{guide_y}" width="{guide_w}" height="{guide_h}" '
        f'fill="none" stroke="{GUIDE_COLOR}" stroke-width="0.5" stroke-dasharray="5,5"/>',
        f'  <text x="{MAT_WIDTH_MM / 2}" y="{MAT_HEIGHT_MM / 2}" '
        f'text-anchor="middle" fill="{GUIDE_COLOR}" font-size="8" font-family="sans-serif">'
        f'PLACE BOOK HERE</text>',
        "",
    ])

    # ArUco markers
    for mid, (cx, cy) in MARKER_CENTERS.items():
        parts.append(f'  <!-- Marker {mid} at ({cx}, {cy}) -->')
        parts.append(marker_to_svg_rects(mid, cx, cy, MARKER_SIZE_MM))
        parts.append("")

    # Corner indicators and measurements
    parts.extend([
        f'  <!-- Measurement reference -->',
        f'  <text x="{MAT_WIDTH_MM / 2}" y="12" text-anchor="middle" '
        f'fill="{TEXT_COLOR}" font-size="6" font-family="monospace">'
        f'Bibliotheque Calibration Mat - {MAT_WIDTH_MM}x{MAT_HEIGHT_MM}mm (A3) - '
        f'Marker size: {MARKER_SIZE_MM}mm</text>',
        "",
        f'  <!-- Scale verification rulers (10mm marks) -->',
        f'  <line x1="10" y1="{MAT_HEIGHT_MM - 10}" x2="60" y2="{MAT_HEIGHT_MM - 10}" '
        f'stroke="{TEXT_COLOR}" stroke-width="0.3"/>',
    ])

    # 10mm tick marks on bottom ruler
    for i in range(6):
        x = 10 + i * 10
        parts.append(
            f'  <line x1="{x}" y1="{MAT_HEIGHT_MM - 12}" x2="{x}" y2="{MAT_HEIGHT_MM - 8}" '
            f'stroke="{TEXT_COLOR}" stroke-width="0.3"/>'
        )
        if i % 2 == 0:
            parts.append(
                f'  <text x="{x}" y="{MAT_HEIGHT_MM - 14}" text-anchor="middle" '
                f'fill="{TEXT_COLOR}" font-size="3" font-family="monospace">{i * 10}mm</text>'
            )

    parts.append("</svg>")
    return "\n".join(parts)


if __name__ == "__main__":
    output_path = sys.argv[1] if len(sys.argv) > 1 else "calibration_mat.svg"
    svg = generate_svg()
    Path(output_path).write_text(svg)
    print(f"Calibration mat saved to: {output_path}")
    print(f"Mat size: {MAT_WIDTH_MM}x{MAT_HEIGHT_MM}mm (A3 landscape)")
    print(f"Markers: DICT_4X4_50, IDs 0-3, size {MARKER_SIZE_MM}mm")
    print(f"\nIMPORTANT: Print at 100% scale, no page fitting!")
    print(f"Verify marker size with ruler after printing ({MARKER_SIZE_MM}mm).")
