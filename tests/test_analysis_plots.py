import argparse
import json
import math

import pytest

pytest.importorskip("pandas")

from analysis import aggregate as agg  # noqa: E402
from analysis import costs as cost  # noqa: E402
from analysis import statistics as stats  # noqa: E402
from runner.reproducibility.aggregate import AGGREGATE_FILE_NAME, aggregate_run  # noqa: E402

CATALOG = {"Model-A": "openai", "Model-A (markdown)": "openai", "Model-B": "llama.cpp"}
MODEL_IDS = {"Model-A": "gpt-5", "Model-B": "models/b.gguf"}


def markdown_case(case_id, matched, text='{"a": 1}'):
    return {"case_id": case_id, "difficulty": 1, "matched": matched, "execution_time": 1.5,
            "prompt_tokens": 1000, "completion_tokens": 12, "response_text": text}


def sonar_case(case_id, *, clean=True, resolved=True, tests=True, analyzed=True, diff="+fix"):
    return {"case_id": case_id, "edit_mode": "structured", "applied": True, "compiled": True,
            "execution_time": 2.0, "compile_time": 1.0, "tests_ran": True, "tests_passed": tests,
            "prompt_tokens": 4000, "completion_tokens": 30, "response_text": diff, "diff": diff, "sonar_analyzed": analyzed,
            "target_resolved": resolved, "new_issues_count": 0 if clean else 1}


def harness_error_case(case_id):
    return {"case_id": case_id, "difficulty": 1, "matched": False, "execution_time": 0,
            "error": "boom", "response_text": None}


def make_run(results_dir, name, *, model="Model-A", repetitions=2, suites=("markdown", "sonar"),
             cases=None, sonar=True, drop_rep=None, markdown_cases=None, sonar_cases=None):
    """Write a reproducibility run the way run_all_reproducibility does:
    rep-NN/report.json per suite, then the real aggregate on top."""
    path = results_dir / name
    markdown_cases = markdown_cases or (lambda rep: [markdown_case("md001", True), markdown_case("md002", rep == 1, text=f'{{"a": {rep}}}')])
    sonar_cases = sonar_cases or (lambda rep: [sonar_case("S1000"), sonar_case("S2000", clean=False)])
    for suite in suites:
        for rep in range(1, repetitions + 1):
            if rep == drop_rep:
                continue
            directory = path / suite / f"rep-{rep:02d}"
            directory.mkdir(parents=True)
            report = {"config": f"{model} ({suite})", "repetition": rep, "summary": {}}
            if suite == "markdown":
                report["cases"] = markdown_cases(rep)
            else:
                report.update(edit_mode="structured", sonar_analyzed=sonar, cases=sonar_cases(rep))
            (directory / "report.json").write_text(json.dumps(report), encoding="utf-8")

    settings = {"repetitions": repetitions, "suites": list(suites),
                "configs": {s: f"{model} ({s})" for s in suites}, "edit_mode": "structured",
                "sonar": sonar, "cases": cases}
    (path / AGGREGATE_FILE_NAME).write_text(json.dumps(aggregate_run(path, settings)), encoding="utf-8")
    return path


def ref_for(path):
    return agg.load_run_ref(path, CATALOG)


# --------------------------------------------------------------------------- #
# models and groups
# --------------------------------------------------------------------------- #


def test_model_key_strips_suite_suffix_only():
    assert agg.model_key("GPT-5 (sonar)") == "GPT-5"
    assert agg.model_key("Gemma-4-E4B-Q4-UD (markdown)") == "Gemma-4-E4B-Q4-UD"
    assert agg.model_key("Qwen2.5-Coder-7B-FP16") == "Qwen2.5-Coder-7B-FP16"


def test_group_from_provider_and_override():
    assert agg.group_of("Model-A", CATALOG) == agg.COMMERCIAL
    assert agg.group_of("Model-B", CATALOG) == agg.OPEN_SOURCE
    assert agg.group_of("Model-C", CATALOG) == agg.UNKNOWN
    overrides = agg.parse_group_overrides(["Model-C=open", "Model-A=open"])
    assert agg.group_of("Model-C", CATALOG, overrides) == agg.OPEN_SOURCE
    assert agg.group_of("Model-A", CATALOG, overrides) == agg.OPEN_SOURCE


def test_bad_group_override_is_rejected():
    with pytest.raises(ValueError):
        agg.parse_group_overrides(["Model-A=proprietary"])


def test_model_catalog_reads_config_names(tmp_path):
    (tmp_path / "x.yaml").write_text("name: X-Model (sonar)\nprovider: llama.cpp\n", encoding="utf-8")
    catalog = agg.model_catalog(tmp_path)
    assert catalog["X-Model"] == "llama.cpp"
    assert catalog["X-Model (sonar)"] == "llama.cpp"


# --------------------------------------------------------------------------- #
# full-run detection and selection
# --------------------------------------------------------------------------- #


def test_complete_run_is_full(tmp_path):
    ref = ref_for(make_run(tmp_path, "2026-01-01_00-00-00"))
    assert (ref.full, ref.reason) == (True, "")
    assert ref.model == "Model-A"
    assert ref.group == agg.COMMERCIAL


@pytest.mark.parametrize("kwargs, reason", [
    ({"suites": ("markdown",)}, "suite(s) not run: sonar"),
    ({"cases": ["md001"]}, "restricted to --cases md001"),
    ({"sonar": False}, "run with --no-sonar"),
    ({"drop_rep": 2}, "markdown: 1/2 repetitions completed"),
])
def test_incomplete_runs_are_not_full(tmp_path, kwargs, reason):
    ref = ref_for(make_run(tmp_path, "2026-01-01_00-00-00", **kwargs))
    assert not ref.full
    assert ref.reason == reason


def test_pending_validation_is_not_full(tmp_path):
    path = make_run(tmp_path, "2026-01-01_00-00-00")
    run = json.loads((path / AGGREGATE_FILE_NAME).read_text())
    run["pending_validation"] = ["sonar"]
    assert agg.is_full_run(run, path) == (False, "not yet validated: sonar")


def test_latest_full_run_per_model_skips_newer_partial_runs(tmp_path):
    make_run(tmp_path, "2026-01-01_00-00-00", model="Model-A")
    make_run(tmp_path, "2026-01-02_00-00-00", model="Model-A")
    make_run(tmp_path, "2026-01-03_00-00-00", model="Model-A", drop_rep=2)
    make_run(tmp_path, "2026-01-01_12-00-00", model="Model-B")

    refs = agg.all_run_refs(tmp_path, catalog=CATALOG)
    assert [r.run_id for r in refs][0] == "2026-01-03_00-00-00"

    selected = agg.latest_full_runs(refs)
    assert [(r.model, r.run_id) for r in selected] == [
        ("Model-A", "2026-01-02_00-00-00"),  # commercial first
        ("Model-B", "2026-01-01_12-00-00"),
    ]
    assert [r.model for r in agg.latest_full_runs(refs, ["model-b"])] == ["Model-B"]
    assert agg.comparability_warnings(selected) == []


def test_comparability_warnings_flag_missing_group_and_setting_mismatch(tmp_path):
    a = ref_for(make_run(tmp_path, "2026-01-01_00-00-00", model="Model-A", repetitions=2))
    b = ref_for(make_run(tmp_path, "2026-01-02_00-00-00", model="Model-A", repetitions=3))
    b.model = "Other"
    warnings = agg.comparability_warnings([a, b])
    assert any("repetitions" in w for w in warnings)
    assert any("open source" in w for w in warnings)


# --------------------------------------------------------------------------- #
# frames and statistics
# --------------------------------------------------------------------------- #


def test_rep_frame_matches_aggregate_and_marks_harness_errors(tmp_path):
    path = make_run(
        tmp_path, "2026-01-01_00-00-00",
        markdown_cases=lambda rep: [markdown_case("md001", True),
                                    harness_error_case("md002") if rep == 2 else markdown_case("md002", False)],
    )
    ref = ref_for(path)
    reps = agg.rep_frame(ref)

    error = reps[(reps["suite"] == "markdown") & (reps["case_id"] == "md002") & (reps["rep"] == 2)].iloc[0]
    assert error["harness_error"] and math.isnan(error["passed"]) and error["stage"] == "error"

    cases = agg.case_frame(ref)
    for (suite, case_id), frame in reps.groupby(["suite", "case_id"]):
        row = cases[(cases["suite"] == suite) & (cases["case_id"] == case_id)].iloc[0]
        assert frame["passed"].sum() == row["pass_count"]
        assert frame["passed"].count() == row["n"]


def test_sonar_stage_derivation(tmp_path):
    assert agg.sonar_stage(sonar_case("S1")) == "clean_fix"
    assert agg.sonar_stage(sonar_case("S1", clean=False)) == "resolved"
    assert agg.sonar_stage(sonar_case("S1", resolved=False)) == "tests_passed"
    assert agg.sonar_stage(sonar_case("S1", tests=False)) == "compiled"
    assert agg.sonar_stage({"applied": False}) == "not_applied"


def test_funnel_rates_are_cumulative(tmp_path):
    ref = ref_for(make_run(tmp_path, "2026-01-01_00-00-00"))
    funnel = stats.funnel_rates(agg.stage_frame(ref)).set_index("stage")["rate"]
    # S1000 is a clean fix, S2000 stops at "resolved", both reps.
    assert funnel["applied"] == funnel["compiled"] == funnel["tests_passed"] == funnel["resolved"] == 1.0
    assert funnel["clean_fix"] == 0.5


def test_summary_table_pools_trials_with_wilson_interval(tmp_path):
    ref = ref_for(make_run(tmp_path, "2026-01-01_00-00-00"))
    summary = stats.summary_table(agg.suite_frame(ref), agg.case_frame(ref)).set_index("suite")
    markdown = summary.loc["markdown"]
    assert (markdown["passes"], markdown["trials"]) == (3, 4)
    assert markdown["pass_rate"] == 0.75
    assert markdown["pass_rate_ci_low"] < 0.75 < markdown["pass_rate_ci_high"]
    assert markdown["share_flaky"] == 0.5


def test_wilson_interval_bounds():
    assert all(math.isnan(bound) for bound in stats.wilson_interval(0, 0))
    low, high = stats.wilson_interval(10, 10)
    assert high == 1.0 and 0.6 < low < 1.0
    low, high = stats.wilson_interval(0, 10)
    assert low == 0.0 and 0.0 < high < 0.4


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #


def test_single_run_plots_render(tmp_path):
    pytest.importorskip("seaborn")
    from analysis.plot_reproducibility import plot_run

    ref = ref_for(make_run(tmp_path, "2026-01-01_00-00-00"))
    written = plot_run(ref, tmp_path / "plots")
    names = {p.stem for p in written}
    assert {"classification", "pass_matrix", "repetition_rate", "case_stability",
            "sonar_funnel", "latency_tokens"} <= names
    assert all(p.stat().st_size > 0 for p in written)


def test_comparison_writes_figures_and_tables(tmp_path):
    pytest.importorskip("seaborn")
    from analysis.compare_models import build_frames, plot_comparison, write_tables

    make_run(tmp_path, "2026-01-01_00-00-00", model="Model-A")
    make_run(tmp_path, "2026-01-02_00-00-00", model="Model-B")
    selected = agg.latest_full_runs(agg.all_run_refs(tmp_path, catalog=CATALOG))
    frames = build_frames(selected, providers=CATALOG, model_ids=MODEL_IDS)
    out = tmp_path / "comparison"
    written = plot_comparison(frames, out) + write_tables(frames, selected, out)

    assert {p.name for p in written} >= {
        "pass_rate.png", "classification.png", "case_heatmap.png", "agreement.png",
        "sonar_funnel.png", "efficiency.png", "group_summary.png", "cost.png",
        "summary.csv", "group_summary.csv", "costs.csv", "cost_assumptions.json", "selected_runs.json",
    }
    assumptions = json.loads((out / "cost_assumptions.json").read_text())
    assert assumptions["eur_per_kwh"] == cost.ELECTRICITY_EUR_PER_KWH
    assert assumptions["openai_prices_usd_per_1m"]["gpt-5"]["output"] == 10.0
    runs = json.loads((out / "selected_runs.json").read_text())
    assert [(r["model"], r["group"]) for r in runs] == [("Model-A", agg.COMMERCIAL), ("Model-B", agg.OPEN_SOURCE)]


# --------------------------------------------------------------------------- #
# cost
# --------------------------------------------------------------------------- #


def costed(tmp_path, model, assumptions=None):
    ref = ref_for(make_run(tmp_path, "2026-01-01_00-00-00", model=model))
    return ref, cost.trial_costs(ref, assumptions or cost.CostAssumptions(), CATALOG, MODEL_IDS)


def test_api_trials_cost_list_price_in_euros(tmp_path):
    _ref, trials = costed(tmp_path, "Model-A")
    markdown = trials[trials["suite"] == "markdown"].iloc[0]
    expected_usd = (1000 * 1.25 + 12 * 10.00) / 1_000_000
    assert markdown["cost_basis"] == cost.API
    assert markdown["api_model"] == "gpt-5"
    assert markdown["cost_eur"] == pytest.approx(expected_usd / cost.USD_PER_EUR)
    # A known price has no uncertainty band.
    assert markdown["cost_eur_low"] == markdown["cost_eur"] == markdown["cost_eur_high"]


def test_local_trials_cost_electricity_with_a_power_band(tmp_path):
    assumptions = cost.CostAssumptions(local_watts=100, local_watts_low=50, local_watts_high=200, eur_per_kwh=0.30)
    _ref, trials = costed(tmp_path, "Model-B", assumptions)
    markdown = trials[trials["suite"] == "markdown"].iloc[0]
    kwh = 1.5 / 3600 * 100 / 1000
    assert markdown["cost_basis"] == cost.ELECTRICITY
    assert markdown["api_model"] == ""
    assert markdown["kwh"] == pytest.approx(kwh)
    assert markdown["cost_eur"] == pytest.approx(kwh * 0.30)
    assert markdown["cost_eur_low"] == pytest.approx(kwh * 0.30 / 2)
    assert markdown["cost_eur_high"] == pytest.approx(kwh * 0.30 * 2)


def test_unknown_models_are_unpriced_not_free(tmp_path):
    _ref, trials = costed(tmp_path, "Model-C")
    assert set(trials["cost_basis"]) == {cost.UNPRICED}
    assert trials["cost_eur"].isna().all()


def test_cost_summary_per_repetition_and_per_pass(tmp_path):
    ref, trials = costed(tmp_path, "Model-A")
    summary = stats.summary_table(agg.suite_frame(ref), agg.case_frame(ref))
    markdown = cost.cost_summary(trials, summary).set_index("suite").loc["markdown"]
    per_trial = (1000 * 1.25 + 12 * 10.00) / 1_000_000 / cost.USD_PER_EUR
    # 2 cases x 2 reps; 3 of the 4 trials pass.
    assert markdown["total_cost_eur"] == pytest.approx(4 * per_trial)
    assert markdown["cost_per_rep_eur"] == pytest.approx(2 * per_trial)
    assert markdown["cost_per_pass_eur"] == pytest.approx(4 * per_trial / 3)
    assert (markdown["prompt_tokens"], markdown["completion_tokens"]) == (4000, 48)


def test_watts_band_always_contains_the_estimate():
    parser = argparse.ArgumentParser()
    cost.add_cost_arguments(parser)
    assumptions = cost.assumptions_from_args(parser.parse_args(["--local-watts", "150", "--local-watts-range", "120", "60"]))
    assert (assumptions.local_watts_low, assumptions.local_watts, assumptions.local_watts_high) == (60, 150, 150)


@pytest.mark.parametrize("value, text", [
    (4.9307, "€4.93"), (0.49307, "€0.49"), (0.0902, "€0.090"), (0.0000553, "€0.000055"),
    (123.4, "€123"), (0.0, "€0"), (math.nan, "n/a"),
])
def test_format_eur(value, text):
    assert cost.format_eur(value) == text


def test_cost_axis_ticks_and_scale():
    pytest.importorskip("seaborn")
    from analysis.plots import _cost_scale, _euro_tick

    # Float noise from the tick locator must not reach the label.
    assert _euro_tick(6.000000000000001e-05) == "€0.00006"
    assert _euro_tick(0.0) == "€0"
    assert _euro_tick(0.12) == "€0.12"
    # Per attempt when that's readable, per 1,000 attempts below €0.10.
    assert _cost_scale(0.5) == 1
    assert _cost_scale(0.045) == 1_000
    assert _cost_scale(0.00012) == 1_000
    assert _cost_scale(0.00000005) == 1_000_000


def test_measured_energy_replaces_the_power_assumption(tmp_path):
    def measured(rep):
        cases = [markdown_case("md001", True), markdown_case("md002", True)]
        cases[0]["energy_wh"] = 0.5  # md002 predates power sampling
        return cases

    ref = ref_for(make_run(tmp_path, "2026-01-01_00-00-00", model="Model-B", markdown_cases=measured))
    trials = cost.trial_costs(ref, cost.CostAssumptions(eur_per_kwh=0.30), CATALOG, MODEL_IDS)
    markdown = trials[trials["suite"] == "markdown"].set_index("case_id")

    row = markdown.loc["md001"].iloc[0]
    assert row["cost_basis"] == cost.ELECTRICITY_MEASURED
    assert row["kwh"] == pytest.approx(0.0005)
    assert row["cost_eur"] == pytest.approx(0.0005 * 0.30)
    assert row["cost_eur_low"] == row["cost_eur_high"] == row["cost_eur"]
    assert set(markdown.loc["md002"]["cost_basis"]) == {cost.ELECTRICITY}

    note = cost.CostAssumptions().note(set(trials["cost_basis"]))
    assert "local (measured)" in note and "local (assumed)" in note


def with_hardware(path, gpus, slurm_job_id="42"):
    run = json.loads((path / AGGREGATE_FILE_NAME).read_text())
    run["settings"]["hardware"] = {"host": "node1", "gpus": gpus, "slurm_job_id": slurm_job_id}
    (path / AGGREGATE_FILE_NAME).write_text(json.dumps(run))
    return path


def test_runs_on_a_priced_gpu_are_costed_by_gpu_hour(tmp_path):
    def cases(rep):
        measured = markdown_case("md001", True)
        measured["energy_wh"] = 0.5  # measured, but a rented GPU is paid by the hour
        return [measured, markdown_case("md002", True)]

    path = with_hardware(make_run(tmp_path, "2026-01-01_00-00-00", model="Model-B", markdown_cases=cases),
                         ["NVIDIA H200 NVL"])
    trials = cost.trial_costs(ref_for(path), cost.CostAssumptions(), CATALOG, MODEL_IDS)
    row = trials[trials["suite"] == "markdown"].iloc[0]
    rate = cost.CostAssumptions().gpu_hour_price(["NVIDIA H200 NVL"])

    assert row["cost_basis"] == cost.GPU_HOURS
    assert row["gpu_hours"] == pytest.approx(1.5 / 3600)
    assert row["cost_eur"] == pytest.approx(1.5 / 3600 * 3.79 / cost.USD_PER_EUR)
    assert row["cost_eur_low"] == pytest.approx(1.5 / 3600 * rate.low)
    assert row["cost_eur_high"] == pytest.approx(1.5 / 3600 * rate.high)
    assert row["kwh"] == pytest.approx(0.0005)  # still recorded, just not what's billed


def test_site_rate_override_and_multi_gpu_jobs(tmp_path):
    parser = argparse.ArgumentParser()
    cost.add_cost_arguments(parser)
    assumptions = cost.assumptions_from_args(parser.parse_args(["--gpu-hour-price", "NVIDIA H200 NVL=2.00"]))
    assert assumptions.gpu_hour_overridden == ("nvidia h200 nvl",)
    assert "site rate" in assumptions.note({cost.GPU_HOURS})

    path = with_hardware(make_run(tmp_path, "2026-01-01_00-00-00", model="Model-B"),
                         ["NVIDIA H200 NVL", "NVIDIA H200 NVL"])
    trials = cost.trial_costs(ref_for(path), assumptions, CATALOG, MODEL_IDS)
    row = trials[trials["suite"] == "markdown"].iloc[0]
    assert row["gpu_hours"] == pytest.approx(2 * 1.5 / 3600)
    assert row["cost_eur"] == row["cost_eur_low"] == row["cost_eur_high"] == pytest.approx(2 * 1.5 / 3600 * 2.00)

    with pytest.raises(SystemExit, match="Bad --gpu-hour-price"):
        cost.assumptions_from_args(parser.parse_args(["--gpu-hour-price", "3.20"]))


def test_own_gpu_stays_on_electricity_but_reports_gpu_hours(tmp_path):
    path = with_hardware(make_run(tmp_path, "2026-01-01_00-00-00", model="Model-B"),
                         ["NVIDIA GeForce RTX 4050 Laptop GPU"], slurm_job_id=None)
    trials = cost.trial_costs(ref_for(path), cost.CostAssumptions(), CATALOG, MODEL_IDS)
    assert set(trials["cost_basis"]) == {cost.ELECTRICITY}
    assert trials["gpu_hours"].notna().all()


def test_cost_summary_reports_allocated_gpu_hours(tmp_path):
    path = with_hardware(make_run(tmp_path, "2026-01-01_00-00-00", model="Model-B"), ["NVIDIA H200 NVL"])
    for report_path in path.glob("*/rep-*/report.json"):
        report = json.loads(report_path.read_text())
        report["summary"] = {"wall_time": 1800.0}  # half an hour per repetition
        report_path.write_text(json.dumps(report))
    trials = cost.trial_costs(ref_for(path), cost.CostAssumptions(), CATALOG, MODEL_IDS)
    markdown = cost.cost_summary(trials).set_index("suite").loc["markdown"]
    assert markdown["allocated_gpu_hours"] == pytest.approx(2 * 0.5)  # 2 reps x 0.5 h x 1 GPU
    assert markdown["gpu_hours"] == pytest.approx(4 * 1.5 / 3600)


def test_cluster_run_on_an_unpriced_gpu_is_unpriced_not_household_electricity(tmp_path):
    path = with_hardware(make_run(tmp_path, "2026-01-01_00-00-00", model="Model-B"), ["NVIDIA L40S"])
    trials = cost.trial_costs(ref_for(path), cost.CostAssumptions(), CATALOG, MODEL_IDS)
    assert set(trials["cost_basis"]) == {cost.UNPRICED}
    assert trials["cost_eur"].isna().all()
    assert trials["gpu_hours"].notna().all()  # still counted as a resource
