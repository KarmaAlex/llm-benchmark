from runner.filesystem.paths import PROMPT_DIR
from runner.models.prompt import Prompt


class PromptLoader:
    @staticmethod
    def load(user_prompt, system_prompt: str="system_v1") -> Prompt:
        system_path = PROMPT_DIR / f"{system_prompt}.md"
        prompt_path = PROMPT_DIR / f"{user_prompt}.md"

        if not system_path.exists():
            raise FileNotFoundError(f"System prompt not found: {system_path}")

        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt not found: {prompt_path}")

        system = system_path.read_text(encoding="utf-8")
        user = prompt_path.read_text(encoding="utf-8")

        return Prompt(
            version=user_prompt,
            system=system,
            user=user
        )