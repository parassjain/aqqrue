from typing import Optional

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
    preview: Optional[dict] = None
    metadata: Optional[dict] = None
    error: Optional[str] = None
    version: Optional[int] = None


class UndoResponse(BaseModel):
    success: bool
    metadata: Optional[dict] = None
    message: str


class HistoryResponse(BaseModel):
    versions: list[dict]
    audit_log: list[dict]
