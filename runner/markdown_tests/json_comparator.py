import json
from dataclasses import dataclass
from typing import Any


@dataclass
class ComparisonResult:
    matched: bool
    message: str


class JsonComparator:

    @staticmethod
    def compare(actual: Any, expected: Any) -> ComparisonResult:
        if actual == expected:
            return ComparisonResult(
                matched=True,
                message="Output matches the expected result.",
            )

        return ComparisonResult(
            matched=False,
            message=(
                "Output does not match the expected result.\n\n"
                f"Expected:\n{json.dumps(expected, indent=2, ensure_ascii=False)}\n\n"
                f"Actual:\n{json.dumps(actual, indent=2, ensure_ascii=False)}"
            ),
        )
