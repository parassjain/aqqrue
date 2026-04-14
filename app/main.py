import traceback

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import router

app = FastAPI(
    title="Aqqrue — Agentic CSV Processor",
    description="AI-powered CSV transformation agent for accountants",
    version="0.1.0",
)

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
