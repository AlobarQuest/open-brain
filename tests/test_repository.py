import pytest

from src.repositories.thoughts import ThoughtRepository


@pytest.mark.asyncio
async def test_create_thought(db_session):
    repo = ThoughtRepository(db_session)
    thought = await repo.create(
        content="Test thought about Python",
        embedding=[0.1] * 1536,
        metadata={"type": "observation", "topics": ["python"], "people": [], "source": "mcp"},
    )
    assert thought.id is not None
    assert thought.content == "Test thought about Python"
    assert thought.metadata_["type"] == "observation"


@pytest.mark.asyncio
async def test_list_thoughts(db_session):
    repo = ThoughtRepository(db_session)
    await repo.create(
        content="First thought",
        embedding=[0.1] * 1536,
        metadata={"type": "observation", "topics": ["test"], "people": [], "source": "mcp"},
    )
    await repo.create(
        content="Second thought",
        embedding=[0.2] * 1536,
        metadata={"type": "idea", "topics": ["test"], "people": [], "source": "mcp"},
    )
    results = await repo.list_thoughts(limit=10)
    assert len(results) >= 2


@pytest.mark.asyncio
async def test_list_thoughts_filter_by_type(db_session):
    repo = ThoughtRepository(db_session)
    await repo.create(
        content="An observation",
        embedding=[0.1] * 1536,
        metadata={"type": "observation", "topics": ["filter"], "people": [], "source": "mcp"},
    )
    await repo.create(
        content="An idea",
        embedding=[0.2] * 1536,
        metadata={"type": "idea", "topics": ["filter"], "people": [], "source": "mcp"},
    )
    results = await repo.list_thoughts(limit=10, type_filter="idea")
    assert all(r.metadata_["type"] == "idea" for r in results)


@pytest.mark.asyncio
async def test_stats(db_session):
    repo = ThoughtRepository(db_session)
    await repo.create(
        content="Stats test thought",
        embedding=[0.1] * 1536,
        metadata={"type": "observation", "topics": ["stats"], "people": ["Devon"], "source": "mcp"},
    )
    stats = await repo.stats()
    assert stats["total"] >= 1
    assert "observation" in stats["types"]
