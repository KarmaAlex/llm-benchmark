"""
Sonar issue-resolution case pipeline shared by the single-case runner
(main_sonar.py), the batch runners (run_all_sonar.py,
run_all_sonar_generate.py) and the post-hoc phases (validate_sonar_run.py,
analyze_sonar_run.py).

A case goes through three phases, each usable on its own:

    generate  - call the model and apply its edit to a fresh workspace
    validate  - mvn compile + mvn test on the patched workspace
    analyze   - SonarQube scan diffed against the pristine baseline (batch)
"""

from collections import Counter
from dataclasses import replace
from pathlib import Path

from runner.core.prompt_builder import PromptBuilder
from runner.core.stats import response_token_stats
from runner.filesystem.benchmark_loader import BenchmarkLoader
from runner.filesystem.prompt_loader import PromptLoader
from runner.models.benchmark import BenchmarkCase
from runner.models.chat_prompt import ChatPrompt
from runner.models.model_response import ModelResponse
from runner.models.prompt import Prompt
from runner.models.sonar_case_result import SonarCaseResult
from runner.providers.base import ModelProvider
from runner.sonar_tests.analysis import NOT_COMPILED, analyze_case, skipped
from runner.sonar_tests.compiler import Compiler
from runner.sonar_tests.edit_pipeline import (
    PROMPT_NAME_BY_EDIT_MODE,
    ApplyOutcome,
    apply_model_response,
)
from runner.sonar_tests.sonar_server import SonarServer, SonarServerError
from runner.sonar_tests.structured_edit import EDIT_FILE_TOOL_SCHEMA
from runner.sonar_tests.test_runner import TestRunner
from runner.sonar_tests.workspace import Workspace

SUITE = "sonar"


def load_case(case_id: str) -> BenchmarkCase:
    return BenchmarkLoader.load(Path(SUITE) / case_id)


def load_prompt(edit_mode: str) -> Prompt:
    return PromptLoader.load(PROMPT_NAME_BY_EDIT_MODE[edit_mode])


def discover_cases() -> list[str]:
    return BenchmarkLoader.discover(SUITE)


def build_chat_prompt(prompt: Prompt, case: BenchmarkCase, edit_mode: str) -> ChatPrompt:
    chat_prompt = PromptBuilder.build(prompt, case)
    if edit_mode == "toolcall":
        chat_prompt = replace(chat_prompt, tools=[EDIT_FILE_TOOL_SCHEMA])
    return chat_prompt


def apply_to_workspace(
    case: BenchmarkCase,
    edit_mode: str,
    response: ModelResponse,
    case_directory: Path,
) -> ApplyOutcome:
    """Copy the case's project into case_directory/project and apply the
    model's edit to it."""
    project_directory = Workspace.create(
        case.project_path,
        case_directory / "project",
    )
    return apply_model_response(edit_mode, project_directory, response)


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
    prompt: Prompt,
    run_directory: Path,
) -> SonarCaseResult:
    """Generate a model response and apply it to a fresh workspace, without
    compiling or running tests. See validate_case() for that phase."""
    case = load_case(case_id)
    response = provider.generate(build_chat_prompt(prompt, case, edit_mode))

    case_directory = run_directory / case_id
    case_directory.mkdir(parents=True, exist_ok=True)

    outcome = apply_to_workspace(case, edit_mode, response, case_directory)

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
        edit_match_summary=_edit_match_summary(outcome.edit_results),
        **response_token_stats(response),
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
        tests_skipped=test_execution.skipped,
        test_time=test_execution.execution_time,
        error=None if test_execution.passed else test_execution.stderr,
    )


def run_case(
    case_id: str,
    edit_mode: str,
    provider: ModelProvider,
    prompt: Prompt,
    run_directory: Path,
) -> SonarCaseResult:
    result = generate_case(case_id, edit_mode, provider, prompt, run_directory)

    if not result.applied:
        return result

    validation = validate_case(run_directory / case_id)
    return replace(result, **validation)


def failed_result(case_id: str, edit_mode: str, error: str) -> SonarCaseResult:
    return SonarCaseResult(
        case_id=case_id,
        edit_mode=edit_mode,
        applied=False,
        compiled=False,
        execution_time=0.0,
        compile_time=0.0,
        error=error,
    )


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
