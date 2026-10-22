# autoselect_unified

Объединённый продукт: **контракт `auto_bot`** (команды, `callback_data`, схемы API) +
**UI/UX `deutsche_motors_bot`** (тексты, экраны, клавиатуры), разложенный на
`bot-service` / `backend-service` / `miniapp-service` / `shared`.

Контракт `auto_bot` не меняется: клиент Telegram и Mini App видят те же команды,
те же кнопки и те же ответы. Изменяются только формулировки (решение D1) и
раскладка (решение D2).

---

## Структура

```
autoselect_unified/
├── shared/                     # библиотека, общая для всех сервисов
│   ├── contracts/              # DTO из auto_bot 1:1 + BackendPort
│   │   └── bot/                # реестр Telegram-контракта: callbacks, commands,
│   │                           #   states, limits, templates
│   ├── mocks/                  # фикстуры, мок-адаптеры домена, MockBackend
│   ├── settings.py             # SERVICE / MODE / ADAPTER_* — только ENV
│   └── http_headers.py         # заголовок внутренней авторизации
├── backend-service/            # домен и BL
│   ├── backend_service/
│   │   ├── ports.py            # Protocol'ы: Users, Catalog, Dialog, Calc, ...
│   │   ├── adapters/legacy.py  # real: тонкий клиент к auto_bot API (strangler)
│   │   ├── container.py        # MODE → конкретные адаптеры (единственное место)
│   │   ├── api/                # те же /api/* роуты, что у auto_bot
│   │   └── main.py
│   └── Dockerfile
├── bot-service/                # Telegram-бот, только UI
│   ├── bot_service/
│   │   ├── handlers/           # menu, dialog, card, calc, catalog, price, ...
│   │   ├── ui/                 # keyboards, render, panel («живая» панель)
│   │   ├── skin/deutsche.py    # ВСЕ тексты (меняются без риска для контракта)
│   │   ├── port.py             # HttpBackend (real) + выбор реализации
│   │   ├── states.py           # ButtonForm, PriceSelection
│   │   └── main.py             # polling, FSM, регистрация команд
│   └── Dockerfile
├── miniapp-service/            # Telegram Mini App: статика + прокси /api/*
│   ├── miniapp_service/main.py # раздача static/ и проброс в backend
│   ├── static/                 # index.html, app.css, app.js, assets/*.svg
│   └── Dockerfile
├── edge-service/               # HTTPS перед Mini App
│   ├── edge_service/
│   │   ├── config.py           # TLS_MODE: selfsigned / letsencrypt / tunnel
│   │   ├── certs.py            # самоподписанный, certbot (ACME HTTP-01)
│   │   ├── tunnel.py           # cloudflared / tunnelmole
│   │   ├── apps.py             # :80 ACME+редирект, :443 прокси
│   │   └── main.py
│   └── Dockerfile
├── scripts/                    # launcher'ы, dev-стек, smoke-проверка
├── tests/                      # контрактные + архитектурные + API + miniapp + edge
├── docker-compose.yml          # профили bot-only / backend-only / miniapp-only / edge / all
├── Makefile / make.ps1         # up-bot, up-backend, up-miniapp, up-edge*, dev, test-contract
└── docs/
```

Границы проверяются тестом (`tests/test_layering.py`): `bot-service` не импортирует
`sqlalchemy`/`aio_pika`/`boto3`, `backend_service/api` не импортирует `httpx`,
`shared` не импортирует `aiogram`/`fastapi`.

---

## Режимы: `SERVICE` × `MODE`

Переключение — **только окружением**, правок кода нет.

| `SERVICE` | `MODE` | Что поднимается | Что нужно снаружи |
|---|---|---|---|
| `bot` | `mock` | бот + `MockBackend` в процессе + `MemoryStorage` | только токен бота |
| `bot` | `real` | бот + HTTP в `backend-service` | `BACKEND_URL` |
| `backend` | `mock` | домен на фикстурах | ничего |
| `backend` | `real` | домен + `LEGACY_BACKEND_URL` (auto_bot API) | работающий `auto_bot` |
| `miniapp` | — | статика + прокси `/api/*` | `BACKEND_URL` |
| `edge` | `selfsigned` | TLS своим сертификатом (Telegram не примет) | ничего |
| `edge` | `letsencrypt` | настоящий сертификат по HTTP-01 | домен + проброс порта 80 + certbot |
| `edge` | `tunnel` | публичный HTTPS через туннель | исходящий интернет |
| `all` | любой | все сервисы | по режиму |

Точечное перекрытие режима порта: `MODE=mock ADAPTER_LLM=real` — всё мокнуто, кроме
LLM. Доступные имена: `users, catalog, dialog, calc, analysis, billing, notify,
backend`.

---

## Быстрый старт

### Windows

```powershell
.\make.ps1 install
.\make.ps1 test

.\make.ps1 dev          # backend + Mini App → http://127.0.0.1:8080
.\make.ps1 up-backend   # только домен → http://127.0.0.1:8000/health
.\make.ps1 up-miniapp   # только Mini App (проксирует в :8000)

# HTTPS перед Mini App
.\make.ps1 up-edge          # self-signed, :8081/8443 (локальная проверка TLS)
.\make.ps1 up-edge-tunnel   # публичный HTTPS через туннель → для кнопки web_app
.\make.ps1 up-edge-le       # Let's Encrypt: нужны DOMAIN и ACME_EMAIL
```

Для бота задайте токен в окружении (шаблон переменных — `.env.example`) и запустите
`.\make.ps1 up-bot`.

### Linux / macOS / Docker

```bash
make install
make test
make dev            # backend + miniapp
make up-bot         # SERVICE=bot MODE=mock
make up-all         # docker compose --profile all
```

Для compose скопируйте `.env.example` в `.env`: секреты в `docker-compose.yml`
намеренно не хранятся.

### Проверка связки bot → backend без Telegram

```bash
python scripts/run_backend.py --port 8010 &
python scripts/smoke_bot_backend.py http://127.0.0.1:8010
```

Скрипт проходит путь старого клиента: `upsert → диалог (3 хода) → finalize →
выдача → карточка → калькулятор → AI-разбор → подписка`. Фактический прогон —
10/10 OK.

---

## Mini App

Отдельная веб-поверхность для «тяжёлого» UI: каталог, карточка лота с галереей,
подбор по цене, калькулятор. Разговорный AI остаётся в чате с ботом — по ТЗ §5.8
бот не должен дублировать приложение.

| Экран | Что внутри |
|---|---|
| Каталог | карточки лотов, пагинация, `MOCK`-бейдж режима |
| Карточка | галерея `📷 N/M` свайпом, спеки сеткой, цена, CTA «Рассчитать доставку» |
| Подбор | чипы диапазонов, поля min/max, выдача по возрастанию цены |
| Расчёт | цена/объём/год, РФ/РБ, смета по компонентам и итог |

Технически: статика без сборки (`index.html` + `app.css` + `app.js`), тема берётся
из Telegram WebApp SDK и **не** применяется вне клиента; `Back` и haptic-фидбек
подключены; адреса экранов — в hash (`#/catalog`, `#/card/12`, `#/price`, `#/calc`),
поэтому на лот можно дать deep-link.

Подробности и ограничения — `docs/MINIAPP.md`.

### HTTPS и кнопка `web_app`

Telegram открывает Mini App только по HTTPS с валидным сертификатом. За это
отвечает `edge-service` (`docs/EDGE.md`), три режима — только через ENV:

| Задача | Режим | Что нужно |
|---|---|---|
| локально проверить TLS | `TLS_MODE=selfsigned` | ничего |
| прототип в Telegram | `TLS_MODE=tunnel` | туннель (по умолчанию `tunnelmole`) |
| продакшн | `TLS_MODE=letsencrypt` | домен, A-запись, проброс порта 80, certbot |

Найденный адрес туннеля пишется в `runtime/public_url.txt`; его же нужно отдать
боту как `MINIAPP_URL` — тогда кнопка меню становится `web_app`.

---

## Тесты

```
python -m pytest tests -q          # 205 тестов
python -m pytest tests -q -k contract   # 118 контрактных
```

| Файл | Что фиксирует |
|---|---|
| `test_contract_callbacks.py` | сборка ↔ разбор каждого `callback_data`, все прежние значения, отсутствие коллизий |
| `test_contract_schemas.py` | набор полей DTO, границы валидации, `MockBackend` как `BackendPort` |
| `test_contract_templates.py` | структура карточки, лимит 1024, отсутствие JSON, порядок полей критериев |
| `test_mock_adapters.py` | детерминированное поведение домена (диалог, каталог, квота, калькулятор, биллинг) |
| `test_layering.py` | границы слоёв (UI без БД, контракты без фреймворков) |
| `test_bot_wiring.py` | две кнопки на главном экране, достижимость прежних действий, FSM-имена, Dispatcher |
| `test_backend_api.py` | HTTP-контракт: пути, коды, 401/403, идемпотентность платежа |
| `test_miniapp.py` | раздача статики, прокси, отсутствие внутреннего ключа в браузерном коде |
| `test_edge.py` | режимы TLS, self-signed, ACME-челлендж, редирект, прокси, разбор адреса туннеля |

---

## Что заморожено и где это лежит

| Контракт | Источник | Проверка |
|---|---|---|
| `callback_data` | `shared/contracts/bot/callbacks.py` | round-trip + golden-список `LEGACY_SAMPLES` |
| Команды и меню (`set_my_commands`) | `shared/contracts/bot/commands.py` | список совпадает с `auto_bot` |
| Имена FSM-групп/состояний | `shared/contracts/bot/states.py` | `ButtonForm.make.state == "ButtonForm:make"` |
| Структура сообщений и лимиты | `shared/contracts/bot/templates.py`, `limits.py` | порядок блоков, caption ≤ 1024, ≤ 8 опций |
| HTTP-схемы | `shared/contracts/*.py` | набор полей DTO, границы значений |
| Коды ошибок | `backend_service/api/*` | 401 без ключа, 403 на квоту |

Новое, чего у `auto_bot` не было (экраны из эталона): `catalog:*`, `price:*`,
`menu:main`, `menu:more`. Коллизий с прежними значениями нет — проверяется
`test_sample_matches_exactly_one_pattern`.

---

## Что уже работает

- `shared/contracts` — DTO перенесены 1:1; `BackendPort` — единственный канал в домен.
- `backend-service` — порты + `mock`/`real` адаптеры, те же `/api/*`, 401/403 по контракту.
- `bot-service` — все прежние сценарии + экраны из эталона, тексты полностью в скине.
- `miniapp-service` — каталог, карточка, подбор, расчёт; прокси без секретов.
- `MODE=mock` поднимает бота без бэкенда, БД, Redis и RabbitMQ.
- `docker-compose` с четырьмя профилями, `Makefile` + `make.ps1`.

## Чего осознанно нет

- Golden-snapshot'ы сообщений (Этап 3) — сейчас проверяется структура, не байты текста.
- E2E на реальном Telegram и авторизация Mini App через `initData` (Этап 4).
- Прямые адаптеры PostgreSQL/RabbitMQ/GLM — интерфейсы готовы; сейчас `real` =
  прокси к работающему `auto_bot` (strangler).
- `FloodMiddleware` (антифлуд), бот-админка (решение D3), вебхуки (решение Q2).
- Фактическая выдача сертификата Let's Encrypt не проверена: нужен домен и
  проброс порта 80. Код и диагностика готовы, проверен только путь ошибки и
  ACME-челлендж; рабочий HTTPS сейчас даёт туннель (`docs/EDGE.md`).

---

## Правила

1. Новая кнопка = билдер в `callbacks.py` + строка в `CALLBACK_PATTERNS` + тест.
2. Текст — только в `bot_service/skin/` (бот) и `miniapp-service/static/` (веб).
3. Хендлер и Mini App не знают, откуда данные: только `BackendPort` / публичный API.
4. `MODE`/`ADAPTER_*` читаются в `container.py` и `port.py`; больше нигде.
