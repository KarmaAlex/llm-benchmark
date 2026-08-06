import time
from typing import cast

from llama_cpp import Llama
from openai.types.chat import ChatCompletion

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

    def generate(self, prompt: ChatPrompt) -> ModelResponse:

        start = time.perf_counter()

        response = self._generate(prompt)

        latency = time.perf_counter() - start

        usage = response.usage

        return ModelResponse(
            text=response.choices[0].message.content or "",
            latency=latency,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            finish_reason=response.choices[0].finish_reason,
            raw=response.model_dump(),
        )

    def _generate(self, prompt: ChatPrompt) -> ChatCompletion:
        response = cast(
            ChatCompletion,
            self.llm.create_chat_completion_openai_v1(
                messages=prompt.messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                stream=False,
            ),
        )

        return response