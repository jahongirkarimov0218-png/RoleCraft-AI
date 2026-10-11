"""FastAPI application factory. Routes are thin: validate -> call core -> serialise."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .. import __version__
from ..analyze import AnalysisError, analyze
from ..ir import SCHEMA_VERSION, AnalysisConfig
from ..validate import GraphInvalid
from .schemas import AnalyzeRequest, AnalyzeResponse, ErrorBody, ErrorDetail, ErrorResponse, Health

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


ERROR_RESPONSES = {code: {"model": ErrorResponse, "description": f"{code}"} for code in (413, 422, 500, 504)}


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or Settings.from_env()
    app = FastAPI(
        title="PromptGraphify API",
        version=__version__,
        description="Static analysis of LLM prompts into a knowledge graph and an execution DAG. "
        "Community-built; not affiliated with Graphify Labs.",
    )
    app.add_middleware(BodyLimitMiddleware, limit=cfg.max_request_bytes)

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

    @app.get("/api/health", response_model=Health, tags=["meta"])
    async def health() -> Health:
        return Health(status="ok", version=__version__, schema_version=SCHEMA_VERSION, llm_enabled=False)

    @app.post(
        "/api/analyze",
        response_model=AnalyzeResponse,
        responses=ERROR_RESPONSES,  # type: ignore[arg-type]
        tags=["analysis"],
        summary="Analyze prompt files into a knowledge graph and an execution DAG",
    )
    async def post_analyze(req: AnalyzeRequest) -> AnalyzeResponse | JSONResponse:
        total = sum(len(f.text) for f in req.files)
        if total > cfg.max_input_chars:
            return error_response(
                "input_too_large", f"input has {total} characters, the limit is {cfg.max_input_chars}"
            )
        config = AnalysisConfig(layer_b=False)
        pairs = [(f.path, f.text) for f in req.files]
        try:
            doc = await asyncio.wait_for(
                asyncio.to_thread(analyze, pairs, config, max_input_chars=cfg.max_input_chars),
                timeout=cfg.analyze_timeout_s,
            )
        except AnalysisError as exc:
            return error_response(exc.code if exc.code in STATUS_BY_CODE else "invalid_request", str(exc))
        except TimeoutError:
            return error_response("timeout", f"analysis took longer than {cfg.analyze_timeout_s:g} s")
        except GraphInvalid:
            return error_response("internal_invariant_failed", "the analyzer produced a graph that failed validation")
        return AnalyzeResponse(graph_id=doc.graph_id, graph=doc)

    return app


app = create_app()
