"""
Plan / PlanStep dataclasses and typed events emitted by agent/loop.py.
No LLM-provider-specific imports here — these are pure Python dataclasses.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StepStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    DONE = "done"
    FAILED = "failed"


@dataclass
class PlanStep:
    step_number: int
    description: str
    tool_to_use: str
    status: StepStatus = StepStatus.PENDING


@dataclass
class Plan:
    steps: list[PlanStep]
    clarification_needed: bool = False
    questions: list[str] = field(default_factory=list)

    @classmethod
    def from_tool_result(cls, result: dict) -> "Plan":
        """Parse a Plan from the dict returned by the provide_plan tool."""
        steps = [
            PlanStep(
                step_number=s.get("step_number", i + 1),
                description=s.get("description", ""),
                tool_to_use=s.get("tool_to_use", ""),
            )
            for i, s in enumerate(result.get("steps", []))
        ]
        return cls(
            steps=steps,
            clarification_needed=result.get("clarification_needed", False),
            questions=result.get("questions", []),
        )

    def get_step_for_tool(self, tool_name: str) -> "PlanStep | None":
        """Return the first pending/active step matching tool_name."""
        for step in self.steps:
            if step.tool_to_use == tool_name and step.status in (
                StepStatus.PENDING, StepStatus.ACTIVE
            ):
                return step
        return None

    def to_markdown(self) -> str:
        icons = {
            StepStatus.PENDING: "⬜",
            StepStatus.ACTIVE: "🔄",
            StepStatus.DONE: "✅",
            StepStatus.FAILED: "❌",
        }
        lines = ["**Plan:**"]
        for step in self.steps:
            lines.append(f"{icons[step.status]} **Step {step.step_number}:** {step.description}")
        if self.clarification_needed and self.questions:
            lines.append("\n**Clarifications needed:**")
            lines.extend(f"- {q}" for q in self.questions)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Typed events yielded by agent/loop.py → consumed by app.py
# ---------------------------------------------------------------------------

@dataclass
class PlanCreated:
    plan: Plan


@dataclass
class PlanStepCompleted:
    step: PlanStep
    result_summary: str


@dataclass
class PlanStepFailed:
    step: PlanStep
    error: str


@dataclass
class DataFrameResult:
    output_file: str
    row_count: int
    columns: list[str]
    message: str


@dataclass
class ChartGenerated:
    chart_file: str
    chart_type: str
    title: str


@dataclass
class StatsResult:
    statistics: dict[str, Any]
    message: str


@dataclass
class FinalResponse:
    text: str


@dataclass
class AgentError:
    message: str


@dataclass
class UndoPerformed:
    restored_file: str
    message: str
