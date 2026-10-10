from collections.abc import Generator
from functools import lru_cache

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .config import get_settings


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    if not url:
        raise HTTPException(503, "Database is not configured.")
    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"prepare_threshold": None} if url.startswith("postgresql+psycopg:") else {},
    )


def get_db() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session
