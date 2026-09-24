from runner.cli.output import format_gpu_memory, print_run_footer, print_token_summary
from runner.core.stats import peak_gpu_memory_mb, token_summary
from runner.models.sonar_case_result import SonarCaseResult


def compute_summary(results: list[SonarCaseResult], wall_time: float) -> dict:
    total = len(results)
    applied_count = sum(1 for r in results if r.applied)
    compiled_count = sum(1 for r in results if r.compiled)
    tests_ran_count = sum(1 for r in results if r.tests_ran)
    tests_passed_count = sum(1 for r in results if r.tests_passed)
    analyzed_count = sum(1 for r in results if r.sonar_analyzed)
    resolved_count = sum(1 for r in results if r.target_resolved)
    clean_fix_count = sum(1 for r in results if r.clean_fix)

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
        "new_issues_total": sum(r.new_issues_count for r in results),
        "total_sonar_time": sum(r.sonar_time for r in results),
        **token_summary(results),
        "total_compile_time": sum(r.compile_time for r in results),
        "total_test_time": sum(r.test_time for r in results),
        "peak_gpu_memory_mb": peak_gpu_memory_mb(results),
        "wall_time": wall_time,
    }


def print_report(results: list[SonarCaseResult], summary: dict) -> None:
    print(
        f"\n{'Case':<10} {'Applied':<9} {'Compiled':<10} {'Tests':<14} {'Resolved':<10} "
        f"{'New':<5} {'Clean':<7} {'Time (s)':<10} {'Tokens':<9} {'Tok/s':<8} "
        f"{'GPU MiB':<9} {'Match':<16} Error"
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
            f"{r.tokens_per_second:<8.1f} {format_gpu_memory(r.gpu_memory_mb):<9} "
            f"{r.edit_match_summary or '':<16} "
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
    print_token_summary(summary)
    print(f"Total model time: {summary['total_execution_time']:.2f}s, "
          f"total compile time: {summary['total_compile_time']:.2f}s, "
          f"total test time: {summary['total_test_time']:.2f}s, "
          f"total sonar time: {summary.get('total_sonar_time', 0.0):.2f}s")
    print_run_footer(summary)


def compute_generation_summary(results: list[SonarCaseResult], wall_time: float) -> dict:
    """Summary for a generate-only run (run_all_sonar_generate.py), before
    any compile/test/analysis phase has happened."""
    total = len(results)
    applied_count = sum(1 for r in results if r.applied)

    return {
        "total_cases": total,
        "applied_count": applied_count,
        "applied_rate": applied_count / total if total else 0.0,
        **token_summary(results),
        "wall_time": wall_time,
    }


def print_generation_report(results: list[SonarCaseResult], summary: dict, run_id: str) -> None:
    print(
        f"\n{'Case':<10} {'Applied':<9} {'Time (s)':<10} "
        f"{'Tokens':<9} {'Tok/s':<8} {'Match':<16} Error"
    )
    for r in results:
        print(
            f"{r.case_id:<10} {str(r.applied):<9} "
            f"{r.execution_time:<10.2f} {r.total_tokens:<9} "
            f"{r.tokens_per_second:<8.1f} {r.edit_match_summary or '':<16} {r.error or ''}"
        )

    print(f"\nApplied:  {summary['applied_count']}/{summary['total_cases']} "
          f"({summary['applied_rate']:.0%})")
    print_token_summary(summary)
    print(f"Total model time: {summary['total_execution_time']:.2f}s")
    print(f"Wall-clock run time: {summary['wall_time']:.2f}s")
    print(
        "\nNot validated yet - run `python -m runner.validate_sonar_run "
        f"{run_id}` to compile and test these cases."
    )
