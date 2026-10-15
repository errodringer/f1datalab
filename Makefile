.PHONY: up down logs demo sync verify
up:
	docker compose up -d --build
logs:
	docker compose logs -f worker
down:
	docker compose down
sync:
	docker compose exec dashboard python -m f1lab.cli --season 2025
demo:
	docker compose exec dashboard python -m f1lab.cli --season 2025 --demo
verify:
	curl -fsS http://localhost:8501/_stcore/health
