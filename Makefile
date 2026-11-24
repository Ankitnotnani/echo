# Echo: run the whole stack locally with Docker.
#   make up     build and start backend (:8000) and frontend (:3000)
#   make down   stop everything (chat history is kept in the app_data volume)

.PHONY: up down logs ps test smoke clean

up:
	docker compose up -d --build
	@echo Frontend: http://localhost:3000
	@echo Backend:  http://localhost:8000/health

down:
	docker compose down

logs:
	docker compose logs -f

ps:
	docker compose ps

# Backend test suite, run inside the "test" stage of the backend image.
test:
	docker build --target test -t echo-backend-test ./backend
	docker run --rm echo-backend-test

# Contract checks against a running backend: make smoke URL=https://your-api.onrender.com
URL ?= http://localhost:8000
smoke:
	python scripts/smoke.py $(URL)

# Stop and DELETE the SQLite volume (all chat history).
clean:
	docker compose down -v
