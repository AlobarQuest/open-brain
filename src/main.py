import hmac
import json
from contextlib import asynccontextmanager

import sqlalchemy
from fastapi import FastAPI, Request, Response
from fastmcp import FastMCP

from src.config import get_settings
from src.db.engine import get_engine, get_session_factory
from src.tools.thoughts import register_thought_tools

mcp = FastMCP("open-brain", json_response=True, stateless_http=True)
register_thought_tools(mcp)

mcp_asgi_app = mcp.http_app(path="/")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp_asgi_app.router.lifespan_context(mcp_asgi_app):
        yield
    await get_engine().dispose()


app = FastAPI(title="Open Brain", lifespan=lifespan)


@app.middleware("http")
async def auth_middleware(request: Request, call_next) -> Response:
    if request.url.path == "/api/health":
        return await call_next(request)

    provided = request.headers.get("x-brain-key") or request.query_params.get("key")
    if not provided or not hmac.compare_digest(provided, get_settings().mcp_access_key):
        return Response(
            content='{"error": "Invalid or missing access key"}',
            status_code=401,
            media_type="application/json",
        )
    return await call_next(request)


app.mount("/mcp", mcp_asgi_app)

MCP_HTTP_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]


class MCPPrefixAlias:
    """Serve /mcp with the same mounted app behavior as /mcp/."""

    def __init__(self, app, mount_path: str):
        self.app = app
        self.mount_path = mount_path.rstrip("/")

    async def __call__(self, scope, receive, send) -> None:
        alias_scope = dict(scope)
        alias_scope["app_root_path"] = alias_scope.get(
            "app_root_path", alias_scope.get("root_path", "")
        )
        alias_scope["root_path"] = f"{alias_scope.get('root_path', '')}{self.mount_path}"
        alias_scope["path"] = f"{scope['path'].rstrip('/')}/"

        raw_path = scope.get("raw_path")
        if raw_path is not None:
            alias_scope["raw_path"] = raw_path.rstrip(b"/") + b"/"

        await self.app(alias_scope, receive, send)


app.add_route(
    "/mcp",
    MCPPrefixAlias(mcp_asgi_app, "/mcp"),
    methods=MCP_HTTP_METHODS,
    include_in_schema=False,
)


@app.get("/api/health")
async def health():
    settings = get_settings()
    async with get_session_factory()() as session:
        try:
            await session.execute(sqlalchemy.text("SELECT 1"))
            db_status = "connected"
        except Exception:
            db_status = "error"
    status_code = 200 if db_status == "connected" else 503
    return Response(
        content=json.dumps({"status": "ok" if db_status == "connected" else "degraded", "app": settings.app_name, "db": db_status}),
        status_code=status_code,
        media_type="application/json",
    )
