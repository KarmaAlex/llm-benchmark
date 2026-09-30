"""
Locate reproducibility runs and turn them into tidy pandas frames for plotting.

A reproducibility run (see runner/run_all_reproducibility.py) is a directory
under results/ holding a reproducibility.json aggregate plus one ordinary
report.json per suite repetition. This module:

  - finds those runs and decides which ones are *full* - both suites, every
    case, every repetition present, sonar graded on the clean-fix criterion -
    so runs that were interrupted or restricted to a subset never end up in a
    model comparison;
  - maps each run to a model (its config name without the "(markdown)" /
    "(sonar)" suffix) and that model to a group, Commercial or Open source,
    from the provider in its configs/*.yaml file;
  - flattens the aggregate and the per-repetition reports into long-form
    DataFrames the plotting code consumes.

Like analysis/report.py, everything reads plain dicts rather than the runner's
dataclasses, so older reports still load and nothing here imports llama.cpp.
"""

import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

from analysis.report import clean_fix
from runner.filesystem.paths import BENCHMARK_DIR, CONFIG_DIR
from runner.filesystem.results_manager import ResultsManager
from runner.reproducibility.aggregate import AGGREGATE_FILE_NAME, SUITES, repetition_directories
from runner.reproducibility.runs import (  # noqa: F401 - re-exported
    is_full_run,
    load_run,
    model_key,
    reproducibility_runs,
    run_model,
)

COMMERCIAL = "Commercial"
OPEN_SOURCE = "Open source"
UNKNOWN = "Unknown"
GROUPS = (COMMERCIAL, OPEN_SOURCE, UNKNOWN)

GROUP_BY_PROVIDER = {
    "openai": COMMERCIAL,
    "llama.cpp": OPEN_SOURCE,
}

# Pipeline stages a sonar case can stop at, in order (see sonar_stage in
# runner/reproducibility/observations.py).
SONAR_STAGES = ("not_applied", "applied", "compiled", "tests_passed", "resolved", "clean_fix")



# --------------------------------------------------------------------------- #
# models and groups
# --------------------------------------------------------------------------- #


def _config_field(field_name: str, config_dir: Path) -> dict[str, str]:
    """Config name -> one field of it, from every configs/*.yaml file. Both
    the full config name and its suffix-less model key are mapped."""
    catalog: dict[str, str] = {}
    for path in sorted(config_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        name, value = data.get("name"), data.get(field_name)
        if name and value:
            catalog.setdefault(name, value)
            catalog.setdefault(model_key(name), value)
    return catalog


def model_catalog(config_dir: Path = CONFIG_DIR) -> dict[str, str]:
    """Model name -> provider."""
    return _config_field("provider", config_dir)


def api_model_ids(config_dir: Path = CONFIG_DIR) -> dict[str, str]:
    """Config name -> the `model:` it sends to its provider (e.g. 'gpt-5')."""
    return _config_field("model", config_dir)


def parse_group_overrides(values: list[str] | None) -> dict[str, str]:
    """`--group NAME=commercial|open` arguments -> {model: group}."""
    aliases = {"commercial": COMMERCIAL, "open": OPEN_SOURCE, "open-source": OPEN_SOURCE, "oss": OPEN_SOURCE}
    overrides = {}
    for value in values or []:
        name, _, group = value.rpartition("=")
        if not name or group.lower() not in aliases:
            raise ValueError(f"Bad --group '{value}': expected NAME=commercial or NAME=open")
        overrides[name] = aliases[group.lower()]
    return overrides


def group_of(model: str, catalog: dict[str, str], overrides: dict[str, str] | None = None) -> str:
    if overrides and model in overrides:
        return overrides[model]
    return GROUP_BY_PROVIDER.get(catalog.get(model, ""), UNKNOWN)


# --------------------------------------------------------------------------- #
# discovering runs
# --------------------------------------------------------------------------- #


@dataclass
class RunRef:
    path: Path
    run: dict
    model: str
    group: str
    full: bool
    reason: str = ""
    configs: dict = field(default_factory=dict)

    @property
    def run_id(self) -> str:
        return self.path.name

    @property
    def settings(self) -> dict:
        return self.run.get("settings") or {}


def load_run_ref(path: Path, catalog: dict[str, str] | None = None, overrides: dict[str, str] | None = None) -> RunRef:
    catalog = model_catalog() if catalog is None else catalog
    run = load_run(path)
    model = run_model(run)
    full, reason = is_full_run(run, path)
    return RunRef(
        path=path,
        run=run,
        model=model,
        group=group_of(model, catalog, overrides),
        full=full,
        reason=reason,
        configs=(run.get("settings") or {}).get("configs") or {},
    )


def all_run_refs(
    results_dir: Path | None = None,
    overrides: dict[str, str] | None = None,
    catalog: dict[str, str] | None = None,
) -> list[RunRef]:
    catalog = model_catalog() if catalog is None else catalog
    refs = []
    for path in reproducibility_runs(results_dir):
        try:
            refs.append(load_run_ref(path, catalog, overrides))
        except (OSError, json.JSONDecodeError) as e:
            print(f"warning: skipping {path.name}: {e}", file=sys.stderr)
    return refs


def latest_full_runs(refs: list[RunRef], models: list[str] | None = None) -> list[RunRef]:
    """The newest full run per model (refs must be newest first). `models`
    restricts the selection (case-insensitive model keys)."""
    wanted = {m.lower() for m in models} if models else None
    selected: dict[str, RunRef] = {}
    for ref in refs:
        if not ref.full or ref.model in selected:
            continue
        if wanted is not None and ref.model.lower() not in wanted:
            continue
        selected[ref.model] = ref
    return sort_by_group(list(selected.values()))


def sort_by_group(refs: list[RunRef]) -> list[RunRef]:
    return sorted(refs, key=lambda r: (GROUPS.index(r.group) if r.group in GROUPS else len(GROUPS), r.model.lower()))


def comparability_warnings(refs: list[RunRef]) -> list[str]:
    """Settings that make a side-by-side comparison less than like-for-like."""
    warnings = []
    for key in ("edit_mode", "repetitions"):
        values = {r.model: r.settings.get(key) for r in refs}
        if len(set(values.values())) > 1:
            detail = ", ".join(f"{m}={v}" for m, v in values.items())
            warnings.append(f"selected runs differ in {key}: {detail}")
    groups = {r.group for r in refs}
    for group in (COMMERCIAL, OPEN_SOURCE):
        if refs and group not in groups:
            warnings.append(f"no {group.lower()} model among the selected runs")
    unknown = [r.model for r in refs if r.group == UNKNOWN]
    if unknown:
        warnings.append(
            f"could not tell whether {', '.join(unknown)} is commercial or open source "
            "(no matching configs/*.yaml) - pass --group NAME=commercial|open"
        )
    return warnings


# --------------------------------------------------------------------------- #
# tidy frames
# --------------------------------------------------------------------------- #


def _case_metadata(suite: str, case_id: str) -> dict:
    path = BENCHMARK_DIR / suite / case_id / "metadata.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def case_frame(ref: RunRef) -> pd.DataFrame:
    """One row per (suite, case) from the aggregate."""
    rows = []
    for suite, aggregate in (ref.run.get("suites") or {}).items():
        for case in aggregate.get("cases", []):
            metadata = _case_metadata(suite, case["case_id"]) if suite == "markdown" else {}
            tokens = case.get("completion_tokens") or {}
            latency = case.get("latency") or {}
            rows.append({
                "run_id": ref.run_id,
                "model": ref.model,
                "group": ref.group,
                "suite": suite,
                "criterion": aggregate.get("criterion"),
                "case_id": case["case_id"],
                "classification": case.get("classification"),
                "valid_classification": case.get("valid_classification"),
                "repetitions": case.get("repetitions", 0),
                "n": case.get("n", 0),
                "pass_count": case.get("pass_count", 0),
                "pass_rate": case.get("pass_rate", 0.0) if case.get("n") else math.nan,
                "agreement_rate": case.get("agreement_rate", 0.0) if case.get("n") else math.nan,
                "distinct_raw_outputs": case.get("distinct_raw_outputs", 0),
                "distinct_effective_outputs": case.get("distinct_effective_outputs", 0),
                "tokens_mean": tokens.get("mean", math.nan),
                "latency_mean": latency.get("mean", math.nan),
                "latency_stdev": latency.get("stdev", math.nan),
                "harness_errors": len(case.get("harness_errors") or []),
                "difficulty": metadata.get("difficulty"),
                "category": metadata.get("category"),
            })
    return pd.DataFrame(rows)


def stage_frame(ref: RunRef) -> pd.DataFrame:
    """Sonar only: one row per (case, stage) with how many repetitions
    stopped at that stage."""
    aggregate = (ref.run.get("suites") or {}).get("sonar")
    rows = []
    for case in (aggregate or {}).get("cases", []):
        stages = case.get("stages") or {}
        for stage in SONAR_STAGES:
            rows.append({
                "run_id": ref.run_id,
                "model": ref.model,
                "group": ref.group,
                "case_id": case["case_id"],
                "stage": stage,
                "count": stages.get(stage, 0),
            })
    return pd.DataFrame(rows, columns=["run_id", "model", "group", "case_id", "stage", "count"])


def suite_frame(ref: RunRef) -> pd.DataFrame:
    """One row per suite with the aggregate's headline numbers."""
    rows = []
    for suite, aggregate in (ref.run.get("suites") or {}).items():
        summary = aggregate.get("summary") or {}
        cases = aggregate.get("cases") or []
        rates = summary.get("repetition_pass_rate") or {}
        rows.append({
            "run_id": ref.run_id,
            "model": ref.model,
            "group": ref.group,
            "suite": suite,
            "criterion": aggregate.get("criterion"),
            "repetitions": aggregate.get("repetitions"),
            "total_cases": summary.get("total_cases", len(cases)),
            "trials": sum(c.get("n", 0) for c in cases),
            "passes": sum(c.get("pass_count", 0) for c in cases),
            "mean_case_pass_rate": summary.get("mean_case_pass_rate"),
            "rep_pass_rate_mean": rates.get("mean"),
            "rep_pass_rate_stdev": rates.get("stdev"),
            "pass_all": summary.get("pass_all"),
            "pass_any": summary.get("pass_any"),
            "pass_none": summary.get("pass_none"),
            **{f"n_{name}": count for name, count in (summary.get("classifications") or {}).items()},
        })
    return pd.DataFrame(rows)


def repetition_rates(ref: RunRef) -> pd.DataFrame:
    """One row per (suite, repetition) with that repetition's pass rate."""
    rows = []
    for suite, aggregate in (ref.run.get("suites") or {}).items():
        for entry in (aggregate.get("summary") or {}).get("per_repetition", []):
            rows.append({"model": ref.model, "suite": suite, **entry})
    return pd.DataFrame(rows, columns=["model", "suite", "rep", "pass_count", "n", "pass_rate"])


def _is_harness_error(case: dict) -> bool:
    """Same rule as runner/reproducibility/observations.py: the case raised
    before the model answered."""
    return case.get("response_text") is None and case.get("error") is not None and not case.get("execution_time")


def sonar_stage(case: dict) -> str:
    """The last pipeline stage the case cleared (mirrors observations.sonar_stage)."""
    if not case.get("applied"):
        return "not_applied"
    if not case.get("compiled"):
        return "applied"
    if not case.get("tests_passed"):
        return "compiled"
    if not case.get("target_resolved"):
        return "tests_passed"
    if not clean_fix(case):
        return "resolved"
    return "clean_fix"


def rep_frame(ref: RunRef) -> pd.DataFrame:
    """One row per (suite, repetition, case) from each rep-NN/report.json.
    `passed` is NaN for repetitions the aggregate excludes as harness errors."""
    rows = []
    suites = ref.run.get("suites") or {}
    for suite in SUITES:
        criterion = (suites.get(suite) or {}).get("criterion")
        for directory in repetition_directories(ref.path / suite):
            report = ResultsManager.load_report(directory)
            # For a repetition generated with --no-sonar and validated later,
            # only the generation ran on the model's machine.
            rep_wall_time = report.get("generation_wall_time", (report.get("summary") or {}).get("wall_time"))
            rep = report.get("repetition") or int(directory.name.removeprefix("rep-"))
            if suite == "sonar" and criterion is None:
                criterion = "clean_fix" if report.get("sonar_analyzed") else "tests_passed"
            for case in report.get("cases", []):
                if suite == "markdown":
                    passed = bool(case.get("matched"))
                    stage = "matched" if passed else "mismatch"
                    error = _is_harness_error(case)
                else:
                    passed = clean_fix(case) if criterion == "clean_fix" else bool(case.get("tests_passed"))
                    stage = sonar_stage(case)
                    error = _is_harness_error(case) or (
                        criterion == "clean_fix" and case.get("tests_passed") and not case.get("sonar_analyzed")
                    )
                rows.append({
                    "run_id": ref.run_id,
                    "model": ref.model,
                    "group": ref.group,
                    "suite": suite,
                    "rep": rep,
                    "case_id": case["case_id"],
                    "harness_error": bool(error),
                    "passed": math.nan if error else float(passed),
                    "stage": "error" if error else stage,
                    "config": report.get("config"),
                    "execution_time": case.get("execution_time"),
                    "prompt_tokens": case.get("prompt_tokens"),
                    "completion_tokens": case.get("completion_tokens"),
                    "tokens_per_second": case.get("tokens_per_second"),
                    "gpu_memory_mb": case.get("gpu_memory_mb"),
                    "gpu_power_w": case.get("gpu_power_w"),
                    "cpu_power_w": case.get("cpu_power_w"),
                    "energy_wh": case.get("energy_wh"),
                    "gpu_other_processes": case.get("gpu_other_processes"),
                    "rep_wall_time": rep_wall_time,
                })
    return pd.DataFrame(rows)
