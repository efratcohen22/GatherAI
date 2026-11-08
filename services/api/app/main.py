import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth_org, events, logistics, operations, participants, public
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("gatherai")
settings = get_settings()

app = FastAPI(title="GatherAI API", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(Exception)
def unhandled(request: Request, exc: Exception) -> JSONResponse:
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse({"detail": "Something went wrong. Please try again."}, status_code=500)


for module in (auth_org, events, participants, logistics, operations, public):
    app.include_router(module.router)
app.include_router(operations.simulator)
