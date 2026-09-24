"""
Run the SonarQube analysis phase for a sonar benchmark run directory that was
already generated and validated, without calling the model again.

This is the cheap path for replicability work: generate N runs unattended
(run_all_sonar.py --no-sonar, or run_all_sonar_generate.py + validate_sonar_run.py),
then grade them all here against one warm server with warm baseline caches.

The existing report.json is updated in place: each case's sonar fields are
(re)computed and the summary is recalculated.

Usage:
    python -m runner.analyze_sonar_run 2026-09-21_15-30-00
    python -m runner.analyze_sonar_run results/2026-09-21_15-30-00 --cases S2259 S1643
"""

import argparse
from dataclasses import asdict

from runner.cli.arguments import add_run_id_argument
from runner.cli.loading import open_run
from runner.filesystem.results_manager import ResultsManager
from runner.models.sonar_case_result import SonarCaseResult
from runner.sonar_tests.pipeline import analyze_run
from runner.sonar_tests.report import compute_summary, print_report


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze every compiled case in a sonar run directory with SonarQube "
            "and record whether the reported issue was resolved and whether new "
            "issues appeared."
        )
    )
    add_run_id_argument(parser)
    parser.add_argument(
        "--cases",
        nargs="+",
        help="Limit the analysis to specific case IDs (default: every compiled case).",
    )
    args = parser.parse_args()

    run_directory, report = open_run(args.run_id)
    results = [SonarCaseResult(**case_data) for case_data in report["cases"]]

    results = analyze_run(results, run_directory, args.cases)

    summary = compute_summary(results, report.get("summary", {}).get("wall_time", 0.0))
    print_report(results, summary)

    report["summary"] = summary
    report["cases"] = [asdict(r) for r in results]
    report["sonar_analyzed"] = True
    report_path = ResultsManager.write_report(run_directory, report)
    print(f"\nUpdated report written to {report_path}")


if __name__ == "__main__":
    main()
