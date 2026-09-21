import argparse
import shutil
from dataclasses import replace
from pathlib import Path

from runner.sonar_tests.compiler import Compiler
from runner.sonar_tests.edit_pipeline import PROMPT_NAME_BY_EDIT_MODE, apply_model_response
from runner.sonar_tests.test_runner import TestRunner
from runner.sonar_tests.workspace import Workspace
from runner.stats import tokens_per_second
from runner.structured_edit import EDIT_FILE_TOOL_SCHEMA
from runner.filesystem.benchmark_loader import BenchmarkLoader
from runner.filesystem.config_loader import ConfigLoader
from runner.filesystem.prompt_loader import PromptLoader
from runner.prompt_builder import PromptBuilder
from runner.providers.factory import ProviderFactory


parser = argparse.ArgumentParser(
    description="Run a single sonar issue-resolution benchmark case against a model."
)
parser.add_argument(
    "case",
    nargs="?",
    default="S1643",
    help="Case id under benchmark/sonar/ to run (default: S1643).",
)
parser.add_argument(
    "--config",
    default="qwen2.5-coder-7b-q4",
    help="Model config name under configs/ to use (default: qwen2.5-coder-7b-q4).",
)
parser.add_argument(
    "--edit-mode",
    choices=["diff", "structured", "toolcall"],
    default="diff",
    help=(
        "How the model expresses its fix: 'diff' (default, unchanged unified-diff "
        "behavior), 'structured' (line-number-free JSON edit list parsed from text), "
        "or 'toolcall' (native tool/function calling, requires supports_tools in the "
        "model config)."
    ),
)
parser.add_argument(
    "--device",
    choices=["cuda", "cpu"],
    default="cuda",
    help="Run local (llama.cpp) models on the GPU (default) or force CPU-only.",
)
args = parser.parse_args()

case = BenchmarkLoader.load(
    Path("sonar") / args.case
)

config = ConfigLoader.load(args.config)
config = ConfigLoader.apply_device(config, args.device)

if args.edit_mode == "toolcall" and not config.supports_tools:
    print(
        f"Model config '{config.name}' does not have supports_tools "
        "enabled. Use --edit-mode structured for this model instead."
    )
    raise SystemExit(1)

prompt = PromptLoader.load(PROMPT_NAME_BY_EDIT_MODE[args.edit_mode])

chat_prompt = PromptBuilder.build(
    prompt,
    case,
)

if args.edit_mode == "toolcall":
    chat_prompt = replace(chat_prompt, tools=[EDIT_FILE_TOOL_SCHEMA])

print(f"Prompt:\n{chat_prompt}\n\n")

provider = ProviderFactory.create(config)

response = provider.generate(
    chat_prompt
)

print(
    f"Tokens: {response.prompt_tokens} prompt + {response.completion_tokens} "
    f"completion = {response.prompt_tokens + response.completion_tokens} total "
    f"(finish_reason={response.finish_reason})"
)
print(
    f"Latency: {response.latency:.2f}s "
    f"({tokens_per_second(response.completion_tokens, response.latency):.1f} tok/s)"
)

run_directory = Path(
    "results/test"
)

if run_directory.exists():
    shutil.rmtree(run_directory)

run_directory.mkdir(
    parents=True,
    exist_ok=True,
)

project_directory = Workspace.create(
    case.project_path,
    run_directory / "project",
)

print(f"Response:\n{response.content}")

outcome = apply_model_response(args.edit_mode, project_directory, response)

print(f"Applied: {outcome.applied}")

if outcome.edit_results is not None:
    for result in outcome.edit_results:
        print(
            f"  {result.path}: applied={result.applied} "
            f"kind={result.match_kind} similarity={result.similarity} "
            f"error={result.error}"
        )

if not outcome.applied:
    print(outcome.error)
    raise SystemExit(1)

print(f"Diff:\n{outcome.diff}")

compilation = Compiler.compile(
    project_directory
)

print(
    f"Compilation successful: {compilation.compiled}"
)

print(
    f"Compilation time: "
    f"{compilation.execution_time:.2f}s"
)

if compilation.compiled:
    test_execution = TestRunner.run(
        project_directory
    )

    print(
        f"Tests ran: {test_execution.ran}, passed: {test_execution.passed} "
        f"({test_execution.tests_run - test_execution.failures - test_execution.errors}/"
        f"{test_execution.tests_run} passing, {test_execution.failures} failures, "
        f"{test_execution.errors} errors, {test_execution.skipped} skipped)"
    )
    print(
        f"Test execution time: {test_execution.execution_time:.2f}s"
    )
