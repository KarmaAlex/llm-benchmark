import shutil
from pathlib import Path

import pytest

from runner.sonar_tests.patch_applier import PatchApplier

pytestmark = pytest.mark.skipif(shutil.which("patch") is None, reason="needs the 'patch' utility")

SOURCE = (
    "package demo;\n"
    "\n"
    "public class Cart {\n"
    "\n"
    "    private final List<String> items = new ArrayList<>();\n"
    "\n"
    "    public boolean isEmpty() {\n"
    "        return items.size() == 0;\n"
    "    }\n"
    "\n"
    "    public int count() {\n"
    "        return items.size();\n"
    "    }\n"
    "\n"
    "    public void clear() {\n"
    "        items.clear();\n"
    "    }\n"
    "}\n"
)

FIXED = SOURCE.replace("items.size() == 0", "items.isEmpty()")

HEADERS = "--- a/Cart.java\n+++ b/Cart.java\n"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "Cart.java").write_text(SOURCE, encoding="utf-8")
    return tmp_path


def read(project: Path) -> str:
    return (project / "Cart.java").read_text(encoding="utf-8")


def test_applies_well_formed_patch(project: Path):
    patch = HEADERS + (
        "@@ -6,5 +6,5 @@\n"
        " \n"
        "     public boolean isEmpty() {\n"
        "-        return items.size() == 0;\n"
        "+        return items.isEmpty();\n"
        "     }\n"
    )

    result = PatchApplier.apply(project, patch)

    assert result.applied, result.error
    assert read(project) == FIXED


def test_applies_bare_hunk_header_without_line_numbers(project: Path):
    patch = HEADERS + (
        "@@\n"
        "     public boolean isEmpty() {\n"
        "-        return items.size() == 0;\n"
        "+        return items.isEmpty();\n"
        "     }\n"
    )

    result = PatchApplier.apply(project, patch)

    assert result.applied, result.error
    assert read(project) == FIXED


def test_applies_hunk_with_miscounted_header(project: Path):
    patch = HEADERS + (
        "@@ -7,9 +7,12 @@\n"
        "     public boolean isEmpty() {\n"
        "-        return items.size() == 0;\n"
        "+        return items.isEmpty();\n"
        "     }\n"
    )

    result = PatchApplier.apply(project, patch)

    assert result.applied, result.error
    assert read(project) == FIXED


def test_applies_hunk_with_lopsided_context(project: Path):
    # Seven lines of leading context against one trailing line: raw GNU patch
    # takes this as "must match at end of file" and rejects it.
    leading = "".join(" " + line + "\n" for line in SOURCE.split("\n")[:7])
    patch = HEADERS + (
        "@@ -1,9 +1,9 @@\n"
        + leading
        + "-        return items.size() == 0;\n"
        "+        return items.isEmpty();\n"
        "     }\n"
    )

    result = PatchApplier.apply(project, patch)

    assert result.applied, result.error
    assert read(project) == FIXED


def test_tolerates_whitespace_differences_in_context(project: Path):
    # The context lines between the two changes carry an extra space of
    # indentation. They sit mid-hunk, so patch's fuzz can't drop them.
    patch = HEADERS + (
        "@@ -7,6 +7,6 @@\n"
        "     public boolean isEmpty() {\n"
        "-        return items.size() == 0;\n"
        "+        return items.isEmpty();\n"
        "      }\n"
        "\n"
        "      public int count() {\n"
        "-        return items.size();\n"
        "+        return this.items.size();\n"
        "     }\n"
    )

    result = PatchApplier.apply(project, patch)

    assert result.applied, result.error
    assert read(project) == FIXED.replace("return items.size();", "return this.items.size();")


def test_applies_multiple_bare_hunks(project: Path):
    patch = HEADERS + (
        "@@\n"
        "     public boolean isEmpty() {\n"
        "-        return items.size() == 0;\n"
        "+        return items.isEmpty();\n"
        "     }\n"
        "@@\n"
        "     public void clear() {\n"
        "-        items.clear();\n"
        "+        this.items.clear();\n"
        "     }\n"
    )

    result = PatchApplier.apply(project, patch)

    assert result.applied, result.error
    assert read(project) == FIXED.replace("        items.clear();", "        this.items.clear();")


def test_failed_hunk_reports_patch_output(project: Path):
    patch = HEADERS + (
        "@@ -6,5 +6,5 @@\n"
        "     public boolean isEmpty() {\n"
        "-        return items.length() == 0;\n"
        "+        return items.isEmpty();\n"
        "     }\n"
    )

    result = PatchApplier.apply(project, patch)

    assert not result.applied
    assert "FAILED" in result.error
    assert read(project) == SOURCE
    assert not list(project.glob("*.orig"))


def test_empty_patch_is_rejected(project: Path):
    result = PatchApplier.apply(project, "   \n")

    assert not result.applied
    assert result.error == "Model returned an empty patch."
