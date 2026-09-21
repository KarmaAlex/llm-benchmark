import argparse
from pathlib import Path

from runner.markdown_tests.json_comparator import JsonComparator
from runner.markdown_tests.json_extractor import JsonExtractionError, JsonExtractor
from runner.filesystem.benchmark_loader import BenchmarkLoader
from runner.filesystem.config_loader import ConfigLoader
from runner.filesystem.prompt_loader import PromptLoader
from runner.models.markdown_result import MarkdownResult
from runner.prompt_builder import PromptBuilder
from runner.providers.factory import ProviderFactory
from runner.stats import tokens_per_second


parser = argparse.ArgumentParser(
    description="Run a single markdown-extraction benchmark case against a model."
)
parser.add_argument(
    "case",
    nargs="?",
    default="md001",
    help="Case id under benchmark/markdown/ to run (default: md001).",
)
parser.add_argument(
    "--config",
    default="llama-3.1-8B-instruct-q6",
    help="Model config name under configs/ to use (default: llama-3.1-8B-instruct-q6).",
)
parser.add_argument(
    "--device",
    choices=["cuda", "cpu"],
    default="cuda",
    help="Run local (llama.cpp) models on the GPU (default) or force CPU-only.",
)
args = parser.parse_args()

case = BenchmarkLoader.load(
    Path("markdown") / args.case
)

prompt = PromptLoader.load("markdown_v1")

config = ConfigLoader.load(args.config)
config = ConfigLoader.apply_device(config, args.device)

chat_prompt = PromptBuilder.build(
    prompt,
    case,
)

print(f"Prompt:\n{chat_prompt}\n\n")

provider = ProviderFactory.create(config)

response = provider.generate(
    chat_prompt
)

print(f"Response:\n{response.content}")

print(
    f"Tokens: {response.prompt_tokens} prompt + {response.completion_tokens} "
    f"completion = {response.prompt_tokens + response.completion_tokens} total "
    f"(finish_reason={response.finish_reason})"
)
print(
    f"Latency: {response.latency:.2f}s "
    f"({tokens_per_second(response.completion_tokens, response.latency):.1f} tok/s)"
)

result = MarkdownResult(
    prompt=str(chat_prompt),
    raw_response=response.raw,
    response_text=response.content,
    expected_output=case.resources["expected"],
    execution_time=response.latency,
    input_tokens=response.prompt_tokens,
    output_tokens=response.completion_tokens,
)

try:
    result.parsed_output = JsonExtractor.extract(response.content)
except JsonExtractionError as e:
    result.parse_error = str(e)
    print(f"Failed to parse model response as JSON: {result.parse_error}")
    raise SystemExit(1)

comparison = JsonComparator.compare(
    result.parsed_output,
    result.expected_output,
)

result.matched = comparison.matched

print(comparison.message)

print(f"Matched: {result.matched}")

print(
    f"Execution time: "
    f"{result.execution_time:.2f}s"
)

if not result.matched:
    raise SystemExit(1)
