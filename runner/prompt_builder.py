import json

from runner.models.chat_prompt import ChatPrompt
from runner.models.prompt import Prompt
from runner.models.benchmark import BenchmarkCase


class PromptBuilder:

    def build(
        self,
        prompt: Prompt,
        benchmark: BenchmarkCase,
    ) -> ChatPrompt:

        user = prompt.user
        replacements = {
            "{{rule}}": benchmark.rule_text,
            "{{issue}}": json.dumps(
                benchmark.issue,
                indent=2,
            ),
            "{{metadata}}": json.dumps(
                benchmark.metadata,
                indent=2,
            ),
        }
        for key, value in replacements.items():
            user = user.replace(key, value)
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