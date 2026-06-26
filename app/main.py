"""
MAIN — The entry point of the entire backend.

This file:
1. Creates the FastAPI app
2. Sets up CORS (so your Next.js frontend can talk to this API)
3. Adds a /health endpoint to verify everything's working

To run: uv run uvicorn app.main:app --reload
Then open: http://localhost:8000/docs  (interactive Swagger UI)
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.routers import auth, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan — code that runs when the app starts and stops.

    On startup: verifies the database connection works.
    On shutdown: closes all database connections cleanly.
    """
    # Startup: test the DB connection
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print("✅ Database connection successful")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("   Make sure Postgres is running (docker compose up)")

    yield  # App runs here

    # Shutdown: close connections
    await engine.dispose()
    print("Database connections closed")


# Create the app
app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware — without this, your browser blocks requests from localhost:3000 to localhost:8000
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Routes ---

app.include_router(auth.router)
app.include_router(admin.router)


@app.get("/health")
async def health_check():
    """
    Simple endpoint to verify the server is alive.
    Visit http://localhost:8000/health to see it.
    """
    return {"status": "healthy", "service": settings.APP_NAME}
