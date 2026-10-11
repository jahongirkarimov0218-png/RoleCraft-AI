"""FastAPI application factory. Routes are thin: validate -> call core -> serialise."""

from __future__ import annotations

import asyncio
import os
import re
import threading
from dataclasses import dataclass
from typing import Annotated

from fastapi import FastAPI, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .. import __version__
from ..analyze import AnalysisError, analyze
from ..graphjson import UnsupportedGraph
from ..ir import SCHEMA_VERSION, AnalysisConfig, GraphDocument
from ..queries import QUERY_NAMES, QUERY_SPECS, QueryResult, QuerySpec, run_query
from ..storage import GraphStore, SqliteGraphStore, default_db_path
from ..validate import GraphInvalid, validate_document
from .schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    ErrorBody,
    ErrorDetail,
    ErrorResponse,
    Health,
    NodeDetail,
    SeverityCounts,
    ValidateRequest,
    ValidateResponse,
    ViolationOut,
)

STATUS_BY_CODE = {
    "invalid_request": 422,
    "input_too_large": 413,
    "no_input": 422,
    "duplicate_path": 422,
    "not_found": 404,
    "unsupported_schema": 422,
    "timeout": 504,
    "internal_error": 500,
    "internal_invariant_failed": 500,
    "llm_unavailable": 503,
}
GRAPH_ID = re.compile(r"^[0-9a-f]{16}$")


@dataclass(frozen=True)
class Settings:
    max_request_bytes: int = 4_000_000
    max_input_chars: int = 500_000
    analyze_timeout_s: float = 30.0

    @classmethod
    def from_env(cls) -> Settings:
        def num(name: str, default, cast):
            raw = os.environ.get(name)
            return cast(raw) if raw else default

        return cls(
            max_request_bytes=num("PROMPTGRAPHIFY_MAX_REQUEST_BYTES", cls.max_request_bytes, int),
            max_input_chars=num("PROMPTGRAPHIFY_MAX_INPUT_CHARS", cls.max_input_chars, int),
            analyze_timeout_s=num("PROMPTGRAPHIFY_ANALYZE_TIMEOUT_S", cls.analyze_timeout_s, float),
        )


class BodyLimitMiddleware:
    """Rejects request bodies larger than ``limit`` bytes, whether announced or streamed."""

    def __init__(self, app: ASGIApp, limit: int):
        self.app, self.limit = app, limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = dict(scope["headers"]).get(b"content-length")
        if declared and declared.isdigit() and int(declared) > self.limit:
            await self._reject(scope, receive, send)
            return
        seen = 0

        async def limited() -> Message:
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > self.limit:
                    raise _TooLarge
            return message

        try:
            await self.app(scope, limited, send)
        except _TooLarge:
            await self._reject(scope, receive, send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        resp = error_response("input_too_large", f"request body exceeds {self.limit} bytes")
        await resp(scope, receive, send)


class _TooLarge(Exception):
    pass


def error_response(code: str, message: str, details: list[ErrorDetail] | None = None) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details))  # type: ignore[arg-type]
    return JSONResponse(body.model_dump(mode="json", exclude_none=True), status_code=STATUS_BY_CODE[code])


ERROR_RESPONSES = {code: {"model": ErrorResponse, "description": f"{code}"} for code in (404, 413, 422, 500, 504)}


def create_app(settings: Settings | None = None, store: GraphStore | None = None) -> FastAPI:
    cfg = settings or Settings.from_env()
    app = FastAPI(
        title="PromptGraphify API",
        version=__version__,
        description="Static analysis of LLM prompts into a knowledge graph and an execution DAG. "
        "Community-built; not affiliated with Graphify Labs.",
    )
    app.add_middleware(BodyLimitMiddleware, limit=cfg.max_request_bytes)

    lazy: dict[str, GraphStore] = {}
    lock = threading.Lock()

    def get_store() -> GraphStore:
        if store is not None:
            return store
        with lock:  # created on first use so importing the module has no side effects
            if "s" not in lazy:
                lazy["s"] = SqliteGraphStore(default_db_path())
            return lazy["s"]

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            ErrorDetail(field=".".join(str(p) for p in e["loc"][1:]) or None, message=str(e["msg"]))
            for e in exc.errors()[:20]
        ]
        return error_response("invalid_request", "the request does not match the schema", details)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "not_found" if exc.status_code == 404 else "invalid_request"
        resp = error_response(code, str(exc.detail))
        resp.status_code = exc.status_code
        return resp

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        # Never leak internals: the type is logged by the server, the client gets a generic message.
        print(f"promptgraphify: unhandled {type(exc).__name__}")  # noqa: T201
        return error_response("internal_error", "unexpected server error")

    async def run_analysis(files, layer_b: bool = False):
        total = sum(len(f.text) for f in files)
        if total > cfg.max_input_chars:
            raise AnalysisError("input_too_large", f"input has {total} characters, the limit is {cfg.max_input_chars}")
        pairs = [(f.path, f.text) for f in files]
        return await asyncio.wait_for(
            asyncio.to_thread(analyze, pairs, AnalysisConfig(layer_b=False), max_input_chars=cfg.max_input_chars),
            timeout=cfg.analyze_timeout_s,
        )

    def failure(exc: Exception) -> JSONResponse:
        if isinstance(exc, AnalysisError):
            return error_response(exc.code if exc.code in STATUS_BY_CODE else "invalid_request", str(exc))
        if isinstance(exc, TimeoutError):
            return error_response("timeout", f"analysis took longer than {cfg.analyze_timeout_s:g} s")
        if isinstance(exc, GraphInvalid):
            return error_response("internal_invariant_failed", "the analyzer produced a graph that failed validation")
        if isinstance(exc, UnsupportedGraph):
            return error_response("unsupported_schema", str(exc))
        raise exc

    def load(graph_id: str) -> GraphDocument | JSONResponse:
        if not GRAPH_ID.match(graph_id):
            return error_response("not_found", "no such graph")
        try:
            doc = get_store().get(graph_id)
        except (UnsupportedGraph, GraphInvalid) as exc:
            return failure(exc)
        return doc if doc is not None else error_response("not_found", "no such graph")

    @app.get("/api/health", response_model=Health, tags=["meta"])
    async def health() -> Health:
        return Health(
            status="ok", version=__version__, schema_version=SCHEMA_VERSION, llm_enabled=False, llm_provider=None
        )

    @app.post(
        "/api/analyze",
        response_model=AnalyzeResponse,
        responses=ERROR_RESPONSES,
        tags=["analysis"],  # type: ignore[arg-type]
        summary="Analyze prompt files into a knowledge graph and an execution DAG",
    )
    async def post_analyze(req: AnalyzeRequest) -> AnalyzeResponse | JSONResponse:
        try:
            doc = await run_analysis(req.files, req.layer_b)
        except Exception as exc:  # noqa: BLE001 - mapped to the error envelope by failure()
            return failure(exc)
        get_store().put(doc)
        return AnalyzeResponse(graph_id=doc.graph_id, graph=doc)

    @app.post(
        "/api/validate",
        response_model=ValidateResponse,
        responses=ERROR_RESPONSES,
        tags=["analysis"],  # type: ignore[arg-type]
        summary="Validate a graph or lint prompt files: schema invariants plus analyzer diagnostics",
    )
    async def post_validate(req: ValidateRequest) -> ValidateResponse | JSONResponse:
        if req.graph is not None:
            doc = req.graph
            violations = validate_document(doc)
        else:
            try:
                doc = await run_analysis(req.files or [])
            except Exception as exc:  # noqa: BLE001
                return failure(exc)
            violations = []
        counts = SeverityCounts(
            error=sum(d.severity == "error" for d in doc.diagnostics),
            warning=sum(d.severity == "warning" for d in doc.diagnostics),
            info=sum(d.severity == "info" for d in doc.diagnostics),
        )
        return ValidateResponse(
            ok=not violations and counts.error == 0,
            graph_id=doc.graph_id,
            violations=[ViolationOut(code=v.code, message=v.message, subject=v.subject) for v in violations],
            diagnostics=doc.diagnostics,
            counts=counts,
        )

    @app.get(
        "/api/graph/{graph_id}",
        response_model=GraphDocument,
        responses=ERROR_RESPONSES,
        tags=["graph"],  # type: ignore[arg-type]
        summary="A stored graph",
    )
    async def get_graph(graph_id: Annotated[str, Path(description="16 hex digits")]) -> GraphDocument | JSONResponse:
        return load(graph_id)

    @app.get(
        "/api/graph/{graph_id}/node/{node_id:path}",
        response_model=NodeDetail,
        responses=ERROR_RESPONSES,
        tags=["graph"],  # type: ignore[arg-type]
        summary="One node with its edges and diagnostics",
    )
    async def get_node(graph_id: str, node_id: str) -> NodeDetail | JSONResponse:
        doc = load(graph_id)
        if isinstance(doc, JSONResponse):
            return doc
        node = next((n for n in doc.nodes if n.id == node_id), None)
        if node is None:
            return error_response("not_found", "no such node in this graph")
        return NodeDetail(
            node=node,
            incoming=[e for e in doc.edges if e.target == node_id],
            outgoing=[e for e in doc.edges if e.source == node_id],
            diagnostics=[d for d in doc.diagnostics if node_id in d.affected_nodes],
        )

    @app.get(
        "/api/graph/{graph_id}/path",
        response_model=QueryResult,
        responses=ERROR_RESPONSES,
        tags=["graph"],  # type: ignore[arg-type]
        summary="Shortest path between two nodes (query 'shortest_path')",
    )
    async def get_path(
        graph_id: str,
        source: Annotated[str, Query(min_length=1, max_length=400)],
        target: Annotated[str, Query(min_length=1, max_length=400)],
        undirected: bool = False,
    ) -> QueryResult | JSONResponse:
        doc = load(graph_id)
        if isinstance(doc, JSONResponse):
            return doc
        return run_query(
            doc, "shortest_path", {"source": source, "target": target, "undirected": str(undirected).lower()}
        )

    @app.get("/api/queries", response_model=list[QuerySpec], tags=["graph"], summary="The named queries")
    async def list_queries() -> list[QuerySpec]:
        return QUERY_SPECS

    @app.get(
        "/api/graph/{graph_id}/query/{name}",
        response_model=QueryResult,
        responses=ERROR_RESPONSES,
        tags=["graph"],  # type: ignore[arg-type]
        summary="Run a named query; parameters are query-string arguments",
    )
    async def get_query(graph_id: str, name: str, request: Request) -> QueryResult | JSONResponse:
        if name not in QUERY_NAMES:
            return error_response("not_found", f"unknown query {name!r}")
        doc = load(graph_id)
        if isinstance(doc, JSONResponse):
            return doc
        return run_query(doc, name, {k: v for k, v in request.query_params.items() if len(v) <= 400})

    return app


app = create_app()
