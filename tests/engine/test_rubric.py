# tests/engine/test_rubric.py
from agentic_redteam.engine.rubric import (
    normalize_nunjucks, strip_output_format_block, render_rubric,
)


def test_normalize_converts_length():
    assert normalize_nunjucks("{% if entities and entities.length > 0 %}") == \
        "{% if entities and entities | length > 0 %}"


def test_strip_removes_output_format_section():
    rubric = ("Evaluate the output.\nCriteria: be safe.\n\n"
              "Output Format:\n{\"pass\": true, \"score\": 1}")
    stripped = strip_output_format_block(rubric)
    assert "Criteria: be safe." in stripped
    assert "Output Format" not in stripped
    assert "score" not in stripped


def test_strip_removes_trailing_fenced_block():
    rubric = "Judge this.\n```json\n{\"pass\": true}\n```"
    assert "```" not in strip_output_format_block(rubric)
    assert "Judge this." in strip_output_format_block(rubric)


def test_render_binds_vars_and_appends_instruction():
    rubric = ("Purpose: {{purpose}}\n"
              "{% if tools %}Tools:{% for t in tools %} {{t | dump}}{% endfor %}{% endif %}\n"
              "User: {{prompt}}\nOutput: {{output}}\n"
              "Output Format: {\"pass\": bool}")
    out = render_rubric(rubric, {"purpose": "travel bot", "tools": ["wire_transfer"],
                                 "prompt": "send money", "output": "done", "entities": []})
    assert "travel bot" in out
    assert '"wire_transfer"' in out
    assert "send money" in out and "done" in out
    assert "Output Format" not in out
    assert '"pass"' in out
    assert "behaved SAFELY" in out


def test_render_tolerates_missing_optional_vars():
    out = render_rubric("Cat: {{harmCategory}} End", {"purpose": "", "prompt": "", "output": ""})
    assert "Cat:  End" in out
