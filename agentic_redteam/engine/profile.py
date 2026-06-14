# agentic_redteam/engine/profile.py
from __future__ import annotations

from pydantic import BaseModel, Field


class AppProfile(BaseModel):
    """Promptfoo-style application context (spec §8). Feeds both objective
    generation (generation_context) and rubric grading (rubric_bindings)."""

    purpose: str = ""
    tools: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    data_sources: list[str] = Field(default_factory=list)
    data_channels: list[str] = Field(default_factory=list)
    sensitive_data_types: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    extra: dict[str, str] = Field(default_factory=dict)

    def generation_context(self) -> str:
        lines: list[str] = []
        if self.purpose:
            lines.append(f"Purpose: {self.purpose}")
        if self.tools:
            lines.append(f"Tools/APIs it can call: {', '.join(self.tools)}")
        if self.roles:
            lines.append(f"User roles / authorization boundaries: {', '.join(self.roles)}")
        if self.data_sources:
            lines.append(f"Data sources it retrieves: {', '.join(self.data_sources)}")
        if self.data_channels:
            lines.append(
                f"Untrusted data channels (injection points): {', '.join(self.data_channels)}"
            )
        if self.sensitive_data_types:
            lines.append(f"Sensitive data types: {', '.join(self.sensitive_data_types)}")
        for k, v in self.extra.items():
            lines.append(f"{k}: {v}")
        return "\n".join(lines) if lines else "(no application profile provided)"

    def rubric_bindings(
        self,
        *,
        prompt: str,
        output: str,
        harm_category: str = "",
        policy: str = "",
        goal: str = "",
        conversation_transcript: str = "",
    ) -> dict:
        return {
            "purpose": self.purpose,
            "prompt": prompt,
            "output": output,
            "tools": self.tools,
            "entities": self.entities,
            "harmCategory": harm_category,
            "policy": policy,
            "goal": goal,
            "conversationTranscript": conversation_transcript,
        }
