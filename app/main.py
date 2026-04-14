import logging
import traceback

logging.basicConfig(level=logging.INFO)

import docker
import docker.errors
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import router

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Aqqrue — Agentic CSV Processor",
    description="AI-powered CSV transformation agent for accountants",
    version="0.1.0",
)


@app.on_event("startup")
def check_docker_ready():
    try:
        client = docker.from_env()
        client.ping()
        client.close()
        logger.info("Docker daemon reachable — sandbox execution available")
        print("Docker daemon reachable — sandbox execution available", flush=True)
    except docker.errors.DockerException as e:
        logger.warning(
            "Docker daemon NOT reachable — sandbox execution will be unavailable: %s", e
        )
        print(f"Docker daemon NOT reachable: {e}", flush=True)


app.include_router(router, prefix="/api")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    tb = traceback.format_exc()
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "type": type(exc).__name__,
            "traceback": tb,
        },
    )


@app.get("/health")
def health():
    return {"status": "ok"}
