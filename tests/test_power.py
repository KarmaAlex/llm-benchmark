from types import SimpleNamespace

import pytest

from runner.core.stats import power_summary
from runner.markdown_tests.report import compute_summary
from runner.models.markdown_case_result import MarkdownCaseResult
from runner.providers import power


def sampler(**samples):
    """A sampler with no live sources and the given (time, watts) samples."""
    s = power.PowerSampler(gpu=False, cpu=False)
    s._gpu.extend(samples.get("gpu", []))
    s._cpu.extend(samples.get("cpu", []))
    return s


def test_reading_averages_the_call_window_and_integrates_energy():
    s = sampler(gpu=[(0.5, 10.0), (1.0, 50.0), (2.0, 60.0), (3.0, 40.0), (9.0, 99.0)],
                cpu=[(1.5, 20.0), (2.5, 30.0)])
    reading = s.reading(1.0, 3.0)
    assert reading.gpu_power_w == pytest.approx(50.0)
    assert reading.gpu_power_peak_w == 60.0
    assert reading.cpu_power_w == pytest.approx(25.0)
    assert reading.cpu_power_peak_w == 30.0
    assert reading.energy_wh == pytest.approx((50 + 25) * 2 / 3600)


def test_short_call_uses_the_first_sample_just_after_it():
    s = sampler(gpu=[(1.0, 10.0), (2.3, 45.0), (5.0, 70.0)])
    reading = s.reading(2.0, 2.1)  # no sample inside; 2.3 is within the grace window
    assert reading.gpu_power_w == 45.0
    assert reading.cpu_power_w is None
    assert reading.energy_wh == pytest.approx(45 * 0.1 / 3600)


def test_nothing_measured_reads_as_none():
    assert sampler().reading(0, 10) == power.PowerReading()


def test_gpu_readings_above_the_ceiling_or_unparseable_are_dropped():
    s = sampler()
    s._gpu_ceiling = 112.5
    s._process = SimpleNamespace(stdout=iter(["57.20\n", "590.01\n", "[N/A]\n", "0\n", "60.5\n"]))
    s._read_gpu()
    assert [w for _t, w in s._gpu] == [57.2, 60.5]


def test_wait_for_samples_only_ever_waits_once(monkeypatch):
    s = sampler()
    s._process = object()  # a GPU source that never yields a valid sample
    s.interval = 0.01
    naps = []
    monkeypatch.setattr(power.time, "sleep", lambda seconds: naps.append(seconds))
    s.wait_for_samples(timeout=0.05)
    first = len(naps)
    s.wait_for_samples(timeout=0.05)
    assert first > 0 and len(naps) == first


def test_rapl_counter_deltas_handle_wraparound(tmp_path, monkeypatch):
    zone = tmp_path / "intel-rapl:0"
    zone.mkdir()
    (zone / "name").write_text("package-0\n")
    (zone / "max_energy_range_uj").write_text("1000000\n")
    energy = zone / "energy_uj"
    clock = iter([10.0, 11.0, 12.0])
    monkeypatch.setattr(power.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(power, "POWERCAP_DIR", tmp_path)

    energy.write_text("900000\n")
    source = power.RaplPackage.find()
    assert source.watts() is None           # first read only sets the baseline
    energy.write_text("950000\n")
    assert source.watts() == pytest.approx(0.05)
    energy.write_text("50000\n")            # wrapped past 1,000,000
    assert source.watts() == pytest.approx(0.1)


def test_unreadable_rapl_counter_is_skipped(tmp_path, monkeypatch):
    zone = tmp_path / "intel-rapl:0"
    zone.mkdir()
    (zone / "name").write_text("package-0\n")  # no readable energy_uj (root-only)
    monkeypatch.setattr(power, "POWERCAP_DIR", tmp_path)
    assert power.RaplPackage.find() is None


def fake_hwmon(root, index, name, label, vram_bytes, microwatts):
    hwmon = root / f"hwmon{index}"
    device = hwmon / "device"
    device.mkdir(parents=True)
    (hwmon / "name").write_text(f"{name}\n")
    (hwmon / "power1_label").write_text(f"{label}\n")
    (hwmon / "power1_input").write_text(f"{microwatts}\n")
    (device / "mem_info_vram_total").write_text(f"{vram_bytes}\n")


def test_apu_ppt_is_used_but_a_discrete_amd_card_is_not(tmp_path, monkeypatch):
    monkeypatch.setattr(power, "HWMON_DIR", tmp_path)
    fake_hwmon(tmp_path, 0, "amdgpu", "PPT", 16 * 1024**3, 150_000_000)  # discrete card
    fake_hwmon(tmp_path, 1, "nvme", "PPT", 0, 5_000_000)
    assert power.ApuPpt.find() is None

    fake_hwmon(tmp_path, 2, "amdgpu", "PPT", 512 * 1024**2, 33_587_000)   # APU carve-out
    source = power.ApuPpt.find()
    assert source is not None and source.watts() == pytest.approx(33.587)


def result(execution_time, gpu=None, gpu_peak=None, cpu=None, energy=None):
    return MarkdownCaseResult(case_id="md001", difficulty=1, matched=True, execution_time=execution_time,
                              gpu_power_w=gpu, gpu_power_peak_w=gpu_peak, cpu_power_w=cpu, energy_wh=energy)


def test_power_summary_weights_by_call_time():
    summary = power_summary([result(1.0, gpu=30, gpu_peak=40, cpu=10, energy=0.01),
                             result(3.0, gpu=50, gpu_peak=65, cpu=20, energy=0.05),
                             result(2.0)])
    assert summary["avg_gpu_power_w"] == pytest.approx((30 * 1 + 50 * 3) / 4)
    assert summary["peak_gpu_power_w"] == 65
    assert summary["avg_cpu_power_w"] == pytest.approx((10 * 1 + 20 * 3) / 4)
    assert summary["peak_cpu_power_w"] is None
    assert summary["total_energy_wh"] == pytest.approx(0.06)


def test_unmeasured_run_summary_has_power_fields_set_to_none():
    summary = compute_summary([result(1.0), result(2.0)], wall_time=3.0)
    for key in ("avg_gpu_power_w", "peak_gpu_power_w", "avg_cpu_power_w", "peak_cpu_power_w", "total_energy_wh"):
        assert key in summary and summary[key] is None


# --------------------------------------------------------------------------- #
# which GPU (gpu_memory)
# --------------------------------------------------------------------------- #

from runner.providers import gpu_memory  # noqa: E402


@pytest.mark.parametrize("value, visible, selector", [
    (None, None, "0"),                         # not set: every GPU, measure GPU 0
    ("0", ["0"], "0"),
    ("3,5", ["3", "5"], "3"),                   # SLURM without device cgroups: physical indices
    ("GPU-8f2e", ["GPU-8f2e"], "GPU-8f2e"),
    ("MIG-1a2b", ["MIG-1a2b"], None),           # a MIG slice has no board readings
    ("NoDevFiles", [], None),                   # SLURM job without a GPU
    ("", [], None),
])
def test_queries_target_the_gpus_cuda_will_use(monkeypatch, value, visible, selector):
    if value is None:
        monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    else:
        monkeypatch.setenv("CUDA_VISIBLE_DEVICES", value)
    assert gpu_memory.visible_gpus() == visible
    assert gpu_memory.gpu_selector() == selector


def fake_smi(monkeypatch, apps):
    calls = []

    def fake(*args, timeout=5):
        calls.append(args)
        return ["71234"] if "--query-gpu=memory.used" in args else apps

    monkeypatch.setattr(gpu_memory, "nvidia_smi", fake)
    return calls


def test_memory_and_process_queries_pass_the_selector(monkeypatch):
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "2")
    calls = fake_smi(monkeypatch, [f"{gpu_memory.os.getpid()}, 3400"])
    gpu_memory.get_gpu_memory_used_mb()
    assert gpu_memory.other_gpu_processes() == 0
    assert all(args[-2:] == ("-i", "2") for args in calls)


def test_memory_counts_only_this_process_on_a_shared_gpu(monkeypatch):
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")
    fake_smi(monkeypatch, [f"{gpu_memory.os.getpid()}, 3400", "5555, 63744"])
    assert gpu_memory.get_gpu_memory_used_mb() == 3400      # not 3400 + someone else's 63744


def test_memory_falls_back_to_the_whole_gpu_when_processes_are_hidden(monkeypatch):
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")
    fake_smi(monkeypatch, [])
    assert gpu_memory.get_gpu_memory_used_mb() == 71234


def test_occupants_before_a_model_loads(monkeypatch):
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")
    fake_smi(monkeypatch, ["1233, 7", "5555, 63744"])
    assert gpu_memory.gpu_occupants() == [{"pid": "5555", "used_memory_mb": 63744.0}]
    fake_smi(monkeypatch, [])
    assert gpu_memory.gpu_occupants() == []


@pytest.mark.parametrize("others, expected", [
    (["1233, 7"], 0),                     # a desktop compositor isn't a co-tenant
    (["1233, 7", "5555, 60000"], 1),      # another job with a model loaded is
    (["5555, [N/A]"], 1),                 # unknown memory: can't rule it out
])
def test_only_sizeable_other_processes_count_as_sharing(monkeypatch, others, expected):
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")
    fake_smi(monkeypatch, [f"{gpu_memory.os.getpid()}, 3400", *others])
    assert gpu_memory.other_gpu_processes() == expected


@pytest.mark.parametrize("apps", [[], ["1001, 3400", "2002, 900"]])
def test_sharing_is_unknown_when_this_process_is_not_listed(monkeypatch, apps):
    """Hidden processes, or a container's own PID namespace."""
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0")
    fake_smi(monkeypatch, apps)
    assert gpu_memory.other_gpu_processes() is None


def test_gpu_names_list_each_allocated_gpu(monkeypatch):
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0,MIG-1a2b")
    monkeypatch.setattr(gpu_memory, "nvidia_smi", lambda *args, timeout=5: ["NVIDIA H200 NVL"])
    assert gpu_memory.gpu_names() == ["NVIDIA H200 NVL", "MIG slice"]


def test_shared_cases_are_counted_in_the_summary():
    shared = MarkdownCaseResult(case_id="a", difficulty=1, matched=True, execution_time=1.0, gpu_other_processes=1)
    alone = MarkdownCaseResult(case_id="b", difficulty=1, matched=True, execution_time=1.0, gpu_other_processes=0)
    assert power_summary([shared, alone])["gpu_shared_cases"] == 1
    assert power_summary([result(1.0)])["gpu_shared_cases"] is None


def test_first_validation_keeps_the_generation_wall_time(tmp_path, monkeypatch):
    import json

    from runner import validate_sonar_run

    run = tmp_path / "rep-01"
    (run / "S1000" / "project").mkdir(parents=True)
    case = {"case_id": "S1000", "edit_mode": "structured", "applied": True, "compiled": False,
            "execution_time": 2.0, "compile_time": 0.0}
    (run / "report.json").write_text(json.dumps(
        {"validated": False, "summary": {"wall_time": 90.0}, "cases": [case]}))
    monkeypatch.setattr(validate_sonar_run, "validate_case", lambda directory: {"compiled": True})
    monkeypatch.setattr(validate_sonar_run, "print_report", lambda *a: None)
    monkeypatch.setattr("sys.argv", ["validate_sonar_run", str(run)])

    validate_sonar_run.main()
    report = json.loads((run / "report.json").read_text())
    assert report["validated"] is True
    assert report["generation_wall_time"] == 90.0
    assert report["summary"]["wall_time"] >= 90.0

    validate_sonar_run.main()  # a re-validation must not overwrite it with the combined time
    assert json.loads((run / "report.json").read_text())["generation_wall_time"] == 90.0
