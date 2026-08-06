from pathlib import Path

import yaml

from runner.filesystem.paths import CONFIG_DIR
from runner.models.model_config import ModelConfig


class ConfigLoader:
    @staticmethod
    def load(name: str) -> ModelConfig:
        path = CONFIG_DIR / f"{name}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Model config not found: {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return ModelConfig(**data)