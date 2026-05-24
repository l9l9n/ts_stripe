# Stripe Test Project

FastAPI + Stripe Checkout + SQLite (async)

## Требования

- Python 3.11+
- [uv](https://astral.sh/uv) — менеджер пакетов
- [Stripe CLI](https://docs.stripe.com/stripe-cli)
- Аккаунт на [stripe.com](https://stripe.com)

---

## 1. Установка uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc  # или перезапусти терминал
```

## 2. Установка Stripe CLI

```bash
# Добавь GPG ключ
curl -s https://packages.stripe.dev/api/security/keypair/stripe-cli-gpg/public | gpg --dearmor | sudo tee /usr/share/keyrings/stripe.gpg > /dev/null

# Добавь репозиторий
echo "deb [signed-by=/usr/share/keyrings/stripe.gpg] https://packages.stripe.dev/stripe-cli-debian-local stable main" | sudo tee -a /etc/apt/sources.list.d/stripe.list

# Установи
sudo apt update

# затем установи
sudo apt install stripe
```

## 3. Установка зависимостей проекта

```bash
uv sync
```

---

## 4. Настройка .env

Скопируй `.env.example` и заполни:

```bash
cp .env.example .env
```

Открой `.env`:

```env
STRIPE_SECRET_KEY=sk_test_...       # из dashboard.stripe.com/test/apikeys
STRIPE_WEBHOOK_SECRET=whsec_...     # получишь на шаге 6
BASE_URL=http://localhost:8000
```

**Где взять `STRIPE_SECRET_KEY`:**
1. Зайди на https://dashboard.stripe.com/test/apikeys
2. Скопируй **Secret key** (`sk_test_...`)
3. Вставь в `.env`

> Publishable key (`pk_test_...`) для этого проекта не нужен — он только для фронтенда.

---

## 5. Запуск сервера

```bash
uvicorn app.main:app --reload
```

---

## 6. Запуск Stripe CLI (в отдельном терминале)

```bash
stripe login       # откроется браузер — подтверди вход
stripe listen --forward-to localhost:8000/webhook/
```

CLI выведет:
```
> Ready! Your webhook signing secret is whsec_abc123...
```

Скопируй `whsec_...` в `.env` как `STRIPE_WEBHOOK_SECRET`, затем перезапусти сервер.

---

## 7. Тестирование

1. Открой http://localhost:8000/docs
2. `POST /checkout/` — введи `email` и `price` (например, `20`)
3. Перейди по `checkout_url` из ответа
4. Оплати тестовой картой:
   - Номер: `4242 4242 4242 4242`
   - Дата: любая в будущем (например `12/26`)
   - CVV: любые 3 цифры (`123`)
5. В терминале со `stripe listen` появится `checkout.session.completed [200]`
6. `GET /success?session_id=...` — проверь что платёж сохранился в БД

---

## Структура проекта

```
stripe_test/
├── app/
│   ├── config.py     # настройки через pydantic-settings
│   ├── database.py   # async engine + get_session
│   ├── models.py     # Payment (MappedAsDataclass) + бизнес-логика
│   ├── schemas.py    # Pydantic v2 схемы запросов и ответов
│   ├── routes.py     # /checkout, /webhook, /success, /cancel
│   └── main.py       # lifespan (create_all при старте) + FastAPI app
├── .env.example
├── pyproject.toml
└── README.md
```

## Эндпоинты

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/checkout/` | Создать Stripe Checkout сессию |
| POST | `/webhook/` | Получить событие от Stripe |
| GET | `/success` | Проверить платёж по `session_id` |
| GET | `/cancel` | Страница отмены оплаты |
