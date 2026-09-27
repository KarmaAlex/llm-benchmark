"""
Aggregate repeated runs of a suite into a per-case reproducibility verdict.

Each case is classified by the first rule that matches:

    harness-error   at least one repetition failed before the model answered
                    (or, for sonar, lost its SonarQube verdict). Those reps are
                    excluded from everything below; `valid_classification`
                    still says how the remaining reps behaved.
    identical       every raw model output is byte-identical
    equivalent      raw outputs differ, but the effective output (parsed JSON /
                    applied diff) is identical
    outcome-stable  effective outputs differ, but every rep got the same verdict
    flaky           the verdict differs across repetitions

Everything is plain dicts so the result serialises straight into
reproducibility.json.
"""

import difflib
import statistics
from collections import Counter
from pathlib import Path

from runner.filesystem.results_manager import ResultsManager
from runner.models.markdown_case_result import MarkdownCaseResult
from runner.models.sonar_case_result import SonarCaseResult
from runner.reproducibility.observations import (
    MARKDOWN_CRITERION,
    SONAR_CLEAN_FIX,
    SONAR_TESTS_PASSED,
    Observation,
    from_markdown,
    from_sonar,
)

AGGREGATE_FILE_NAME = "reproducibility.json"
SUITES = ("markdown", "sonar")
CLASSIFICATIONS = ("flaky", "harness-error", "outcome-stable", "equivalent", "identical")
SAMPLE_DIFF_MAX_LINES = 40


def classify(observations: list[Observation]) -> str | None:
    if not observations:
        return None
    if len({o.raw_fingerprint for o in observations}) == 1:
        return "identical"
    if len({o.effective_fingerprint for o in observations}) == 1:
        return "equivalent"
    if len({o.passed for o in observations}) == 1:
        return "outcome-stable"
    return "flaky"


def _output_groups(observations: list[Observation]) -> list[dict]:
    """Reps grouped by effective output, most common first, labelled A, B, ..."""
    groups: dict[str, list[Observation]] = {}
    for o in observations:
        groups.setdefault(o.effective_fingerprint, []).append(o)

    ordered = sorted(groups.values(), key=lambda g: (-len(g), g[0].rep))
    return [
        {
            "label": chr(ord("A") + i) if i < 26 else f"#{i + 1}",
            "reps": [o.rep for o in group],
            "pass_count": sum(o.passed for o in group),
            "stages": dict(Counter(o.stage for o in group)),
            "output": group[0].effective_output,
        }
        for i, group in enumerate(ordered)
    ]


def _sample_diff(groups: list[dict]) -> str | None:
    """A unified diff between the two most common effective outputs."""
    if len(groups) < 2:
        return None
    first, second = groups[0], groups[1]
    lines = list(difflib.unified_diff(
        (first["output"] or "").splitlines(),
        (second["output"] or "").splitlines(),
        fromfile=f"output {first['label']}",
        tofile=f"output {second['label']}",
        lineterm="",
    ))
    if len(lines) > SAMPLE_DIFF_MAX_LINES:
        omitted = len(lines) - SAMPLE_DIFF_MAX_LINES
        lines = lines[:SAMPLE_DIFF_MAX_LINES] + [f"... ({omitted} more lines)"]
    return "\n".join(lines)


def aggregate_case(case_id: str, observations: list[Observation]) -> dict:
    valid = [o for o in observations if o.harness_error is None]
    errors = [o for o in observations if o.harness_error is not None]

    n = len(valid)
    pass_count = sum(o.passed for o in valid)
    groups = _output_groups(valid)
    valid_classification = classify(valid)
    tokens = [o.completion_tokens for o in valid]
    latencies = [o.latency for o in valid]

    return {
        "case_id": case_id,
        "classification": "harness-error" if errors else valid_classification,
        "valid_classification": valid_classification,
        "repetitions": len(observations),
        "n": n,
        "pass_count": pass_count,
        "pass_rate": pass_count / n if n else 0.0,
        "stages": dict(Counter(o.stage for o in valid)),
        "distinct_raw_outputs": len({o.raw_fingerprint for o in valid}),
        "distinct_effective_outputs": len(groups),
        "agreement_rate": len(groups[0]["reps"]) / n if n else 0.0,
        "completion_tokens": {
            "min": min(tokens) if tokens else 0,
            "mean": statistics.fmean(tokens) if tokens else 0.0,
            "max": max(tokens) if tokens else 0,
        },
        "latency": {
            "mean": statistics.fmean(latencies) if latencies else 0.0,
            "stdev": statistics.stdev(latencies) if len(latencies) > 1 else 0.0,
        },
        "finish_reasons": sorted({str(o.finish_reason) for o in valid}),
        "system_fingerprints": sorted({o.system_fingerprint for o in valid if o.system_fingerprint}),
        "harness_errors": [{"rep": o.rep, "error": o.harness_error} for o in errors],
        # Only worth the space when the reps actually disagree.
        "output_groups": groups if len(groups) > 1 else [],
        "sample_diff": _sample_diff(groups),
    }


def _instability_key(case: dict) -> tuple:
    """Most unstable first: flaky (closest to a coin flip), harness errors,
    outcome-stable, equivalent, identical; lowest agreement first within each."""
    p = case["pass_rate"]
    return (
        CLASSIFICATIONS.index(case["classification"]) if case["classification"] in CLASSIFICATIONS else len(CLASSIFICATIONS),
        -min(p, 1 - p),
        case["agreement_rate"],
        case["case_id"],
    )


def aggregate_suite(
    suite: str,
    criterion: str,
    repetitions: list[tuple[int, list[tuple[str, Observation]], str]],
) -> dict:
    """`repetitions` is (rep number, (case id, observation) per case, config name)."""
    case_order: list[str] = []
    by_case: dict[str, list[Observation]] = {}
    per_rep_rates: list[dict] = []

    for rep, observations, _config in repetitions:
        valid = [o for _case_id, o in observations if o.harness_error is None]
        per_rep_rates.append({
            "rep": rep,
            "pass_count": sum(o.passed for o in valid),
            "n": len(valid),
            "pass_rate": sum(o.passed for o in valid) / len(valid) if valid else 0.0,
        })
        for case_id, observation in observations:
            if case_id not in by_case:
                case_order.append(case_id)
                by_case[case_id] = []
            by_case[case_id].append(observation)

    cases = [aggregate_case(case_id, by_case[case_id]) for case_id in case_order]
    scored = [c for c in cases if c["n"]]
    rates = [r["pass_rate"] for r in per_rep_rates if r["n"]]

    return {
        "suite": suite,
        "configs": sorted({config for _rep, _obs, config in repetitions}),
        "criterion": criterion,
        "repetitions": len(repetitions),
        "summary": {
            "total_cases": len(cases),
            "classifications": {
                name: sum(1 for c in cases if c["classification"] == name)
                for name in CLASSIFICATIONS
            },
            "mean_case_pass_rate": statistics.fmean(c["pass_rate"] for c in scored) if scored else 0.0,
            "pass_all": sum(1 for c in scored if c["pass_count"] == c["n"]),
            "pass_any": sum(1 for c in scored if c["pass_count"] > 0),
            "pass_none": sum(1 for c in scored if c["pass_count"] == 0),
            "per_repetition": per_rep_rates,
            "repetition_pass_rate": {
                "mean": statistics.fmean(rates) if rates else 0.0,
                "stdev": statistics.stdev(rates) if len(rates) > 1 else 0.0,
                "min": min(rates) if rates else 0.0,
                "max": max(rates) if rates else 0.0,
            },
            "most_unstable": [c["case_id"] for c in sorted(cases, key=_instability_key)
                              if c["classification"] != "identical"],
        },
        "cases": cases,
    }


# --------------------------------------------------------------------------- #
# reading a reproducibility run back from disk
# --------------------------------------------------------------------------- #


def repetition_directories(suite_directory: Path) -> list[Path]:
    """Completed repetitions (those with a report.json), in order."""
    if not suite_directory.is_dir():
        return []
    return sorted(
        p for p in suite_directory.iterdir()
        if p.is_dir() and p.name.startswith("rep-") and (p / "report.json").exists()
    )


def _rep_number(directory: Path) -> int:
    return int(directory.name.removeprefix("rep-"))


def _needs_validation(suite: str, reports: list[dict]) -> bool:
    """True for a sonar suite whose repetitions were generated with
    --no-sonar and have not been through validate_sonar_run yet (see
    run_all_reproducibility.py) - there is nothing to grade until then."""
    return suite == "sonar" and all(report.get("validated") is False for report in reports)


def aggregate_suite_directory(suite: str, suite_directory: Path) -> dict | None:
    reports = [
        (_rep_number(d), ResultsManager.load_report(d))
        for d in repetition_directories(suite_directory)
    ]
    if not reports or _needs_validation(suite, [report for _rep, report in reports]):
        return None

    if suite == "markdown":
        criterion = MARKDOWN_CRITERION
        build = lambda case, rep: from_markdown(MarkdownCaseResult(**case), rep)
    else:
        # Grade on the full clean-fix criterion whenever SonarQube ran; a run
        # made with --no-sonar can only be judged on its tests.
        analyzed = any(report.get("sonar_analyzed") for _rep, report in reports)
        criterion = SONAR_CLEAN_FIX if analyzed else SONAR_TESTS_PASSED
        build = lambda case, rep: from_sonar(SonarCaseResult(**case), rep, criterion)

    repetitions = [
        (rep, [(case["case_id"], build(case, rep)) for case in report["cases"]], report.get("config", ""))
        for rep, report in reports
    ]
    return aggregate_suite(suite, criterion, repetitions)


def _pending_validation(run_directory: Path) -> list[str]:
    pending = []
    for suite in SUITES:
        suite_directory = run_directory / suite
        reports = [ResultsManager.load_report(d) for d in repetition_directories(suite_directory)]
        if reports and _needs_validation(suite, reports):
            pending.append(suite)
    return pending


def aggregate_run(run_directory: Path, settings: dict | None = None) -> dict:
    return {
        "settings": settings or {},
        "suites": {
            suite: aggregate
            for suite in SUITES
            if (aggregate := aggregate_suite_directory(suite, run_directory / suite)) is not None
        },
        # Suites generated with --no-sonar: nothing to grade until
        # validate_sonar_run has compiled and tested each repetition.
        "pending_validation": _pending_validation(run_directory),
    }
