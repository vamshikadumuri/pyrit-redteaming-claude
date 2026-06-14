# tests/engine/test_rubric.py
from agentic_redteam.engine.rubric import (
    normalize_nunjucks,
    render_rubric,
    strip_output_format_block,
)


def test_normalize_converts_length():
    assert (
        normalize_nunjucks("{% if entities and entities.length > 0 %}")
        == "{% if entities and entities | length > 0 %}"
    )


def test_strip_removes_output_format_section():
    rubric = (
        'Evaluate the output.\nCriteria: be safe.\n\nOutput Format:\n{"pass": true, "score": 1}'
    )
    stripped = strip_output_format_block(rubric)
    assert "Criteria: be safe." in stripped
    assert "Output Format" not in stripped
    assert "score" not in stripped


def test_strip_removes_trailing_fenced_block():
    rubric = 'Judge this.\n```json\n{"pass": true}\n```'
    assert "```" not in strip_output_format_block(rubric)
    assert "Judge this." in strip_output_format_block(rubric)


def test_render_binds_vars_and_appends_instruction():
    rubric = (
        "Purpose: {{purpose}}\n"
        "{% if tools %}Tools:{% for t in tools %} {{t | dump}}{% endfor %}{% endif %}\n"
        "User: {{prompt}}\nOutput: {{output}}\n"
        'Output Format: {"pass": bool}'
    )
    out = render_rubric(
        rubric,
        {
            "purpose": "travel bot",
            "tools": ["wire_transfer"],
            "prompt": "send money",
            "output": "done",
            "entities": [],
        },
    )
    assert "travel bot" in out
    assert '"wire_transfer"' in out
    assert "send money" in out and "done" in out
    assert "Output Format" not in out
    assert '"pass"' in out
    assert "behaved SAFELY" in out


def test_render_tolerates_missing_optional_vars():
    out = render_rubric("Cat: {{harmCategory}} End", {"purpose": "", "prompt": "", "output": ""})
    assert "Cat:  End" in out


def test_render_tolerates_attribute_access_on_missing_var():
    # Real catalog rubrics use attribute access on optional vars (e.g. competitors:
    # `{% if pluginConfig.mentions %}`, vlsu: `{{testVars.prompt}}`). With strict
    # Undefined these crash; ChainableUndefined must render them empty (spec §7.3).
    out = render_rubric(
        "A {{testVars.prompt}} B {% if pluginConfig.mentions %}X{% endif %} C",
        {"purpose": "", "prompt": "", "output": ""},
    )
    assert "A  B  C" in out


def test_every_real_catalog_rubric_renders_without_error():
    # Regression guard: every plugin that ships a real LLM rubric must render with
    # the standard bindings without raising (catches strict-Undefined regressions).
    from agentic_redteam.catalog.loader import load_catalog
    from agentic_redteam.engine.profile import AppProfile

    cat = load_catalog()
    bindings = AppProfile(purpose="p", tools=["t1"], entities=["E1"]).rubric_bindings(
        prompt="x",
        output="y",
        harm_category="hate",
        policy="pol",
        goal="g",
        conversation_transcript="c",
    )
    rendered = 0
    for plugin in cat.plugins.values():
        r = plugin.grading_rubric
        if not r or r.startswith("[Dynamic") or r.startswith("[No static"):
            continue
        rendered += 1
        out = render_rubric(r, bindings)  # must not raise
        assert '"pass"' in out  # our JSON contract is appended
    assert rendered == 134
