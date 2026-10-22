# edge-service — HTTPS для Mini App: Let's Encrypt, свой сертификат или туннель

Отдельный сервис перед `miniapp-service`. Его задача — дать Mini App **валидный
HTTPS-адрес**, потому что кнопка `web_app` в Telegram работает только по HTTPS.

```
Telegram / браузер
        │  :443 (TLS)                 :80 (ACME + редирект 308)
        ▼                                    ▼
   edge-service  ────────────────────────────┘
        │  прокси /api/*, /, /assets/*
        ▼
   miniapp-service :8080  ──►  backend-service
```

---

## 1. Три режима

| `TLS_MODE` | Что делает | Что нужно | Telegram примет? |
|---|---|---|---|
| `selfsigned` | TLS своим сертификатом на :443 | ничего | ❌ нет (CA неизвестен) |
| `letsencrypt` | Настоящий сертификат LE по HTTP-01 | домен, A-запись на этот хост, **порт 80 из интернета**, certbot | ✅ да |
| `tunnel` | Туннель до `:8080`, HTTPS на стороне провайдера | исходящий интернет | ✅ да |

Переключение — только переменными окружения, код не меняется.

---

## 2. Let's Encrypt: что именно требуется

HTTP-01 не может «просто сработать»: удостоверяющий центр должен достучаться до
`http://<домен>/.well-known/acme-challenge/<token>` **из интернета**.

Чек-лист:

1. **Домен** с A-записью на публичный IP этой машины (сейчас `82.209.250.140`).
2. **Проброс порта 80** на роутере: `82.209.250.140:80 → 192.168.1.81:80`.
3. **certbot** на хосте (или образ `certbot/certbot`, или `pip install certbot`).
4. Свободные порты 80 и 443.

Запуск:

```powershell
$env:DOMAIN = "cars.example.com"
$env:ACME_EMAIL = "me@example.com"
.\make.ps1 up-edge-le
```

Что происходит внутри:

1. поднимается `:80` и начинает отдавать `/.well-known/acme-challenge/*` из
   `CERTS_DIR/webroot`;
2. вызывается `certbot certonly --webroot` с каталогами внутри `CERTS_DIR`
   (в системный `/etc/letsencrypt` ничего не пишется);
3. сертификат читается из `CERTS_DIR/letsencrypt/live/<домен>/`, поднимается `:443`;
4. раз в 12 часов вызывается `certbot renew`; если файл обновился, в лог уходит
   предупреждение — uvicorn читает сертификат только на старте, поэтому нужен
   рестарт (`docker restart`, `systemctl restart`).

Если условия не выполнены, сервис **не притворяется**, что выпустил сертификат, а
завершается с понятным текстом. Фактический вывод на этой машине:

```
[edge] ОШИБКА: certbot не найден. Варианты: `apt install certbot` на хосте,
образ `certbot/certbot` рядом, либо `pip install certbot` для локального запуска.
Либо переключитесь на TLS_MODE=tunnel — он даёт HTTPS без домена.
```

В Docker всё готово: в образе `edge-service` certbot уже установлен, каталог
сертификатов вынесен в volume `edge_certs`.

---

## 3. Туннель: когда домена нет

Провайдер задаётся `TUNNEL_PROVIDER`:

| Провайдер | Адрес | Замечания |
|---|---|---|
| `cloudflared` | `*.trycloudflare.com` | нужен бинарник cloudflared |
| `tunnelmole` | `*.tunnelmole.net` | работает через `npx`, Node.js |

```powershell
$env:TLS_MODE = "tunnel"
$env:TUNNEL_PROVIDER = "tunnelmole"
.\make.ps1 up-edge-tunnel
```

Сервис печатает адрес и кладёт его в `runtime/public_url.txt`:

```
[edge] ПУБЛИЧНЫЙ HTTPS: https://kcqixt-ip-82-209-250-140.tunnelmole.net
[edge] в бота: MINIAPP_URL=https://kcqixt-ip-82-209-250-140.tunnelmole.net
```

**Проверено на этой сети:** quick tunnel Cloudflare стабильно отбивается —
`failed to request quick Tunnel: ... An existing connection was forcibly closed
by the remote host` (TCP до `api.trycloudflare.com:443` открывается, но POST
рвётся). `tunnelmole` через ту же сеть работает. Поэтому по умолчанию в
make-цели подставлен он.

Ограничения туннеля: адрес живёт, пока жив процесс; при перезапуске поддомен
меняется; это демо-канал, не продакшн.

---

## 4. Что проверено

| Проверка | Как | Результат |
|---|---|---|
| Самоподписанный TLS | `TLS_MODE=selfsigned`, порты 8081/8443 | `http /health → 200`, `http /app.js → 308`, `https / → 200` (Mini App отдаётся) |
| ACME-челлендж | файл в `webroot`, GET `/.well-known/acme-challenge/<name>` | `200` + содержимое файла; отсутствующий — `404` |
| Редирект | GET по HTTP | `308` на `https://<домен>/<путь>?<query>` |
| Прокси | `build_https_app(transport=MockTransport)` | путь/query/тело доходят, при мёртвом upstream — `503` |
| Диагностика LE | `TLS_MODE=letsencrypt` без certbot | текст про домен/порт 80/certbot, exit code 2 |
| Публичный HTTPS | `TUNNEL_PROVIDER=tunnelmole` | `/health 200`, `/ 200`, `/api/listings 200`, `/app.js 200` |
| Кнопка в Telegram | `getChatMenuButton` после рестарта бота | `type=web_app`, `url=https://…tunnelmole.net/` |

Не проверено: фактическая выдача сертификата Let's Encrypt — для неё нужен домен
и проброс порта 80, которых в этой среде нет.

---

## 5. Переменные

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `TLS_MODE` | `selfsigned` | `selfsigned` / `letsencrypt` / `tunnel` |
| `DOMAIN` | — | домен для LE и для `https://` в редиректе |
| `ACME_EMAIL` | — | контакт для LE |
| `TUNNEL_PROVIDER` | `cloudflared` | `cloudflared` / `tunnelmole` |
| `UPSTREAM` | `http://127.0.0.1:8080` | куда проксировать (miniapp) |
| `EDGE_HTTP_PORT` / `EDGE_HTTPS_PORT` | `80` / `443` | порты (локально удобно 8081/8443) |
| `CERTS_DIR` | `./.certs` | сертификаты, webroot, состояние certbot |
| `RUNTIME_DIR` | `./runtime` | сюда пишется `public_url.txt` для туннеля |
| `CERTBOT_BIN` / `CLOUDFLARED_BIN` / `TUNNELMOLE_BIN` | `certbot` / `cloudflared` / `npx` | пути к бинарникам |

---

## 6. Что дальше

1. **Домен + проброс 80** → `TLS_MODE=letsencrypt`, адрес перестаёт меняться.
2. **Автоперезапуск после renew** — сейчас только предупреждение в логе.
3. **HSTS и заголовки безопасности** — после стабилизации домена.
4. **Туннель как постоянный канал** — именованный туннель Cloudflare (нужен
   аккаунт) вместо quick tunnel.
