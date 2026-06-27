# agentic_redteam/catalog/models.py
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class PluginType(StrEnum):
    generative = "generative"
    dataset = "dataset"
    config_required = "config_required"


class ObjectiveSource(StrEnum):
    generate_locally = "generate_locally"
    dataset_rows = "dataset_rows"
    intent_passthrough = "intent_passthrough"


class Severity(StrEnum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class RubricKind(StrEnum):
    llm_rubric = "llm_rubric"
    shared_grader = "shared_grader"
    dynamic = "dynamic"
    dataset = "dataset"
    heuristic = "heuristic"


class TurnType(StrEnum):
    single_turn = "single_turn"
    multi_turn = "multi_turn"
    meta = "meta"


class Requirement(StrEnum):
    offline = "offline"
    llm_target = "llm_target"
    multimodal = "multimodal"
    audio = "audio"
    file = "file"
    azure_service = "azure_service"


class ConverterCategory(StrEnum):
    encoding = "encoding"
    text_transform = "text_transform"
    smuggling = "smuggling"
    llm_rewrite = "llm_rewrite"
    multimodal = "multimodal"
    audio = "audio"
    file = "file"
    azure = "azure"


class FrameworkRefs(BaseModel):
    owasp_llm: list[str] = Field(default_factory=list)
    owasp_agentic: list[str] = Field(default_factory=list)
    owasp_api: list[str] = Field(default_factory=list)
    atlas: list[str] = Field(default_factory=list)


class Plugin(BaseModel):
    id: str
    name: str
    severity: Severity
    plugin_type: PluginType
    objective_source: ObjectiveSource
    category_group: str
    framework_refs: FrameworkRefs = Field(default_factory=FrameworkRefs)
    risk_description: str = ""
    generation_hint: str = ""
    grading_rubric: str = ""
    rubric_kind: RubricKind
    seed_dataset: str | None = None
    strategy_exempt: bool = False
    runnable: bool = True
    runnable_reason: str = ""


class PyritAttack(BaseModel):
    class_name: str
    display_name: str
    turn_type: TurnType
    needs: list[str] = Field(default_factory=list)
    params: dict = Field(default_factory=dict)
    objective_scorer_kind: str = "true_false"  # "true_false" | "float_scale" (TAP/PAIR)
    runnable: bool = True
    runnable_reason: str = ""


class PyritConverter(BaseModel):
    class_name: str
    display_name: str
    category: ConverterCategory
    requirement: Requirement
    runnable: bool = True
    runnable_reason: str = ""


class Preset(BaseModel):
    id: str
    framework: str
    title: str
    plugins: list[str]
