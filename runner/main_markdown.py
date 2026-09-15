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
args = parser.parse_args()

case = BenchmarkLoader.load(
    Path("markdown") / args.case
)

prompt = PromptLoader.load("markdown_v1")

config = ConfigLoader.load(args.config)

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
