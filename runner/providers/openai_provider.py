import json
import os
import time

from openai import OpenAI

from runner.models.chat_prompt import ChatPrompt
from runner.models.model_config import ModelConfig
from runner.models.model_response import ModelResponse
from runner.providers.base import ModelProvider


class OpenAIProvider(ModelProvider):
    """
    Config contract for `provider: openai`.

    `parameters` holds settings for the client and for the shape of the
    request, none of which are valid request fields themselves:

        max_tokens_param     name of the output-budget field to send.
                             Reasoning models (gpt-5, o-series) reject
                             `max_tokens` and require
                             `max_completion_tokens`.
        supports_temperature set false for models that only accept the
                             default temperature, so it is omitted rather
                             than rejected.

    Any remaining key is forwarded to the OpenAI client constructor
    (`timeout`, `max_retries`, `base_url`, ...).

    `sampling` is forwarded verbatim as request fields, and is where
    model-specific knobs such as `reasoning_effort` and `verbosity` go.
    """

    REQUEST_SHAPING_KEYS = frozenset({
        "max_tokens_param",
        "supports_temperature",
    })

    def __init__(self, config: ModelConfig):
        self.config = config

        api_key = os.environ.get("OPENAI_API_KEY")

        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set, so the 'openai' provider config "
                f"'{config.name}' cannot run. Export a key first:\n"
                "    export OPENAI_API_KEY='sk-...'"
            )

        client_kwargs = {
            key: value
            for key, value in config.parameters.items()
            if key not in self.REQUEST_SHAPING_KEYS
        }

        self.client = OpenAI(api_key=api_key, **client_kwargs)

    def generate(self, prompt: ChatPrompt) -> ModelResponse:
        start = time.perf_counter()

        response = self.client.chat.completions.create(
            **self._request_kwargs(prompt)
        )

        latency = time.perf_counter() - start

        usage = response.usage
        message = response.choices[0].message

        return ModelResponse(
            content=message.content or "",
            latency=latency,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            finish_reason=response.choices[0].finish_reason,
            raw=response.model_dump(),
            tool_calls=self._extract_tool_calls(message),
            system_fingerprint=getattr(response, "system_fingerprint", None),
        )

    def _request_kwargs(self, prompt: ChatPrompt) -> dict:
        parameters = self.config.parameters

        token_param = parameters.get("max_tokens_param", "max_tokens")

        request_kwargs = {
            "model": self.config.model,
            "messages": prompt.messages,
            token_param: self.config.max_tokens,
            **self.config.sampling,
        }

        if parameters.get("supports_temperature", True):
            request_kwargs["temperature"] = self.config.temperature

        if prompt.tools:
            request_kwargs["tools"] = prompt.tools
            request_kwargs["tool_choice"] = "required"

        return request_kwargs

    @staticmethod
    def _extract_tool_calls(message) -> list[dict] | None:
        if not getattr(message, "tool_calls", None):
            return None

        calls = []
        for call in message.tool_calls:
            try:
                arguments = json.loads(call.function.arguments)
            except json.JSONDecodeError:
                arguments = {}
            calls.append({
                "name": call.function.name,
                "arguments": arguments,
            })
        return calls
