# agentic_redteam/ingest/ingest_catalog.py
"""Transform promptfoo_plugins_catalog_1.xlsx -> catalog/data/{plugins,strategies,presets}.json.

Parsing rules are derived from the actual cell formats in the v0.121.13 catalog.
Run once; the JSON is committed and read by catalog.loader at runtime."""

from __future__ import annotations

import json
from pathlib import Path

from agentic_redteam.catalog.grouping import category_group
from agentic_redteam.ingest.xlsx_reader import read_sheet

# -- plugin parsing -----------------------------------------------------------
_PTYPE = {"generative": "generative", "dataset": "dataset", "config-required": "config_required"}
_STRATEGY_EXEMPT_IDS = {"system-prompt-override", "agentic:memory-poisoning"}


def _ptype(cell: str) -> str:
    return _PTYPE[cell.strip().lower()]


def _obj_source(cell: str) -> str:
    c = cell.strip().lower()
    if c.startswith("dataset-rows"):
        return "dataset_rows"
    if c.startswith("intent-passthrough"):
        return "intent_passthrough"
    return "generate_locally"


def _codes(cell: str, atlas: bool = False) -> list[str]:
    cell = (cell or "").strip()
    if not cell or cell == "—":  # em dash = "not mapped"
        return []
    out = []
    for part in (p.strip() for p in cell.split(",")):
        if not part:
            continue
        if atlas:
            out.append(part.split(":", 1)[1].strip() if ":" in part else part)
        else:
            out.append(part.split(":", 1)[0].strip())
    return out


def _rubric_kind(plugin_id: str, rubric: str) -> str:
    r = (rubric or "").strip()
    if r.startswith("[Dynamic"):
        return "dynamic"
    if r.startswith("[No static") or not r:
        return "heuristic"
    family = plugin_id.split(":", 1)[0]
    if family in ("bias", "pii") or family == "harmful":
        return "shared_grader"
    return "llm_rubric"


def build_plugins(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        pid = r["Plugin ID"].strip()
        ptype = _ptype(r["Plugin Type"])
        rubric = r.get("Grading Rubric / Notes", "")
        is_dataset = ptype == "dataset"
        out.append(
            {
                "id": pid,
                "name": r.get("Name", "").strip() or pid,
                "severity": r["Severity"].strip().lower(),
                "plugin_type": ptype,
                "objective_source": _obj_source(r["Objective Source"]),
                "category_group": category_group(pid),
                "framework_refs": {
                    "owasp_llm": _codes(r.get("OWASP LLM Top 10", "")),
                    "owasp_agentic": _codes(r.get("OWASP Agentic Top 10", "")),
                    "owasp_api": _codes(r.get("OWASP API Top 10", "")),
                    "atlas": _codes(r.get("MITRE ATLAS", ""), atlas=True),
                },
                "risk_description": r.get("Objective (description)", "").strip(),
                "generation_hint": r.get(
                    "Imperative Objective Seed / Attacker-Goal Hint (draft)", ""
                ).strip(),
                "grading_rubric": rubric.strip(),
                "rubric_kind": _rubric_kind(pid, rubric),
                "seed_dataset": pid if is_dataset else None,
                "strategy_exempt": is_dataset or pid in _STRATEGY_EXEMPT_IDS,
                "runnable": not is_dataset,
                "runnable_reason": f"dataset '{pid}' not mirrored" if is_dataset else "",
            }
        )
    return out


# -- strategy parsing ---------------------------------------------------------
def _stype(cell: str) -> str:
    c = cell.strip().lower()
    if c.startswith("encoding"):
        return "encoding"
    if c.startswith("single-turn"):
        return "single_turn"
    if c.startswith("multi-turn"):
        return "multi_turn"
    if c.startswith("multimodal"):
        return "multimodal"
    return "utility"


def _fidelity(cell: str) -> str:
    c = cell.strip().lower()
    for prefix, val in (
        ("clean", "clean"),
        ("approximate", "approximate"),
        ("custom", "custom_needed"),
        ("meta", "meta"),
        ("n/a", "na"),
    ):
        if c.startswith(prefix):
            return val
    return "approximate"


def _kind(sid: str, stype: str, fidelity: str) -> str:
    if sid == "retry":
        return "utility"
    if stype == "encoding":
        return "converter"
    if fidelity == "meta":
        return "meta"
    return "attack"


def build_strategies(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        sid = r["Promptfoo Strategy ID"].strip()
        stype = _stype(r["Type"])
        fid = _fidelity(r["PyRIT Fidelity (how clean?)"])
        out.append(
            {
                "id": sid,
                "display_name": r.get("Display Name", "").strip() or sid,
                "type": stype,
                "kind": _kind(sid, stype, fid),
                "offline": r["Air-gap (offline?)"].strip().lower().startswith("runs locally"),
                "pyrit_class": None,
                "converter_chain": [],
                "pyrit_equivalent": r.get("PyRIT 0.13.0 Equivalent", "").strip(),
                "fidelity": fid,
                "is_default": r.get("DEFAULT?", "").strip().lower() == "yes",
                "needs": [],
                "params": {},
                "description": r.get("Description (Promptfoo)", "").strip(),
            }
        )
    return out


# -- preset aggregation (framework-level) -------------------------------------
_FRAMEWORK_PRESET = {
    "owasp llm top 10": ("owasp_llm", "OWASP LLM Top 10"),
    "owasp api top 10": ("owasp_api", "OWASP API Top 10"),
    "owasp agentic": ("owasp_agentic", "OWASP Agentic Top 10"),
    "mitre atlas": ("mitre_atlas", "MITRE ATLAS"),
    "nist ai rmf": ("nist_ai_rmf", "NIST AI RMF"),
    "eu ai act": ("eu_ai_act", "EU AI Act"),
}
_DEFAULT_STRATEGIES = ["basic", "jailbreak:meta", "jailbreak:composite"]
_PARENT_PREFIXES = {"harmful", "pii", "bias"}


def _split_list(cell: str) -> list[str]:
    cell = (cell or "").strip()
    if not cell or cell == "—" or cell.lower().startswith("(none"):
        return []
    return [x.strip() for x in cell.split(",") if x.strip()]


def _expand_plugins(entries: list[str], all_ids: set[str]) -> list[str]:
    out = []
    for e in entries:
        if e in all_ids:
            out.append(e)
        elif e in _PARENT_PREFIXES:
            out.extend(sorted(i for i in all_ids if i.split(":", 1)[0] == e))
    return out


def _dedup(seq):
    seen, out = set(), []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def build_presets(
    rows: list[dict], all_plugin_ids: set[str], all_strategy_ids: set[str]
) -> list[dict]:
    acc: dict[str, dict] = {}

    def ensure(pid, framework, title):
        if pid not in acc:
            acc[pid] = {
                "id": pid,
                "framework": framework,
                "title": title,
                "plugins": [],
                "recommended_strategies": [],
                "category_index": {},
            }
        return acc[pid]

    for r in rows:
        framework = r["Framework"].strip()
        cat_id = r["Category ID"].strip()
        fl = framework.lower()
        if fl in _FRAMEWORK_PRESET:
            preset_id, title = _FRAMEWORK_PRESET[fl]
        elif fl == "collection":
            preset_id, title = cat_id, r["Category / Name"].strip()
        else:
            continue

        a = ensure(preset_id, framework, title)
        cat_plugins = _expand_plugins(
            _split_list(r["Plugins (as Promptfoo defines)"]), all_plugin_ids
        )
        strategies = _split_list(r["Promptfoo Recommended Strategies"]) or list(_DEFAULT_STRATEGIES)
        strategies = [s for s in strategies if s in all_strategy_ids]

        a["plugins"].extend(cat_plugins)
        a["recommended_strategies"].extend(strategies)
        if cat_id:
            a["category_index"][cat_id] = cat_plugins

    out = []
    for a in acc.values():
        a["plugins"] = _dedup(a["plugins"])
        a["recommended_strategies"] = _dedup(a["recommended_strategies"])
        out.append(a)
    return out


def write_catalog(xlsx_path, out_dir) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    plugins = build_plugins(read_sheet(xlsx_path, "Plugins"))
    strategies = build_strategies(read_sheet(xlsx_path, "Strategy Map"))
    presets = build_presets(
        read_sheet(xlsx_path, "Presets"),
        {p["id"] for p in plugins},
        {s["id"] for s in strategies},
    )

    for name, data in (("plugins", plugins), ("strategies", strategies), ("presets", presets)):
        (out_dir / f"{name}.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )


if __name__ == "__main__":
    here = Path(__file__).resolve().parents[1]  # agentic_redteam/
    root = here.parent
    write_catalog(root / "promptfoo_plugins_catalog_enriched.xlsx", here / "catalog" / "data")
    print("catalog written to agentic_redteam/catalog/data/")
