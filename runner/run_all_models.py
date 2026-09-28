"""
Run the reproducibility benchmark for every available model, one after the
other, so each ends up with a full run to compare.

A model is a base config name under configs/ (`qwen2.5-coder-7b-q4`, not its
`-markdown` / `-sonar` variants), exactly what `run_all_reproducibility
--model` takes. It is *available* when every suite it would run resolves to
a config whose model can actually be loaded:

    llama.cpp   the config's GGUF file exists (relative to the project root,
                normally under models/)
    openai      OPENAI_API_KEY is set (in the environment or .env) - these
                runs are billed per token

By default a model that already has a full reproducibility run with the
same repetitions and edit mode is skipped (--rerun to run it again), so the
script can be re-run after an interruption and only fills the gaps. GGUF
files under models/ that no config points at are listed, since they can't
be run until one does.

Each model runs as its own `python -m runner.run_all_reproducibility`
process: its GPU memory is released before the next model loads, and one
model failing doesn't stop the rest.

Usage:
    python -m runner.run_all_models --dry-run                # what would run
    python -m runner.run_all_models                          # everything available
    python -m runner.run_all_models --local-only --repetitions 5
    python -m runner.run_all_models --models qwen2.5-coder-3b-q4 phi4-mini-instruct-q4
    python -m runner.run_all_models --compare                # + analysis.compare_models at the end
"""

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from runner.cli.arguments import add_device_argument, add_edit_mode_argument, add_sonar_argument
from runner.cli.loading import resolve_config_name
from runner.filesystem.paths import CONFIG_DIR, MODELS_DIR, PROJECT_ROOT
from runner.reproducibility.aggregate import SUITES
from runner.reproducibility.runs import is_full_run, load_run, model_key, reproducibility_runs, run_model

SUITE_SUFFIXES = tuple(f"-{suite}" for suite in SUITES)


@dataclass
class Candidate:
    base: str
    configs: dict[str, str] = field(default_factory=dict)  # suite -> config file stem
    names: dict[str, str] = field(default_factory=dict)    # suite -> config `name:`
    provider: str = ""
    problem: str | None = None                              # why it can't run
    existing_run: str | None = None                         # a full run that makes it skippable

    @property
    def model(self) -> str:
        """The model key results are filed under (see runs.model_key)."""
        keys = {model_key(name) for name in self.names.values()}
        return keys.pop() if len(keys) == 1 else self.base

    @property
    def is_api(self) -> bool:
        return self.provider == "openai"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run run_all_reproducibility for every available model, one after the other."
    )
    parser.add_argument("--models", nargs="+", metavar="BASE", help="Only these base configs (default: all available).")
    parser.add_argument("--exclude", nargs="+", metavar="BASE", default=[], help="Base configs to leave out.")
    parser.add_argument("--local-only", action="store_true", help="Skip API (billed) models.")
    parser.add_argument("--rerun", action="store_true",
                        help="Run models that already have a full run with the same settings.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would run, then exit.")
    parser.add_argument("--stop-on-failure", action="store_true", help="Stop at the first model that fails.")
    parser.add_argument("--require-free-gpu", action="store_true",
                        help="Have each run refuse to start on a GPU another process is using.")
    parser.add_argument("--compare", action="store_true",
                        help="Run analysis.compare_models once every model has finished.")
    parser.add_argument("--repetitions", type=int, default=10, help="Repetitions per suite (default: 10).")
    parser.add_argument("--suites", nargs="+", choices=SUITES, default=list(SUITES),
                        help="Which suites to run (default: both; a run of one suite isn't 'full').")
    add_edit_mode_argument(parser)
    # Structured is what the existing full runs used; runs are only compared
    # like-for-like, so the batch default follows them rather than 'diff'.
    parser.set_defaults(edit_mode="structured")
    add_device_argument(parser)
    add_sonar_argument(parser, help="Run the SonarQube analysis phase (default: on).")
    return parser.parse_args()


# --------------------------------------------------------------------------- #
# discovery
# --------------------------------------------------------------------------- #


def _load_config(stem: str) -> dict:
    try:
        return yaml.safe_load((CONFIG_DIR / f"{stem}.yaml").read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}


def base_configs() -> list[str]:
    """Every base config name: config file stems with any suite suffix removed."""
    bases = set()
    for path in CONFIG_DIR.glob("*.yaml"):
        stem = path.stem
        for suffix in SUITE_SUFFIXES:
            if stem.endswith(suffix):
                stem = stem.removesuffix(suffix)
                break
        bases.add(stem)
    return sorted(bases)


def examine(base: str, suites: list[str]) -> Candidate:
    candidate = Candidate(base)
    providers = set()
    for suite in suites:
        stem = resolve_config_name(base, suite)
        config = _load_config(stem)
        if not config:
            candidate.problem = f"no config for the {suite} suite ({stem}.yaml)"
            return candidate
        candidate.configs[suite] = stem
        candidate.names[suite] = config.get("name", stem)
        providers.add(config.get("provider", ""))

        if config.get("provider") == "llama.cpp":
            weights = PROJECT_ROOT / config.get("model", "")
            if not weights.is_file():
                candidate.problem = f"weights not found: {config.get('model')}"
        elif config.get("provider") == "openai":
            if not os.environ.get("OPENAI_API_KEY"):
                candidate.problem = "OPENAI_API_KEY not set"
        else:
            candidate.problem = f"unknown provider '{config.get('provider')}'"

    candidate.provider = "/".join(sorted(providers))
    return candidate


def full_runs_by_model(repetitions: int, edit_mode: str) -> dict[str, str]:
    """model key -> newest full run with these settings."""
    found: dict[str, str] = {}
    for path in reproducibility_runs():
        try:
            run = load_run(path)
        except (OSError, ValueError):
            continue
        settings = run.get("settings") or {}
        if settings.get("repetitions") != repetitions or settings.get("edit_mode") != edit_mode:
            continue
        full, _reason = is_full_run(run, path)
        if full:
            found.setdefault(run_model(run), path.name)
    return found


def orphan_weights() -> list[str]:
    """GGUF files under models/ that no config points at."""
    referenced = set()
    for path in CONFIG_DIR.glob("*.yaml"):
        model = _load_config(path.stem).get("model")
        if model:
            referenced.add((PROJECT_ROOT / model).resolve())
    return sorted(p.name for p in MODELS_DIR.glob("*.gguf") if p.resolve() not in referenced)


def plan(args: argparse.Namespace) -> tuple[list[Candidate], list[Candidate], list[Candidate]]:
    """(to run, skipped because a full run exists, unavailable)."""
    bases = base_configs()
    if args.models:
        unknown = sorted(set(args.models) - set(bases))
        if unknown:
            raise SystemExit(f"Unknown base config(s): {', '.join(unknown)} (available: {', '.join(bases)})")
        bases = [b for b in bases if b in args.models]
    bases = [b for b in bases if b not in args.exclude]

    existing = {} if args.rerun else full_runs_by_model(args.repetitions, args.edit_mode)
    to_run, skipped, unavailable = [], [], []
    for base in bases:
        candidate = examine(base, args.suites)
        if candidate.problem:
            unavailable.append(candidate)
        elif args.local_only and candidate.is_api:
            candidate.problem = "API model (--local-only)"
            unavailable.append(candidate)
        elif candidate.model in existing:
            candidate.existing_run = existing[candidate.model]
            skipped.append(candidate)
        else:
            to_run.append(candidate)
    # Local models first: a missing or rate-limited API key shouldn't hold
    # up the runs that only need this machine.
    to_run.sort(key=lambda c: (c.is_api, c.base))
    return to_run, skipped, unavailable


def print_plan(to_run: list[Candidate], skipped: list[Candidate], unavailable: list[Candidate],
               args: argparse.Namespace) -> None:
    settings = f"{args.repetitions} repetitions, suites {'+'.join(args.suites)}, edit mode {args.edit_mode}"
    print(f"Reproducibility batch: {settings}\n")
    print(f"To run ({len(to_run)}):")
    for c in to_run:
        billed = "  (API - billed per token)" if c.is_api else ""
        print(f"  {c.base:<26} {c.model:<26} {c.provider}{billed}")
    if not to_run:
        print("  nothing")
    if skipped:
        print(f"\nAlready have a full run with these settings ({len(skipped)}, --rerun to run again):")
        for c in skipped:
            print(f"  {c.base:<26} {c.model:<26} run {c.existing_run}")
    if unavailable:
        print(f"\nNot available ({len(unavailable)}):")
        for c in unavailable:
            print(f"  {c.base:<26} {c.problem}")
    orphans = orphan_weights()
    if orphans:
        print("\nWeights under models/ with no config (add one under configs/ to include them):")
        for name in orphans:
            print(f"  {name}")


# --------------------------------------------------------------------------- #
# running
# --------------------------------------------------------------------------- #


def reproducibility_command(candidate: Candidate, args: argparse.Namespace) -> list[str]:
    command = [
        sys.executable, "-m", "runner.run_all_reproducibility",
        "--model", candidate.base,
        "--repetitions", str(args.repetitions),
        "--suites", *args.suites,
        "--edit-mode", args.edit_mode,
        "--device", args.device,
    ]
    if not args.sonar:
        command.append("--no-sonar")
    if getattr(args, "require_free_gpu", False):
        command.append("--require-free-gpu")
    return command


def _format_duration(seconds: float) -> str:
    hours, rest = divmod(int(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}h{minutes:02d}m" if hours else f"{minutes}m{secs:02d}s"


def run_batch(to_run: list[Candidate], args: argparse.Namespace) -> list[dict]:
    outcomes = []
    for index, candidate in enumerate(to_run, start=1):
        print(f"\n{'#' * 78}\n# [{index}/{len(to_run)}] {candidate.base} ({candidate.model})\n{'#' * 78}", flush=True)
        before = {p.name for p in reproducibility_runs()}
        start = time.monotonic()
        try:
            returncode = subprocess.run(reproducibility_command(candidate, args), cwd=PROJECT_ROOT).returncode
            status = "ok" if returncode == 0 else f"failed (exit {returncode})"
        except KeyboardInterrupt:
            status = "interrupted"
        new_runs = sorted({p.name for p in reproducibility_runs()} - before)
        outcomes.append({
            "base": candidate.base,
            "model": candidate.model,
            "status": status,
            "duration": time.monotonic() - start,
            "run": new_runs[-1] if new_runs else None,
        })
        if status == "interrupted" or (status != "ok" and args.stop_on_failure):
            break
    return outcomes


def print_outcomes(outcomes: list[dict], planned: int) -> None:
    print(f"\n{'=' * 78}\nBatch summary\n{'=' * 78}")
    for o in outcomes:
        run = f"run {o['run']}" if o["run"] else "no run directory"
        print(f"  {o['base']:<26} {o['status']:<20} {_format_duration(o['duration']):>8}  {run}")
    if len(outcomes) < planned:
        print(f"  ... {planned - len(outcomes)} model(s) not started")


def main() -> None:
    args = parse_args()
    if args.repetitions < 1:
        raise SystemExit("--repetitions must be at least 1")

    to_run, skipped, unavailable = plan(args)
    print_plan(to_run, skipped, unavailable, args)
    if args.dry_run or not to_run:
        return

    outcomes = run_batch(to_run, args)
    print_outcomes(outcomes, len(to_run))

    if args.compare and any(o["status"] == "ok" for o in outcomes):
        print("\nComparing every model's latest full run:")
        subprocess.run([sys.executable, "-m", "analysis.compare_models"], cwd=PROJECT_ROOT)

    if any(o["status"] != "ok" for o in outcomes):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
