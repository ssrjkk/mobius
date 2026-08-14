.PHONY: help install doctor test-unit test-api test-api-live test-wire test-all \
        test-ui test-ui-headed test-ui-smoke test-ui-parallel \
        test-parallel lint fmt cov cov-open clean appium-start ci security

help: ## Показать все доступные команды
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

install: ## Установить все зависимости
	uv pip install -e ".[test,lint]"

doctor: ## Проверить окружение (Python, Appium, adb, iOS simctl, ENV)
	@-mobius doctor

# ── Тесты без устройства ────────────────────────────────────────────────────

test-unit: ## Unit тесты (без устройства, ~8s)
	pytest tests/unit/ -m unit -v

test-api: ## API тесты — respx моки (без сети)
	pytest tests/api/ -m api -v

test-api-live: ## API тесты — реальный dummyjson.com (нужен интернет)
	pytest tests/api/ -m api --live-api -v

test-wire: ## Wire-protocol тесты — реальный HTTP через fake WebDriver server
	pytest tests/wire_protocol/ -m wire_protocol -v

test-all: ## Unit + API + Wire-protocol (без устройства, полный "CI-ready" прогон)
	pytest tests/unit/ tests/api/ tests/wire_protocol/ -v

test-parallel: ## test-all параллельно на 4 ядрах (проверяет thread-safety)
	pytest tests/unit/ tests/api/ tests/wire_protocol/ -n 4 -v

# ── Тесты с реальным устройством ────────────────────────────────────────────

test-ui: ## UI тесты — нужен запущенный Appium + эмулятор
	pytest tests/ui/ -m ui -v --alluredir=allure-results

test-ui-smoke: ## Только smoke UI тесты
	pytest tests/ui/ -m "ui and smoke" -v

test-ui-headed: ## UI тесты с полным stdout (для дебага)
	pytest tests/ui/ -m ui -v -s --tb=long

test-ui-parallel: ## UI тесты параллельно через DevicePool (нужно N эмуляторов)
	pytest tests/ui/ -m ui -n auto -v --alluredir=allure-results

# ── Инструменты ──────────────────────────────────────────────────────────────

appium-start: ## Запустить локальный Appium сервер
	appium --base-path /wd/hub

lint: ## ruff + mypy
	ruff check mobius/ tests/
	mypy mobius/ --no-error-summary

fmt: ## Автоформатирование ruff
	ruff format mobius/ tests/

security: ## bandit (SAST) + pip-audit (dependency CVEs) — изолированный venv
	bandit -r mobius/ -c pyproject.toml
	@echo "--- pip-audit (требует изолированный venv, см. docs/adr/004) ---"
	@python3 -m venv /tmp/mqf_audit_venv 2>/dev/null || true
	/tmp/mqf_audit_venv/bin/pip install -e . pip-audit --quiet --upgrade pip
	/tmp/mqf_audit_venv/bin/pip-audit

cov: ## Coverage report — unit + api + wire
	pytest tests/unit/ tests/api/ tests/wire_protocol/ \
		--cov=framework --cov-report=term-missing --cov-report=html:reports/htmlcov

cov-open: cov ## Coverage report + открыть в браузере
	python -m webbrowser reports/htmlcov/index.html

clean: ## Удалить артефакты тестов
	rm -rf reports/ allure-results/ .pytest_cache/ .coverage htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# ── CI ───────────────────────────────────────────────────────────────────────

ci: lint test-all security ## Полный pre-merge pipeline (без UI)
