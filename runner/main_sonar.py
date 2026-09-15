import argparse
import shutil
from dataclasses import replace
from pathlib import Path

from runner.sonar_tests.compiler import Compiler
from runner.sonar_tests.patch_applier import PatchApplier
from runner.sonar_tests.workspace import Workspace
from runner.structured_edit import (
    EDIT_FILE_TOOL_SCHEMA,
    EditCall,
    StructuredEditParseError,
    StructuredEditParser,
    apply_edits,
)
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
args = parser.parse_args()

case = BenchmarkLoader.load(
    Path("sonar") / args.case
)

config = ConfigLoader.load(args.config)

if args.edit_mode == "diff":
    prompt = PromptLoader.load("sonar_v2")
elif args.edit_mode == "structured":
    prompt = PromptLoader.load("sonar_structured_v1")
else:
    prompt = PromptLoader.load("sonar_toolcall_v1")

chat_prompt = PromptBuilder.build(
    prompt,
    case,
)

if args.edit_mode == "toolcall":
    if not config.supports_tools:
        print(
            f"Model config '{config.name}' does not have supports_tools "
            "enabled. Use --edit-mode structured for this model instead."
        )
        raise SystemExit(1)
    chat_prompt = replace(chat_prompt, tools=[EDIT_FILE_TOOL_SCHEMA])

print(f"Prompt:\n{chat_prompt}\n\n")

provider = ProviderFactory.create(config)

response = provider.generate(
    chat_prompt
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

if args.edit_mode == "diff":
    patch_result = PatchApplier.apply(
        project_directory,
        response.content,
    )

    print(f"Patch applied: {patch_result.applied}")

    if not patch_result.applied:
        print(patch_result.error)
        raise SystemExit(1)

else:
    if args.edit_mode == "toolcall":
        if not response.tool_calls:
            print("Model returned no tool calls.")
            raise SystemExit(1)
        edits = [
            EditCall(
                path=call["arguments"]["path"],
                search=call["arguments"]["search"],
                replacement=call["arguments"]["replacement"],
                occurrence=call["arguments"].get("occurrence", 1),
            )
            for call in response.tool_calls
            if call["name"] == "edit_file"
        ]
    else:
        try:
            edits = StructuredEditParser.parse(response.content)
        except StructuredEditParseError as e:
            print(f"Failed to parse structured edits: {e}")
            raise SystemExit(1)

    edit_result = apply_edits(project_directory, edits)

    print(f"Edits applied: {edit_result.applied}")
    for outcome in edit_result.edit_results:
        print(
            f"  {outcome.path}: applied={outcome.applied} "
            f"kind={outcome.match_kind} similarity={outcome.similarity} "
            f"error={outcome.error}"
        )

    if not edit_result.applied:
        print(edit_result.error)
        raise SystemExit(1)

    print(f"Diff:\n{edit_result.diff}")

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
