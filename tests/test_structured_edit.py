from pathlib import Path

import pytest

from runner.sonar_tests.structured_edit import (
    AmbiguousMatchError,
    EditCall,
    FuzzyMatcher,
    NoMatchError,
    StructuredEditParseError,
    StructuredEditParser,
    apply_edits,
    generate_diff,
)


# ---------------------------------------------------------------------------
# FuzzyMatcher.find_match
# ---------------------------------------------------------------------------

def test_exact_match_found_verbatim():
    text = "line one\nline two\nline three\n"
    match = FuzzyMatcher.find_match(text, "line two", occurrence=1)

    assert match.kind == "exact"
    assert match.similarity == 1.0
    assert text[match.start:match.end] == "line two"


def test_exact_match_honors_occurrence():
    text = "dup\nmiddle\ndup\nend\n"
    match = FuzzyMatcher.find_match(text, "dup", occurrence=2)

    # second "dup" starts after "dup\nmiddle\n"
    assert text[match.start:match.end] == "dup"
    assert match.start == text.index("dup", text.index("dup") + 1)
    assert match.kind == "exact"


def test_fuzzy_match_with_whitespace_drift():
    text = (
        "public boolean isValid() {\n"
        "        if (flag == true) {\n"
        "            return true;\n"
        "        }\n"
        "        return false;\n"
        "}\n"
    )
    # Model reproduces the same two lines but re-indents them (e.g. tabs
    # instead of spaces, or a different indent width), so this is not a
    # literal substring of the file even though it's clearly the same code.
    search = "  if (flag == true) {\n    return true;"
    match = FuzzyMatcher.find_match(text, search, occurrence=1)

    assert match.kind == "fuzzy"
    assert 0.0 < match.similarity < 1.0
    assert "if (flag == true) {" in text[match.start:match.end]


def test_ambiguous_match_is_rejected():
    # Two near-identical, non-overlapping blocks; search matches neither
    # exactly but is equally close to both.
    text = (
        "if (userA.isActive()) {\n"
        "    process(userA);\n"
        "}\n"
        "\n"
        "if (userB.isActive()) {\n"
        "    process(userB);\n"
        "}\n"
    )
    search = "if (userC.isActive()) {\n    process(userC);\n}"

    with pytest.raises(AmbiguousMatchError):
        FuzzyMatcher.find_match(text, search, occurrence=1)


def test_no_match_raises_clean_error():
    text = "completely unrelated file content\nwith nothing similar\n"
    search = "totally different text that does not appear anywhere near this"

    with pytest.raises(NoMatchError):
        FuzzyMatcher.find_match(text, search, occurrence=1)


def test_blank_line_heavy_exact_match():
    text = (
        "public void reset() {\n"
        "    this.value = null;\n"
        "\n"
        "\n"
        "    this.other = null;\n"
        "}\n"
    )
    search = "this.value = null;\n\n\n    this.other = null;"
    match = FuzzyMatcher.find_match(text, search, occurrence=1)

    assert match.kind == "exact"


def test_blank_line_heavy_fuzzy_match_collapsed_blank_lines():
    text = (
        "public void reset() {\n"
        "    this.value = null;\n"
        "\n"
        "\n"
        "    this.other = null;\n"
        "}\n"
    )
    # Model collapsed the double blank line into a single blank line.
    search = "this.value = null;\n\n    this.other = null;"
    match = FuzzyMatcher.find_match(text, search, occurrence=1)

    assert match.kind == "fuzzy"
    assert match.similarity >= 0.75


# ---------------------------------------------------------------------------
# apply_edits / generate_diff
# ---------------------------------------------------------------------------

def test_apply_edits_multi_file_sequencing(tmp_path: Path):
    file_a = tmp_path / "A.java"
    file_b = tmp_path / "B.java"
    file_a.write_text(
        "public class A {\n"
        "    int x = 1;\n"
        "    int y = 2;\n"
        "}\n",
        encoding="utf-8",
    )
    file_b.write_text(
        "public class B {\n"
        "    String name = \"old\";\n"
        "}\n",
        encoding="utf-8",
    )

    edits = [
        EditCall(path="A.java", search="int x = 1;", replacement="int x = 10;"),
        EditCall(path="A.java", search="int y = 2;", replacement="int y = 20;"),
        EditCall(path="B.java", search='String name = "old";', replacement='String name = "new";'),
    ]

    result = apply_edits(tmp_path, edits)

    assert result.applied is True
    assert len(result.edit_results) == 3
    assert all(o.applied for o in result.edit_results)

    updated_a = file_a.read_text(encoding="utf-8")
    assert "int x = 10;" in updated_a
    assert "int y = 20;" in updated_a

    updated_b = file_b.read_text(encoding="utf-8")
    assert 'String name = "new";' in updated_b

    assert "--- a/A.java" in result.diff
    assert "+++ b/A.java" in result.diff
    assert "--- a/B.java" in result.diff


def test_apply_edits_reports_per_edit_failures_independently(tmp_path: Path):
    file_a = tmp_path / "A.java"
    file_a.write_text("public class A {\n    int x = 1;\n}\n", encoding="utf-8")

    edits = [
        EditCall(path="A.java", search="int x = 1;", replacement="int x = 10;"),
        EditCall(path="A.java", search="does not exist anywhere in this file", replacement="whatever"),
    ]

    result = apply_edits(tmp_path, edits)

    assert result.applied is False
    assert result.edit_results[0].applied is True
    assert result.edit_results[1].applied is False
    assert result.edit_results[1].error is not None

    # The successful edit was still applied to disk despite the other failing.
    assert "int x = 10;" in file_a.read_text(encoding="utf-8")


def test_generate_diff_produces_standard_unified_diff():
    original = {"foo.txt": "hello\nworld\n"}
    updated = {"foo.txt": "hello\nthere\n"}

    diff = generate_diff(original, updated)

    assert "--- a/foo.txt" in diff
    assert "+++ b/foo.txt" in diff
    assert "-world" in diff
    assert "+there" in diff


# ---------------------------------------------------------------------------
# StructuredEditParser
# ---------------------------------------------------------------------------

def test_parser_accepts_fenced_json_array():
    raw = (
        "```json\n"
        "[\n"
        '  {"path": "Foo.java", "search": "a", "replacement": "b"}\n'
        "]\n"
        "```"
    )
    edits = StructuredEditParser.parse(raw)

    assert edits == [EditCall(path="Foo.java", search="a", replacement="b", occurrence=1)]


def test_parser_accepts_multiple_edits_with_occurrence():
    raw = (
        "```json\n"
        "[\n"
        '  {"path": "Foo.java", "search": "a", "replacement": "b"},\n'
        '  {"path": "Bar.java", "search": "c", "replacement": "d", "occurrence": 2}\n'
        "]\n"
        "```"
    )
    edits = StructuredEditParser.parse(raw)

    assert len(edits) == 2
    assert edits[1].occurrence == 2


def test_parser_rejects_malformed_json():
    raw = "```json\n[{\"path\": \"Foo.java\", broken}]\n```"

    with pytest.raises(StructuredEditParseError):
        StructuredEditParser.parse(raw)


def test_parser_rejects_non_array_payload():
    raw = '```json\n{"path": "Foo.java", "search": "a", "replacement": "b"}\n```'

    with pytest.raises(StructuredEditParseError):
        StructuredEditParser.parse(raw)


def test_parser_rejects_missing_required_field():
    raw = '```json\n[{"path": "Foo.java", "search": "a"}]\n```'

    with pytest.raises(StructuredEditParseError):
        StructuredEditParser.parse(raw)
