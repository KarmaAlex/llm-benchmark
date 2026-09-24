from pathlib import Path

from runner.filesystem.benchmark_loader import BenchmarkLoader
from runner.filesystem.config_loader import ConfigLoader
from runner.filesystem.prompt_loader import PromptLoader
from runner.core.prompt_builder import PromptBuilder
from runner.providers.factory import ProviderFactory

case = BenchmarkLoader.load(
    Path("markdown/md001")
)

prompt = PromptLoader.load("markdown_v1")

config = ConfigLoader.load("llama-3.1-8B-instruct-q6")

builder = PromptBuilder()

chat_prompt = builder.build(
    prompt,
    case,
)

Path("prompt.txt").write_text(
    chat_prompt.messages[1]["content"],
    encoding="utf-8",
)

provider = ProviderFactory.create(config)

response = provider.generate(chat_prompt)

print(response.content)

metrics = {
    "latency": response.latency,
    "prompt_tokens": response.prompt_tokens,
    "completion_tokens": response.completion_tokens,
    "finish_reason": response.finish_reason,
}

print(metrics)