"""Shared pure data models for orchestration + reporting (spec §11, §12, §14).
No PyRIT import. ExecutionRecord is the canonical per-execution outcome produced by
BOTH the live executor (reports.memory_query) and a memory replay, and consumed by
reports.aggregation — one record type, two producers, one consumer. from_plan()
keeps record construction DRY across the orchestrator, the executor, and tests."""
from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from agentic_redteam.config import ModelConfig
from agentic_redteam.engine.plan import RunConfig
from agentic_redteam.engine.trajectory import TEXT_INFERRED

if TYPE_CHECKING:                       # avoid any import cost at runtime; plan.py never imports us
    from agentic_redteam.engine.plan import AttackPlan


class RunRequest(BaseModel):
    """Everything the orchestrator needs to run one self-service request (spec §11/§13)."""
    config: RunConfig                                   # resolve() input: plugins x strategies x profile
    target: ModelConfig
    judge: ModelConfig
    adversarial: ModelConfig | None = None              # required iff a multi-turn strategy is selected
    user_goals: dict[str, list[str]] = Field(default_factory=dict)   # plugin_id -> goals (intent)
    datasets_dir: str | None = None                     # mirror dir for dataset plugins (gated, §6.2)
    concurrency: int = 4                                # semaphore size (protect gateway + local vLLM)
    requested_by: str = ""                              # authorization record (audit log, §12)


class ExecutionRecord(BaseModel):
    """One (plugin x strategy x objective) outcome. status: 'succeeded' == attack
    worked (VIOLATION) / 'defended' == target held / 'error' == harness failure."""
    run_id: str
    plugin_id: str
    strategy_id: str
    objective_id: str
    objective: str
    status: str
    score_value: str = ""                               # "true"/"false" from the scorer
    rationale: str = ""
    fidelity: str = TEXT_INFERRED                       # observed fidelity (spec §9)
    severity: str = "low"
    framework_refs: dict[str, list[str]] = Field(default_factory=dict)
    conversation_id: str = ""
    error: str = ""

    @property
    def succeeded(self) -> bool:
        return self.status == "succeeded"

    @classmethod
    def from_plan(cls, plan: "AttackPlan", *, status: str, score_value: str = "",
                  rationale: str = "", fidelity: str = TEXT_INFERRED,
                  conversation_id: str = "", error: str = "") -> "ExecutionRecord":
        fr = plan.plugin.framework_refs
        return cls(
            run_id=plan.run_id, plugin_id=plan.plugin.id, strategy_id=plan.strategy_id,
            objective_id=plan.labels["objective_id"], objective=plan.objective, status=status,
            score_value=score_value, rationale=rationale, fidelity=fidelity,
            severity=plan.plugin.severity.value,
            framework_refs={"owasp_llm": fr.owasp_llm, "owasp_agentic": fr.owasp_agentic,
                            "owasp_api": fr.owasp_api, "atlas": fr.atlas},
            conversation_id=conversation_id, error=error,
        )


class RunSummary(BaseModel):
    """Denormalised run-level rollup persisted to SQLite for the run list (spec §12)."""
    run_id: str
    status: str = "pending"                             # pending|running|completed|stopped|failed
    total: int = 0
    completed: int = 0
    succeeded: int = 0
    errors: int = 0

    @property
    def asr(self) -> float:
        graded = self.completed - self.errors
        return (self.succeeded / graded) if graded else 0.0
