# Athletic Mindset — Backend

FastAPI + PostgreSQL backend for the Athletic Mindset platform. Async SQLAlchemy,
Alembic migrations, JWT auth with role-based access, and a multilingual content
(CMS) system with automatic translation.

## Tech Stack

- **FastAPI** (async) with Pydantic settings
- **PostgreSQL** via async SQLAlchemy 2.0 + asyncpg
- **Alembic** for migrations
- **JWT** auth (PyJWT) with bcrypt password hashing
- **Resend** for transactional email
- **DeepL** for automatic content translation
- **uv** for dependency management

## Prerequisites

- Docker (for local PostgreSQL)
- uv (Python package manager)

## Quick Start

```bash
# 1. Start Postgres
docker compose up -d postgres

# 2. Apply migrations
uv run alembic upgrade head

# 3. Run the API (hot-reload)
uv run uvicorn app.main:app --reload

# 4. Open the interactive API docs
open http://localhost:8000/docs
```

Create the first admin (needed for the CMS):

```bash
uv run python -m app.cli create-admin --email you@example.com --password yourpassword
```

## Project Structure

```
backend/
├── app/
│   ├── main.py            # App entry: CORS, routers, startup (DB check + auto-seed)
│   ├── config.py          # Settings from .env (DB, JWT, Resend, DeepL)
│   ├── database.py        # Async engine + session
│   ├── models.py          # ORM models: User, UserRole, AthleteProfile, ContentEntry
│   ├── schemas.py         # Pydantic request/response models
│   ├── auth.py            # Password hashing + JWT helpers
│   ├── dependencies.py    # get_current_user, require_role
│   ├── email.py           # Resend transactional email
│   ├── translation.py     # DeepL translate service
│   ├── seed_content.py    # Site content seed + ensure_seeded() (auto-runs on startup)
│   ├── cli.py             # create-admin command
│   └── routers/
│       ├── auth.py        # register, login, verify, reset, profile, deactivate
│       ├── profile.py     # athlete demographic profile
│       ├── admin.py       # user management (list, create-admin, status, delete)
│       └── content.py     # public content + admin content editing
├── alembic/               # Migrations
├── docker-compose.yml     # Local Postgres + Adminer
└── pyproject.toml
```

## Auth & Roles

- Roles: `athlete`, `parent`, `coach`, `admin`.
- `get_current_user` validates the JWT; `require_role("admin")` guards admin routes.
- Endpoints: `/auth/register`, `/auth/login`, `/auth/verify-email`, `/auth/forgot-password`,
  `/auth/reset-password`, `/auth/me`, `/auth/change-password`, `/auth/deactivate`, `/auth/set-role`.

## Content & Translation (CMS)

The site's editable text lives in the `content_entries` table as `(key, locale, value)`.

- `GET /content/{locale}` — public. Returns `{ key: value }` for a language, with English
  as fallback. Cached in memory; the cache clears when content is saved. Any language is
  **translated on first request** and stored, so the backend keeps no language list.
- `GET /admin/content` — admin. Lists the English master strings.
- `PUT /admin/content` — admin. Saves English string(s); auto-translates into every language
  that already exists and clears the cache.

**English is the master.** English is authored in `app/seed_content.py`. On startup,
`ensure_seeded()` inserts any missing English keys (never overwriting edits), so deploys
need no manual seed step. Translation uses DeepL (`DEEPL_API_KEY`).

Adding a page's content: add its `t()` keys + English to `CONTENT` in `app/seed_content.py`.
On deploy, the new keys seed automatically and translate on first view.

## Admin / User Management

- `GET /admin/users` — list users
- `POST /admin/users/create-admin` — create another admin
- `PATCH /admin/users/{id}/status?active=<bool>` — activate/deactivate
- `DELETE /admin/users/{id}` — delete a user (admins can't delete themselves)

## Environment (.env)

```
DEBUG=true
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/athletic_mindset
SECRET_KEY=<random-secret>
FRONTEND_URL=http://localhost:3000
CORS_ORIGINS=["http://localhost:3000"]
RESEND_API_KEY=<optional>
DEEPL_API_KEY=<required for content translation>
```

## Deployment (Render + Neon)

- DB: Neon (pooled connection string, `ssl=require`).
- Build: `pip install uv && uv sync --frozen`
- Start: `uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check path: `/health`
- Set env vars including `DATABASE_URL`, `SECRET_KEY`, `FRONTEND_URL`, `CORS_ORIGINS`,
  `DEEPL_API_KEY`, `RESEND_API_KEY`, `DEBUG=false`.
- Migrations run and content seeds automatically on deploy. No manual steps.

## Useful Commands

```bash
docker compose down            # stop Postgres
docker compose down -v         # stop + wipe data
uv run alembic revision --autogenerate -m "msg"   # new migration
uv run python -m app.seed_content                  # seed content manually (optional)
```

## Viewing the Database (local)

Adminer at http://localhost:8080/ — Host `localhost`, Port `5432`, User `postgres`,
Password `postgres`, Database `athletic_mindset`.
