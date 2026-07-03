"""
DATABASE — Connection setup for PostgreSQL.

Three things happen here:
1. Create an "engine" (a pool of connections to Postgres)
2. Create a "session factory" (how routes get a DB connection)
3. Define the Base class (all future models inherit from this)

Think of it like this:
- Engine = the pipe between your app and the database
- Session = one conversation through that pipe (open, do stuff, close)
- Base = the parent class that tells SQLAlchemy "this Python class = a DB table"
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# Create the connection pool
# - echo prints SQL when DEBUG is on (local only)
# - pool_pre_ping checks a connection is alive before using it (managed/serverless
#   Postgres like Neon drops idle connections, so this avoids stale-connection errors)
# - pool_recycle refreshes connections periodically for the same reason
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={"statement_cache_size": 0},
)

# Factory that creates new sessions
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Every ORM model will inherit from this. SQLAlchemy uses it to track all tables."""
    pass


async def get_db():
    """
    Dependency — gives a route handler a database session.

    Usage:
        @app.get("/something")
        async def my_route(db: AsyncSession = Depends(get_db)):
            # use db here
            ...

    The session auto-closes when the request finishes (the 'finally' block).
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
