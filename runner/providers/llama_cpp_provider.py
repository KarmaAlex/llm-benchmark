import json
import time
import weakref
from typing import cast

from llama_cpp import Llama
from openai.types.chat import ChatCompletion

from runner.providers.gpu_memory import get_gpu_memory_used_mb, other_gpu_processes
from runner.providers.power import PowerSampler
from runner.models.chat_prompt import ChatPrompt
from runner.models.model_config import ModelConfig
from runner.models.model_response import ModelResponse
from runner.providers.base import ModelProvider


class LlamaCppProvider(ModelProvider):
    def __init__(self, config: ModelConfig):
        self.config = config

        self.llm = Llama(
            model_path=config.model,
            n_ctx=config.context,
            **config.parameters,
        )

        # Sampled for as long as the model is loaded; stopped when this
        # provider is garbage-collected (run_all_reproducibility releases one
        # suite's provider before loading the next).
        self.power = PowerSampler()
        weakref.finalize(self, self.power.close)

    def generate(self, prompt: ChatPrompt) -> ModelResponse:

        if prompt.tools and not self.config.supports_tools:
            raise ValueError(
                f"Model config '{self.config.name}' does not have "
                "supports_tools enabled, but the prompt requires tool "
                "calling. Either set supports_tools: true in the config "
                "(only if this GGUF's chat template supports it) or use "
                "the text-mode structured-edit prompt instead."
            )

        self.power.wait_for_samples(timeout=5)
        window_start = time.monotonic()
        start = time.perf_counter()

        response = self._generate(prompt)

        latency = time.perf_counter() - start
        power = self.power.reading(window_start, time.monotonic())
        gpu_memory_mb = get_gpu_memory_used_mb()
        gpu_other_processes = other_gpu_processes()

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
            gpu_memory_mb=gpu_memory_mb,
            gpu_power_w=power.gpu_power_w,
            gpu_power_peak_w=power.gpu_power_peak_w,
            cpu_power_w=power.cpu_power_w,
            cpu_power_peak_w=power.cpu_power_peak_w,
            energy_wh=power.energy_wh,
            gpu_other_processes=gpu_other_processes,
        )

    def _generate(self, prompt: ChatPrompt) -> ChatCompletion:
        request_kwargs = dict(
            messages=prompt.messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            stream=False,
            **self.config.sampling,
        )

        # Pass the seed on every request: without one, llama-cpp-python
        # derives the next call's seed from the previous one, so a case's
        # output would depend on how many requests ran before it.
        seed = self.config.parameters.get("seed")
        if seed is not None:
            request_kwargs["seed"] = seed

        if prompt.tools and self.config.supports_tools:
            request_kwargs["tools"] = prompt.tools
            request_kwargs["tool_choice"] = "required"

        response = cast(
            ChatCompletion,
            self.llm.create_chat_completion_openai_v1(**request_kwargs),
        )

        return response

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
