import io
import traceback

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse

from app.api.schemas import (
    SessionCreateResponse,
    UploadResponse,
    ChatRequest,
    ChatResponse,
    UndoResponse,
    HistoryResponse,
)
from app.services.session_manager import session_manager
from app.agent.graph import agent_graph

router = APIRouter()


@router.post("/session/create", response_model=SessionCreateResponse)
def create_session():
    session_id = session_manager.create_session()
    return SessionCreateResponse(session_id=session_id)


@router.post("/session/{session_id}/upload", response_model=UploadResponse)
async def upload_csv(session_id: str, file: UploadFile = File(...)):
    csv_mgr = session_manager.get_session(session_id)
    if csv_mgr is None:
        raise HTTPException(status_code=404, detail="Session not found")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        metadata = csv_mgr.load_csv(content, filename=file.filename or "upload.csv")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {e}")

    return UploadResponse(session_id=session_id, metadata=metadata)


@router.post("/session/{session_id}/chat", response_model=ChatResponse)
def chat(session_id: str, request: ChatRequest):
    csv_mgr = session_manager.get_session(session_id)
    if csv_mgr is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if csv_mgr.current_csv_path is None:
        raise HTTPException(status_code=400, detail="No CSV uploaded yet")

    metadata = csv_mgr.get_metadata()

    # Build initial state for the graph
    initial_state = {
        "session_id": session_id,
        "csv_metadata": metadata,
        "user_message": request.message,
        "intent": "",
        "plan": "",
        "generated_code": "",
        "retry_count": 0,
        "last_error": "",
        "validation_result": {"valid": False, "errors": [], "warnings": []},
        "preview": {},
        "execution_result": {"success": False, "csv_output": None, "error": None},
        "audit_log": [],
        "error": None,
        "response_message": "",
    }

    # Run the agent graph
    try:
        result = agent_graph.invoke(initial_state)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "message": str(e),
                "type": type(e).__name__,
                "traceback": traceback.format_exc(),
            },
        )

    # Get updated metadata
    updated_metadata = csv_mgr.get_metadata()

    return ChatResponse(
        response=result.get("response_message", "Operation completed."),
        preview=result.get("preview"),
        metadata=updated_metadata,
        error=result.get("error"),
        version=updated_metadata.get("version"),
    )


@router.post("/session/{session_id}/undo", response_model=UndoResponse)
def undo(session_id: str):
    csv_mgr = session_manager.get_session(session_id)
    if csv_mgr is None:
        raise HTTPException(status_code=404, detail="Session not found")

    result = csv_mgr.undo()
    if result is None:
        return UndoResponse(success=False, message="Nothing to undo")

    return UndoResponse(
        success=True,
        metadata=result,
        message=f"Reverted to version {result['version']}",
    )


@router.get("/session/{session_id}/download")
def download_csv(session_id: str):
    csv_mgr = session_manager.get_session(session_id)
    if csv_mgr is None:
        raise HTTPException(status_code=404, detail="Session not found")

    csv_bytes = csv_mgr.get_current_csv_bytes()
    if csv_bytes is None:
        raise HTTPException(status_code=400, detail="No CSV available")

    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=output_v{csv_mgr.current_version}.csv"
        },
    )


@router.get("/session/{session_id}/history", response_model=HistoryResponse)
def get_history(session_id: str):
    csv_mgr = session_manager.get_session(session_id)
    if csv_mgr is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return HistoryResponse(
        versions=csv_mgr.get_history(),
        audit_log=[],  # TODO: persist audit log in session manager
    )
