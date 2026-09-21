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
import json
import time
from dataclasses import asdict, replace
from pathlib import Path

from runner.filesystem.paths import RESULTS_DIR
from runner.run_all_sonar import (
    SonarCaseResult,
    compute_summary,
    print_report,
    validate_case,
)


def resolve_run_directory(run_id: str) -> Path:
    candidate = Path(run_id)
    if candidate.is_dir():
        return candidate

    candidate = RESULTS_DIR / run_id
    if candidate.is_dir():
        return candidate

    raise SystemExit(f"No run directory found for '{run_id}' (looked for it directly and under {RESULTS_DIR})")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compile and run tests for every already-applied case in a sonar "
            "run directory, without calling the model again."
        )
    )
    parser.add_argument(
        "run_id",
        help="Run directory name under results/ (or a path to it directly).",
    )
    args = parser.parse_args()

    run_directory = resolve_run_directory(args.run_id)
    report_path = run_directory / "report.json"
    if not report_path.exists():
        raise SystemExit(f"No report.json found in {run_directory}")

    report = json.loads(report_path.read_text(encoding="utf-8"))

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

    report["summary"] = summary
    report["cases"] = [asdict(r) for r in results]
    report["validated"] = True
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nUpdated report written to {report_path}")


if __name__ == "__main__":
    main()
