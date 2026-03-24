"""
One-time migration: export thoughts from Supabase, import to Coolify Postgres.

Prerequisites:
  - Supabase connection string (from Supabase dashboard > Settings > Database)
  - Coolify Postgres accessible (via SSH tunnel or direct)
  - pip install asyncpg

Usage:
  # Set env vars
  export SOURCE_DB="postgresql://postgres.<ref>:<password>@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
  export TARGET_DB="postgresql+asyncpg://openbrain:password@localhost:5433/openbrain"

  # Run (from project root)
  python seed/migrate_from_supabase.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncpg


async def migrate():
    source_url = os.environ["SOURCE_DB"]
    target_url = os.environ["TARGET_DB"].replace("postgresql+asyncpg://", "postgresql://")

    print("Connecting to Supabase...")
    source = await asyncpg.connect(source_url)

    print("Connecting to Coolify Postgres...")
    target = await asyncpg.connect(target_url)

    # Export all thoughts
    rows = await source.fetch(
        "SELECT id, content, embedding::text, metadata, created_at, updated_at FROM thoughts ORDER BY created_at"
    )
    print(f"Exported {len(rows)} thoughts from Supabase")

    # Import into target
    imported = 0
    for row in rows:
        await target.execute(
            """
            INSERT INTO thoughts (id, content, embedding, metadata, created_at, updated_at)
            VALUES ($1, $2, $3::vector, $4, $5, $6)
            ON CONFLICT (id) DO NOTHING
            """,
            row["id"],
            row["content"],
            row["embedding"],
            row["metadata"],
            row["created_at"],
            row["updated_at"],
        )
        imported += 1

    print(f"Imported {imported} thoughts into Coolify Postgres")

    # Verify
    target_count = await target.fetchval("SELECT count(*) FROM thoughts")
    print(f"Verification: {target_count} rows in target database")

    await source.close()
    await target.close()


if __name__ == "__main__":
    asyncio.run(migrate())
