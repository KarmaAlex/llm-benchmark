import argparse
import json

import pytest

from runner import run_all_models as batch
from runner.reproducibility import runs


@pytest.fixture
def project(tmp_path, monkeypatch):
    """configs/, models/ and results/ for a small fake project:

        local-a    base config only, weights present
        local-b    -markdown / -sonar variants, weights missing
        local-c    base + -sonar variant, weights present
        api        openai
        models/orphan.gguf is referenced by no config
    """
    configs, models, results = tmp_path / "configs", tmp_path / "models", tmp_path / "results"
    for directory in (configs, models, results):
        directory.mkdir()

    def config(stem, name, provider, model):
        (configs / f"{stem}.yaml").write_text(
            f"name: {name}\nprovider: {provider}\nmodel: {model}\n", encoding="utf-8"
        )

    config("local-a", "Local-A", "llama.cpp", "models/a.gguf")
    config("local-b-markdown", "Local-B (markdown)", "llama.cpp", "models/b.gguf")
    config("local-b-sonar", "Local-B (sonar)", "llama.cpp", "models/b.gguf")
    config("local-c", "Local-C", "llama.cpp", "models/c.gguf")
    config("local-c-sonar", "Local-C (sonar)", "llama.cpp", "models/c.gguf")
    config("api", "Api-Model", "openai", "gpt-5")
    for name in ("a.gguf", "c.gguf", "orphan.gguf"):
        (models / name).write_bytes(b"")

    monkeypatch.setattr(batch, "CONFIG_DIR", configs)
    monkeypatch.setattr(batch, "MODELS_DIR", models)
    monkeypatch.setattr(batch, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr("runner.cli.loading.CONFIG_DIR", configs)
    monkeypatch.setattr(runs, "RESULTS_DIR", results)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    return tmp_path


def write_full_run(results, name, model, *, repetitions=2, edit_mode="structured"):
    """The smallest run is_full_run accepts."""
    path = results / name
    suites = {}
    for suite in ("markdown", "sonar"):
        for rep in range(1, repetitions + 1):
            directory = path / suite / f"rep-{rep:02d}"
            directory.mkdir(parents=True)
            (directory / "report.json").write_text("{}", encoding="utf-8")
        suites[suite] = {
            "criterion": "clean_fix" if suite == "sonar" else "matched",
            "repetitions": repetitions,
            "cases": [{"case_id": "x", "repetitions": repetitions}],
        }
    run = {
        "settings": {"repetitions": repetitions, "suites": ["markdown", "sonar"], "edit_mode": edit_mode,
                     "sonar": True, "cases": None,
                     "configs": {"markdown": f"{model} (markdown)", "sonar": f"{model} (sonar)"}},
        "suites": suites,
        "pending_validation": [],
    }
    (path / "reproducibility.json").write_text(json.dumps(run), encoding="utf-8")


def args(**overrides):
    defaults = dict(models=None, exclude=[], local_only=False, rerun=False, repetitions=2,
                    suites=["markdown", "sonar"], edit_mode="structured", device="cuda", sonar=True)
    return argparse.Namespace(**{**defaults, **overrides})


def bases(candidates):
    return [c.base for c in candidates]


def test_base_configs_strip_suite_suffixes(project):
    assert batch.base_configs() == ["api", "local-a", "local-b", "local-c"]


def test_plan_runs_available_models_local_first(project):
    to_run, skipped, unavailable = batch.plan(args())
    assert bases(to_run) == ["local-a", "local-c", "api"]
    assert skipped == []
    assert [(c.base, c.problem) for c in unavailable] == [("local-b", "weights not found: models/b.gguf")]


def test_suite_variant_is_preferred_over_base(project):
    candidate = batch.examine("local-c", ["markdown", "sonar"])
    assert candidate.configs == {"markdown": "local-c", "sonar": "local-c-sonar"}
    assert candidate.model == "Local-C"


def test_api_models_need_a_key_and_are_dropped_by_local_only(project, monkeypatch):
    _to_run, _skipped, unavailable = batch.plan(args(local_only=True))
    assert ("api", "API model (--local-only)") in [(c.base, c.problem) for c in unavailable]

    monkeypatch.delenv("OPENAI_API_KEY")
    _to_run, _skipped, unavailable = batch.plan(args())
    assert ("api", "OPENAI_API_KEY not set") in [(c.base, c.problem) for c in unavailable]


def test_models_with_a_matching_full_run_are_skipped_unless_rerun(project):
    write_full_run(project / "results", "2026-01-01_00-00-00", "Local-A")
    to_run, skipped, _unavailable = batch.plan(args())
    assert bases(skipped) == ["local-a"]
    assert skipped[0].existing_run == "2026-01-01_00-00-00"
    assert "local-a" not in bases(to_run)

    to_run, skipped, _unavailable = batch.plan(args(rerun=True))
    assert "local-a" in bases(to_run) and skipped == []


@pytest.mark.parametrize("setting", [{"repetitions": 3}, {"edit_mode": "diff"}])
def test_full_run_with_different_settings_does_not_count(project, setting):
    write_full_run(project / "results", "2026-01-01_00-00-00", "Local-A", **setting)
    to_run, skipped, _unavailable = batch.plan(args())
    assert "local-a" in bases(to_run) and skipped == []


def test_model_selection_and_exclusion(project):
    to_run, _skipped, _unavailable = batch.plan(args(models=["local-a", "api"], exclude=["api"]))
    assert bases(to_run) == ["local-a"]
    with pytest.raises(SystemExit, match="Unknown base config"):
        batch.plan(args(models=["nope"]))


def test_orphan_weights_are_reported(project):
    assert batch.orphan_weights() == ["orphan.gguf"]


def test_reproducibility_command_passes_settings_through(project):
    candidate = batch.examine("local-a", ["markdown"])
    command = batch.reproducibility_command(candidate, args(suites=["markdown"], sonar=False, device="cpu"))
    assert command[1:] == [
        "-m", "runner.run_all_reproducibility", "--model", "local-a", "--repetitions", "2",
        "--suites", "markdown", "--edit-mode", "structured", "--device", "cpu", "--no-sonar",
    ]


def test_run_batch_records_outcomes_and_new_run_directories(project, monkeypatch):
    results = project / "results"
    calls = []

    def fake_run(command, cwd):
        base = command[command.index("--model") + 1]
        calls.append(base)
        if base == "local-a":
            write_full_run(results, "2026-01-02_00-00-00", "Local-A")
            return argparse.Namespace(returncode=0)
        return argparse.Namespace(returncode=2)

    monkeypatch.setattr(batch.subprocess, "run", fake_run)
    to_run, _skipped, _unavailable = batch.plan(args())

    outcomes = batch.run_batch(to_run, args(stop_on_failure=False))
    assert calls == ["local-a", "local-c", "api"]
    assert [(o["base"], o["status"], o["run"]) for o in outcomes] == [
        ("local-a", "ok", "2026-01-02_00-00-00"),
        ("local-c", "failed (exit 2)", None),
        ("api", "failed (exit 2)", None),
    ]

    calls.clear()
    outcomes = batch.run_batch(to_run[1:], args(stop_on_failure=True))
    assert calls == ["local-c"] and len(outcomes) == 1


def test_require_free_gpu_is_passed_through(project):
    candidate = batch.examine("local-a", ["markdown"])
    command = batch.reproducibility_command(candidate, args(suites=["markdown"], require_free_gpu=True))
    assert command[-1] == "--require-free-gpu"


def test_occupied_gpu_warns_or_stops_the_run(monkeypatch, capsys):
    from runner import run_all_reproducibility as repro

    occupant = [{"pid": "5555", "used_memory_mb": 63744.0}]
    monkeypatch.setattr(repro, "gpu_occupants", lambda: occupant)
    assert repro.check_gpu_is_free(required=False) == occupant
    assert "pid 5555 (63744 MiB)" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="--require-free-gpu"):
        repro.check_gpu_is_free(required=True)

    monkeypatch.setattr(repro, "gpu_occupants", lambda: [])
    assert repro.check_gpu_is_free(required=True) == []
