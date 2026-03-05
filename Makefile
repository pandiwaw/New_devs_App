back:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

front:
	cd frontend && npm run dev

pre-commit:
	cd backend && uv add --dev pre-commit
	uv run pre-commit install --install-hooks --overwrite

uv-install:
	cd backend && uv sync

# ── Tests ────────────────────────────────────────────────────────────────
# Tests live under docker compose --profile test. They never start with
# a normal `docker compose up`.

test-unit:                          ## Run pytest unit tests (no running app needed)
	docker compose --profile test run --rm unit-tests

test-integration:                   ## Run Bruno API tests (app must be running)
	docker compose --profile test run --rm bruno-tests

test: test-unit test-integration    ## Run all tests
