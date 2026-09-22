import json

import pytest

from analysis import report


def write_run(tmp_path, name, payload):
    run_directory = tmp_path / name
    run_directory.mkdir()
    (run_directory / "report.json").write_text(json.dumps(payload), encoding="utf-8")
    return run_directory


MARKDOWN_REPORT = {
    "config": "Some-Model (markdown)",
    "summary": {"total_cases": 2, "matched_count": 1, "matched_rate": 0.5,
                "by_difficulty": {"1": {"total": 1, "matched": 1}, "3": {"total": 1, "matched": 0}}},
    "cases": [
        {"case_id": "md001", "difficulty": 1, "matched": True, "execution_time": 1.0},
        {"case_id": "md002", "difficulty": 3, "matched": False, "execution_time": 2.0,
         "error": "Output does not match.\nsecond line", "finish_reason": "length"},
    ],
}

SONAR_REPORT = {
    "config": "Some-Model (sonar)",
    "edit_mode": "diff",
    "summary": {"total_cases": 2, "applied_rate": 1.0},
    "cases": [
        {"case_id": "S1", "applied": True, "compiled": True, "tests_ran": True, "tests_passed": True,
         "tests_run_count": 3, "tests_failed": 0, "tests_errored": 0,
         "sonar_analyzed": True, "target_resolved": True, "new_issues_count": 0},
        {"case_id": "S2", "applied": True, "compiled": True, "tests_ran": True, "tests_passed": True,
         "tests_run_count": 2, "tests_failed": 0, "tests_errored": 0,
         "sonar_analyzed": True, "target_resolved": True, "new_issues_count": 1,
         "new_issues": [{"rule": "java:S1481", "file": "src/main/java/A.java", "line": 9,
                         "message": "Remove this unused local variable"}]},
    ],
}


def test_detects_markdown_from_summary():
    assert report.detect_suite(MARKDOWN_REPORT) == "markdown"


def test_detects_sonar_from_summary():
    assert report.detect_suite(SONAR_REPORT) == "sonar"


def test_detects_suite_from_cases_when_summary_is_empty():
    """An interrupted run can leave a report without a usable summary."""
    assert report.detect_suite({"summary": {}, "cases": [{"matched": False}]}) == "markdown"
    assert report.detect_suite({"summary": {}, "cases": [{"applied": False}]}) == "sonar"


def test_unknown_suite_is_reported_not_guessed():
    assert report.detect_suite({"summary": {}, "cases": []}) == "unknown"


def test_clean_fix_requires_all_three_conditions():
    base = {"tests_passed": True, "target_resolved": True, "new_issues_count": 0}
    assert report.clean_fix(base)
    assert not report.clean_fix({**base, "tests_passed": False})
    assert not report.clean_fix({**base, "target_resolved": False})
    assert not report.clean_fix({**base, "new_issues_count": 2})


def test_clean_fix_is_false_for_an_unanalyzed_case():
    """target_resolved is None when SonarQube never ran - that is not a pass."""
    assert not report.clean_fix({"tests_passed": True, "target_resolved": None, "new_issues_count": 0})


@pytest.mark.parametrize("case,expected", [
    ({"applied": False}, "patch did not apply"),
    ({"applied": True, "compiled": False}, "project did not compile"),
    ({"applied": True, "compiled": True, "tests_passed": False}, "existing tests failed"),
    ({"applied": True, "compiled": True, "tests_passed": True}, "not analyzed by SonarQube"),
    ({"applied": True, "compiled": True, "tests_passed": True, "sonar_analyzed": True,
      "target_resolved": False}, "reported issue still present"),
    ({"applied": True, "compiled": True, "tests_passed": True, "sonar_analyzed": True,
      "target_resolved": True, "new_issues_count": 1}, "introduced new issues"),
    ({"applied": True, "compiled": True, "tests_passed": True, "sonar_analyzed": True,
      "target_resolved": True, "new_issues_count": 0}, None),
])
def test_dropout_reason_names_the_first_failed_stage(case, expected):
    assert report.dropout_reason(case) == expected


def test_tests_cell_counts_failures_and_errors_as_not_passing():
    assert report.tests_cell({"tests_ran": True, "tests_run_count": 5,
                              "tests_failed": 1, "tests_errored": 1}) == "3/5"
    assert report.tests_cell({"tests_ran": False}) == "-"


def test_truncate_takes_the_first_line_only():
    assert report.truncate("first\nsecond", 40) == "first"
    assert report.truncate("", 10) == ""
    assert report.truncate(None, 10) == ""


def test_truncate_clips_with_an_ellipsis():
    assert report.truncate("abcdefghij", 5) == "abcd…"


def test_percent_and_bar_handle_an_empty_run():
    assert report.percent(0, 0) == "n/a"
    assert report.bar(0, 0) == ""


def test_markdown_report_renders(tmp_path, capsys):
    report.print_report(write_run(tmp_path, "2026-01-01_00-00-00", MARKDOWN_REPORT), verbose=False)
    out = capsys.readouterr().out
    assert "Markdown extraction" in out
    assert "matched expected" in out
    assert "Hit the token limit (1): md002" in out
    assert "second line" not in out  # truncated in the table


def test_markdown_verbose_shows_the_whole_error(tmp_path, capsys):
    report.print_report(write_run(tmp_path, "2026-01-01_00-00-00", MARKDOWN_REPORT), verbose=True)
    assert "second line" in capsys.readouterr().out


def test_sonar_report_renders(tmp_path, capsys):
    report.print_report(write_run(tmp_path, "2026-01-01_00-00-00", SONAR_REPORT), verbose=False)
    out = capsys.readouterr().out
    assert "Sonar issue resolution" in out
    assert "edit mode: diff" in out
    assert "clean fix" in out
    assert "New issues introduced (1 across 1 case(s))" in out
    assert "java:S1481" in out


def test_sonar_report_without_analysis_says_so(tmp_path, capsys):
    unanalyzed = {**SONAR_REPORT,
                  "cases": [{**c, "sonar_analyzed": False, "target_resolved": None}
                            for c in SONAR_REPORT["cases"]]}
    report.print_report(write_run(tmp_path, "2026-01-01_00-00-00", unanalyzed), verbose=False)
    out = capsys.readouterr().out
    assert "no SonarQube analysis" in out
    assert "runner.analyze_sonar_run" in out


def test_unrecognizable_report_is_rejected(tmp_path):
    run_directory = write_run(tmp_path, "2026-01-01_00-00-00", {"cases": []})
    with pytest.raises(SystemExit):
        report.print_report(run_directory, verbose=False)


def test_missing_run_directory_is_rejected():
    with pytest.raises(SystemExit):
        report.resolve_run_directory("no-such-run")
