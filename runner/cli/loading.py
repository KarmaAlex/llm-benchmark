"""
Loading helpers for entry points: they turn missing/invalid inputs into a
clean SystemExit message instead of a traceback.
"""

from pathlib import Path

from runner.filesystem.config_loader import ConfigLoader
from runner.filesystem.paths import CONFIG_DIR
from runner.filesystem.results_manager import ResultsManager
from runner.models.model_config import ModelConfig


def load_model_config(name: str, device: str, edit_mode: str | None = None) -> ModelConfig:
    """Load a model config for `device`, refusing tool-call edit mode on a
    model that doesn't support it."""
    config = ConfigLoader.load(name)
    config = ConfigLoader.apply_device(config, device)

    if edit_mode == "toolcall" and not config.supports_tools:
        print(
            f"Model config '{config.name}' does not have supports_tools "
            "enabled. Use --edit-mode structured for this model instead."
        )
        raise SystemExit(1)

    return config


def resolve_config_name(base: str, suite: str) -> str:
    """Prefer the suite-specific variant of a model config
    (`<base>-markdown` / `<base>-sonar`), falling back to `<base>` itself."""
    variant = f"{base}-{suite}"
    return variant if (CONFIG_DIR / f"{variant}.yaml").exists() else base


def open_run(run_id: str) -> tuple[Path, dict]:
    """Resolve an existing run directory and load its report.json."""
    try:
        run_directory = ResultsManager.resolve_run_directory(run_id)
        return run_directory, ResultsManager.load_report(run_directory)
    except FileNotFoundError as e:
        raise SystemExit(str(e))
