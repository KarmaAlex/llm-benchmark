"""
Run every SonarQube issue-resolution benchmark case under benchmark/sonar/
against a single model and report the results.

Usage:
    python -m runner.run_all_sonar --config qwen2.5-coder-7b-q4 --edit-mode diff
"""

import argparse
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from runner.filesystem.benchmark_loader import BenchmarkLoader
from runner.filesystem.config_loader import ConfigLoader
from runner.filesystem.paths import BENCHMARK_DIR
from runner.filesystem.prompt_loader import PromptLoader
from runner.filesystem.results_manager import ResultsManager
from runner.models.model_config import ModelConfig
from runner.models.model_response import ModelResponse
from runner.prompt_builder import PromptBuilder
from runner.providers.base import ModelProvider
from runner.providers.factory import ProviderFactory
from runner.sonar_tests.compiler import Compiler
from runner.sonar_tests.edit_pipeline import PROMPT_NAME_BY_EDIT_MODE, apply_model_response
from runner.sonar_tests.workspace import Workspace
from runner.structured_edit import EDIT_FILE_TOOL_SCHEMA


@dataclass
class SonarCaseResult:
    case_id: str
    edit_mode: str
    applied: bool
    compiled: bool
    execution_time: float
    compile_time: float
    error: str | None = None
    response_text: str | None = None
    diff: str | None = None


def discover_cases() -> list[str]:
    sonar_dir = BENCHMARK_DIR / "sonar"
    return sorted(
        p.name for p in sonar_dir.iterdir()
        if p.is_dir() and (p / "metadata.json").exists()
    )


def run_case(
    case_id: str,
    edit_mode: str,
    provider: ModelProvider,
    prompt,
    run_directory: Path,
) -> SonarCaseResult:
    case = BenchmarkLoader.load(Path("sonar") / case_id)
    chat_prompt = PromptBuilder.build(prompt, case)

    if edit_mode == "toolcall":
        chat_prompt = replace(chat_prompt, tools=[EDIT_FILE_TOOL_SCHEMA])

    response: ModelResponse = provider.generate(chat_prompt)

    case_directory = run_directory / case_id
    case_directory.mkdir(parents=True, exist_ok=True)
    (case_directory / "response.txt").write_text(response.content, encoding="utf-8")

    project_directory = Workspace.create(
        case.project_path,
        case_directory / "project",
    )

    outcome = apply_model_response(edit_mode, project_directory, response)
    (case_directory / "patch.diff").write_text(outcome.diff or "", encoding="utf-8")

    if not outcome.applied:
        return SonarCaseResult(
            case_id=case_id,
            edit_mode=edit_mode,
            applied=False,
            compiled=False,
            execution_time=response.latency,
            compile_time=0.0,
            error=outcome.error,
            response_text=response.content,
            diff=outcome.diff,
        )

    compilation = Compiler.compile(project_directory)

    return SonarCaseResult(
        case_id=case_id,
        edit_mode=edit_mode,
        applied=True,
        compiled=compilation.compiled,
        execution_time=response.latency,
        compile_time=compilation.execution_time,
        error=None if compilation.compiled else compilation.stderr,
        response_text=response.content,
        diff=outcome.diff,
    )


def print_report(results: list[SonarCaseResult]) -> None:
    total = len(results)
    applied_count = sum(1 for r in results if r.applied)
    compiled_count = sum(1 for r in results if r.compiled)

    print(f"\n{'Case':<10} {'Applied':<9} {'Compiled':<10} {'Time (s)':<10} Error")
    for r in results:
        print(
            f"{r.case_id:<10} {str(r.applied):<9} {str(r.compiled):<10} "
            f"{r.execution_time:<10.2f} {r.error or ''}"
        )

    print(f"\nApplied:  {applied_count}/{total}")
    print(f"Compiled: {compiled_count}/{total}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run every sonar benchmark case against a model and report the results."
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
        help="How the model expresses its fix (see main_sonar.py for details).",
    )
    args = parser.parse_args()

    config: ModelConfig = ConfigLoader.load(args.config)

    if args.edit_mode == "toolcall" and not config.supports_tools:
        print(
            f"Model config '{config.name}' does not have supports_tools "
            "enabled. Use --edit-mode structured for this model instead."
        )
        raise SystemExit(1)

    prompt = PromptLoader.load(PROMPT_NAME_BY_EDIT_MODE[args.edit_mode])
    provider = ProviderFactory.create(config)

    run_directory = ResultsManager.create_run_directory()
    print(f"Run directory: {run_directory}")

    results: list[SonarCaseResult] = []
    for case_id in discover_cases():
        print(f"Running {case_id}...")
        try:
            result = run_case(case_id, args.edit_mode, provider, prompt, run_directory)
        except Exception as e:
            result = SonarCaseResult(
                case_id=case_id,
                edit_mode=args.edit_mode,
                applied=False,
                compiled=False,
                execution_time=0.0,
                compile_time=0.0,
                error=f"{type(e).__name__}: {e}",
            )
        results.append(result)

    print_report(results)

    report_path = run_directory / "report.json"
    report_path.write_text(
        json.dumps([asdict(r) for r in results], indent=2),
        encoding="utf-8",
    )
    print(f"\nFull report written to {report_path}")


if __name__ == "__main__":
    main()
