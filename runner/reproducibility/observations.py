"""
One observation per (case, repetition): the fingerprints and verdict the
reproducibility aggregate compares across repetitions.

Three levels are compared, from strictest to loosest:

    raw        the exact model output (text, plus tool calls in toolcall mode)
    effective  what the harness actually acted on - the canonical parsed JSON
               for markdown, the normalised applied diff for sonar - so
               differences in fences, key order or trailing whitespace don't
               count as a different answer
    verdict    pass/fail under the suite's criterion

Observations are built from the per-case result dataclasses exactly as they
are stored in each repetition's report.json, so a finished run can be
re-aggregated from disk without calling the model.
"""

import hashlib
import json
from dataclasses import dataclass

from runner.markdown_tests.json_extractor import JsonExtractionError, JsonExtractor
from runner.models.markdown_case_result import MarkdownCaseResult
from runner.models.sonar_case_result import SonarCaseResult

UNPARSEABLE = "<unparseable>"
NOT_APPLIED = "<not-applied>"

# Pass criteria, recorded in the aggregate so a reader knows what "pass" meant.
MARKDOWN_CRITERION = "matched"
SONAR_CLEAN_FIX = "clean_fix"
SONAR_TESTS_PASSED = "tests_passed"


@dataclass(frozen=True)
class Observation:
    rep: int
    passed: bool
    stage: str
    raw_fingerprint: str | None = None
    effective_fingerprint: str | None = None
    effective_output: str | None = None
    harness_error: str | None = None
    completion_tokens: int = 0
    latency: float = 0.0
    finish_reason: str | None = None
    system_fingerprint: str | None = None


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False)


def normalize_diff(diff: str) -> str:
    lines = diff.replace("\r\n", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines).strip("\n")


def _is_harness_error(result: MarkdownCaseResult | SonarCaseResult) -> bool:
    """The shape failed_result() produces when a case raised before the
    model answered: there is nothing to compare, so it isn't a model
    outcome."""
    return result.response_text is None and result.error is not None and result.execution_time == 0


def _harness_error(rep: int, error: str) -> Observation:
    return Observation(rep=rep, passed=False, stage="error", harness_error=error)


def _usage(result: MarkdownCaseResult | SonarCaseResult) -> dict:
    return dict(
        completion_tokens=result.completion_tokens,
        latency=result.execution_time,
        finish_reason=result.finish_reason,
        system_fingerprint=result.system_fingerprint,
    )


def from_markdown(result: MarkdownCaseResult, rep: int) -> Observation:
    if _is_harness_error(result):
        return _harness_error(rep, result.error)

    text = result.response_text or ""
    try:
        effective = canonical_json(JsonExtractor.extract(text))
        stage = "matched" if result.matched else "mismatch"
    except JsonExtractionError:
        effective = UNPARSEABLE
        stage = "unparseable"

    return Observation(
        rep=rep,
        passed=result.matched,
        stage=stage,
        raw_fingerprint=sha256(text),
        effective_fingerprint=sha256(effective),
        effective_output=effective,
        **_usage(result),
    )


def sonar_stage(result: SonarCaseResult) -> str:
    """The last pipeline stage the case cleared before its first failure."""
    if not result.applied:
        return "not_applied"
    if not result.compiled:
        return "applied"
    if not result.tests_passed:
        return "compiled"
    if not result.target_resolved:
        return "tests_passed"
    if not result.clean_fix:
        return "resolved"
    return "clean_fix"


def from_sonar(result: SonarCaseResult, rep: int, criterion: str) -> Observation:
    if _is_harness_error(result):
        return _harness_error(rep, result.error)

    if criterion == SONAR_CLEAN_FIX and result.tests_passed and not result.sonar_analyzed:
        # The patch survived compile + test but SonarQube never looked at it
        # (server down, scanner crash): the verdict is unknown, not a fail.
        return _harness_error(rep, f"SonarQube analysis missing: {result.sonar_error}")

    raw = result.response_text or ""
    if result.tool_calls:
        raw += "\n" + canonical_json(result.tool_calls)

    effective = normalize_diff(result.diff or "") if result.applied else NOT_APPLIED
    passed = result.clean_fix if criterion == SONAR_CLEAN_FIX else result.tests_passed

    return Observation(
        rep=rep,
        passed=passed,
        stage=sonar_stage(result),
        raw_fingerprint=sha256(raw),
        effective_fingerprint=sha256(effective),
        effective_output=effective,
        **_usage(result),
    )
