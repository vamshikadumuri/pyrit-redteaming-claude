# agentic_redteam/catalog/models.py
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class PluginType(str, Enum):
    generative = "generative"
    dataset = "dataset"
    config_required = "config_required"


class ObjectiveSource(str, Enum):
    generate_locally = "generate_locally"
    dataset_rows = "dataset_rows"
    intent_passthrough = "intent_passthrough"


class Severity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class StrategyType(str, Enum):
    encoding = "encoding"
    single_turn = "single_turn"
    multi_turn = "multi_turn"
    multimodal = "multimodal"
    utility = "utility"


class StrategyKind(str, Enum):
    attack = "attack"
    converter = "converter"
    meta = "meta"
    utility = "utility"


class Fidelity(str, Enum):
    clean = "clean"
    approximate = "approximate"
    custom_needed = "custom_needed"
    meta = "meta"
    na = "na"


class RubricKind(str, Enum):
    llm_rubric = "llm_rubric"
    shared_grader = "shared_grader"
    dynamic = "dynamic"
    dataset = "dataset"
    heuristic = "heuristic"


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


class Strategy(BaseModel):
    id: str
    display_name: str
    type: StrategyType
    kind: StrategyKind
    offline: bool
    pyrit_class: str | None = None
    converter_chain: list[str] = Field(default_factory=list)
    pyrit_equivalent: str = ""
    fidelity: Fidelity
    is_default: bool = False
    needs: list[str] = Field(default_factory=list)
    params: dict = Field(default_factory=dict)
    description: str = ""


class Preset(BaseModel):
    id: str
    framework: str
    title: str
    plugins: list[str]
    recommended_strategies: list[str] = Field(default_factory=list)
    category_index: dict[str, list[str]] = Field(default_factory=dict)
