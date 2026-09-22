import json
import re

from runner.models.benchmark import BenchmarkCase
from runner.models.chat_prompt import ChatPrompt
from runner.models.prompt import Prompt


class PromptBuilder:
    @staticmethod
    def build(
        prompt: Prompt,
        benchmark: BenchmarkCase,
    ) -> ChatPrompt:
        user = prompt.user
        replacements = {
            "metadata": benchmark.metadata,
            **benchmark.resources
        }
        for name, value in replacements.items():
            if not isinstance(value, str):
                value = json.dumps(
                    value,
                    indent=2,
                    ensure_ascii=False,
                )
            placeholder = f"{{{{{name}}}}}"
            user = user.replace(
                placeholder,
                value,
            )
        files_concat = ""
        for name, content in benchmark.files.items():
            files_concat += f"### File: {name}\n\n{content}\n\n---\n\n"
        user = user.replace("{{files}}", files_concat)
        unresolved = re.findall(
                    r"\{\{(.*?)\}\}",
                    user,
                )
        if unresolved:
            raise ValueError(
                "Unresolved prompt placeholders: "
                + ", ".join(sorted(unresolved))
            )
        return ChatPrompt(
            version=prompt.version,
            messages=[
                {
                    "role": "system",
                    "content": prompt.system,
                },
                {
                    "role": "user",
                    "content": user,
                },
            ],
        )