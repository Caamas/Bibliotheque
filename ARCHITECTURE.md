# Bibliotheque - Architecture & Proposal

## Overview

**Bibliotheque** is a self-hosted bookshelf management application designed for a
personal collection of ~1000 books. It consists of a Python backend (FastAPI) and
a React PWA frontend, deployable via Docker on a home server.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    iPad / Browser                     │
│              (React PWA - Camera Access)              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐  │
│  │ Scanner  │ │ Library  │ │ Shelves  │ │Wishlist│  │
│  │ (Camera) │ │ Browser  │ │ Manager  │ │ Share  │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └───┬────┘  │
└───────┼─────────────┼───────────┼────────────┼───────┘
        │             │           │            │
        ▼             ▼           ▼            ▼
┌─────────────────────────────────────────────────────┐
│              FastAPI Backend (Home Server)            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐  │
│  │ ISBN     │ │ Book     │ │ Shelf    │ │Lending │  │
│  │ Lookup   │ │ CRUD     │ │Optimizer │ │Reminder│  │
│  └────┬─────┘ └──────────┘ └──────────┘ └────────┘  │
│       │                                              │
│  ┌────┴──────────────────────────────┐               │
│  │     External APIs                  │               │
│  │  - Open Library  - Google Books    │               │
│  │  - Babelio (scraping)              │               │
│  └───────────────────────────────────┘               │
│                                                       │
│  ┌───────────────────────────────────┐               │
│  │  SQLite Database + File Storage    │               │
│  │  (covers, signatures, shelf photos)│               │
│  └───────────────────────────────────┘               │
└─────────────────────────────────────────────────────┘
```

## Technology Stack

| Layer    | Technology                  | Rationale                          |
|----------|-----------------------------|------------------------------------|
| Backend  | Python 3.11 + FastAPI       | Async, fast, great ecosystem       |
| Database | SQLite (via SQLAlchemy 2.0) | Zero config, single-file, portable |
| Frontend | React 18 + TypeScript + Vite| PWA support, camera API access     |
| Styling  | TailwindCSS                 | Rapid responsive UI development    |
| Scanner  | html5-qrcode (frontend)     | Browser-native barcode scanning    |
| Deploy   | Docker Compose              | One-command deployment             |

## Database Schema

### Core Entities

```
books                    book_copies              shelves
─────────────            ─────────────            ─────────────
id (PK)                  id (PK)                  id (PK)
isbn                     book_id (FK)             bookcase_id (FK)
title                    condition                shelf_number
subtitle                 is_signed                label
authors (JSON)           signature_photo          usable_height_mm
publisher                purchase_date            usable_width_mm
publication_date         purchase_location        usable_depth_mm
page_count               purchase_price
height_mm ◄──────────── personal_rating          bookcases
width_mm                 personal_review          ─────────────
depth_mm                 last_read_date           id (PK)
cover_url                read_count               name
genre                    storage_type             location
language                 shelf_id (FK) ──────────►room
description              shelf_position           photo
babelio_url              created_at
                         updated_at

lendings                 wishlists                awards
─────────────            ─────────────            ─────────────
id (PK)                  id (PK)                  id (PK)
book_copy_id (FK)        name                     name
borrower_name            share_token              year
borrower_contact         created_at
lent_date                                         book_awards
expected_return                                   ─────────────
actual_return            wishlist_items           book_id (FK)
reminder_sent            ─────────────            award_id (FK)
                         wishlist_id (FK)         status (nominated/
                         isbn                       shortlisted/won)
                         title
                         author
                         priority
                         notes
```

### Key Design Decisions

1. **books vs book_copies**: A `book` is the abstract work (ISBN, metadata).
   A `book_copy` is your physical copy (condition, signed, location). This
   allows wishlists to reference books you don't own, and supports multiple
   editions of the same work.

2. **height_mm on books table**: Critical for the shelf optimizer. Sourced from
   metadata APIs when available, otherwise measured manually. The optimizer
   groups books by height to minimize wasted vertical space.

3. **SQLite**: For ~1000 books, SQLite is more than sufficient and eliminates
   the need for a database server. The entire DB is a single file, trivially
   backed up.

## Shelf Optimization Algorithm

### Problem
Given N books with known heights and M adjustable shelves, assign books to
shelves such that vertical wasted space is minimized.

### Approach: Height-Clustered Bin Packing

```
Phase 1: Clustering
  1. Collect all book heights
  2. Apply k-means or fixed-threshold clustering:
     - Pocket:      < 190mm  (typically 178mm)
     - Standard:    190-230mm (typically 210mm)
     - Trade:       230-260mm (typically 240mm)
     - Large/Art:   > 260mm
  3. Allow user-defined custom clusters

Phase 2: Shelf Assignment
  1. For each cluster, compute required shelf height = max(heights) + 15mm margin
  2. Compute total linear width needed per cluster
  3. Solve assignment: which shelves get which clusters
  4. Greedy algorithm: assign largest cluster first to best-fitting shelves
  5. Sub-sort within shelves by: genre > author > title

Phase 3: Physical Layout
  1. Generate shelf-by-shelf assignment list
  2. Provide "moving plan" - which books go where
  3. Suggest adjustable shelf pin positions
```

### Height Data Sources
- Open Library: sometimes includes physical dimensions
- Google Books: `dimensions` field in volume info
- Manual input: fallback with quick-entry UI
- Common ISBNs: pocket editions are ~178mm, standard ~210mm

## User Workflows

### Phase 1: Initial Scanning (~1000 books)
```
1. Open PWA on iPad
2. Enter "Batch Scan" mode
3. Point camera at ISBN barcode → auto-detect
4. Backend fetches metadata → display for confirmation
5. Quick-edit fields (height if missing, condition, location)
6. Tap "Next" → scan next book
7. Target: 10-15 seconds per book → ~3-4 hours for 1000 books
```

### Phase 2: Shelf Organization
```
1. Define bookcases and shelves (dimensions)
2. Run optimizer → get proposed layout
3. Review and adjust groupings
4. Print/display shelf assignment lists
5. Physically reorganize books
6. Take shelf photos for visual reference
```

### Phase 3: Daily Use
```
- In bookstore: scan ISBN → "Already owned!" or "Add to wishlist"
- Lending: select book → record borrower → auto-reminder
- Reading: mark as "currently reading" → rate when done
- Share wishlist: generate link → send to friends
```

## API Endpoints (Summary)

| Method | Endpoint                     | Purpose                      |
|--------|------------------------------|------------------------------|
| POST   | /api/books/scan              | Scan ISBN, fetch metadata    |
| GET    | /api/books                   | List/search/filter books     |
| GET    | /api/books/{id}              | Book details                 |
| POST   | /api/books                   | Add book manually            |
| PUT    | /api/books/{id}              | Update book                  |
| POST   | /api/copies                  | Add a physical copy          |
| PUT    | /api/copies/{id}             | Update copy (rating, etc.)   |
| GET    | /api/books/check/{isbn}      | Check if ISBN already owned  |
| GET    | /api/shelves                 | List all shelves             |
| POST   | /api/shelves/optimize        | Run shelf optimizer          |
| POST   | /api/lendings                | Record a lending             |
| PUT    | /api/lendings/{id}/return    | Record return                |
| GET    | /api/wishlists               | List wishlists               |
| GET    | /api/wishlists/share/{token} | Public wishlist view         |
| POST   | /api/wishlists/{id}/items    | Add to wishlist              |
| GET    | /api/babelio/search          | Search Babelio               |

## File Structure

```
Bibliotheque/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry
│   │   ├── config.py            # Settings
│   │   ├── database.py          # DB setup
│   │   ├── models/              # SQLAlchemy models
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── api/                 # Route handlers
│   │   └── services/            # Business logic
│   ├── uploads/                 # Cover images, signatures, photos
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/          # Reusable UI components
│   │   ├── pages/               # Route pages
│   │   ├── services/            # API client
│   │   ├── hooks/               # Custom React hooks
│   │   └── App.tsx
│   ├── public/
│   │   └── manifest.json        # PWA manifest
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── ARCHITECTURE.md
└── Makefile
```

## Deployment

Single command: `docker compose up -d`

- Backend: port 8000
- Frontend: port 3000 (served by nginx in production)
- Data persisted in Docker volumes

## Nice-to-have / Future

1. **Babelio integration**: Scrape reviews, ratings, book metadata
2. **Shelf photo recognition**: Take photo of shelf, use OCR/ML to identify spines
3. **Reading statistics**: Charts of books read per year, genre distribution
4. **Barcode batch mode**: Continuous scanning without confirmation for speed
5. **Export/Import**: CSV/JSON export for backup or migration
6. **Multi-user**: Family members with separate ratings/reviews
