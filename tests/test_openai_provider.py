import inspect

import pytest
from openai.resources.chat.completions import Completions

from runner.models.chat_prompt import ChatPrompt
from runner.models.model_config import ModelConfig
from runner.providers.openai_provider import OpenAIProvider


SDK_REQUEST_FIELDS = set(inspect.signature(Completions.create).parameters) - {"self"}


def _make_config(**overrides) -> ModelConfig:
    defaults = dict(
        name="GPT-5 (test)",
        provider="openai",
        model="gpt-5",
        temperature=1,
        max_tokens=16384,
        context=400000,
        parameters={
            "max_tokens_param": "max_completion_tokens",
            "supports_temperature": False,
            "timeout": 600,
            "max_retries": 3,
        },
        sampling={"reasoning_effort": "high", "verbosity": "low"},
    )
    defaults.update(overrides)
    return ModelConfig(**defaults)


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")


def test_missing_api_key_raises_an_actionable_error(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAIProvider(_make_config())


def test_request_shaping_keys_are_not_passed_to_the_client(api_key):
    provider = OpenAIProvider(_make_config())

    # They would be unexpected kwargs for OpenAI(); reaching here proves it.
    assert provider.client.timeout == 600
    assert provider.client.max_retries == 3


def test_reasoning_model_request_uses_max_completion_tokens(api_key):
    provider = OpenAIProvider(_make_config())

    kwargs = provider._request_kwargs(ChatPrompt(version="test", messages=[]))

    assert kwargs["max_completion_tokens"] == 16384
    assert "max_tokens" not in kwargs
    assert "temperature" not in kwargs
    assert kwargs["reasoning_effort"] == "high"
    assert kwargs["verbosity"] == "low"


def test_request_only_uses_fields_the_sdk_accepts(api_key):
    provider = OpenAIProvider(_make_config())

    kwargs = provider._request_kwargs(ChatPrompt(version="test", messages=[]))

    assert set(kwargs) <= SDK_REQUEST_FIELDS


def test_temperature_is_sent_when_the_model_supports_it(api_key):
    config = _make_config(
        temperature=0,
        parameters={"supports_temperature": True},
    )

    kwargs = OpenAIProvider(config)._request_kwargs(ChatPrompt(version="test", messages=[]))

    assert kwargs["temperature"] == 0
    assert kwargs["max_tokens"] == 16384
