from dataclasses import replace
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

    @staticmethod
    def apply_device(config: ModelConfig, device: str) -> ModelConfig:
        """
        Override a llama.cpp config's GPU offload for this run without
        touching the underlying YAML file. 'cuda' (the default) leaves the
        config's own n_gpu_layers untouched; 'cpu' forces it to 0 so the
        model runs entirely on CPU. No-op for non-llama.cpp providers.
        """
        if device not in ("cuda", "cpu"):
            raise ValueError(f"Unknown device: {device}")

        if config.provider != "llama.cpp":
            return config

        if device == "cpu":
            return replace(
                config,
                parameters={**config.parameters, "n_gpu_layers": 0},
            )

        return config