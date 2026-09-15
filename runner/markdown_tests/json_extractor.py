import json
import re
from typing import Any


class JsonExtractionError(Exception):
    pass


class JsonExtractor:

    @staticmethod
    def extract(raw_text: str) -> Any:
        """
        Parse a model's response as JSON.

        Expected model output:

            ```json
            { ... }
            ```

        or plain JSON with no fences at all.
        """

        cleaned = JsonExtractor._clean(raw_text)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise JsonExtractionError(
                f"Model response is not valid JSON: {e}"
            ) from e

    @staticmethod
    def _clean(raw_text: str) -> str:
        text = raw_text.strip()

        fenced = re.fullmatch(
            r"```(?:json)?\s*\n?(.*?)\n?```",
            text,
            re.DOTALL | re.IGNORECASE,
        )

        if fenced:
            text = fenced.group(1).strip()

        return text
