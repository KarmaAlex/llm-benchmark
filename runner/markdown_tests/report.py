from collections import defaultdict

from runner.cli.output import format_gpu_memory, print_run_footer, print_token_summary
from runner.core.stats import peak_gpu_memory_mb, token_summary
from runner.models.markdown_case_result import MarkdownCaseResult


def compute_summary(results: list[MarkdownCaseResult], wall_time: float) -> dict:
    total = len(results)
    matched_count = sum(1 for r in results if r.matched)

    by_difficulty: dict[int, dict] = defaultdict(lambda: {"total": 0, "matched": 0})
    for r in results:
        key = r.difficulty if r.difficulty is not None else -1
        by_difficulty[key]["total"] += 1
        if r.matched:
            by_difficulty[key]["matched"] += 1

    return {
        "total_cases": total,
        "matched_count": matched_count,
        "matched_rate": matched_count / total if total else 0.0,
        **token_summary(results),
        "peak_gpu_memory_mb": peak_gpu_memory_mb(results),
        "wall_time": wall_time,
        "by_difficulty": {
            str(k): v for k, v in sorted(by_difficulty.items())
        },
    }


def print_report(results: list[MarkdownCaseResult], summary: dict) -> None:
    print(
        f"\n{'Case':<10} {'Difficulty':<11} {'Matched':<9} {'Time (s)':<10} "
        f"{'Tokens':<9} {'Tok/s':<8} {'GPU MiB':<9} Error"
    )
    for r in results:
        error_summary = (r.error or "").splitlines()[0] if r.error else ""
        print(
            f"{r.case_id:<10} {str(r.difficulty):<11} {str(r.matched):<9} "
            f"{r.execution_time:<10.2f} {r.total_tokens:<9} "
            f"{r.tokens_per_second:<8.1f} {format_gpu_memory(r.gpu_memory_mb):<9} {error_summary}"
        )

    print(f"\nMatched: {summary['matched_count']}/{summary['total_cases']} "
          f"({summary['matched_rate']:.0%})")

    print("\nBy difficulty:")
    for difficulty, stats in summary["by_difficulty"].items():
        rate = stats["matched"] / stats["total"] if stats["total"] else 0.0
        print(f"  {difficulty}: {stats['matched']}/{stats['total']} ({rate:.0%})")

    print()
    print_token_summary(summary)
    print(f"Total model time: {summary['total_execution_time']:.2f}s")
    print_run_footer(summary)
