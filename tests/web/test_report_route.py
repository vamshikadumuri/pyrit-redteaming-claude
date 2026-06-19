"""Tests that the report route passes run_config to the template."""

from agentic_redteam.config import ModelConfig
from agentic_redteam.engine.plan import RunConfig
from agentic_redteam.engine.profile import AppProfile
from agentic_redteam.records import RunRequest


def _make_request_json() -> str:
    req = RunRequest(
        config=RunConfig(
            run_id="run_test01",
            plugin_ids=["pi_jailbreak"],
            strategy_ids=["basic"],
            profile=AppProfile(),
            n=3,
            policy_text="",
        ),
        target=ModelConfig(endpoint="http://target:8000", model_name="gpt-4"),
        judge=ModelConfig(endpoint="http://judge:8000", model_name="gpt-4"),
        adversarial=ModelConfig(endpoint="http://attacker:8001", model_name="llama3"),
        concurrency=2,
        requested_by="tester",
    )
    return req.model_dump_json()


def test_run_config_extracted_from_request_json():
    """_extract_run_config should parse request_json into a display dict."""
    from agentic_redteam.web.routes.runs import _extract_run_config

    cfg = _extract_run_config(_make_request_json())
    assert cfg is not None
    assert cfg["target_endpoint"] == "http://target:8000"
    assert cfg["target_model"] == "gpt-4"
    assert cfg["adversarial_endpoint"] == "http://attacker:8001"
    assert cfg["adversarial_model"] == "llama3"
    assert cfg["judge_endpoint"] == "http://judge:8000"
    assert cfg["judge_model"] == "gpt-4"
    assert cfg["plugin_ids"] == ["pi_jailbreak"]
    assert cfg["strategy_ids"] == ["basic"]
    assert cfg["n"] == 3
    assert cfg["concurrency"] == 2
    assert cfg["requested_by"] == "tester"
    assert cfg["policy_text"] == ""


def test_run_config_returns_none_for_missing_json():
    from agentic_redteam.web.routes.runs import _extract_run_config

    assert _extract_run_config(None) is None
    assert _extract_run_config("") is None
