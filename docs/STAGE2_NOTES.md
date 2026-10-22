# Этап 2 — что собрано, что проверено, что осталось

Документ фиксирует выполнение Этапа 2 и границы сделанного. Ссылки на код — от
корня `autoselect_unified/`.

---

## 1. Решения заказчика и как они реализованы

| # | Решение | Реализация |
|---|---|---|
| **D1** | Тексты менять можно | Формулировки — только в `bot-service/bot_service/skin/deutsche.py`. Структура (порядок блоков, `<b>`, лимиты) — в `shared/contracts/bot/templates.py` и `limits.py`. Хендлеры текстов не содержат. |
| **D2** | На главном экране 2 крупные кнопки | `ui/keyboards.py:main_menu_kb()` — ровно два ряда: `🚗 AI-подбор авто` (`menu:ai`) и `⚙️ Ещё` (`menu:more`). Все прежние действия живут на втором уровне и достигаются за два клика: `menu:calc`, `menu:compare`, `menu:notify`, `menu:subscribe`, `menu:reset`, `menu:help`, Mini App. |
| **D3** | Бот-админку не переносим | Экраны `admin:*` из `deutsche_motors_bot` не реализованы. В `callbacks.py` их нет — они не входят в контракт `auto_bot`. Веб-админка `auto_bot` остаётся единственным входом. |
| **Q2** | Оставляем long polling | `bot_service/main.py:main()` вызывает `delete_webhook(drop_pending_updates=True)` и `start_polling`. Вебхук-эндпоинтов нет. |

---

## 2. Пункты Этапа 2

| Пункт ТЗ | Где | Статус |
|---|---|---|
| 1. Структура `bot-service/`, `backend-service/`, `shared/contracts/`, `shared/mocks/`, `infra/` | каталоги в корне; infra-часть — `docker-compose.yml`, `Makefile`, `make.ps1`, `*/Dockerfile` | ✅ |
| 2. `shared/contracts` — DTO из `auto_bot` без изменений | `shared/contracts/{criteria,listing,dialog,delivery,notifications,payments,users,analysis}.py` | ✅ (оговорка в §5.1) |
| 3. `backend-service` — домен + порты + mock/real адаптеры, переключение через ENV | `ports.py`, `adapters/legacy.py`, `container.py` | ✅ (оговорка в §5.2) |
| 4. `bot-service` — UI из эталона, вызовы только через `shared/contracts` | `handlers/`, `ui/`, `skin/`, `port.py` | ✅ |
| 5. `docker-compose` с профилями `bot-only` / `backend-only` / `all` | `docker-compose.yml` | ✅ |
| 6. `make up-bot`, `make up-backend`, `make up-all`, `make test-contract` | `Makefile`, дубль для Windows — `make.ps1` | ✅ |

---

## 3. Что проверено и чем

Всё ниже — фактически выполненные команды, не «должно работать».

| Проверка | Команда | Результат |
|---|---|---|
| Полный набор тестов | `python -m pytest tests -q` | 175 passed |
| Контрактные тесты | `python -m pytest tests -q -k contract` | зелёные |
| backend без инфраструктуры | `python scripts/run_backend.py --port 8010` | `/health` → `{"status":"ok","service":"backend","mode":"mock"}` |
| связка bot → backend по HTTP | `python scripts/smoke_bot_backend.py http://127.0.0.1:8010` | 10/10 OK (upsert, 3 хода диалога, finalize, выдача, карточка, калькулятор ≈29 600 $, AI-разбор, подписка) |
| переключение режимов | `build_backend(Settings(mode=...))` | `mock → MockBackend`, `real → HttpBackend` |
| точечное перекрытие порта | `MODE=mock ADAPTER_BACKEND=real` | `HttpBackend` |
| профили compose | `yaml.safe_load(docker-compose.yml)` | `backend: [backend-only, all]`, `bot: [bot-only, all]` |
| пустой `BOT_TOKEN` | `Settings.require_bot_token()` | `ConfigError: BOT_TOKEN не задан — заполните .env или окружение` |

### Чего проверить не удалось (и почему)

- **`docker compose up`** — Docker в окружении не установлен. Проверен только разбор
  YAML и корректность профилей; сами образы не собирались.
- **`make up-bot` в реальном Telegram** — нужен настоящий `BOT_TOKEN` и сеть до
  Telegram. Проверены: сборка `Dispatcher`, регистрация роутеров, клавиатуры,
  FSM-имена — всё без сети.
- **`MODE=real` против живого `auto_bot`** — сервис `auto_bot` не поднимался.
  Проверено, что `real` даёт `HttpBackend`, а его контракт совпадает с
  `backend-service` (тот же код прошёл smoke в `MODE=mock`).

---

## 4. Найденные по пути вещи, которые стоит знать

1. **`menu:` — единственное общее пространство префиксов** с эталоном. `menu:main`
   и `menu:more` — новые значения; в `auto_bot` их не было. Если бы они
   обрабатывались через `startswith("menu:")`, старый обработчик молча глотал бы
   клик. Поэтому фильтр в `handlers/menu.py` — точный набор `.in_({...})`, а
   уведомления (`menu:notify*`, `menu:quiet*`) вынесены в отдельный роутер.
2. **`menu:quiet_set:23:00-08:00` содержит `:` внутри значения.** Разбор режет по
   первым двум двоеточиям (`split(":", 2)`), значение сохраняется целиком.
3. **Сортировка по цене — по USD-нормализованной.** В каталоге есть лот в KRW,
   поэтому «сырые» цены не монотонны. Это поведение `auto_bot`, тесты приведены
   к нему (а не наоборот).
4. **`Panel` опция «устарела»** отвечает тостом, а не сообщением — иначе панель
   съезжает. Токен хода (`dlg:opt:{turn}:{idx}`) сохранён.
5. **`MockCalc` — заглушка**: ставки условные, в ответе `util_note` об этом
   говорит прямо. Реальные ставки — в `auto_bot/app/services/delivery.py`,
   подключаются на Этапе 4.

---

## 5. Отклонения и ограничения

### 5.1. DTO: две оговорки

- `InspectionReport*` (карта повреждений) **не** перенесены: это исключительно
  веб-PDP, бот и Mini App их не читают.
- `DialogFinalizeOut`, `DialogRestoreOut`, `DialogResetOut`, `PaymentSuccessOut`,
  `LoginLinkConfirmOut` — новые *классы* поверх уже существующих JSON-ответов
  `auto_bot`. Форма ответа не менялась, добавлена только типизация.

### 5.2. Real-адаптеры = strangler, а не прямой доступ к БД

`MODE=real` направляет порты в работающий `auto_bot` API (`LEGACY_BACKEND_URL`).
Это даёт 100 % совместимость контракта по построению и позволяет переключать
бота постепенно. Прямые адаптеры (`PostgreSQL`, `RabbitMQ`, `GLM`, `RAG`, `NLLB`)
встают на те же протоколы Этапом 4 — менять придётся только `container.py`.

### 5.3. Покрытие `/api/*` — только то, что нужно боту

Перенесены: `users/upsert`, `auth/telegram/link/confirm`, `listings*`,
`bot/listings/{id}/analysis`, `calc/*`, `dialog/*`, `ai/*`, `notifications/settings`,
`payments/prepare`, `payments/success`, `users/{id}/subscription`, `health*`.

**Не перенесены:** `admin/*`, `partners/*`, `leads/*`, `filters/*`, `favorites/*`,
`me/*`, JWT-авторизация Mini App. Они не используются ботом; для Mini App
источником пока остаётся `auto_bot`, а перенос — отдельный шаг (Этап 4), потому
что требует реальной БД и JWT-секретов.

### 5.4. Не перенесено поведение (сознательно)

- **`FloodMiddleware`** (антифлуд, `app/bot/throttle.py` в `auto_bot`). Не влияет
  на контракт, но влияет на нагрузку. Кандидат на Этап 3–4: реализуется
  middleware в `bot_service` без изменений в хендлерах.
- **FSM в Redis** — код есть (`build_storage`), но пакет `redis` не входит в
  зависимости Этапа 2. Без `REDIS_URL` используется `MemoryStorage`; при
  `MODE=mock` это и есть целевой режим.
- **Отправка уведомлений** (`workers/send.py`, дайджест, price drop) — остаётся
  в `auto_bot`; домен уведомлений пока только хранит настройки.
- **Парсинг источников** (`encar`/`kcar`/`chie168`) — не переносился.

---

## 6. Что нужно для Этапа 3

1. **Golden-snapshot'ы**: снять из `auto_bot` эталонные строки сообщений для
   каждого экрана и зафиксировать в `tests/golden/*.txt`; тест сравнивает рендер
   скина построчно (сейчас проверяется структура, не байты).
2. **Тестовый бот-токен** для E2E «клиент не замечает разницы» — нужен отдельный
   бот (`TEST_BOT_TOKEN`), иначе конфликт `getUpdates` с прод-ботом.
3. **Решение по объёму `/api/*`** для Этапа 4: переносить admin/partners/leads
   целиком или оставить за `auto_bot` до появления реальных адаптеров БД.
