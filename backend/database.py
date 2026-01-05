# backend/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from typing import AsyncGenerator # <--- IMPORT THIS

# --- [START] SECURITY FIX ---
from .config import DATABASE_URL # Import the secure URL
# --- [END] SECURITY FIX ---

if not DATABASE_URL:
    raise ValueError("No DATABASE_URL set in the .env file")

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

# --- [START] TYPE HINT FIX ---
# The return type is an AsyncGenerator that yields an AsyncSession
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
# --- [END] TYPE HINT FIX ---
    """
    Dependency to get an AsyncSession.
    Ensures the session is always closed.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()