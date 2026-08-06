import os
import time

from openai import OpenAI

from runner.models.chat_prompt import ChatPrompt
from runner.models.model_config import ModelConfig
from runner.models.model_response import ModelResponse
from runner.providers.base import ModelProvider


class OpenAIProvider(ModelProvider):
    def __init__(self, config: ModelConfig):
        self.config = config

        self.client = OpenAI(
            api_key=os.environ["OPENAI_API_KEY"]
        )

    def generate(self, prompt: ChatPrompt) -> ModelResponse:
        start = time.perf_counter()

        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=prompt.messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

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