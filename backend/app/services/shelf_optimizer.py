"""Shelf optimization service - assigns books to shelves minimizing wasted vertical space.

Uses a height-clustered bin-packing approach:
1. Group books by height into clusters
2. Calculate optimal shelf heights for adjustable shelves
3. Assign books to shelves considering width constraints
4. Sub-sort within shelves by user preference (genre, author, etc)
"""

import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# Default height clusters (mm) - based on common French book formats
DEFAULT_CLUSTERS = {
    "poche": (150, 190),         # Livres de poche (pocket books)
    "standard": (190, 225),      # Format standard broché
    "grand_format": (225, 260),  # Grand format
    "beau_livre": (260, 350),    # Beaux livres / art books
    "oversize": (350, 500),      # Oversized books
}

SHELF_MARGIN_MM = 15  # Extra space above tallest book on a shelf


class SortOrder(str, Enum):
    GENRE = "genre"
    AUTHOR = "author"
    PUBLISHER = "publisher"
    TITLE = "title"
    LAST_READ = "last_read"


@dataclass
class BookForOptimizer:
    """Minimal book representation for the optimizer."""
    copy_id: int
    book_id: int
    title: str
    authors: list[str]
    height_mm: float
    width_mm: float  # spine width for linear space calculation
    genre: str = ""
    publisher: str = ""
    last_read: str = ""  # ISO date string for sorting


@dataclass
class ShelfForOptimizer:
    """Minimal shelf representation for the optimizer."""
    shelf_id: int
    bookcase_id: int
    bookcase_name: str
    shelf_number: int
    usable_height_mm: float
    usable_width_mm: float
    adjustable: bool = True


@dataclass
class ShelfAssignment:
    """Result: a book assigned to a specific shelf position."""
    copy_id: int
    shelf_id: int
    position: int
    book_title: str


@dataclass
class HeightCluster:
    """A group of books with similar heights."""
    name: str
    min_height: float
    max_height: float
    books: list[BookForOptimizer] = field(default_factory=list)

    @property
    def required_shelf_height(self) -> float:
        """Minimum shelf height needed for this cluster."""
        if not self.books:
            return 0
        return max(b.height_mm for b in self.books) + SHELF_MARGIN_MM

    @property
    def total_width(self) -> float:
        """Total linear width needed for all books in this cluster."""
        return sum(b.width_mm for b in self.books)


@dataclass
class OptimizationResult:
    """Complete result of shelf optimization."""
    assignments: list[ShelfAssignment]
    unassigned_books: list[BookForOptimizer]
    clusters: list[HeightCluster]
    shelf_utilization: dict[int, dict]  # shelf_id -> {height_used, width_used, %util}
    suggested_shelf_heights: dict[int, float]  # shelf_id -> recommended height
    total_books: int
    assigned_count: int
    warnings: list[str] = field(default_factory=list)


def _cluster_books(
    books: list[BookForOptimizer],
    clusters: dict[str, tuple[float, float]] | None = None,
) -> list[HeightCluster]:
    """Group books into height clusters."""
    if clusters is None:
        clusters = DEFAULT_CLUSTERS

    height_clusters = [
        HeightCluster(name=name, min_height=min_h, max_height=max_h)
        for name, (min_h, max_h) in clusters.items()
    ]

    for book in books:
        assigned = False
        for cluster in height_clusters:
            if cluster.min_height <= book.height_mm < cluster.max_height:
                cluster.books.append(book)
                assigned = True
                break

        if not assigned:
            # Book doesn't fit any cluster - assign to nearest
            if book.height_mm < height_clusters[0].min_height:
                height_clusters[0].books.append(book)
            else:
                height_clusters[-1].books.append(book)

    # Remove empty clusters
    return [c for c in height_clusters if c.books]


def _sort_books_on_shelf(
    books: list[BookForOptimizer],
    sort_order: SortOrder = SortOrder.AUTHOR,
) -> list[BookForOptimizer]:
    """Sort books within a shelf by the given criterion."""
    if sort_order == SortOrder.GENRE:
        return sorted(books, key=lambda b: (b.genre or "", b.authors[0] if b.authors else "", b.title))
    elif sort_order == SortOrder.AUTHOR:
        return sorted(books, key=lambda b: (b.authors[0] if b.authors else "", b.title))
    elif sort_order == SortOrder.PUBLISHER:
        return sorted(books, key=lambda b: (b.publisher or "", b.authors[0] if b.authors else "", b.title))
    elif sort_order == SortOrder.TITLE:
        return sorted(books, key=lambda b: b.title)
    elif sort_order == SortOrder.LAST_READ:
        return sorted(books, key=lambda b: b.last_read or "0000-00-00", reverse=True)
    return books


def optimize_shelves(
    books: list[BookForOptimizer],
    shelves: list[ShelfForOptimizer],
    sort_order: SortOrder = SortOrder.AUTHOR,
    custom_clusters: dict[str, tuple[float, float]] | None = None,
) -> OptimizationResult:
    """
    Main optimization function.

    Algorithm:
    1. Cluster books by height
    2. Sort clusters by required height (descending) - assign tallest first
    3. For each cluster, find shelves that can accommodate the height
    4. Pack books into shelves respecting width constraints
    5. Sort books within each shelf

    Returns an OptimizationResult with assignments and statistics.
    """
    if not books:
        return OptimizationResult(
            assignments=[], unassigned_books=[], clusters=[],
            shelf_utilization={}, suggested_shelf_heights={},
            total_books=0, assigned_count=0,
        )

    # Books without height data get a default estimate
    warnings = []
    for book in books:
        if not book.height_mm or book.height_mm <= 0:
            book.height_mm = 210  # Default to standard format
            warnings.append(f"No height for '{book.title}', defaulting to 210mm")
        if not book.width_mm or book.width_mm <= 0:
            book.width_mm = 25  # Default spine width

    # Step 1: Cluster
    clusters = _cluster_books(books, custom_clusters)

    # Sort clusters by required height descending (assign tall books first)
    clusters.sort(key=lambda c: c.required_shelf_height, reverse=True)

    # Step 2: Prepare shelf tracking
    shelf_remaining_width = {s.shelf_id: s.usable_width_mm for s in shelves}
    shelf_books: dict[int, list[BookForOptimizer]] = {s.shelf_id: [] for s in shelves}
    suggested_heights: dict[int, float] = {}
    assignments: list[ShelfAssignment] = []
    unassigned: list[BookForOptimizer] = []

    # Sort shelves by height descending for matching
    available_shelves = sorted(shelves, key=lambda s: s.usable_height_mm, reverse=True)

    # Step 3: Assign clusters to shelves
    for cluster in clusters:
        required_height = cluster.required_shelf_height
        cluster_books = list(cluster.books)  # Copy for consumption

        # Find all shelves that can accommodate this height
        fitting_shelves = [
            s for s in available_shelves
            if s.usable_height_mm >= required_height and shelf_remaining_width[s.shelf_id] > 0
        ]

        if not fitting_shelves:
            # Try adjustable shelves - suggest new height
            adjustable = [s for s in available_shelves if s.adjustable and shelf_remaining_width[s.shelf_id] > 0]
            if adjustable:
                fitting_shelves = adjustable
                for s in adjustable:
                    suggested_heights[s.shelf_id] = required_height

        # Pack books into fitting shelves (first-fit decreasing width)
        for book in cluster_books:
            placed = False
            # Prefer shelf with least remaining space that still fits (best-fit)
            fitting_shelves.sort(key=lambda s: shelf_remaining_width[s.shelf_id])

            for shelf in fitting_shelves:
                if shelf_remaining_width[shelf.shelf_id] >= book.width_mm:
                    shelf_books[shelf.shelf_id].append(book)
                    shelf_remaining_width[shelf.shelf_id] -= book.width_mm
                    placed = True
                    break

            if not placed:
                unassigned.append(book)

    # Step 4: Sort books within each shelf and generate assignments
    for shelf in shelves:
        books_on_shelf = shelf_books[shelf.shelf_id]
        if not books_on_shelf:
            continue

        sorted_books = _sort_books_on_shelf(books_on_shelf, sort_order)
        for pos, book in enumerate(sorted_books, 1):
            assignments.append(ShelfAssignment(
                copy_id=book.copy_id,
                shelf_id=shelf.shelf_id,
                position=pos,
                book_title=book.title,
            ))

    # Step 5: Calculate utilization stats
    utilization = {}
    for shelf in shelves:
        books_on_shelf = shelf_books[shelf.shelf_id]
        if not books_on_shelf:
            utilization[shelf.shelf_id] = {
                "books_count": 0,
                "width_used_mm": 0,
                "width_total_mm": shelf.usable_width_mm,
                "width_utilization_pct": 0,
                "max_book_height_mm": 0,
                "height_available_mm": shelf.usable_height_mm,
                "height_wasted_mm": shelf.usable_height_mm,
            }
        else:
            width_used = sum(b.width_mm for b in books_on_shelf)
            max_height = max(b.height_mm for b in books_on_shelf)
            utilization[shelf.shelf_id] = {
                "books_count": len(books_on_shelf),
                "width_used_mm": round(width_used, 1),
                "width_total_mm": shelf.usable_width_mm,
                "width_utilization_pct": round(width_used / shelf.usable_width_mm * 100, 1),
                "max_book_height_mm": round(max_height, 1),
                "height_available_mm": shelf.usable_height_mm,
                "height_wasted_mm": round(shelf.usable_height_mm - max_height - SHELF_MARGIN_MM, 1),
            }

    if unassigned:
        warnings.append(
            f"{len(unassigned)} book(s) could not be assigned to any shelf. "
            "Consider adding more shelf space."
        )

    return OptimizationResult(
        assignments=assignments,
        unassigned_books=unassigned,
        clusters=clusters,
        shelf_utilization=utilization,
        suggested_shelf_heights=suggested_heights,
        total_books=len(books),
        assigned_count=len(assignments),
        warnings=warnings,
    )


def suggest_shelf_configuration(
    books: list[BookForOptimizer],
    bookcase_height_mm: float,
    bookcase_width_mm: float,
    min_shelf_height_mm: float = 160,
    shelf_thickness_mm: float = 20,
) -> list[dict]:
    """Given books and an empty bookcase, suggest optimal shelf heights.

    This solves: "I have an empty bookcase of height H and width W.
    How should I set the adjustable shelves to best fit my books?"

    Returns a list of suggested shelves with heights.
    """
    clusters = _cluster_books(books)

    # Calculate how many shelves of each height we need
    shelf_configs = []
    remaining_height = bookcase_height_mm

    for cluster in sorted(clusters, key=lambda c: c.required_shelf_height):
        shelf_height = cluster.required_shelf_height
        if shelf_height < min_shelf_height_mm:
            shelf_height = min_shelf_height_mm

        # How many shelves of this height do we need?
        shelves_needed = 1
        total_book_width = cluster.total_width
        while total_book_width > bookcase_width_mm * shelves_needed:
            shelves_needed += 1

        for i in range(shelves_needed):
            cost = shelf_height + shelf_thickness_mm
            if remaining_height >= cost:
                shelf_configs.append({
                    "cluster": cluster.name,
                    "height_mm": shelf_height,
                    "books_count": len(cluster.books) if i == 0 else 0,
                    "max_book_height_mm": max(b.height_mm for b in cluster.books),
                })
                remaining_height -= cost

    # If there's leftover space, distribute it to the tallest shelves
    if remaining_height > 0 and shelf_configs:
        extra_per_shelf = remaining_height / len(shelf_configs)
        for config in shelf_configs:
            config["height_mm"] = round(config["height_mm"] + extra_per_shelf, 1)

    return shelf_configs
