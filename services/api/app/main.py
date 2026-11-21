import logging
import re
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth_org, events, logistics, operations, participants, public
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("gatherai")
settings = get_settings()

app = FastAPI(title="GatherAI API", version="0.1.0")
REQUEST_ID_HEADER = "X-Request-ID"
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")
_SECRET_PATH = re.compile(r"(/registrations/)[^/]+")


def _redact(path: str) -> str:
    """Private registration links carry a bearer token in the path; keep it out of logs."""
    return _SECRET_PATH.sub(r"<redacted>", path)


@app.middleware("http")
async def request_id(request: Request, call_next):
    """Tags each request with an ID that support can match to server logs. Bodies are never logged."""
    incoming = request.headers.get(REQUEST_ID_HEADER, "")
    rid = incoming if _SAFE_REQUEST_ID.match(incoming) else uuid.uuid4().hex
    request.state.request_id = rid
    started = time.perf_counter()
    response = await call_next(request)
    response.headers[REQUEST_ID_HEADER] = rid
    level = logging.WARNING if response.status_code >= 500 else logging.INFO
    log.log(level, "request_id=%s %s %s -> %s in %.0fms", rid, request.method, _redact(request.url.path), response.status_code,
            (time.perf_counter() - started) * 1000)
    return response


app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", REQUEST_ID_HEADER], expose_headers=[REQUEST_ID_HEADER],
)


@app.exception_handler(Exception)
def unhandled(request: Request, exc: Exception) -> JSONResponse:
    rid = getattr(request.state, "request_id", None) or uuid.uuid4().hex
    log.exception("Unhandled error request_id=%s on %s %s", rid, request.method, _redact(request.url.path))
    return JSONResponse(
        {"detail": "Something went wrong. Please try again.", "request_id": rid}, status_code=500, headers={REQUEST_ID_HEADER: rid},
    )


for module in (auth_org, events, participants, logistics, operations, public):
    app.include_router(module.router)
if settings.app_env != "production":
    # The simulator stands in for a real channel during development and demos only.
    app.include_router(operations.simulator)
