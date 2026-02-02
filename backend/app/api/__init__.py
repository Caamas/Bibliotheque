from fastapi import APIRouter

from app.api.books import router as books_router
from app.api.shelves import router as shelves_router
from app.api.lending import router as lending_router
from app.api.wishlist import router as wishlist_router
from app.api.scanner import router as scanner_router
from app.api.optimizer import router as optimizer_router

api_router = APIRouter(prefix="/api")
api_router.include_router(books_router)
api_router.include_router(shelves_router)
api_router.include_router(lending_router)
api_router.include_router(wishlist_router)
api_router.include_router(scanner_router)
api_router.include_router(optimizer_router)
