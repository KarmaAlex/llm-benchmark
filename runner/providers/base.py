from abc import ABC, abstractmethod

from runner.models.chat_prompt import ChatPrompt
from runner.models.model_response import ModelResponse


class ModelProvider(ABC):
    @abstractmethod
    def generate(
        self,
        prompt: ChatPrompt,
    ) -> ModelResponse:
        ...