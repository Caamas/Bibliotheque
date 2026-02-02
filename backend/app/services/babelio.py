"""Babelio integration service - scrape book info from babelio.com.

Note: Babelio doesn't have a public API. This uses web scraping.
Please respect their terms of service and rate limits.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BABELIO_BASE = "https://www.babelio.com"
SEARCH_URL = f"{BABELIO_BASE}/recherche.php"


@dataclass
class BabelioBookInfo:
    """Book information from Babelio."""
    url: str = ""
    title: str = ""
    author: str = ""
    rating: Optional[float] = None
    rating_count: Optional[int] = None
    review_count: Optional[int] = None
    summary: Optional[str] = None
    tags: list[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


async def search_babelio(query: str, isbn: Optional[str] = None) -> Optional[BabelioBookInfo]:
    """Search Babelio for a book by title/author or ISBN.

    Args:
        query: Search string (title, author, or combined)
        isbn: Optional ISBN for more precise matching

    Returns:
        BabelioBookInfo if found, None otherwise
    """
    search_term = isbn if isbn else query

    async with httpx.AsyncClient(
        timeout=15.0,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; Bibliotheque/1.0; personal library manager)",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        },
        follow_redirects=True,
    ) as client:
        try:
            resp = await client.get(SEARCH_URL, params={"q": search_term})
            if resp.status_code != 200:
                logger.warning(f"Babelio search returned {resp.status_code}")
                return None

            soup = BeautifulSoup(resp.text, "html.parser")

            # Find the first book result
            results = soup.select(".list_livre .titre")
            if not results:
                # Try alternative selectors
                results = soup.select("a.titre1")

            if not results:
                logger.info(f"No Babelio results for: {search_term}")
                return None

            # Get the first result's page
            book_link = results[0]
            book_url = book_link.get("href", "")
            if book_url and not book_url.startswith("http"):
                book_url = f"{BABELIO_BASE}{book_url}"

            if not book_url:
                return None

            # Fetch the book page
            book_resp = await client.get(book_url)
            if book_resp.status_code != 200:
                return None

            return _parse_book_page(book_resp.text, book_url)

        except httpx.RequestError as e:
            logger.error(f"Babelio request error: {e}")
            return None
        except Exception as e:
            logger.error(f"Babelio parsing error: {e}")
            return None


def _parse_book_page(html: str, url: str) -> BabelioBookInfo:
    """Parse a Babelio book page for metadata."""
    soup = BeautifulSoup(html, "html.parser")
    info = BabelioBookInfo(url=url)

    # Title
    title_el = soup.select_one("h1.livre_header_titre a") or soup.select_one("h1 a")
    if title_el:
        info.title = title_el.get_text(strip=True)

    # Author
    author_el = soup.select_one("span.livre_header_auteur a") or soup.select_one(".auteur a")
    if author_el:
        info.author = author_el.get_text(strip=True)

    # Rating
    rating_el = soup.select_one(".gro_stars_div") or soup.select_one("[itemprop='ratingValue']")
    if rating_el:
        try:
            rating_text = rating_el.get_text(strip=True).replace(",", ".")
            info.rating = float(rating_text.split("/")[0])
        except (ValueError, IndexError):
            pass

    # Summary
    summary_el = soup.select_one("#d_bio") or soup.select_one("[itemprop='description']")
    if summary_el:
        info.summary = summary_el.get_text(strip=True)

    # Tags/Genres
    tag_els = soup.select(".tags a") or soup.select(".livre_tags a")
    info.tags = [t.get_text(strip=True) for t in tag_els[:10]]

    return info
