"""
Run every SonarQube issue-resolution benchmark case under benchmark/sonar/
against a single model and report the results.

Usage:
    python -m runner.run_all_sonar --config qwen2.5-coder-7b-q4 --edit-mode diff
"""

import argparse
import json
import time
from collections import Counter
from dataclasses import asdict, dataclass, field, replace
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
from runner.sonar_tests.analysis import NOT_COMPILED, analyze_case, skipped
from runner.sonar_tests.compiler import Compiler
from runner.sonar_tests.edit_pipeline import PROMPT_NAME_BY_EDIT_MODE, apply_model_response
from runner.sonar_tests.sonar_server import SonarServer, SonarServerError
from runner.sonar_tests.test_runner import TestRunner
from runner.sonar_tests.workspace import Workspace
from runner.stats import tokens_per_second
from runner.structured_edit import EDIT_FILE_TOOL_SCHEMA


@dataclass
class SonarCaseResult:
    case_id: str
    edit_mode: str
    applied: bool
    compiled: bool
    execution_time: float
    compile_time: float
    tests_ran: bool = False
    tests_passed: bool = False
    tests_run_count: int = 0
    tests_failed: int = 0
    tests_errored: int = 0
    test_time: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    tokens_per_second: float = 0.0
    finish_reason: str | None = None
    edit_match_summary: str | None = None
    error: str | None = None
    response_text: str | None = None
    diff: str | None = None
    # Filled in by the SonarQube analysis phase. All defaulted so reports
    # written before that phase existed still load (validate_sonar_run.py and
    # analyze_sonar_run.py both rebuild this dataclass from report.json).
    sonar_analyzed: bool = False
    target_resolved: bool | None = None
    new_issues_count: int = 0
    new_issues: list[dict] = field(default_factory=list)
    remaining_target_issues: list[dict] = field(default_factory=list)
    baseline_issue_count: int = 0
    after_issue_count: int = 0
    sonar_time: float = 0.0
    sonar_error: str | None = None

    @property
    def clean_fix(self) -> bool:
        """The metric the suite actually cares about: the reported issue is
        gone, nothing new was introduced, and the behaviour tests still
        pass."""
        return bool(self.tests_passed and self.target_resolved and self.new_issues_count == 0)


def discover_cases() -> list[str]:
    sonar_dir = BENCHMARK_DIR / "sonar"
    return sorted(
        p.name for p in sonar_dir.iterdir()
        if p.is_dir() and (p / "metadata.json").exists()
    )


def _edit_match_summary(edit_results) -> str | None:
    if not edit_results:
        return None
    counts = Counter(r.match_kind for r in edit_results if r.applied)
    if not counts:
        return None
    return ", ".join(f"{count} {kind}" for kind, count in sorted(counts.items()))


def generate_case(
    case_id: str,
    edit_mode: str,
    provider: ModelProvider,
    prompt,
    run_directory: Path,
) -> SonarCaseResult:
    """Generate a model response and apply it to a fresh workspace, without
    compiling or running tests. See validate_case() for that phase."""
    case = BenchmarkLoader.load(Path("sonar") / case_id)
    chat_prompt = PromptBuilder.build(prompt, case)

    if edit_mode == "toolcall":
        chat_prompt = replace(chat_prompt, tools=[EDIT_FILE_TOOL_SCHEMA])

    response: ModelResponse = provider.generate(chat_prompt)

    case_directory = run_directory / case_id
    case_directory.mkdir(parents=True, exist_ok=True)
    
    project_directory = Workspace.create(
        case.project_path,
        case_directory / "project",
    )

    outcome = apply_model_response(edit_mode, project_directory, response)
    
    token_stats = dict(
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
        total_tokens=response.prompt_tokens + response.completion_tokens,
        tokens_per_second=tokens_per_second(response.completion_tokens, response.latency),
        finish_reason=response.finish_reason,
        edit_match_summary=_edit_match_summary(outcome.edit_results),
    )

    return SonarCaseResult(
        case_id=case_id,
        edit_mode=edit_mode,
        applied=outcome.applied,
        compiled=False,
        execution_time=response.latency,
        compile_time=0.0,
        error=outcome.error if not outcome.applied else None,
        response_text=response.content,
        diff=outcome.diff,
        **token_stats,
    )


def validate_case(case_directory: Path) -> dict:
    """Compile and run tests for a case directory previously produced by
    generate_case() (i.e. containing an already-patched project/ folder).
    Returns a dict of SonarCaseResult field updates suitable for
    dataclasses.replace()."""
    project_directory = case_directory / "project"

    compilation = Compiler.compile(project_directory)

    if not compilation.compiled:
        return dict(
            compiled=False,
            compile_time=compilation.execution_time,
            error=compilation.stderr,
        )

    test_execution = TestRunner.run(project_directory)

    return dict(
        compiled=True,
        compile_time=compilation.execution_time,
        tests_ran=test_execution.ran,
        tests_passed=test_execution.passed,
        tests_run_count=test_execution.tests_run,
        tests_failed=test_execution.failures,
        tests_errored=test_execution.errors,
        test_time=test_execution.execution_time,
        error=None if test_execution.passed else test_execution.stderr,
    )


def run_case(
    case_id: str,
    edit_mode: str,
    provider: ModelProvider,
    prompt,
    run_directory: Path,
) -> SonarCaseResult:
    result = generate_case(case_id, edit_mode, provider, prompt, run_directory)

    if not result.applied:
        return result

    validation = validate_case(run_directory / case_id)
    return replace(result, **validation)


def analyze_run(
    results: list[SonarCaseResult],
    run_directory: Path,
    case_ids: list[str] | None = None,
) -> list[SonarCaseResult]:
    """Batch SonarQube phase: bring up (or reuse) the shared server once and
    analyze every case that compiled. Cases that never compiled are recorded
    as skipped rather than failed - there is nothing to scan. Cases excluded
    by `case_ids` are left exactly as they were."""
    selected = {r.case_id for r in results if case_ids is None or r.case_id in case_ids}
    analyzable = {r.case_id for r in results if r.compiled and r.case_id in selected}

    def without_analysis(result: SonarCaseResult) -> SonarCaseResult:
        if result.case_id not in selected:
            return result
        reason = NOT_COMPILED if result.applied else "patch was never applied"
        return replace(result, **skipped(reason))

    if not analyzable:
        print("No compiled cases to analyze with SonarQube.")
        return [without_analysis(r) for r in results]

    try:
        server = SonarServer.ensure_running()
    except (SonarServerError, FileNotFoundError) as e:
        # A missing podman or an unhealthy server shouldn't throw away a run
        # whose expensive part (model generation) already succeeded.
        print(f"SonarQube analysis unavailable: {e}")
        unavailable = skipped(f"{type(e).__name__}: {e}")
        return [replace(r, **unavailable) if r.case_id in selected else r for r in results]

    run_id = run_directory.name.replace("_", "").replace("-", "")[-14:] or "run"
    log_directory = run_directory / "sonar-logs"

    updated: list[SonarCaseResult] = []
    for result in results:
        if result.case_id not in analyzable:
            updated.append(without_analysis(result))
            continue
        print(f"Analyzing {result.case_id}...")
        try:
            analysis = analyze_case(
                result.case_id,
                run_directory / result.case_id,
                server,
                run_id,
                log_directory,
            )
        except Exception as e:
            analysis = skipped(f"{type(e).__name__}: {e}")
        updated.append(replace(result, **analysis))
    return updated


def compute_summary(results: list[SonarCaseResult], wall_time: float) -> dict:
    total = len(results)
    applied_count = sum(1 for r in results if r.applied)
    compiled_count = sum(1 for r in results if r.compiled)
    tests_ran_count = sum(1 for r in results if r.tests_ran)
    tests_passed_count = sum(1 for r in results if r.tests_passed)
    total_prompt_tokens = sum(r.prompt_tokens for r in results)
    total_completion_tokens = sum(r.completion_tokens for r in results)
    total_execution_time = sum(r.execution_time for r in results)
    total_compile_time = sum(r.compile_time for r in results)
    total_test_time = sum(r.test_time for r in results)
    analyzed_count = sum(1 for r in results if r.sonar_analyzed)
    resolved_count = sum(1 for r in results if r.target_resolved)
    clean_fix_count = sum(1 for r in results if r.clean_fix)
    new_issues_total = sum(r.new_issues_count for r in results)
    total_sonar_time = sum(r.sonar_time for r in results)

    return {
        "total_cases": total,
        "applied_count": applied_count,
        "applied_rate": applied_count / total if total else 0.0,
        "compiled_count": compiled_count,
        "compiled_rate": compiled_count / total if total else 0.0,
        "tests_ran_count": tests_ran_count,
        "tests_passed_count": tests_passed_count,
        "tests_passed_rate": tests_passed_count / compiled_count if compiled_count else 0.0,
        "sonar_analyzed_count": analyzed_count,
        "resolved_count": resolved_count,
        # Rated over analyzed cases: a case that never compiled was never
        # given a chance to resolve anything, so it would only dilute this.
        "resolved_rate": resolved_count / analyzed_count if analyzed_count else 0.0,
        "clean_fix_count": clean_fix_count,
        "clean_fix_rate": clean_fix_count / total if total else 0.0,
        "new_issues_total": new_issues_total,
        "total_sonar_time": total_sonar_time,
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_tokens": total_prompt_tokens + total_completion_tokens,
        "avg_tokens_per_second": tokens_per_second(total_completion_tokens, total_execution_time),
        "avg_execution_time": total_execution_time / total if total else 0.0,
        "total_execution_time": total_execution_time,
        "total_compile_time": total_compile_time,
        "total_test_time": total_test_time,
        "wall_time": wall_time,
    }


def print_report(results: list[SonarCaseResult], summary: dict) -> None:
    print(
        f"\n{'Case':<10} {'Applied':<9} {'Compiled':<10} {'Tests':<14} {'Resolved':<10} "
        f"{'New':<5} {'Clean':<7} {'Time (s)':<10} {'Tokens':<9} {'Tok/s':<8} {'Match':<16} Error"
    )
    for r in results:
        if not r.tests_ran:
            tests_summary = "n/a"
        else:
            tests_summary = f"{r.tests_run_count - r.tests_failed - r.tests_errored}/{r.tests_run_count}"
        resolved = str(r.target_resolved) if r.sonar_analyzed else "n/a"
        new_issues = str(r.new_issues_count) if r.sonar_analyzed else "-"
        print(
            f"{r.case_id:<10} {str(r.applied):<9} {str(r.compiled):<10} {tests_summary:<14} "
            f"{resolved:<10} {new_issues:<5} {str(r.clean_fix):<7} "
            f"{r.execution_time:<10.2f} {r.total_tokens:<9} "
            f"{r.tokens_per_second:<8.1f} {r.edit_match_summary or '':<16} "
            f"{r.error or r.sonar_error or ''}"
        )

    print(f"\nApplied:  {summary['applied_count']}/{summary['total_cases']} "
          f"({summary['applied_rate']:.0%})")
    print(f"Compiled: {summary['compiled_count']}/{summary['total_cases']} "
          f"({summary['compiled_rate']:.0%})")
    print(f"Tests passed: {summary['tests_passed_count']}/{summary['compiled_count']} "
          f"of compiled cases ({summary['tests_passed_rate']:.0%})")
    if summary.get("sonar_analyzed_count"):
        print(f"Issue resolved: {summary['resolved_count']}/{summary['sonar_analyzed_count']} "
              f"of analyzed cases ({summary['resolved_rate']:.0%})")
        print(f"Clean fixes:  {summary['clean_fix_count']}/{summary['total_cases']} "
              f"({summary['clean_fix_rate']:.0%}) "
              f"- resolved, no new issues, tests passing")
        print(f"New issues introduced: {summary['new_issues_total']}")
    print(f"Tokens:   {summary['total_prompt_tokens']} prompt + "
          f"{summary['total_completion_tokens']} completion = "
          f"{summary['total_tokens']} total")
    print(f"Throughput: {summary['avg_tokens_per_second']:.1f} completion tok/s (avg)")
    print(f"Avg model latency: {summary['avg_execution_time']:.2f}s per case")
    print(f"Total model time: {summary['total_execution_time']:.2f}s, "
          f"total compile time: {summary['total_compile_time']:.2f}s, "
          f"total test time: {summary['total_test_time']:.2f}s, "
          f"total sonar time: {summary.get('total_sonar_time', 0.0):.2f}s")
    print(f"Wall-clock run time: {summary['wall_time']:.2f}s")


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
    parser.add_argument(
        "--device",
        choices=["cuda", "cpu"],
        default="cuda",
        help="Run local (llama.cpp) models on the GPU (default) or force CPU-only.",
    )
    parser.add_argument(
        "--sonar",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "After compiling and testing, analyze every case with a real SonarQube "
            "to check the reported issue is gone and no new ones appeared "
            "(default: on). Uses the shared long-lived container; see "
            "scripts/sonar_server.py."
        ),
    )
    args = parser.parse_args()

    config: ModelConfig = ConfigLoader.load(args.config)
    config = ConfigLoader.apply_device(config, args.device)

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

    run_start = time.perf_counter()

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

    if args.sonar:
        print("\nRunning SonarQube analysis...")
        results = analyze_run(results, run_directory)

    wall_time = time.perf_counter() - run_start

    summary = compute_summary(results, wall_time)
    print_report(results, summary)

    report_path = run_directory / "report.json"
    report_path.write_text(
        json.dumps(
            {
                "config": config.name,
                "edit_mode": args.edit_mode,
                "sonar_analyzed": args.sonar,
                "summary": summary,
                "cases": [asdict(r) for r in results],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nFull report written to {report_path}")


if __name__ == "__main__":
    main()
