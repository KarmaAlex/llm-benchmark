"""
The analysis phase: grade already-generated, already-compiled case
workspaces against a real SonarQube.

Shaped like validate_case() in sonar_tests/pipeline.py - it returns a dict of
SonarCaseResult field updates suitable for dataclasses.replace() - so the
inline pipeline and the standalone analyze_sonar_run.py entry point share
one implementation.

It is a *batch* phase on purpose. One server is brought up (or reused) for
the whole set of cases, so container startup is amortized over the whole
benchmark instead of being paid per case.
"""

import json
from pathlib import Path

from runner.filesystem.paths import BENCHMARK_DIR
from runner.sonar_tests.baseline import baseline_findings
from runner.sonar_tests.issue_diff import compare, normalize_all
from runner.sonar_tests.sonar_server import SonarServer

NOT_COMPILED = "case did not compile - nothing meaningful to analyze"
NO_WORKSPACE = "no project workspace on disk"


def expected_issue(case_id: str) -> dict:
    return json.loads((BENCHMARK_DIR / "sonar" / case_id / "issue.json").read_text(encoding="utf-8"))


def skipped(reason: str) -> dict:
    return dict(sonar_analyzed=False, sonar_error=reason)


def analyze_case(
    case_id: str,
    case_directory: Path,
    server: SonarServer,
    run_id: str,
    log_directory: Path | None = None,
) -> dict:
    """Analyze one patched workspace and diff it against the case's cached
    pristine baseline."""
    project_directory = case_directory / "project"
    if not project_directory.exists():
        return skipped(NO_WORKSPACE)

    expected = expected_issue(case_id)
    baseline = baseline_findings(case_id, server, expected)

    # A key unique per run keeps SonarQube's cross-analysis issue tracking
    # (which would carry statuses over from a previous run of the same case)
    # out of the comparison; deleting the project afterwards keeps the
    # embedded database from growing across dozens of replication runs.
    project_key = f"benchmark-run-{run_id}-{case_id}"
    log_path = (log_directory / f"{case_id}.sonar.log") if log_directory else None

    try:
        outcome = server.analyze(project_directory, project_key, log_path=log_path)
        if not outcome.ok:
            return dict(sonar_analyzed=False, sonar_error=outcome.error, sonar_time=outcome.duration)
        after = normalize_all(server.fetch_findings(project_key), project_key)
    finally:
        server.delete_project(project_key)

    comparison = compare(expected, baseline, after)

    return dict(
        sonar_analyzed=True,
        target_resolved=comparison.target_resolved,
        new_issues_count=len(comparison.new_issues),
        new_issues=comparison.new_issues,
        remaining_target_issues=comparison.remaining_target,
        baseline_issue_count=comparison.baseline_count,
        after_issue_count=comparison.after_count,
        sonar_time=outcome.duration,
        sonar_error=None,
    )
