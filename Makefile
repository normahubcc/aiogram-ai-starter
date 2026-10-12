.PHONY: install dev test lint docker clean

install:
	pip install -e ".[dev]"

dev:
	python -m bot.main

test:
	pytest -v

lint:
	ruff check .

docker:
	docker compose up -d

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
