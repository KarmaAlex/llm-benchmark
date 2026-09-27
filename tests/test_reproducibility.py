import json
from dataclasses import asdict

from runner.cli.loading import resolve_config_name
from runner.markdown_tests.pipeline import failed_result as markdown_failed_result
from runner.models.markdown_case_result import MarkdownCaseResult
from runner.models.sonar_case_result import SonarCaseResult
from runner.reproducibility import aggregate as agg
from runner.reproducibility.observations import (
    NOT_APPLIED,
    SONAR_CLEAN_FIX,
    SONAR_TESTS_PASSED,
    from_markdown,
    from_sonar,
)
from runner.reproducibility.report import print_reproducibility_report


def md(response_text: str, matched: bool, case_id: str = "md001", tokens: int = 10) -> MarkdownCaseResult:
    return MarkdownCaseResult(
        case_id=case_id,
        difficulty=1,
        matched=matched,
        execution_time=1.0,
        completion_tokens=tokens,
        response_text=response_text,
    )


def sonar(diff: str | None, *, applied=True, tests_passed=True, resolved=True, new_issues=0,
          analyzed=True, response_text=None, tool_calls=None, case_id="S1000") -> SonarCaseResult:
    return SonarCaseResult(
        case_id=case_id,
        edit_mode="diff",
        applied=applied,
        compiled=applied,
        execution_time=2.0,
        compile_time=1.0,
        tests_ran=applied,
        tests_passed=applied and tests_passed,
        response_text=response_text if response_text is not None else (diff or ""),
        tool_calls=tool_calls,
        diff=diff,
        sonar_analyzed=analyzed and applied,
        target_resolved=resolved if analyzed and applied else None,
        new_issues_count=new_issues,
    )


def md_case(results: list[MarkdownCaseResult]) -> dict:
    return agg.aggregate_case("md001", [from_markdown(r, i + 1) for i, r in enumerate(results)])


def sonar_case(results: list[SonarCaseResult], criterion=SONAR_CLEAN_FIX) -> dict:
    return agg.aggregate_case("S1000", [from_sonar(r, i + 1, criterion) for i, r in enumerate(results)])


# --------------------------------------------------------------------------- #
# classification
# --------------------------------------------------------------------------- #


def test_identical_responses():
    case = md_case([md('{"a": 1}', True)] * 3)
    assert case["classification"] == "identical"
    assert case["pass_rate"] == 1.0
    assert case["agreement_rate"] == 1.0
    assert case["output_groups"] == [] and case["sample_diff"] is None


def test_markdown_key_order_and_fences_are_equivalent():
    case = md_case([
        md('{"a": 1, "b": 2}', True),
        md('```json\n{"b": 2, "a": 1}\n```', True),
    ])
    assert case["classification"] == "equivalent"
    assert case["distinct_raw_outputs"] == 2
    assert case["distinct_effective_outputs"] == 1


def test_sonar_diff_trailing_whitespace_is_equivalent():
    case = sonar_case([
        sonar("--- a\n+++ b\n+x = 1\n"),
        sonar("--- a  \r\n+++ b\r\n+x = 1   \r\n", response_text="Here you go:\n--- a\n+++ b\n+x = 1"),
    ])
    assert case["classification"] == "equivalent"


def test_different_outputs_same_verdict_is_outcome_stable():
    case = md_case([md('{"a": 2}', False), md('{"a": 3}', False), md("nonsense", False)])
    assert case["classification"] == "outcome-stable"
    assert case["distinct_effective_outputs"] == 3
    assert case["stages"] == {"mismatch": 2, "unparseable": 1}


def test_changing_verdict_is_flaky_with_groups_and_sample_diff():
    case = md_case([
        md('{"a": 1}', True), md('{"a": 1}', True), md('{"a": 2}', False), md('{"a": 1}', True),
    ])
    assert case["classification"] == "flaky"
    assert case["pass_count"] == 3 and case["n"] == 4
    assert case["agreement_rate"] == 0.75
    groups = case["output_groups"]
    assert [(g["label"], g["reps"], g["pass_count"]) for g in groups] == [("A", [1, 2, 4], 3), ("B", [3], 0)]
    assert '-  "a": 1' in case["sample_diff"] and '+  "a": 2' in case["sample_diff"]


def test_harness_errors_are_excluded_but_flagged():
    crash = markdown_failed_result("md001", "RuntimeError: boom")
    case = md_case([md('{"a": 1}', True), crash, md('{"a": 1}', True)])
    assert case["classification"] == "harness-error"
    assert case["valid_classification"] == "identical"
    assert case["n"] == 2 and case["pass_rate"] == 1.0
    assert case["harness_errors"] == [{"rep": 2, "error": "RuntimeError: boom"}]


def test_toolcall_raw_fingerprint_includes_tool_calls():
    call = lambda text: [{"name": "edit_file", "arguments": {"path": "A.java", "search": text, "replacement": "y"}}]
    first = sonar("--- same diff", response_text="", tool_calls=call("x"))
    second = sonar("--- same diff", response_text="", tool_calls=call("x "))
    case = sonar_case([first, second])
    assert case["distinct_raw_outputs"] == 2
    assert case["classification"] == "equivalent"


def test_sonar_stages_and_clean_fix_criterion():
    case = sonar_case([
        sonar("d1"),                        # clean fix
        sonar("d2", new_issues=1),          # resolved but introduced an issue
        sonar("d3", tests_passed=False),    # compiled, tests failed
        sonar(None, applied=False),         # patch never applied
    ])
    assert case["classification"] == "flaky"
    assert case["pass_count"] == 1
    assert case["stages"] == {"clean_fix": 1, "resolved": 1, "compiled": 1, "not_applied": 1}
    assert any(g["output"] == NOT_APPLIED for g in case["output_groups"])


def test_missing_sonar_verdict_is_a_harness_error_not_a_fail():
    case = sonar_case([sonar("d1"), sonar("d1", analyzed=False)])
    assert case["classification"] == "harness-error"
    assert case["n"] == 1 and case["pass_count"] == 1


def test_tests_passed_criterion_without_sonar():
    case = sonar_case([sonar("d1", analyzed=False), sonar("d1", analyzed=False)], SONAR_TESTS_PASSED)
    assert case["classification"] == "identical"
    assert case["pass_rate"] == 1.0


# --------------------------------------------------------------------------- #
# suite aggregate
# --------------------------------------------------------------------------- #


def _markdown_reps():
    # md001 always passes, md002 passes in rep 1 only, md003 never passes
    # (unparseable twice, then wrong JSON).
    return [
        [md('{"a": 1}', True, "md001"), md('{"b": 1}', True, "md002"), md("x", False, "md003")],
        [md('{"a": 1}', True, "md001"), md('{"b": 2}', False, "md002"), md("x", False, "md003")],
        [md('{"a": 1}', True, "md001"), md('{"b": 2}', False, "md002"), md('{"c": 9}', False, "md003")],
    ]


def test_suite_summary_counts_and_per_repetition_rates():
    repetitions = [
        (rep, [(r.case_id, from_markdown(r, rep)) for r in results], "cfg")
        for rep, results in enumerate(_markdown_reps(), start=1)
    ]
    suite = agg.aggregate_suite("markdown", "matched", repetitions)
    summary = suite["summary"]

    assert summary["classifications"]["identical"] == 1
    assert summary["classifications"]["flaky"] == 1
    assert summary["classifications"]["outcome-stable"] == 1
    assert (summary["pass_all"], summary["pass_any"], summary["pass_none"]) == (1, 2, 1)
    assert [r["pass_count"] for r in summary["per_repetition"]] == [2, 1, 1]
    assert summary["repetition_pass_rate"]["max"] == 2 / 3
    assert summary["most_unstable"] == ["md002", "md003"]
    assert [c["case_id"] for c in suite["cases"]] == ["md001", "md002", "md003"]


def _write_rep(directory, suite, rep, payload):
    rep_directory = directory / suite / f"rep-{rep:02d}"
    rep_directory.mkdir(parents=True)
    (rep_directory / "report.json").write_text(json.dumps(payload), encoding="utf-8")


def test_aggregate_run_reads_repetitions_from_disk(tmp_path, capsys):
    for rep, results in enumerate(_markdown_reps(), start=1):
        _write_rep(tmp_path, "markdown", rep, {
            "config": "cfg-markdown",
            "summary": {},
            "cases": [asdict(r) for r in results],
        })

    # An old-format sonar report, written before tool_calls/system_fingerprint/
    # tests_skipped existed, must still load.
    old_case = asdict(sonar("d1"))
    for key in ("tool_calls", "system_fingerprint", "tests_skipped"):
        del old_case[key]
    for rep in (1, 2):
        _write_rep(tmp_path, "sonar", rep, {
            "config": "cfg-sonar", "sonar_analyzed": True, "summary": {}, "cases": [old_case],
        })
    # An interrupted repetition (no report.json) is ignored.
    (tmp_path / "sonar" / "rep-03").mkdir()

    result = agg.aggregate_run(tmp_path, {"repetitions": 3})

    assert result["settings"] == {"repetitions": 3}
    assert result["suites"]["markdown"]["repetitions"] == 3
    assert result["suites"]["markdown"]["configs"] == ["cfg-markdown"]
    sonar_suite = result["suites"]["sonar"]
    assert sonar_suite["repetitions"] == 2
    assert sonar_suite["criterion"] == SONAR_CLEAN_FIX
    assert sonar_suite["cases"][0]["classification"] == "identical"
    json.dumps(result)  # serialisable as-is

    print_reproducibility_report(result)
    out = capsys.readouterr().out
    assert "Reproducibility: markdown (cfg-markdown)" in out
    assert "md002 - flaky, passed 1/3" in out


def test_resolve_config_name_prefers_suite_variant():
    # Both exist in configs/: qwen2.5-coder-7b-q4.yaml and -markdown.yaml.
    assert resolve_config_name("qwen2.5-coder-7b-q4", "markdown") == "qwen2.5-coder-7b-q4-markdown"
    assert resolve_config_name("gpt5", "sonar") == "gpt5-sonar"
    assert resolve_config_name("does-not-exist", "sonar") == "does-not-exist"
