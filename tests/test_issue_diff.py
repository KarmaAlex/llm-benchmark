from runner.sonar_tests.issue_diff import compare, normalize, normalize_all

EXPECTED = {
    "rule": "java:S2259",
    "file": "src/main/java/com/benchmark/UserService.java",
    "line": 18,
    "message": 'A "NullPointerException" could be thrown; "user" is nullable here.',
}


def finding(rule, file, line, message="msg", **extra):
    return {"rule": rule, "file": file, "line": line, "message": message, **extra}


def target(line=18, message=EXPECTED["message"]):
    return finding(EXPECTED["rule"], EXPECTED["file"], line, message)


def test_target_resolved_when_rule_gone_from_file():
    comparison = compare(EXPECTED, [target()], [])
    assert comparison.target_resolved
    assert comparison.remaining_target == []


def test_target_not_resolved_when_rule_still_on_file():
    still_there = target(line=22)
    comparison = compare(EXPECTED, [target()], [still_there])
    assert not comparison.target_resolved
    assert comparison.remaining_target == [still_there]


def test_line_shift_alone_does_not_count_as_resolved_or_new():
    """The whole point of matching on (rule, file, message): a patch that
    only moves the violation down a few lines has fixed nothing."""
    comparison = compare(EXPECTED, [target(line=18)], [target(line=31)])
    assert not comparison.target_resolved
    assert comparison.new_issues == []


def test_rule_moved_to_another_file_counts_as_resolved_but_new():
    elsewhere = finding(EXPECTED["rule"], "src/main/java/com/benchmark/Other.java", 5)
    comparison = compare(EXPECTED, [target()], [elsewhere])
    assert comparison.target_resolved
    assert comparison.new_issues == [elsewhere]


def test_new_issue_detected():
    smell = finding("java:S1481", EXPECTED["file"], 9, "Remove this unused local variable")
    comparison = compare(EXPECTED, [target()], [smell])
    assert comparison.new_issues == [smell]
    assert comparison.after_count == 1
    assert comparison.baseline_count == 1


def test_preexisting_issue_on_another_file_is_not_new():
    preexisting = finding("java:S1192", "src/main/java/com/benchmark/User.java", 4, "dup")
    comparison = compare(EXPECTED, [target(), preexisting], [dict(preexisting, line=7)])
    assert comparison.new_issues == []
    assert comparison.target_resolved


def test_extra_occurrence_of_an_existing_rule_is_new():
    """Two before, three after: exactly one is a regression."""
    dup = finding("java:S1192", EXPECTED["file"], 3, "Define a constant")
    baseline = [target(), dup, dict(dup, line=8)]
    after = [dict(dup, line=3), dict(dup, line=8), dict(dup, line=12)]
    comparison = compare(EXPECTED, baseline, after)
    assert len(comparison.new_issues) == 1
    assert comparison.new_issues[0]["rule"] == "java:S1192"


def test_renamed_identifier_in_preexisting_finding_is_not_new():
    """S2077: switching to PreparedStatement renames the pre-existing
    unclosed-resource finding, it doesn't add one."""
    before = finding("java:S2095", EXPECTED["file"], 17,
                     'Use try-with-resources or close this "Statement" in a "finally" clause.')
    after = finding("java:S2095", EXPECTED["file"], 17,
                    'Use try-with-resources or close this "PreparedStatement" in a "finally" clause.')
    comparison = compare(EXPECTED, [target(), before], [after])
    assert comparison.new_issues == []
    assert comparison.target_resolved


def test_changed_metric_in_remaining_target_is_not_also_new():
    expected = {"rule": "java:S3776", "file": EXPECTED["file"], "line": 7, "message": ""}
    before = finding("java:S3776", EXPECTED["file"], 7,
                     "Refactor this method to reduce its Cognitive Complexity from 28 to the 15 allowed.")
    after = dict(before, message="Refactor this method to reduce its Cognitive Complexity from 17 to the 15 allowed.")
    comparison = compare(expected, [before], [after])
    assert not comparison.target_resolved
    assert comparison.new_issues == []


def test_new_unused_import_is_still_new_next_to_renamed_finding():
    before = finding("java:S2095", EXPECTED["file"], 17, 'close this "Statement"')
    renamed = dict(before, message='close this "PreparedStatement"')
    unused = finding("java:S1128", EXPECTED["file"], 6, "Remove this unused import 'java.sql.Statement'.")
    comparison = compare(EXPECTED, [target(), before], [renamed, unused])
    assert comparison.new_issues == [unused]


def test_identical_duplicates_are_counted_not_deduplicated():
    dup = finding("java:S1192", EXPECTED["file"], 3, "Define a constant")
    comparison = compare(EXPECTED, [], [dup, dict(dup), dict(dup)])
    assert len(comparison.new_issues) == 3


def test_resolved_incidental_counts_other_removed_findings():
    smell = finding("java:S1481", EXPECTED["file"], 9, "unused")
    comparison = compare(EXPECTED, [target(), smell], [])
    assert comparison.resolved_incidental == 1


def test_normalize_strips_the_project_key_prefix():
    raw = {
        "rule": "java:S2259",
        "component": "benchmark-run-1-S2259:src/main/java/com/benchmark/UserService.java",
        "line": 18,
        "message": "boom",
        "severity": "MAJOR",
        "type": "BUG",
        "status": "OPEN",
    }
    assert normalize(raw, "benchmark-run-1-S2259") == {
        "rule": "java:S2259",
        "file": "src/main/java/com/benchmark/UserService.java",
        "line": 18,
        "message": "boom",
        "severity": "MAJOR",
        "type": "BUG",
        "status": "OPEN",
    }


def test_normalize_handles_hotspots():
    raw = {
        "ruleKey": "java:S2077",
        "component": "key:src/main/java/com/benchmark/Dao.java",
        "line": 42,
        "message": "sql",
        "vulnerabilityProbability": "HIGH",
        "status": "TO_REVIEW",
    }
    normalized = normalize(raw, "key")
    assert normalized["rule"] == "java:S2077"
    assert normalized["type"] == "SECURITY_HOTSPOT"
    assert normalized["severity"] == "HIGH"
    assert normalized["file"] == "src/main/java/com/benchmark/Dao.java"


def test_normalize_records_flow_locations():
    raw = {
        "rule": "java:S2259",
        "component": "key:A.java",
        "line": 18,
        "message": "npe",
        "flows": [{"locations": [{"textRange": {"startLine": 12}}, {"textRange": {"startLine": 15}}]}],
    }
    assert normalize(raw, "key")["secondary_lines"] == [12, 15]


def test_normalize_omits_flow_key_when_there_are_none():
    normalized = normalize({"rule": "r", "component": "key:A.java", "line": 1}, "key")
    assert "secondary_lines" not in normalized


def test_normalize_all_is_line_order_preserving():
    raw = [
        {"rule": "r", "component": "key:A.java", "line": 3},
        {"rule": "r", "component": "key:A.java", "line": 1},
    ]
    assert [f["line"] for f in normalize_all(raw, "key")] == [3, 1]
