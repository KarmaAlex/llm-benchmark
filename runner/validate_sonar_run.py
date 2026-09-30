"""
Run the validation phase (mvn compile + mvn test) for a sonar benchmark run
directory that was already generated - either by run_all_sonar.py (which
validates inline) or by run_all_sonar_generate.py (which does not) - without
calling the model again. Cases whose patch was never applied are left alone,
matching the behavior of the inline pipeline.

The existing report.json in the run directory is updated in place: each
case's compiled/tests fields are (re)computed and the summary is
recalculated.

Usage:
    python -m runner.validate_sonar_run 2026-09-21_15-30-00
    python -m runner.validate_sonar_run results/2026-09-21_15-30-00
"""

import argparse
import time
from dataclasses import asdict, replace

from runner.cli.arguments import add_run_id_argument
from runner.cli.loading import open_run
from runner.filesystem.results_manager import ResultsManager
from runner.models.sonar_case_result import SonarCaseResult
from runner.sonar_tests.pipeline import validate_case
from runner.sonar_tests.report import compute_summary, print_report


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compile and run tests for every already-applied case in a sonar "
            "run directory, without calling the model again."
        )
    )
    add_run_id_argument(parser)
    args = parser.parse_args()

    run_directory, report = open_run(args.run_id)

    results: list[SonarCaseResult] = []
    validation_start = time.perf_counter()
    for case_data in report["cases"]:
        result = SonarCaseResult(**case_data)
        case_directory = run_directory / result.case_id

        if not result.applied or not (case_directory / "project").exists():
            results.append(result)
            continue

        print(f"Validating {result.case_id}...")
        try:
            validation = validate_case(case_directory)
        except Exception as e:
            validation = dict(compiled=False, error=f"{type(e).__name__}: {e}")
        results.append(replace(result, **validation))

    validation_time = time.perf_counter() - validation_start
    previous_wall_time = report.get("summary", {}).get("wall_time", 0.0)

    summary = compute_summary(results, previous_wall_time + validation_time)
    print_report(results, summary)

    # Validation often runs somewhere else later (no GPU needed), so keep the
    # generation run's own wall time apart from the total: it's how long the
    # model's machine was held (see analysis/costs.py, allocated GPU-hours).
    if not report.get("validated"):
        report.setdefault("generation_wall_time", previous_wall_time)
    report["summary"] = summary
    report["cases"] = [asdict(r) for r in results]
    report["validated"] = True
    report_path = ResultsManager.write_report(run_directory, report)
    print(f"\nUpdated report written to {report_path}")


if __name__ == "__main__":
    main()
