dev:
	docker compose up postgres redis -d
	@echo "Starting backend..."
	uvicorn backend.api.main:app --reload --port 8000 &
	@echo "Starting frontend..."
	cd frontend && npm run dev

test:
	cd backend/api && pytest tests/ -v
	cd frontend && npm run test:ci

test-backend:
	cd backend/api && pytest tests/ -v --tb=short

test-frontend:
	cd frontend && npm run test:ci

lint:
	ruff check backend/
	cd frontend && npm run lint

train:
	cd ml && source .venv/bin/activate && python train.py

migrate:
	cd backend/api && alembic upgrade head

build-prod:
	docker compose --profile prod build

clean:
	docker compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .next -exec rm -rf {} +

.PHONY: dev test test-backend test-frontend lint train migrate build-prod clean
