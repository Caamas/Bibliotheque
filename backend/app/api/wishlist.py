"""Wishlist management endpoints, including public sharing."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.wishlist import Wishlist, WishlistItem
from app.schemas.wishlist import (
    WishlistCreate, WishlistResponse, WishlistDetailResponse,
    WishlistItemCreate, WishlistItemResponse, WishlistShareResponse,
)

router = APIRouter(prefix="/wishlists", tags=["wishlists"])


@router.get("", response_model=list[WishlistResponse])
async def list_wishlists(db: AsyncSession = Depends(get_db)):
    """List all wishlists."""
    stmt = select(Wishlist).options(selectinload(Wishlist.items)).order_by(Wishlist.created_at.desc())
    result = await db.execute(stmt)
    wishlists = result.scalars().all()

    responses = []
    for wl in wishlists:
        resp = WishlistResponse.model_validate(wl)
        resp.items_count = len(wl.items)
        responses.append(resp)
    return responses


@router.get("/{wishlist_id}", response_model=WishlistDetailResponse)
async def get_wishlist(wishlist_id: int, db: AsyncSession = Depends(get_db)):
    """Get wishlist with all items."""
    stmt = (
        select(Wishlist)
        .where(Wishlist.id == wishlist_id)
        .options(selectinload(Wishlist.items))
    )
    result = await db.execute(stmt)
    wl = result.scalar_one_or_none()

    if not wl:
        raise HTTPException(status_code=404, detail="Wishlist not found")

    resp = WishlistDetailResponse.model_validate(wl)
    resp.items_count = len(wl.items)
    return resp


@router.post("", response_model=WishlistResponse, status_code=201)
async def create_wishlist(data: WishlistCreate, db: AsyncSession = Depends(get_db)):
    """Create a new wishlist."""
    wl = Wishlist(**data.model_dump())
    db.add(wl)
    await db.flush()
    await db.refresh(wl)
    resp = WishlistResponse.model_validate(wl)
    resp.items_count = 0
    return resp


@router.delete("/{wishlist_id}", status_code=204)
async def delete_wishlist(wishlist_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a wishlist."""
    wl = await db.get(Wishlist, wishlist_id)
    if not wl:
        raise HTTPException(status_code=404, detail="Wishlist not found")
    await db.delete(wl)


@router.post("/{wishlist_id}/items", response_model=WishlistItemResponse, status_code=201)
async def add_wishlist_item(
    wishlist_id: int, data: WishlistItemCreate, db: AsyncSession = Depends(get_db)
):
    """Add an item to a wishlist."""
    wl = await db.get(Wishlist, wishlist_id)
    if not wl:
        raise HTTPException(status_code=404, detail="Wishlist not found")

    item = WishlistItem(
        wishlist_id=wishlist_id,
        **data.model_dump(),
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return WishlistItemResponse.model_validate(item)


@router.delete("/{wishlist_id}/items/{item_id}", status_code=204)
async def remove_wishlist_item(
    wishlist_id: int, item_id: int, db: AsyncSession = Depends(get_db)
):
    """Remove an item from a wishlist."""
    stmt = select(WishlistItem).where(
        WishlistItem.id == item_id,
        WishlistItem.wishlist_id == wishlist_id,
    )
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    await db.delete(item)


# --- Public sharing ---

@router.get("/share/{token}", response_model=WishlistShareResponse)
async def get_shared_wishlist(token: str, db: AsyncSession = Depends(get_db)):
    """Public endpoint to view a shared wishlist (no auth required)."""
    stmt = (
        select(Wishlist)
        .where(Wishlist.share_token == token)
        .options(selectinload(Wishlist.items))
    )
    result = await db.execute(stmt)
    wl = result.scalar_one_or_none()

    if not wl:
        raise HTTPException(status_code=404, detail="Wishlist not found")

    return WishlistShareResponse(
        name=wl.name,
        items=[WishlistItemResponse.model_validate(item) for item in wl.items],
    )
