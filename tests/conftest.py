import os
import subprocess
from unittest.mock import AsyncMock, patch

import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

# Set required env vars BEFORE any src imports so Settings doesn't fail.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("OPENROUTER_API_KEY", "sk-test-fake-key")
os.environ.setdefault("MCP_ACCESS_KEY", "a" * 64)
os.environ.setdefault("APP_ENV", "test")


@pytest.fixture(scope="session")
def pg_container():
    """Start a pgvector Postgres container for the entire test session."""
    with PostgresContainer(
        image="pgvector/pgvector:pg16",
        username="openbrain_test",
        password="testpass",
        dbname="openbrain_test",
    ) as pg:
        yield pg


@pytest.fixture(scope="session")
def database_url(pg_container):
    """Async database URL for the test container."""
    sync_url = pg_container.get_connection_url()
    return sync_url.replace("postgresql://", "postgresql+asyncpg://").replace(
        "psycopg2", "asyncpg"
    )


@pytest.fixture(scope="session")
def _run_migrations(database_url):
    """Run Alembic migrations via subprocess to avoid event loop conflicts."""
    os.environ["DATABASE_URL"] = database_url

    import sys
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env={**os.environ, "DATABASE_URL": database_url},
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(__file__)),
    )
    if result.returncode != 0:
        raise RuntimeError(f"Alembic migration failed:\n{result.stderr}")


@pytest.fixture(scope="session")
def test_engine(database_url, _run_migrations):
    """Create an async engine for the test DB. NullPool avoids connection reuse issues."""
    return create_async_engine(database_url, echo=False, poolclass=NullPool)


@pytest.fixture
async def db_session(test_engine):
    """Per-test async session with table truncation for isolation."""
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    session = session_factory()
    yield session
    await session.close()
    # Truncate for clean state
    async with test_engine.connect() as conn:
        await conn.execute(sqlalchemy.text("TRUNCATE TABLE thoughts CASCADE"))
        await conn.commit()


@pytest.fixture
def _patch_db(test_engine, db_session, monkeypatch):
    """Patch the src.db.engine lazy getters so tools/repos use the test DB."""
    import src.db.engine as engine_mod
    from sqlalchemy.ext.asyncio import async_sessionmaker

    test_factory = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)

    monkeypatch.setattr(engine_mod, "get_engine", lambda: test_engine)
    monkeypatch.setattr(engine_mod, "get_session_factory", lambda: test_factory)


@pytest.fixture
def mock_openrouter():
    """Mock all OpenRouter-dependent services."""
    fake_embedding = [0.1] * 1536
    fake_metadata = {"topics": ["test"], "people": [], "action_items": [], "type": "observation"}

    with (
        patch("src.services.openrouter.embed", new_callable=AsyncMock, return_value=fake_embedding) as mock_embed,
        patch("src.services.openrouter.extract_metadata", new_callable=AsyncMock, return_value=fake_metadata) as mock_meta,
    ):
        yield {
            "embed": mock_embed,
            "extract_metadata": mock_meta,
            "embedding": fake_embedding,
            "metadata": fake_metadata,
        }


@pytest.fixture
async def app_client(_patch_db, mock_openrouter):
    """Async HTTP client for non-MCP routes (health, auth checks)."""
    import httpx
    from src.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def auth_headers():
    """Valid auth headers for MCP requests."""
    return {
        "x-brain-key": "a" * 64,
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
