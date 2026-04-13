from typing import TypedDict, List, Dict, Optional


class CSVVersion(TypedDict):
    version: int
    csv_bytes: bytes
    operation: str
    timestamp: float


class ValidationResult(TypedDict):
    valid: bool
    errors: List[str]
    warnings: List[str]


class PreviewResult(TypedDict):
    rows_affected: int
    sample_before: List[dict]
    sample_after: List[dict]
    columns_added: List[str]
    columns_removed: List[str]
    summary: str


class ExecutionResult(TypedDict):
    success: bool
    csv_output: Optional[bytes]
    error: Optional[str]
    rows: Optional[int]
    columns: Optional[List[str]]


class AuditEntry(TypedDict):
    turn: int
    instruction: str
    code: str
    status: str
    timestamp: float
    rows_before: int
    rows_after: int


class AgentState(TypedDict):
    """State that flows through the LangGraph agent graph."""

    # Session context
    session_id: str

    # CSV data (current version bytes — not stored in graph state, read from CSVManager)
    csv_metadata: dict  # Column names, dtypes, sample rows, row count

    # User input for this turn
    user_message: str

    # Planner output
    plan: str

    # Code generation
    generated_code: str
    retry_count: int
    last_error: str  # Error from previous attempt (for retry context)

    # Validation
    validation_result: ValidationResult

    # Preview
    preview: PreviewResult

    # Execution
    execution_result: ExecutionResult

    # Audit
    audit_log: List[AuditEntry]

    # Control flow
    error: Optional[str]
    response_message: str  # Final message to send back to user
