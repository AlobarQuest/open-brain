import asyncio
from typing import Optional

from fastmcp import FastMCP

from src.db.engine import async_session_factory
from src.repositories.thoughts import ThoughtRepository
from src.services.openrouter import embed, extract_metadata


def register_thought_tools(mcp: FastMCP) -> None:

    @mcp.tool()
    async def capture_thought(content: str) -> dict:
        """Save a new thought to the Open Brain. Generates an embedding and extracts metadata automatically. Use this when the user wants to save something to their brain directly from any AI client — notes, insights, decisions, or migrated content from other systems."""
        embedding, metadata = await asyncio.gather(
            embed(content),
            extract_metadata(content),
        )
        metadata["source"] = "mcp"

        async with async_session_factory() as session:
            repo = ThoughtRepository(session)
            await repo.create(
                content=content,
                embedding=embedding,
                metadata=metadata,
            )
            await session.commit()

        confirmation = f"Captured as {metadata.get('type', 'thought')}"
        if topics := metadata.get("topics"):
            confirmation += f" — {', '.join(topics)}"
        if people := metadata.get("people"):
            confirmation += f" | People: {', '.join(people)}"
        if actions := metadata.get("action_items"):
            confirmation += f" | Actions: {'; '.join(actions)}"
        return {"message": confirmation}

    @mcp.tool()
    async def search_thoughts(
        query: str,
        limit: int = 10,
        threshold: float = 0.5,
    ) -> dict:
        """Search captured thoughts by meaning. Use this when the user asks about a topic, person, or idea they've previously captured."""
        query_embedding = await embed(query)

        async with async_session_factory() as session:
            repo = ThoughtRepository(session)
            results = await repo.search(
                query_embedding=query_embedding,
                threshold=threshold,
                limit=limit,
            )

        if not results:
            return {"message": f'No thoughts found matching "{query}".'}

        formatted = []
        for i, r in enumerate(results):
            m = r["metadata"] or {}
            parts = [
                f"--- Result {i + 1} ({r['similarity'] * 100:.1f}% match) ---",
                f"Captured: {r['created_at'].strftime('%m/%d/%Y') if r['created_at'] else 'unknown'}",
                f"Type: {m.get('type', 'unknown')}",
            ]
            if topics := m.get("topics"):
                parts.append(f"Topics: {', '.join(topics)}")
            if people := m.get("people"):
                parts.append(f"People: {', '.join(people)}")
            if actions := m.get("action_items"):
                parts.append(f"Actions: {'; '.join(actions)}")
            parts.append(f"\n{r['content']}")
            formatted.append("\n".join(parts))

        return {"message": f"Found {len(results)} thought(s):\n\n" + "\n\n".join(formatted)}

    @mcp.tool()
    async def list_thoughts(
        limit: int = 10,
        type: Optional[str] = None,
        topic: Optional[str] = None,
        person: Optional[str] = None,
        days: Optional[int] = None,
    ) -> dict:
        """List recently captured thoughts with optional filters by type, topic, person, or time range."""
        async with async_session_factory() as session:
            repo = ThoughtRepository(session)
            thoughts = await repo.list_thoughts(
                limit=limit,
                type_filter=type,
                topic_filter=topic,
                person_filter=person,
                days=days,
            )

        if not thoughts:
            return {"message": "No thoughts found."}

        formatted = []
        for i, t in enumerate(thoughts):
            m = t.metadata_ or {}
            tags = ", ".join(m.get("topics", []))
            line = (
                f"{i + 1}. [{t.created_at.strftime('%m/%d/%Y')}] "
                f"({m.get('type', '??')}{' - ' + tags if tags else ''})\n"
                f"   {t.content}"
            )
            formatted.append(line)

        return {"message": f"{len(thoughts)} recent thought(s):\n\n" + "\n\n".join(formatted)}

    @mcp.tool()
    async def thought_stats() -> dict:
        """Get a summary of all captured thoughts: totals, types, top topics, and people."""
        async with async_session_factory() as session:
            repo = ThoughtRepository(session)
            stats = await repo.stats()

        lines = [
            f"Total thoughts: {stats['total']}",
            f"Date range: {stats['date_range']['earliest'] or 'N/A'} → {stats['date_range']['latest'] or 'N/A'}",
            "",
            "Types:",
        ]
        for t, count in stats["types"].items():
            lines.append(f"  {t}: {count}")

        if stats["topics"]:
            lines.append("\nTop topics:")
            for t, count in stats["topics"].items():
                lines.append(f"  {t}: {count}")

        if stats["people"]:
            lines.append("\nPeople mentioned:")
            for p, count in stats["people"].items():
                lines.append(f"  {p}: {count}")

        return {"message": "\n".join(lines)}
