"""Strategy id -> StrategySpec: the curated, PyRIT-free authority that names the
PyRIT class(es) the adapter builds (spec §5.3, §10). Returns *name strings* only;
adapter.py maps names -> real classes. Honors fidelity + plugin strategy-exemption
(spec §4 input-routing rule). `basic` is the always-on direct-send baseline."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agentic_redteam.catalog.models import Fidelity, Plugin, Strategy

_ATTACK_NEEDS = ["adversarial_chat", "objective_scorer"]


class StrategySpec(BaseModel):
    strategy_id: str
    mechanism: str  # "send" | "converter" | "multi_turn" | "unsupported"
    attack_class: str | None = None  # PyRIT attack class name (send/converter/multi_turn)
    converter_classes: list[str] = Field(default_factory=list)
    needs: list[str] = Field(default_factory=list)  # e.g. adversarial_chat, objective_scorer
    params: dict = Field(default_factory=dict)
    fidelity: Fidelity = Fidelity.na
    supported: bool = False
    note: str = ""


# Curated map. Only entries we can build in this POC with verified class names are
# supported=True; everything else falls through to an unsupported spec with a note.
# kind: "send" plain; "conv" converter-on-PromptSendingAttack; "mt" multi-turn attack.
_MAP: dict[str, dict] = {
    "basic": {"kind": "send"},
    # ---- clean drop-in converters (spec §5.3) ----
    "base64": {"kind": "conv", "conv": ["Base64Converter"]},
    "rot13": {"kind": "conv", "conv": ["ROT13Converter"]},
    "leetspeak": {"kind": "conv", "conv": ["LeetspeakConverter"]},
    "homoglyph": {"kind": "conv", "conv": ["UnicodeConfusableConverter"]},
    "emoji": {"kind": "conv", "conv": ["EmojiConverter"]},
    "morse": {"kind": "conv", "conv": ["MorseConverter"]},
    "math-prompt": {"kind": "conv", "conv": ["MathPromptConverter"]},
    "hex": {"kind": "conv", "conv": ["BinAsciiConverter"]},
    "multilingual": {"kind": "conv", "conv": ["TranslationConverter"], "needs": ["language"]},
    "jailbreak-templates": {"kind": "conv", "conv": ["TextJailbreakConverter"]},
    # ---- multi-turn attacks ----
    "crescendo": {
        "kind": "mt",
        "attack": "CrescendoAttack",
        "params": {"max_turns": 10, "max_backtracks": 5},
    },
    "jailbreak:tree": {"kind": "mt", "attack": "TreeOfAttacksWithPruningAttack"},
    "mischievous-user": {"kind": "mt", "attack": "RolePlayAttack"},
    # ---- RedTeamingAttack family (approximate; reproduced via local attacker) ----
    "goat": {"kind": "mt", "attack": "RedTeamingAttack"},
    "jailbreak:hydra": {"kind": "mt", "attack": "RedTeamingAttack"},
    "jailbreak:likert": {"kind": "mt", "attack": "RedTeamingAttack"},
    "jailbreak:meta": {"kind": "mt", "attack": "RedTeamingAttack"},
    "jailbreak": {"kind": "mt", "attack": "RedTeamingAttack"},
    "jailbreak:composite": {"kind": "mt", "attack": "RedTeamingAttack"},
}


def resolve_strategy(strategy: Strategy) -> StrategySpec:
    m = _MAP.get(strategy.id)
    if m is None:
        return StrategySpec(
            strategy_id=strategy.id,
            mechanism="unsupported",
            fidelity=strategy.fidelity,
            supported=False,
            note=f"'{strategy.id}' ({strategy.fidelity.value}) is not buildable in this POC "
            f"({strategy.pyrit_equivalent or 'no stock PyRIT equivalent'}).",
        )
    kind = m["kind"]
    if kind == "send":
        return StrategySpec(
            strategy_id=strategy.id,
            mechanism="send",
            attack_class="PromptSendingAttack",
            fidelity=strategy.fidelity,
            supported=True,
        )
    if kind == "conv":
        return StrategySpec(
            strategy_id=strategy.id,
            mechanism="converter",
            attack_class="PromptSendingAttack",
            converter_classes=m["conv"],
            needs=m.get("needs", []),
            fidelity=strategy.fidelity,
            supported=True,
        )
    # kind == "mt"
    return StrategySpec(
        strategy_id=strategy.id,
        mechanism="multi_turn",
        attack_class=m["attack"],
        needs=list(_ATTACK_NEEDS),
        params=dict(m.get("params", {})),
        fidelity=strategy.fidelity,
        supported=True,
    )


def combo_supported(plugin: Plugin, spec: StrategySpec) -> bool:
    """A (plugin, strategy) pair is runnable iff the strategy is supported AND
    (the plugin is not strategy-exempt OR the strategy is the direct-send `basic`)."""
    if not spec.supported:
        return False
    return not (plugin.strategy_exempt and spec.strategy_id != "basic")
