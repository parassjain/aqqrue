"""
Plan and PlanStep dataclasses + typed events emitted by the agent loop.
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
    def from_tool_input(cls, tool_input: dict) -> "Plan":
        steps = [
            PlanStep(
                step_number=s["step_number"],
                description=s["description"],
                tool_to_use=s["tool_to_use"],
            )
            for s in tool_input.get("steps", [])
        ]
        return cls(
            steps=steps,
            clarification_needed=tool_input.get("clarification_needed", False),
            questions=tool_input.get("questions", []),
        )

    def get_step_for_tool(self, tool_name: str) -> PlanStep | None:
        """Return the first pending/active step that matches the given tool name."""
        for step in self.steps:
            if step.tool_to_use == tool_name and step.status in (StepStatus.PENDING, StepStatus.ACTIVE):
                return step
        return None

    def to_markdown(self) -> str:
        lines = ["**Plan:**"]
        status_icons = {
            StepStatus.PENDING: "⬜",
            StepStatus.ACTIVE: "🔄",
            StepStatus.DONE: "✅",
            StepStatus.FAILED: "❌",
        }
        for step in self.steps:
            icon = status_icons[step.status]
            lines.append(f"{icon} **Step {step.step_number}:** {step.description}")
        if self.clarification_needed and self.questions:
            lines.append("\n**Clarifications needed:**")
            for q in self.questions:
                lines.append(f"- {q}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Event types yielded by the agent loop
# ---------------------------------------------------------------------------

@dataclass
class PlanCreated:
    plan: Plan


@dataclass
class PlanStepStarted:
    step: PlanStep


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
