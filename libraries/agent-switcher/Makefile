# agent-switcher library – common targets (uv)
# Use from libraries/agent-switcher: make lint, make test, make build, etc.

UV ?= uv
VENV ?= .venv

.PHONY: help venv lock install-dev lint test coverage build clean

help:
	@echo "Targets: venv, lock, install-dev, lint, test, coverage, build, clean"

venv:
	$(UV) venv $(VENV)

lock:
	$(UV) lock

install-dev: venv
	$(UV) sync --extra dev

lint:
	$(UV) run ruff check src tests
	$(UV) run ruff format --check src tests

format:
	$(UV) run ruff format src tests
	$(UV) run ruff check --fix src tests

test:
	$(UV) run pytest tests

coverage:
	$(UV) run pytest tests --cov=agent_switcher --cov-report=term-missing

build:
	$(UV) run python -m build

clean:
	rm -rf build/ dist/ *.egg-info .eggs
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
