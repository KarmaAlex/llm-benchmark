"""
Structured, line-number-free edit interface.

Replaces unified-diff generation with a single canonical edit operation
(`EditCall`) that the model can produce either via native tool/function
calling or via a parsed structured-text fallback. The harness — not the
model — locates the edit target in real file content (exact match first,
fuzzy fallback second), applies it, and computes the final unified diff
for scoring.
"""

import difflib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Tool schema (native function-calling path)
# ---------------------------------------------------------------------------

EDIT_FILE_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "edit_file",
        "description": (
            "Replace a piece of code in a file. Identify the target by its "
            "exact surrounding content (the 'search' text), never by line "
            "number. If the same text appears more than once in the file, "
            "use 'occurrence' to pick which one (1 = first). Call this tool "
            "once per distinct change; call it multiple times for multiple "
            "changes, including across different files."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path of the file to edit, relative to the project root.",
                },
                "search": {
                    "type": "string",
                    "description": (
                        "The exact text to find in the file, including any "
                        "surrounding blank lines needed to make it unambiguous."
                    ),
                },
                "replacement": {
                    "type": "string",
                    "description": "The text that should replace 'search'.",
                },
                "occurrence": {
                    "type": "integer",
                    "description": "Which occurrence of 'search' to replace (1-indexed). Defaults to 1.",
                    "default": 1,
                },
            },
            "required": ["path", "search", "replacement"],
        },
    },
}


# ---------------------------------------------------------------------------
# Canonical edit representation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EditCall:
    path: str
    search: str
    replacement: str
    occurrence: int = 1


# ---------------------------------------------------------------------------
# Text-mode parsing
# ---------------------------------------------------------------------------

class StructuredEditParseError(Exception):
    """
    Raised with a precise, model-facing message so it can be reused as-is
    in a re-prompt/retry loop.
    """


_REQUIRED_FIELDS = ("path", "search", "replacement")


class StructuredEditParser:

    @staticmethod
    def parse(raw_text: str) -> list[EditCall]:
        block = StructuredEditParser._extract_json_block(raw_text)

        try:
            data = json.loads(block)
        except json.JSONDecodeError as e:
            raise StructuredEditParseError(
                f"Could not parse the JSON array: {e}. "
                "Return a single ```json fenced block containing a JSON "
                "array of edit objects."
            ) from e

        if not isinstance(data, list):
            raise StructuredEditParseError(
                "Expected a JSON array of edit objects, got "
                f"{type(data).__name__}."
            )

        if not data:
            raise StructuredEditParseError(
                "The edit array is empty; at least one edit is required."
            )

        edits: list[EditCall] = []
        for index, entry in enumerate(data):
            edits.append(StructuredEditParser._parse_entry(entry, index))

        return edits

    @staticmethod
    def _extract_json_block(raw_text: str) -> str:
        text = raw_text.strip()

        fenced = re.search(
            r"```(?:json)?\s*\n?(.*?)\n?```",
            text,
            re.DOTALL | re.IGNORECASE,
        )

        if fenced:
            return fenced.group(1).strip()

        return text

    @staticmethod
    def _parse_entry(entry: Any, index: int) -> EditCall:
        if not isinstance(entry, dict):
            raise StructuredEditParseError(
                f"Edit at index {index} must be a JSON object, got "
                f"{type(entry).__name__}."
            )

        missing = [f for f in _REQUIRED_FIELDS if f not in entry]
        if missing:
            raise StructuredEditParseError(
                f"Edit at index {index} is missing required field(s): "
                f"{', '.join(missing)}."
            )

        for f in _REQUIRED_FIELDS:
            if not isinstance(entry[f], str):
                raise StructuredEditParseError(
                    f"Edit at index {index}: field '{f}' must be a string, "
                    f"got {type(entry[f]).__name__}."
                )

        occurrence = entry.get("occurrence", 1)
        if not isinstance(occurrence, int) or isinstance(occurrence, bool) or occurrence < 1:
            raise StructuredEditParseError(
                f"Edit at index {index}: field 'occurrence' must be a "
                "positive integer."
            )

        return EditCall(
            path=entry["path"],
            search=entry["search"],
            replacement=entry["replacement"],
            occurrence=occurrence,
        )


# ---------------------------------------------------------------------------
# Fuzzy matching
# ---------------------------------------------------------------------------

FUZZY_SIMILARITY_THRESHOLD = 0.75
FUZZY_AMBIGUITY_MARGIN = 0.02


@dataclass(frozen=True)
class MatchResult:
    start: int
    end: int
    kind: str  # "exact" | "fuzzy"
    similarity: float


class NoMatchError(Exception):
    def __init__(self, message: str, similarity: float | None = None):
        super().__init__(message)
        self.similarity = similarity


class AmbiguousMatchError(Exception):
    def __init__(self, message: str, candidates: list[float]):
        super().__init__(message)
        self.candidates = candidates


def _normalize(text: str) -> str:
    """
    Collapse blank-line runs and strip leading/trailing whitespace per line.

    Leading whitespace has to go too: models routinely copy code without its
    indentation, and scoring it would bias the match towards shorter windows
    (a dropped closing `}` line costs less similarity than its indent adds).
    """
    lines = [line.strip() for line in text.splitlines()]
    normalized_lines: list[str] = []
    previous_blank = False
    for line in lines:
        is_blank = line == ""
        if is_blank and previous_blank:
            continue
        normalized_lines.append(line)
        previous_blank = is_blank
    return "\n".join(normalized_lines)


class FuzzyMatcher:

    @staticmethod
    def find_match(file_text: str, search: str, occurrence: int = 1) -> MatchResult:
        exact = FuzzyMatcher._find_exact(file_text, search, occurrence)
        if exact is not None:
            return exact

        return FuzzyMatcher._find_fuzzy(file_text, search)

    @staticmethod
    def _find_exact(file_text: str, search: str, occurrence: int) -> MatchResult | None:
        start = -1
        found = 0
        while True:
            start = file_text.find(search, start + 1)
            if start == -1:
                return None
            found += 1
            if found == occurrence:
                return MatchResult(
                    start=start,
                    end=start + len(search),
                    kind="exact",
                    similarity=1.0,
                )

    @staticmethod
    def _find_fuzzy(file_text: str, search: str) -> MatchResult:
        normalized_search = _normalize(search)
        search_line_count = max(len(search.splitlines()), 1)

        file_lines = file_text.splitlines(keepends=True)
        if not file_lines:
            raise NoMatchError("The file is empty; nothing to match against.")

        # Slide a window of +/- 2 lines around the search's own line count,
        # scoring each candidate window against the normalized search text.
        candidates: list[tuple[float, int, int]] = []  # (score, start_line, end_line)
        for window in (search_line_count - 1, search_line_count, search_line_count + 1, search_line_count + 2):
            if window < 1:
                continue
            for start_line in range(0, max(len(file_lines) - window + 1, 1)):
                end_line = min(start_line + window, len(file_lines))
                candidate_text = "".join(file_lines[start_line:end_line])
                score = difflib.SequenceMatcher(
                    None,
                    _normalize(candidate_text),
                    normalized_search,
                ).ratio()
                candidates.append((score, start_line, end_line))

        if not candidates:
            raise NoMatchError("No candidate spans found in the file.")

        # Highest score first; on ties prefer the window closest to the
        # search's own line count.
        candidates.sort(key=lambda c: (c[0], -abs((c[2] - c[1]) - search_line_count)), reverse=True)
        best_score = candidates[0][0]

        if best_score < FUZZY_SIMILARITY_THRESHOLD:
            raise NoMatchError(
                f"No sufficiently similar match found (best similarity "
                f"{best_score:.2f}, threshold {FUZZY_SIMILARITY_THRESHOLD}).",
                similarity=best_score,
            )

        # Collapse overlapping/duplicate top candidates that refer to
        # essentially the same span before checking for ambiguity.
        top_candidates = [c for c in candidates if best_score - c[0] <= FUZZY_AMBIGUITY_MARGIN]
        distinct_spans = {(c[1], c[2]) for c in top_candidates}

        if len(distinct_spans) > 1:
            # Check whether the distinct spans actually overlap (same match,
            # different window size) — only flag as ambiguous if they don't.
            spans_sorted = sorted(distinct_spans)
            non_overlapping = []
            for span in spans_sorted:
                if not non_overlapping or span[0] >= non_overlapping[-1][1]:
                    non_overlapping.append(span)
            if len(non_overlapping) > 1:
                raise AmbiguousMatchError(
                    f"Multiple equally-good candidate matches found "
                    f"(similarity ~{best_score:.2f}); refusing to guess.",
                    candidates=[c[0] for c in top_candidates],
                )

        _, start_line, end_line = candidates[0]
        char_start = sum(len(line) for line in file_lines[:start_line])
        char_end = sum(len(line) for line in file_lines[:end_line])

        return MatchResult(
            start=char_start,
            end=char_end,
            kind="fuzzy",
            similarity=best_score,
        )


# ---------------------------------------------------------------------------
# Fitting the replacement to the matched span
# ---------------------------------------------------------------------------

def _indent_width(line: str) -> int:
    return len(line) - len(line.lstrip(" \t"))


def _shift_line(line: str, shift: int, indent_char: str) -> str:
    if shift == 0 or not line.strip():
        return line
    width = max(_indent_width(line) + shift, 0)
    return indent_char * width + line.lstrip(" \t")


def _continuation_shift(
    search_lines: list[str],
    target_lines: list[str],
    replacement_lines: list[str],
    first_shift: int,
    target_indent: int,
) -> int:
    """
    Indent shift for every replacement line after the first.

    Models sometimes indent the first line differently from the rest (e.g.
    copying from the first token of a line), so the shift is measured on
    later lines that appear exactly once in both the search and the matched
    text. Without any such line, the first line's shift is reused unless the
    replacement's later lines already sit at or beyond the file's indentation.
    """
    def unique_lines(lines: list[str]) -> dict[str, str]:
        counts: dict[str, int] = {}
        for line in lines:
            counts[line.strip()] = counts.get(line.strip(), 0) + 1
        return {line.strip(): line for line in lines if line.strip() and counts[line.strip()] == 1}

    search_unique = unique_lines(search_lines)
    target_unique = unique_lines(target_lines)
    shifts = [
        _indent_width(target_unique[content]) - _indent_width(line)
        for content, line in search_unique.items()
        if content in target_unique
    ]
    if shifts:
        return max(set(shifts), key=shifts.count)

    continuation = [line for line in replacement_lines if line.strip()]
    if continuation and all(_indent_width(line) >= target_indent for line in continuation):
        return 0
    return first_shift


def fit_replacement(file_text: str, match: MatchResult, search: str, replacement: str) -> tuple[int, int, str]:
    """
    Adapt `replacement` to the span it replaces and return the (start, end,
    text) to splice into `file_text`.

    Models tend to write `search`/`replacement` without the file's
    indentation. A fuzzy match covers whole lines (indent and trailing
    newline included) and an exact match may start after the line's indent,
    so the raw replacement would otherwise lose indentation, get glued to the
    following line, or leave indent-only lines behind on deletion.
    Replacements that start mid-line (after non-whitespace) are left as-is.
    """
    start, end = match.start, match.end
    line_start = file_text.rfind("\n", 0, start) + 1
    prefix = file_text[line_start:start]
    if prefix.strip():
        return start, end, replacement

    if not replacement.strip():
        # Deleting code: take out the whole line(s) if nothing else is on them.
        if not file_text[start:end].endswith("\n"):
            line_end = file_text.find("\n", end)
            line_end = len(file_text) if line_end == -1 else line_end + 1
            if file_text[end:line_end].strip():
                return start, end, replacement
            end = line_end
        return line_start, end, ""

    search_lines = search.split("\n")
    target_lines = file_text[line_start:end].split("\n")
    search_first = next((line for line in search_lines if line.strip()), "")
    target_first = next((line for line in target_lines if line.strip()), "")
    target_indent = _indent_width(target_first)
    first_shift = target_indent - _indent_width(search_first)
    indent_char = "\t" if target_first.startswith("\t") else " "

    replacement_lines = replacement.split("\n")
    rest_shift = _continuation_shift(
        search_lines[1:], target_lines[1:], replacement_lines[1:], first_shift, target_indent,
    )

    # The first replacement line is inserted after `prefix`, which already
    # supplies that much of its indentation.
    fitted = [_shift_line(replacement_lines[0], first_shift - len(prefix), indent_char)]
    fitted += [_shift_line(line, rest_shift, indent_char) for line in replacement_lines[1:]]
    text = "\n".join(fitted)

    if match.kind == "fuzzy" and file_text[start:end].endswith("\n") and not text.endswith("\n"):
        text += "\n"

    return start, end, text


# ---------------------------------------------------------------------------
# Applying edits + diff generation
# ---------------------------------------------------------------------------

@dataclass
class EditOutcome:
    path: str
    applied: bool
    match_kind: str | None = None
    similarity: float | None = None
    error: str | None = None


@dataclass
class EditApplyResult:
    applied: bool
    edit_results: list[EditOutcome] = field(default_factory=list)
    diff: str = ""
    error: str | None = None


def apply_edits(project_directory: Path, edits: list[EditCall]) -> EditApplyResult:
    """
    Apply edits in sequence against progressively-updated in-memory file
    state, one file read/write per touched file. Each edit's outcome is
    recorded independently; a failing edit does not abort the others.
    """
    original_files: dict[str, str] = {}
    working_files: dict[str, str] = {}
    outcomes: list[EditOutcome] = []

    def _load(path: str) -> str:
        if path not in working_files:
            file_path = project_directory / path
            text = file_path.read_text(encoding="utf-8")
            original_files[path] = text
            working_files[path] = text
        return working_files[path]

    for edit in edits:
        file_path = project_directory / edit.path
        if not file_path.is_file():
            outcomes.append(EditOutcome(
                path=edit.path,
                applied=False,
                error=f"File not found: {edit.path}",
            ))
            continue

        current_text = _load(edit.path)

        try:
            match = FuzzyMatcher.find_match(current_text, edit.search, edit.occurrence)
        except NoMatchError as e:
            outcomes.append(EditOutcome(
                path=edit.path,
                applied=False,
                error=str(e),
            ))
            continue
        except AmbiguousMatchError as e:
            outcomes.append(EditOutcome(
                path=edit.path,
                applied=False,
                error=str(e),
            ))
            continue

        start, end, text = fit_replacement(current_text, match, edit.search, edit.replacement)
        working_files[edit.path] = current_text[:start] + text + current_text[end:]
        outcomes.append(EditOutcome(
            path=edit.path,
            applied=True,
            match_kind=match.kind,
            similarity=match.similarity,
        ))

    for path, text in working_files.items():
        (project_directory / path).write_text(text, encoding="utf-8")

    diff = generate_diff(original_files, working_files)
    all_applied = all(o.applied for o in outcomes)
    failed = [o for o in outcomes if not o.applied]

    return EditApplyResult(
        applied=all_applied,
        edit_results=outcomes,
        diff=diff,
        error=None if all_applied else "; ".join(f"{o.path}: {o.error}" for o in failed),
    )


def edits_from_tool_calls(tool_calls: list[dict[str, Any]]) -> list[EditCall]:
    """Build EditCalls from the provider-agnostic tool_calls shape on ModelResponse."""
    edits: list[EditCall] = []
    for call in tool_calls:
        if call.get("name") != "edit_file":
            continue
        arguments = call.get("arguments", {})
        edits.append(EditCall(
            path=arguments["path"],
            search=arguments["search"],
            replacement=arguments["replacement"],
            occurrence=arguments.get("occurrence", 1),
        ))
    return edits


def generate_diff(original_files: dict[str, str], updated_files: dict[str, str]) -> str:
    """Build a standard unified diff for every changed file."""
    chunks: list[str] = []

    for path in sorted(updated_files):
        original = original_files.get(path, "")
        updated = updated_files[path]
        if original == updated:
            continue

        diff_lines = difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
        chunks.append("".join(diff_lines))

    return "".join(chunks)
