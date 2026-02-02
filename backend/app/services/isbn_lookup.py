"""ISBN lookup service - fetches book metadata from Open Library and Google Books."""

import logging
from dataclasses import dataclass, field
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Common book height mappings (format -> typical height in mm)
FORMAT_HEIGHTS = {
    "mass_market_paperback": 175,
    "pocket": 178,
    "paperback": 210,
    "trade_paperback": 235,
    "hardcover": 240,
    "large_print": 250,
    "folio": 310,
}


@dataclass
class BookMetadata:
    """Normalized book metadata from any source."""
    isbn_13: Optional[str] = None
    isbn_10: Optional[str] = None
    title: str = ""
    subtitle: Optional[str] = None
    authors: list[str] = field(default_factory=list)
    publisher: Optional[str] = None
    publication_date: Optional[str] = None
    page_count: Optional[int] = None
    height_mm: Optional[float] = None
    width_mm: Optional[float] = None
    depth_mm: Optional[float] = None
    cover_url: Optional[str] = None
    genre: Optional[str] = None
    language: Optional[str] = None
    description: Optional[str] = None

    def merge(self, other: "BookMetadata") -> "BookMetadata":
        """Merge another metadata object, filling in missing fields."""
        for attr in self.__dataclass_fields__:
            current = getattr(self, attr)
            other_val = getattr(other, attr)
            if not current and other_val:
                setattr(self, attr, other_val)
            elif attr == "authors" and not current and other_val:
                setattr(self, attr, other_val)
        return self


def _normalize_isbn(isbn: str) -> str:
    """Strip hyphens and spaces from ISBN."""
    return isbn.replace("-", "").replace(" ", "").strip()


def _parse_dimensions_cm(dimensions: dict) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """Parse Google Books dimensions (in cm) to mm."""
    h = dimensions.get("height")
    w = dimensions.get("width")
    d = dimensions.get("thickness")

    def to_mm(val: Optional[str]) -> Optional[float]:
        if not val:
            return None
        try:
            # Google returns strings like "21.5 cm"
            num = float(val.replace("cm", "").strip())
            return num * 10
        except (ValueError, AttributeError):
            return None

    return to_mm(h), to_mm(w), to_mm(d)


async def lookup_open_library(isbn: str) -> Optional[BookMetadata]:
    """Fetch metadata from Open Library API."""
    isbn = _normalize_isbn(isbn)
    url = f"{settings.OPEN_LIBRARY_BASE_URL}/isbn/{isbn}.json"

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url, follow_redirects=True)
            if resp.status_code != 200:
                logger.info(f"Open Library: no result for ISBN {isbn}")
                return None

            data = resp.json()
            meta = BookMetadata(title=data.get("title", ""))
            meta.subtitle = data.get("subtitle")
            meta.page_count = data.get("number_of_pages")
            meta.publication_date = data.get("publish_date")

            # Publishers
            publishers = data.get("publishers", [])
            if publishers:
                meta.publisher = publishers[0]

            # Authors - need to resolve author keys
            author_keys = [a.get("key") for a in data.get("authors", []) if a.get("key")]
            for key in author_keys[:5]:
                try:
                    author_resp = await client.get(
                        f"{settings.OPEN_LIBRARY_BASE_URL}{key}.json",
                        follow_redirects=True
                    )
                    if author_resp.status_code == 200:
                        author_data = author_resp.json()
                        name = author_data.get("name", "")
                        if name:
                            meta.authors.append(name)
                except Exception:
                    pass

            # Cover
            covers = data.get("covers", [])
            if covers:
                meta.cover_url = f"https://covers.openlibrary.org/b/id/{covers[0]}-L.jpg"

            # Physical dimensions
            physical = data.get("physical_dimensions", "")
            if physical:
                # Format: "21.5 x 13.5 x 1.5 centimeters"
                try:
                    parts = physical.replace("centimeters", "").replace("inches", "")
                    dims = [float(p.strip()) for p in parts.split("x")]
                    if "centimeters" in physical.lower() or "cm" in physical.lower():
                        if len(dims) >= 1:
                            meta.height_mm = dims[0] * 10
                        if len(dims) >= 2:
                            meta.width_mm = dims[1] * 10
                        if len(dims) >= 3:
                            meta.depth_mm = dims[2] * 10
                    elif "inches" in physical.lower():
                        if len(dims) >= 1:
                            meta.height_mm = dims[0] * 25.4
                        if len(dims) >= 2:
                            meta.width_mm = dims[1] * 25.4
                        if len(dims) >= 3:
                            meta.depth_mm = dims[2] * 25.4
                except (ValueError, IndexError):
                    pass

            # Physical format -> estimate height
            if not meta.height_mm:
                phys_format = data.get("physical_format", "").lower()
                for fmt, height in FORMAT_HEIGHTS.items():
                    if fmt in phys_format:
                        meta.height_mm = height
                        break

            # Languages
            langs = data.get("languages", [])
            if langs:
                lang_key = langs[0].get("key", "")
                meta.language = lang_key.split("/")[-1] if lang_key else None

            # ISBN normalization
            isbn_13s = data.get("isbn_13", [])
            isbn_10s = data.get("isbn_10", [])
            if isbn_13s:
                meta.isbn_13 = isbn_13s[0]
            elif len(isbn) == 13:
                meta.isbn_13 = isbn
            if isbn_10s:
                meta.isbn_10 = isbn_10s[0]
            elif len(isbn) == 10:
                meta.isbn_10 = isbn

            # Description (might need works endpoint)
            if not meta.description:
                works = data.get("works", [])
                if works:
                    work_key = works[0].get("key", "")
                    try:
                        work_resp = await client.get(
                            f"{settings.OPEN_LIBRARY_BASE_URL}{work_key}.json",
                            follow_redirects=True
                        )
                        if work_resp.status_code == 200:
                            work_data = work_resp.json()
                            desc = work_data.get("description")
                            if isinstance(desc, dict):
                                meta.description = desc.get("value", "")
                            elif isinstance(desc, str):
                                meta.description = desc

                            # Subjects as genre
                            subjects = work_data.get("subjects", [])
                            if subjects:
                                meta.genre = subjects[0] if isinstance(subjects[0], str) else ""
                    except Exception:
                        pass

            return meta

        except httpx.RequestError as e:
            logger.error(f"Open Library request error: {e}")
            return None


async def lookup_google_books(isbn: str) -> Optional[BookMetadata]:
    """Fetch metadata from Google Books API."""
    isbn = _normalize_isbn(isbn)
    params = {"q": f"isbn:{isbn}"}
    if settings.GOOGLE_BOOKS_API_KEY:
        params["key"] = settings.GOOGLE_BOOKS_API_KEY

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                f"{settings.GOOGLE_BOOKS_BASE_URL}/volumes",
                params=params
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            if data.get("totalItems", 0) == 0:
                return None

            volume = data["items"][0]["volumeInfo"]
            meta = BookMetadata(
                title=volume.get("title", ""),
                subtitle=volume.get("subtitle"),
                authors=volume.get("authors", []),
                publisher=volume.get("publisher"),
                publication_date=volume.get("publishedDate"),
                page_count=volume.get("pageCount"),
                language=volume.get("language"),
                description=volume.get("description"),
            )

            # ISBNs
            for identifier in volume.get("industryIdentifiers", []):
                if identifier["type"] == "ISBN_13":
                    meta.isbn_13 = identifier["identifier"]
                elif identifier["type"] == "ISBN_10":
                    meta.isbn_10 = identifier["identifier"]

            # Cover image
            images = volume.get("imageLinks", {})
            meta.cover_url = images.get("thumbnail", images.get("smallThumbnail"))
            # Upgrade to higher quality
            if meta.cover_url:
                meta.cover_url = meta.cover_url.replace("zoom=1", "zoom=2")

            # Dimensions
            dimensions = volume.get("dimensions", {})
            if dimensions:
                meta.height_mm, meta.width_mm, meta.depth_mm = _parse_dimensions_cm(dimensions)

            # Categories as genre
            categories = volume.get("categories", [])
            if categories:
                meta.genre = categories[0]

            return meta

        except httpx.RequestError as e:
            logger.error(f"Google Books request error: {e}")
            return None


async def lookup_isbn(isbn: str) -> Optional[BookMetadata]:
    """Look up ISBN from multiple sources, merging results.

    Tries Open Library first (better for physical dimensions and French books),
    then Google Books for additional data.
    """
    isbn = _normalize_isbn(isbn)

    # Query both in parallel would be ideal, but sequential is simpler
    # and avoids rate limiting issues
    ol_meta = await lookup_open_library(isbn)
    gb_meta = await lookup_google_books(isbn)

    if ol_meta and gb_meta:
        return ol_meta.merge(gb_meta)
    elif ol_meta:
        return ol_meta
    elif gb_meta:
        return gb_meta

    logger.warning(f"No metadata found for ISBN {isbn}")
    return None
