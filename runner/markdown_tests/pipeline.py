"""
Markdown-extraction case pipeline shared by the single-case runner
(main_markdown.py) and the batch runner (run_all_markdown.py): load a case,
build its prompt, and grade the model's JSON answer against the expected one.
"""

from pathlib import Path

from runner.core.prompt_builder import PromptBuilder
from runner.core.stats import response_token_stats
from runner.filesystem.benchmark_loader import BenchmarkLoader
from runner.filesystem.prompt_loader import PromptLoader
from runner.markdown_tests.json_comparator import JsonComparator
from runner.markdown_tests.json_extractor import JsonExtractionError, JsonExtractor
from runner.models.benchmark import BenchmarkCase
from runner.models.chat_prompt import ChatPrompt
from runner.models.markdown_case_result import MarkdownCaseResult
from runner.models.model_response import ModelResponse
from runner.models.prompt import Prompt
from runner.providers.base import ModelProvider

SUITE = "markdown"
PROMPT_NAME = "markdown_v1"


def load_case(case_id: str) -> BenchmarkCase:
    return BenchmarkLoader.load(Path(SUITE) / case_id)


def load_prompt() -> Prompt:
    return PromptLoader.load(PROMPT_NAME)


def discover_cases() -> list[str]:
    return BenchmarkLoader.discover(SUITE)


def evaluate_response(case: BenchmarkCase, response: ModelResponse) -> MarkdownCaseResult:
    """Parse the model's answer as JSON and compare it to the case's expected output."""
    result = MarkdownCaseResult(
        case_id=case.id,
        difficulty=case.metadata.get("difficulty"),
        matched=False,
        execution_time=response.latency,
        response_text=response.content,
        **response_token_stats(response),
    )

    try:
        result.parsed_output = JsonExtractor.extract(response.content)
    except JsonExtractionError as e:
        result.error = str(e)
        return result

    comparison = JsonComparator.compare(result.parsed_output, case.resources["expected"])
    result.matched = comparison.matched
    result.error = None if comparison.matched else comparison.message
    return result


def build_chat_prompt(prompt: Prompt, case: BenchmarkCase) -> ChatPrompt:
    return PromptBuilder.build(prompt, case)


def run_case(case_id: str, provider: ModelProvider, prompt: Prompt) -> MarkdownCaseResult:
    case = load_case(case_id)
    response = provider.generate(build_chat_prompt(prompt, case))
    return evaluate_response(case, response)


def failed_result(case_id: str, error: str) -> MarkdownCaseResult:
    return MarkdownCaseResult(
        case_id=case_id,
        difficulty=None,
        matched=False,
        execution_time=0.0,
        error=error,
    )
