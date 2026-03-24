import pytest
from unittest.mock import patch

from src.services.openrouter import embed, extract_metadata


@pytest.mark.asyncio
async def test_embed_returns_vector():
    with patch("src.services.openrouter._post_openrouter", return_value={
        "data": [{"embedding": [0.1] * 1536}]
    }):
        result = await embed("test thought")
        assert len(result) == 1536
        assert result[0] == 0.1


@pytest.mark.asyncio
async def test_extract_metadata_returns_dict():
    with patch("src.services.openrouter._post_openrouter", return_value={
        "choices": [{"message": {"content": '{"type":"observation","topics":["testing"],"people":[],"action_items":[],"dates_mentioned":[]}'}}]
    }):
        result = await extract_metadata("this is a test")
        assert result["type"] == "observation"
        assert "testing" in result["topics"]


@pytest.mark.asyncio
async def test_extract_metadata_fallback_on_bad_json():
    with patch("src.services.openrouter._post_openrouter", return_value={
        "choices": [{"message": {"content": "not json at all"}}]
    }):
        result = await extract_metadata("test")
        assert result["type"] == "observation"
        assert result["topics"] == ["uncategorized"]


@pytest.mark.asyncio
async def test_embed_raises_on_api_error():
    with patch("src.services.openrouter._post_openrouter", side_effect=RuntimeError("OpenRouter request failed: 500")):
        with pytest.raises(RuntimeError, match="request failed"):
            await embed("test")
