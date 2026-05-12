import os
import re
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession, AsyncEngine, async_sessionmaker, create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData


class Base(DeclarativeBase):
    metadata = MetaData()


def _get_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    url = re.sub(r"^postgres://", "postgresql+asyncpg://", url)
    url = re.sub(r"^postgresql://", "postgresql+asyncpg://", url)
    return url


engine: AsyncEngine = create_async_engine(
    _get_url(),
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=False,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
