import os

# Set required env vars BEFORE any app imports trigger Settings() instantiation
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
os.environ.setdefault("MCP_ACCESS_KEY", "correct-key")

import pytest
from httpx import AsyncClient, ASGITransport

from src.main import app


@pytest.mark.asyncio
async def test_health_no_auth_required():
    """Health endpoint should work without auth for Coolify probes."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")
        # May fail DB check but should not 401
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_mcp_rejects_missing_key():
    """MCP endpoint should 401 without access key."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/mcp/")
        assert response.status_code == 401
