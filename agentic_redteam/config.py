"""Target/attacker/judge model config (spec §9, §16). Pure: holds connection
details and resolves the API key from the environment at run time. The adapter
(engine/adapter.py) turns a ModelConfig into an OpenAIChatTarget."""

from __future__ import annotations

import os

from pydantic import BaseModel


class ModelConfig(BaseModel):
    endpoint: str
    model_name: str
    api_key_env: str = ""  # name of the env var holding the key; "" -> "none"
    temperature: float | None = None

    def resolve_api_key(self) -> str:
        if not self.api_key_env:
            return "none"  # local vLLM / keyless gateway (crescendo.py attacker)
        try:
            return os.environ[self.api_key_env]
        except KeyError:
            raise KeyError(f"API key env var '{self.api_key_env}' is not set") from None
