from runner.providers.llama_cpp_provider import LlamaCppProvider
from runner.providers.openai_provider import OpenAIProvider


class ProviderFactory:

    @staticmethod
    def create(config):

        if config.provider == "llama.cpp":
            return LlamaCppProvider(config)

        if config.provider == "openai":
            return OpenAIProvider(config)

        raise ValueError(
            f"Unknown provider: {config.provider}"
        )