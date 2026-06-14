# agentic_redteam/catalog/grouping.py
"""Derive a UI category group for a promptfoo plugin id (spec §5.1)."""

from __future__ import annotations

_DATASETS = {
    "aegis",
    "beavertails",
    "cyberseceval",
    "donotanswer",
    "harmbench",
    "pliny",
    "toxic-chat",
    "unsafebench",
    "vlguard",
    "vlsu",
    "xstest",
}
_DOMAIN_PREFIXES = (
    "financial",
    "medical",
    "pharmacy",
    "insurance",
    "realestate",
    "telecom",
    "ecommerce",
    "teen-safety",
)
_PRIVACY_IDS = {"cross-session-leak", "data-exfil", "rag-document-exfiltration"}
_AGENTIC_IDS = {"rag-poisoning", "rag-source-attribution"}
_SECURITY_IDS = {
    "bola",
    "bfla",
    "rbac",
    "excessive-agency",
    "hijacking",
    "prompt-extraction",
    "indirect-prompt-injection",
    "cca",
    "system-prompt-override",
    "tool-discovery",
    "debug-access",
    "shell-injection",
    "sql-injection",
    "ssrf",
    "special-token-injection",
    "ascii-smuggling",
    "mcp",
}
_TRUST_IDS = {
    "hallucination",
    "overreliance",
    "imitation",
    "competitors",
    "politics",
    "religion",
    "contracts",
    "unverifiable-claims",
    "divergent-repetition",
    "reasoning-dos",
    "off-topic",
    "goal-misalignment",
    "model-identification",
    "wordplay",
}


def category_group(plugin_id: str) -> str:
    pid = plugin_id
    family = pid.split(":", 1)[0]

    if pid in _DATASETS:
        return "Datasets"
    if pid in ("intent", "policy"):
        return "Config-required"
    if family in _DOMAIN_PREFIXES or pid in ("coppa", "ferpa"):
        return "Domain Packs"
    if family == "bias":
        return "Bias & Fairness"
    if pid == "harmful:privacy":
        return "Privacy & PII"
    if family == "harmful":
        return "Harmful Content"
    if family == "pii" or pid in _PRIVACY_IDS:
        return "Privacy & PII"
    if family in ("coding-agent", "agentic") or pid in _AGENTIC_IDS:
        return "Agentic & RAG"
    if pid in _SECURITY_IDS:
        return "Security & Access Control"
    if pid in _TRUST_IDS:
        return "Trust, Reliability & Brand"
    return "Other"
