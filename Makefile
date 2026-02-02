.PHONY: dev dev-backend dev-frontend build up down logs

# Development
dev: dev-backend dev-frontend

dev-backend:
	cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm install && npm run dev

# Docker
build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

# Database
db-reset:
	rm -f backend/bibliotheque.db
	cd backend && python -c "import asyncio; from app.database import init_db; asyncio.run(init_db())"
