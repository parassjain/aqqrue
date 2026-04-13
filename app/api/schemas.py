from pydantic import BaseModel


class SessionCreateResponse(BaseModel):
    session_id: str


class UploadResponse(BaseModel):
    session_id: str
    metadata: dict


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    preview: dict | None = None
    metadata: dict | None = None
    error: str | None = None
    version: int | None = None


class UndoResponse(BaseModel):
    success: bool
    metadata: dict | None = None
    message: str


class HistoryResponse(BaseModel):
    versions: list[dict]
    audit_log: list[dict]
