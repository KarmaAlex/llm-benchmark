"""
Print a human-readable summary of an existing benchmark run.

The run_all_* scripts print a report as they go, but that output is gone the
moment the terminal scrolls. This reads a run's report.json back and renders
it properly - the per-case table, where cases dropped out of the pipeline,
and what it cost.

The two suites are graded on entirely different things, so they get entirely
different reports: markdown is one binary "did the JSON match", sonar is a
five-stage funnel ending at "clean fix". The suite is detected from the
report itself.

Everything here reads plain dicts rather than the runner's dataclasses, so a
report written by an older version of the harness still renders (missing
fields simply read as absent) and importing this module doesn't drag in
llama.cpp.

Usage:
    python -m analysis.report                        # the most recent run
    python -m analysis.report 2026-09-22_19-50-38    # a specific run
    python -m analysis.report <run> <run> ...        # several, one after another
    python -m analysis.report <run> --verbose        # + full errors and per-issue detail
    python -m analysis.report --list                 # what's available
"""

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from runner.filesystem.paths import RESULTS_DIR

BAR_WIDTH = 24
RULE = "=" * 78


# --------------------------------------------------------------------------- #
# locating and loading runs
# --------------------------------------------------------------------------- #


def run_directories() -> list[Path]:
    """Every directory under results/ holding a report.json, newest first."""
    if not RESULTS_DIR.is_dir():
        return []
    return sorted(
        (p for p in RESULTS_DIR.iterdir() if p.is_dir() and (p / "report.json").exists()),
        key=lambda p: p.name,
        reverse=True,
    )


def resolve_run_directory(run_id: str) -> Path:
    for candidate in (Path(run_id), RESULTS_DIR / run_id):
        if (candidate / "report.json").exists():
            return candidate
        if candidate.is_dir():
            raise SystemExit(f"'{candidate}' has no report.json - was the run interrupted?")
    raise SystemExit(
        f"No run found for '{run_id}' (looked for it directly and under {RESULTS_DIR}). "
        "Use --list to see what's available."
    )


def latest_run_directory() -> Path:
    directories = run_directories()
    if not directories:
        raise SystemExit(f"No runs with a report.json under {RESULTS_DIR}.")
    return directories[0]


def load_report(run_directory: Path) -> dict:
    return json.loads((run_directory / "report.json").read_text(encoding="utf-8"))


def detect_suite(report: dict) -> str:
    """Which benchmark produced this report. The summary is the reliable
    signal - the two suites share no grading keys - with the per-case fields
    as a fallback for a report whose summary is empty."""
    summary = report.get("summary") or {}
    if "matched_rate" in summary:
        return "markdown"
    if "applied_rate" in summary:
        return "sonar"

    cases = report.get("cases") or []
    if cases and "matched" in cases[0]:
        return "markdown"
    if cases and "applied" in cases[0]:
        return "sonar"
    return "unknown"


def run_timestamp(run_directory: Path) -> str:
    """Run directories are named for their UTC start time."""
    try:
        started = datetime.strptime(run_directory.name, "%Y-%m-%d_%H-%M-%S")
    except ValueError:
        return ""
    return started.strftime("%Y-%m-%d %H:%M UTC")


# --------------------------------------------------------------------------- #
# formatting helpers
# --------------------------------------------------------------------------- #


def truncate(text: str, width: int) -> str:
    """First line only, clipped to width - error text is often a whole Maven
    stack trace and only its opening line belongs in a table."""
    first_line = (text or "").splitlines()[0] if text else ""
    if len(first_line) <= width:
        return first_line
    return first_line[: max(0, width - 1)] + "…"

def bar(count: int, total: int) -> str:
    if not total:
        return ""
    filled = round(BAR_WIDTH * count / total)
    return "█" * filled + "·" * (BAR_WIDTH - filled)


def percent(count: int, total: int) -> str:
    return f"{count / total:.0%}" if total else "n/a"


def stage_line(label: str, count: int, total: int) -> str:
    return f"  {label:<22} {count:>3}/{total:<3} {bar(count, total)} {percent(count, total):>5}"


def error_width(prefix_width: int) -> int:
    """Whatever the terminal has left once the fixed columns are laid out."""
    return max(20, shutil.get_terminal_size((120, 24)).columns - prefix_width - 1)


def header(title: str, report: dict, run_directory: Path, extra: list[str]) -> None:
    parts = [str(run_directory)]
    timestamp = run_timestamp(run_directory)
    if timestamp:
        parts.append(timestamp)
    parts += extra

    print(f"\n{RULE}")
    print(f" {title} — {report.get('config', 'unknown model')}")
    print(f" {'  ·  '.join(parts)}")
    print(RULE)


def cost_section(summary: dict) -> None:
    print("\nCost")
    print(f"  tokens        {summary.get('total_prompt_tokens', 0):,} prompt + "
          f"{summary.get('total_completion_tokens', 0):,} completion = "
          f"{summary.get('total_tokens', 0):,} total")
    print(f"  throughput    {summary.get('avg_tokens_per_second', 0.0):.1f} completion tok/s (avg)")
    print(f"  model time    {summary.get('total_execution_time', 0.0):.1f}s "
          f"({summary.get('avg_execution_time', 0.0):.1f}s per case)")

    grading = [
        ("compile", summary.get("total_compile_time")),
        ("test", summary.get("total_test_time")),
        ("sonar", summary.get("total_sonar_time")),
    ]
    measured = [f"{label} {value:.1f}s" for label, value in grading if value]
    if measured:
        print(f"  grading time  {', '.join(measured)}")
    print(f"  wall clock    {summary.get('wall_time', 0.0):.1f}s")


# --------------------------------------------------------------------------- #
# markdown
# --------------------------------------------------------------------------- #


def print_markdown_report(report: dict, run_directory: Path, verbose: bool) -> None:
    cases = report.get("cases", [])
    summary = report.get("summary", {})
    total = summary.get("total_cases", len(cases))
    width = error_width(50)  # the fixed columns of the row below

    header("Markdown extraction", report, run_directory, [f"{total} cases"])

    print(f"\n{'Case':<9} {'Diff':<5} {'Match':<7} {'Time':>7} {'Tokens':>8} {'Tok/s':>7}  Error")
    for case in cases:
        difficulty = case.get("difficulty")
        print(
            f"{case.get('case_id', '?'):<9} "
            f"{('-' if difficulty is None else str(difficulty)):<5} "
            f"{('yes' if case.get('matched') else 'NO'):<7} "
            f"{case.get('execution_time', 0.0):>7.2f} "
            f"{case.get('total_tokens', 0):>8,} "
            f"{case.get('tokens_per_second', 0.0):>7.1f}  "
            f"{truncate(case.get('error') or '', width)}"
        )

    matched = summary.get("matched_count", sum(1 for c in cases if c.get("matched")))
    print("\nResult")
    print(stage_line("matched expected", matched, total))

    by_difficulty = summary.get("by_difficulty") or {}
    if by_difficulty:
        print("\nBy difficulty")
        for difficulty, stats in sorted(by_difficulty.items()):
            label = "unlabelled" if difficulty == "-1" else f"level {difficulty}"
            print(stage_line(label, stats.get("matched", 0), stats.get("total", 0)))

    failures = [c for c in cases if not c.get("matched")]
    if failures:
        print(f"\nFailures ({len(failures)})")
        for case in failures:
            reason = case.get("error") or "no error recorded"
            if verbose:
                print(f"  {case.get('case_id', '?')}")
                for line in reason.splitlines():
                    print(f"      {line}")
            else:
                print(f"  {case.get('case_id', '?'):<9} {truncate(reason, error_width(11))}")

    truncated = [c for c in cases if c.get("finish_reason") == "length"]
    if truncated:
        # Worth calling out separately: these aren't extraction failures, the
        # model simply ran out of budget mid-answer.
        print(f"\nHit the token limit ({len(truncated)}): "
              f"{', '.join(c.get('case_id', '?') for c in truncated)}")

    cost_section(summary)


# --------------------------------------------------------------------------- #
# sonar
# --------------------------------------------------------------------------- #


def clean_fix(case: dict) -> bool:
    return bool(case.get("tests_passed") and case.get("target_resolved")
                and not case.get("new_issues_count"))


def tests_cell(case: dict) -> str:
    if not case.get("tests_ran"):
        return "-"
    run = case.get("tests_run_count", 0)
    bad = case.get("tests_failed", 0) + case.get("tests_errored", 0)
    return f"{run - bad}/{run}"


def dropout_reason(case: dict) -> str | None:
    """The first stage of the pipeline this case failed at, or None if it
    made it all the way through."""
    if not case.get("applied"):
        return "patch did not apply"
    if not case.get("compiled"):
        return "project did not compile"
    if not case.get("tests_passed"):
        return "existing tests failed"
    if not case.get("sonar_analyzed"):
        return "not analyzed by SonarQube"
    if not case.get("target_resolved"):
        return "reported issue still present"
    if case.get("new_issues_count"):
        return "introduced new issues"
    return None


def print_sonar_report(report: dict, run_directory: Path, verbose: bool) -> None:
    cases = report.get("cases", [])
    summary = report.get("summary", {})
    total = summary.get("total_cases", len(cases))
    width = error_width(77)  # the fixed columns of the case table below

    extra = [f"{total} cases"]
    if report.get("edit_mode"):
        extra.insert(0, f"edit mode: {report['edit_mode']}")
    if not any(c.get("sonar_analyzed") for c in cases):
        extra.append("no SonarQube analysis")
    header("Sonar issue resolution", report, run_directory, extra)

    print(f"\n{'Case':<9} {'Applied':<8} {'Compiled':<9} {'Tests':<7} {'Resolved':<9} "
          f"{'New':>4} {'Clean':<6} {'Time':>7} {'Tokens':>8}  Note")
    for case in cases:
        analyzed = case.get("sonar_analyzed")
        resolved = ("yes" if case.get("target_resolved") else "no") if analyzed else "-"
        new_issues = str(case.get("new_issues_count", 0)) if analyzed else "-"
        note = case.get("error") or case.get("sonar_error") or ""
        print(
            f"{case.get('case_id', '?'):<9} "
            f"{('yes' if case.get('applied') else 'NO'):<8} "
            f"{('yes' if case.get('compiled') else 'NO'):<9} "
            f"{tests_cell(case):<7} "
            f"{resolved:<9} "
            f"{new_issues:>4} "
            f"{('yes' if clean_fix(case) else ''):<6} "
            f"{case.get('execution_time', 0.0):>7.2f} "
            f"{case.get('total_tokens', 0):>8,}  "
            f"{truncate(note, width)}"
        )

    analyzed_cases = [c for c in cases if c.get("sonar_analyzed")]
    print("\nPipeline")
    print(stage_line("patch applied", sum(1 for c in cases if c.get("applied")), total))
    print(stage_line("compiled", sum(1 for c in cases if c.get("compiled")), total))
    print(stage_line("tests passed", sum(1 for c in cases if c.get("tests_passed")), total))
    if analyzed_cases:
        print(stage_line("issue resolved", sum(1 for c in cases if c.get("target_resolved")), total))
        print(stage_line("clean fix", sum(1 for c in cases if clean_fix(c)), total))
        print(f"\n  A clean fix resolves the reported issue, introduces no new ones, and\n"
              f"  leaves the existing tests passing. {len(cases) - len(analyzed_cases)} of "
              f"{total} cases never reached analysis.")
    else:
        print("\n  No SonarQube analysis in this report - whether the reported issues were\n"
              "  actually resolved is unknown. Run: python -m runner.analyze_sonar_run "
              f"{run_directory.name}")

    dropouts: dict[str, list[str]] = {}
    for case in cases:
        reason = dropout_reason(case)
        if reason is not None:
            dropouts.setdefault(reason, []).append(case.get("case_id", "?"))
    if dropouts:
        print("\nWhere cases fell short")
        for reason, case_ids in sorted(dropouts.items(), key=lambda item: -len(item[1])):
            print(f"  {reason:<30} {len(case_ids):>3}  {', '.join(case_ids)}")

    still_present = [c for c in analyzed_cases if not c.get("target_resolved")]
    if still_present:
        # Counted over analyzed cases, so this can exceed the "reported issue
        # still present" dropout line above, which only counts cases that got
        # that far without failing something earlier.
        print(f"\nIssue still present after the fix "
              f"({len(still_present)} of {len(analyzed_cases)} analyzed)")
        for case in still_present:
            for issue in case.get("remaining_target_issues") or []:
                prefix = f"  {case.get('case_id', '?'):<9} {issue.get('rule', '?')} line {issue.get('line')} — "
                print(f"{prefix}{truncate(issue.get('message', ''), error_width(len(prefix)))}")

    regressions = [c for c in analyzed_cases if c.get("new_issues_count")]
    if regressions:
        introduced = sum(c.get("new_issues_count", 0) for c in regressions)
        print(f"\nNew issues introduced ({introduced} across {len(regressions)} case(s))")
        for case in regressions:
            # A finding counts as new when its (rule, file, message) wasn't in
            # the baseline. For a case whose target issue also survived, that
            # can be the *same* defect reworded or moved rather than an extra
            # one - say so instead of letting it read as two separate faults.
            target = {(i.get("rule"), i.get("file")) for i in case.get("remaining_target_issues") or []}
            for issue in case.get("new_issues") or []:
                location = f"{Path(issue.get('file', '')).name}:{issue.get('line')}"
                restated = " (same rule/file as the unresolved issue)" \
                    if (issue.get("rule"), issue.get("file")) in target else ""
                message = truncate(issue.get("message", ""), error_width(55 + len(restated)))
                print(f"  {case.get('case_id', '?'):<9} {issue.get('rule', '?'):<14} {location:<28} "
                      f"{message}{restated}")

    if verbose:
        print_sonar_details(cases)

    cost_section(summary)


def print_sonar_details(cases: list[dict]) -> None:
    """Full, untruncated failure text for the cases that didn't get through."""
    failed = [c for c in cases if c.get("error") or c.get("sonar_error")]
    if not failed:
        return
    print(f"\n{'-' * 78}\nFailure detail")
    for case in failed:
        print(f"\n{case.get('case_id', '?')} ({dropout_reason(case) or 'completed'})")
        for label, text in (("error", case.get("error")), ("sonar", case.get("sonar_error"))):
            if not text:
                continue
            print(f"  {label}:")
            for line in text.splitlines():
                print(f"    {line}")


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #


def print_report(run_directory: Path, verbose: bool) -> None:
    report = load_report(run_directory)
    suite = detect_suite(report)

    if suite == "markdown":
        print_markdown_report(report, run_directory, verbose)
    elif suite == "sonar":
        print_sonar_report(report, run_directory, verbose)
    else:
        raise SystemExit(
            f"{run_directory / 'report.json'} doesn't look like a markdown or sonar "
            "report (no recognizable grading fields)."
        )


def print_listing() -> None:
    directories = run_directories()
    if not directories:
        print(f"No runs with a report.json under {RESULTS_DIR}.")
        return

    print(f"\n{'Run':<22} {'Suite':<10} {'Model':<28} Headline")
    for directory in directories:
        try:
            report = load_report(directory)
        except json.JSONDecodeError:
            print(f"{directory.name:<22} {'unreadable report.json'}")
            continue
        suite = detect_suite(report)
        summary = report.get("summary", {})
        total = summary.get("total_cases", len(report.get("cases", [])))
        if suite == "markdown":
            headline = f"matched {summary.get('matched_count', 0)}/{total}"
        elif suite == "sonar":
            cases = report.get("cases", [])
            headline = (f"clean fixes {sum(1 for c in cases if clean_fix(c))}/{total}"
                        if any(c.get("sonar_analyzed") for c in cases)
                        else f"tests passed {summary.get('tests_passed_count', 0)}/{total} (no analysis)")
        else:
            headline = ""
        print(f"{directory.name:<22} {suite:<10} "
              f"{truncate(str(report.get('config', '?')), 27):<28} {headline}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print a human-readable summary of an existing benchmark run.",
    )
    parser.add_argument(
        "run_id",
        nargs="*",
        help="Run directory name under results/ (or a path to it). Defaults to the most recent run.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List the available runs with a one-line headline each, and exit.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Include full, untruncated error output for the cases that failed.",
    )
    args = parser.parse_args()

    if args.list:
        print_listing()
        return

    directories = [resolve_run_directory(r) for r in args.run_id] or [latest_run_directory()]
    for directory in directories:
        print_report(directory, args.verbose)
    print()


if __name__ == "__main__":
    main()
