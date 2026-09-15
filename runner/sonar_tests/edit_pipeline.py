"""
Shared logic for turning a model's response into an applied change on disk,
regardless of which --edit-mode produced it. Used by both the single-case
runner (main_sonar.py) and the batch runner (run_all_sonar.py) so the two
scripts can't drift apart.
"""

from dataclasses import dataclass
from pathlib import Path

from runner.models.model_response import ModelResponse
from runner.sonar_tests.patch_applier import PatchApplier
from runner.structured_edit import (
    StructuredEditParseError,
    StructuredEditParser,
    apply_edits,
    edits_from_tool_calls,
)

PROMPT_NAME_BY_EDIT_MODE = {
    "diff": "sonar_v2",
    "structured": "sonar_structured_v1",
    "toolcall": "sonar_toolcall_v1",
}


@dataclass
class ApplyOutcome:
    applied: bool
    diff: str
    error: str | None
    edit_results: list = None


def apply_model_response(
    edit_mode: str,
    project_directory: Path,
    response: ModelResponse,
) -> ApplyOutcome:
    if edit_mode == "diff":
        patch_result = PatchApplier.apply(project_directory, response.content)
        return ApplyOutcome(
            applied=patch_result.applied,
            diff=response.content,
            error=patch_result.error,
        )

    if edit_mode == "toolcall":
        if not response.tool_calls:
            return ApplyOutcome(
                applied=False,
                diff="",
                error="Model returned no tool calls.",
            )
        edits = edits_from_tool_calls(response.tool_calls)
    else:
        try:
            edits = StructuredEditParser.parse(response.content)
        except StructuredEditParseError as e:
            return ApplyOutcome(
                applied=False,
                diff="",
                error=f"Failed to parse structured edits: {e}",
            )

    edit_result = apply_edits(project_directory, edits)
    return ApplyOutcome(
        applied=edit_result.applied,
        diff=edit_result.diff,
        error=edit_result.error,
        edit_results=edit_result.edit_results,
    )
