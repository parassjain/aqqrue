from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(
    title="Aqqrue — Agentic CSV Processor",
    description="AI-powered CSV transformation agent for accountants",
    version="0.1.0",
)

app.include_router(router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}
