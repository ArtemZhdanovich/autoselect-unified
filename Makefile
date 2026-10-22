# autoselect_unified — объединённый бот: контракт auto_bot + UI deutsche_motors_bot
#
# Все цели работают без правок кода: режим задаётся только ENV (SERVICE / MODE / ADAPTER_*).

PYTHON ?= python
MODE ?= mock
SERVICE ?= bot

export PYTHONPATH := .:bot-service:backend-service:miniapp-service:edge-service

.DEFAULT_GOAL := help

.PHONY: help install test test-contract up-bot up-backend up-miniapp dev up-edge up-edge-tunnel up-edge-le up-all docker-bot docker-backend docker-miniapp docker-edge docker-all clean

help:
	@echo "make install       - поставить зависимости"
	@echo "make test          - все тесты"
	@echo "make test-contract - только контрактные (callback_data, DTO, шаблоны)"
	@echo "make up-bot        - бот без бэкенда (SERVICE=bot MODE=mock)"
	@echo "make up-backend    - только домен (SERVICE=backend MODE=mock)"
	@echo "make up-miniapp    - Mini App: статика + прокси на :8080"
	@echo "make dev           - backend + Mini App одной командой"
	@echo "make up-edge       - HTTPS локально (self-signed, :8081/:8443)"
	@echo "make up-edge-tunnel- публичный HTTPS через туннель (для Telegram)"
	@echo "make up-edge-le    - Let's Encrypt: нужны DOMAIN и ACME_EMAIL"
	@echo "make up-all        - полный стек в docker (профиль all)"

install:
	$(PYTHON) -m pip install --quiet \
		"aiogram>=3.13,<4" "fastapi>=0.110,<1" "uvicorn>=0.27,<1" \
		"httpx>=0.27,<1" "pydantic>=2.7,<3" pytest pyyaml

test:
	$(PYTHON) -m pytest tests -q

test-contract:
	$(PYTHON) -m pytest tests -q -k contract

# Бот без бэкенда: MODE=mock подставляет MockBackend в процессе.
up-bot:
	SERVICE=bot MODE=$(MODE) $(PYTHON) scripts/run_bot.py

# Только домен: ни Telegram, ни инфраструктуры при MODE=mock.
up-backend:
	SERVICE=backend MODE=$(MODE) $(PYTHON) scripts/run_backend.py --port 8000

# Mini App: статика + прокси /api/* в BACKEND_URL (по умолчанию :8000).
up-miniapp:
	$(PYTHON) scripts/run_miniapp.py --port 8080

# Backend + Mini App в одном процессе — быстрее всего посмотреть UI.
dev:
	$(PYTHON) scripts/dev_stack.py

# Локальный TLS своим сертификатом: браузер ругнётся, но HTTPS настоящий.
up-edge:
	TLS_MODE=selfsigned EDGE_HTTP_PORT=8081 EDGE_HTTPS_PORT=8443 $(PYTHON) scripts/run_edge.py

# Публичный HTTPS без домена — то, что нужно для кнопки web_app в Telegram.
up-edge-tunnel:
	TLS_MODE=tunnel TUNNEL_PROVIDER=$(TUNNEL_PROVIDER) $(PYTHON) scripts/run_edge.py

# Let's Encrypt по HTTP-01: требует DOMAIN, ACME_EMAIL, DNS на этот хост и порт 80.
up-edge-le:
	TLS_MODE=letsencrypt $(PYTHON) scripts/run_edge.py

docker-bot:
	docker compose --profile bot-only up --build

docker-backend:
	docker compose --profile backend-only up --build

docker-miniapp:
	docker compose --profile miniapp-only up --build

docker-edge:
	docker compose --profile edge up --build

up-all:
	docker compose --profile all up --build

clean:
	$(PYTHON) -c "import shutil,pathlib;[shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"
