# Athletic Mindset — Backend

FastAPI + PostgreSQL backend for the Athletic Mindset platform.

## Prerequisites

- Docker (for running PostgreSQL)
- uv (Python package manager) — already installed at `~/.local/bin/uv`

## Quick Start

```bash
# 1. Start Postgres (runs in background via Docker)
docker compose up -d

# 2. Run the API server (with hot-reload)
uv run uvicorn app.main:app --reload

# 3. Open the interactive API docs
open http://localhost:8000/docs
```

## Project Structure

```
backend/
├── app/
│   ├── __init__.py      # Makes 'app' a Python package
│   ├── main.py          # FastAPI app — entry point, CORS, routes
│   ├── config.py        # All settings loaded from .env
│   └── database.py      # Postgres connection setup
├── docker-compose.yml   # Runs Postgres locally
├── pyproject.toml       # Dependencies (like package.json)
├── uv.lock              # Locked versions (like package-lock.json)
├── .env                 # Your local settings (git-ignored)
└── .env.example         # Template for .env
```

## Useful Commands

```bash
# Stop Postgres
docker compose down

# Stop Postgres AND delete all data
docker compose down -v

# Add a new dependency
uv add <package-name>
```

## Viewing the Database

Adminer has been setup, you can simply view the database when running locally on:
http://localhost:8080/

Connection settings:
- Host: localhost
- Port: 5432
- User: postgres
- Password: postgres
- Database: athletic_mindset
