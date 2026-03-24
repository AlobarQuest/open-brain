#!/bin/sh

set -eu

if [ -z "${DATABASE_URL:-}" ]; then
  : "${POSTGRES_PASSWORD:?DATABASE_URL or POSTGRES_PASSWORD must be set}"

  export DATABASE_URL="$(
    python - <<'PY'
import os
from urllib.parse import quote

user = os.environ.get("POSTGRES_USER", "openbrain")
password = os.environ["POSTGRES_PASSWORD"]
host = os.environ.get("POSTGRES_HOST", "openbrain-db")
port = os.environ.get("POSTGRES_PORT", "5432")
database = os.environ.get("POSTGRES_DB", "openbrain")

print(
    f"postgresql+asyncpg://{quote(user, safe='')}:{quote(password, safe='')}@"
    f"{host}:{port}/{quote(database, safe='')}"
)
PY
  )"
fi

alembic upgrade head
exec uvicorn src.main:app --host 0.0.0.0 --port "${PORT:-80}"
