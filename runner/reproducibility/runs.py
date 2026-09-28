"""
Finding reproducibility runs on disk and deciding which are complete.

Kept free of pandas and plotting so the runner itself (run_all_models) can
use it; analysis/aggregate.py re-exports everything here.

A run is *full* when it ran both suites on every case, every repetition
completed, sonar was graded on clean fixes, and both suites used the same
model - the only runs a model comparison should draw on.
"""

import re
from pathlib import Path

from runner.filesystem.paths import RESULTS_DIR
from runner.filesystem.results_manager import ResultsManager
from runner.reproducibility.aggregate import AGGREGATE_FILE_NAME, SUITES, repetition_directories

_SUITE_SUFFIX = re.compile(r"\s*\((?:markdown|sonar)\)$")


def model_key(config_name: str) -> str:
    """'GPT-5 (sonar)' -> 'GPT-5'. Quantizations stay separate models."""
    return _SUITE_SUFFIX.sub("", config_name or "").strip()


def reproducibility_runs(results_dir: Path | None = None) -> list[Path]:
    """Every directory holding a reproducibility.json, newest first
    (directories are named for their UTC start time)."""
    results_dir = results_dir or RESULTS_DIR
    if not results_dir.is_dir():
        return []
    return sorted(
        (p for p in results_dir.iterdir() if p.is_dir() and (p / AGGREGATE_FILE_NAME).exists()),
        key=lambda p: p.name,
        reverse=True,
    )


def load_run(path: Path) -> dict:
    return ResultsManager.load_report(path, AGGREGATE_FILE_NAME)


def run_model(run: dict) -> str:
    """The model a run tested. Mixed-model runs (one config per suite pointing
    at different models) report both, joined, so they're easy to spot."""
    configs = (run.get("settings") or {}).get("configs") or {}
    if not configs:
        configs = {s: (a.get("configs") or [""])[0] for s, a in (run.get("suites") or {}).items()}
    keys = sorted({model_key(name) for name in configs.values() if name})
    return " + ".join(keys) if keys else "unknown"


def is_full_run(run: dict, path: Path) -> tuple[bool, str]:
    """(True, "") for a complete run of both suites, otherwise (False, why)."""
    settings = run.get("settings") or {}
    suites = run.get("suites") or {}

    missing = [s for s in SUITES if s not in (settings.get("suites") or [])]
    if missing:
        return False, f"suite(s) not run: {', '.join(missing)}"
    if settings.get("cases"):
        return False, f"restricted to --cases {' '.join(settings['cases'])}"
    if not settings.get("sonar", True):
        return False, "run with --no-sonar"
    if run.get("pending_validation"):
        return False, f"not yet validated: {', '.join(run['pending_validation'])}"
    missing = [s for s in SUITES if s not in suites]
    if missing:
        return False, f"no aggregate for: {', '.join(missing)}"
    if suites["sonar"].get("criterion") != "clean_fix":
        return False, f"sonar graded on {suites['sonar'].get('criterion')}, not clean_fix"

    models = {model_key(name) for name in (settings.get("configs") or {}).values()}
    if len(models) > 1:
        return False, f"suites use different models: {', '.join(sorted(models))}"

    expected = settings.get("repetitions")
    for suite in SUITES:
        completed = len(repetition_directories(path / suite))
        aggregated = suites[suite].get("repetitions")
        if expected is not None and (completed != expected or aggregated != expected):
            return False, f"{suite}: {completed}/{expected} repetitions completed"
        short = [c["case_id"] for c in suites[suite].get("cases", []) if c.get("repetitions") != aggregated]
        if short:
            return False, f"{suite}: case(s) missing from some repetitions: {', '.join(short)}"
    return True, ""
