# BUZZ Reservations — прототип модуля бронирования столов

**Прод:** https://buzz-reservations-andrahap07-2168s-projects.vercel.app (Vercel: Angular статикой,
FastAPI — serverless-функция `/api`, БД — Supabase Postgres, схема `buzz`).
Serverless-функция при холодном старте подтягивает `backend/app` из этого репозитория (ветка main),
поэтому обновление API на проде = push в main + новый деплой фронта не требуется.
Секрет подключения к БД живёт только в Vercel-бандле (`api/_config.py`, в git не попадает).

Реализация ТЗ «BUZZ Table Reservations»: Python (FastAPI) backend + Angular (TypeScript) фронт
(white-label виджет + экраны админ-панели). Уровень доступности — «столы с вместимостью»,
без плана зала и объединения столов (v1).

## Структура

```
backend/            FastAPI + SQLAlchemy (SQLite в прототипе, целевая БД — PostgreSQL)
  app/
    models.py       схема ТЗ §5 (venue_booking_settings, venue_tables, venue_hours,
                    venue_hours_override, reservations, widget_configs + outbox/idempotency)
    availability.py движок слотов ТЗ §6 (venue tz, min-capacity-first, overrides)
    services.py     создание/отмена/подтверждение брони, конфликт-контроль ТЗ §6.4
    routers/        public.py, widget.py, admin.py — эндпоинты ТЗ §7
    worker.py       фоновые задачи ТЗ §11 (просроченные pending, напоминания, completed)
    notifications.py outbox-стаб Notification Service ТЗ §10
    security.py     rate-limit, captcha-hook, admin-auth стаб ТЗ §12
    seed.py         демо-рестораны RIVIERA (auto) и GONGU (manual)
  tests/            16 тестов: критерии приёмки ТЗ §14, включая конкурентный тест двойного бронирования
frontend/           Angular: /widget/:slug (white-label, en/ru/lv) + /admin (расширение панели)
```

## Запуск

```bash
# backend (порт 8000)
cd backend
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python -m uvicorn app.main:app --port 8000

# frontend (порт 4200, проксирует /api на 8000)
cd frontend
npm install
npm start
```

- Виджет: http://localhost:4200/widget/riviera (auto-confirm, EN) и
  http://localhost:4200/widget/gongu-riga-latvia (manual, RU)
- Демо in-app флоу (ТЗ §8): http://localhost:4200/app-demo — карточка заведения
  как в приложении BUZZ с кнопкой «Book a table», открывающей виджет
- Админка: http://localhost:4200/admin (токен прототипа: `dev-admin`)
- API-доки: http://localhost:8000/docs
- Фото заведений/блюд сгенерированы (Recraft V4.1 через Higgsfield), лежат в
  `frontend/public/img/`, обложка виджета — `widget_configs.photo_url`

## Тесты

```bash
cd backend && .venv/Scripts/python -m pytest tests/ -q
```

Покрыто: сетка слотов и split-часы (обед/ужин), подбор минимального стола, auto/manual флоу,
decline, «группа больше max → позвоните», отмена гостем в окне, идемпотентность POST,
исчерпание столов → 409, конкурентный тест (20 потоков → ровно 4 брони на 4 стола),
override-закрытие дня, авто-экспирация pending, конфиг виджета.

## Точки интеграции (в реальную систему BUZZ)

- `models.Venue`, `models.User` — стабы; заменить FK на существующие сущности.
- `security.require_admin` / `optional_user` — заменить на существующую авторизацию.
- `notifications` — прототип пишет в outbox-таблицу и лог; подключить реальный сервис.
- CORS `*` и SQLite — только для дев-режима.

## Открытые вопросы из ТЗ (§15) — что принято в прототипе

1. Схема БД — стабы venue/user, имена таблиц по ТЗ.
2. Взрослые/дети — принят единый `party_size` (как у Tablein); разделение
   взрослые/дети (Tableo) — вопрос к команде, модель менять не потребуется
   (достаточно добавить поле-разбивку в reservations).
3. Embed-iframe — v1 redirect-страница; iframe-сниппет работает с той же страницей.
4. SMS — канал заведён в outbox, по умолчанию выключен (email+push).
5. Домен — прототип `/widget/{slug}` на 4200.
6. Админ-авторизация — стаб `X-Admin-Token: dev-admin`.
7. Просмотр брони по коду — публичный `GET /reservations/{id}?code=`.
