from agentic_redteam.config import ModelConfig


def test_resolve_api_key_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_CHAT_KEY", "sekret")
    mc = ModelConfig(endpoint="https://gw/v1", model_name="m1", api_key_env="OPENAI_CHAT_KEY")
    assert mc.resolve_api_key() == "sekret"


def test_resolve_api_key_defaults_to_none_when_no_env_name():
    mc = ModelConfig(endpoint="http://host:8001/v1", model_name="qwen")
    assert mc.resolve_api_key() == "none"  # local vLLM attacker pattern


def test_resolve_api_key_missing_env_raises(monkeypatch):
    monkeypatch.delenv("MISSING_KEY", raising=False)
    mc = ModelConfig(endpoint="https://gw/v1", model_name="m1", api_key_env="MISSING_KEY")
    try:
        mc.resolve_api_key()
        raise AssertionError("expected KeyError")
    except KeyError as e:
        assert "MISSING_KEY" in str(e)
