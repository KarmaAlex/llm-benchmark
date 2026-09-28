"""Best-effort power sampling while a local model generates.

GPU memory can be read once after a call, but power can't: by the time the
call returns the GPU is idling again. So a PowerSampler runs in the
background for as long as a provider is loaded, and each call takes the
samples that fall inside its own time window:

    GPU   board power of this process's GPU (see gpu_memory.gpu_selector)
          from one streaming `nvidia-smi -lms` process (on Ampere and newer,
          power.draw is itself a 1 s average). If other jobs share that GPU
          their work is in the reading too - gpu_memory.other_gpu_processes
          tells a caller when that happened.
    CPU   package power, from the first readable of
            - the RAPL package energy counter (/sys/class/powercap), which
              is normally root-only;
            - the amdgpu "PPT" sensor of an AMD APU - the socket power of
              the whole chip, CPU cores and integrated GPU included.
              A discrete AMD card also reports a PPT, so it's used only
              when its VRAM is a small carve-out (an APU).

Neither source covers RAM, the display, storage or power-supply losses, so
energy_wh is what the GPU board and the CPU package drew - a lower bound on
what the machine drew from the wall.

Like gpu_memory.py this is dependency-free and returns None for whatever
the machine can't measure: CPU-only machines, non-NVIDIA GPUs, no readable
CPU sensor. Laptop GPUs can report nonsense while waking from runtime
suspend (590 W on a 60 W part), so GPU samples above 1.5x the card's
maximum power limit are dropped.
"""

import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from runner.providers.gpu_memory import gpu_selector

SAMPLE_INTERVAL_S = 0.25
# Samples older than this are dropped; no single call runs anywhere near it.
RETENTION_S = 3600
# An amdgpu device with at most this much VRAM is an APU's carve-out.
APU_MAX_VRAM_BYTES = 2 * 1024**3
# Used when the GPU doesn't report a power limit.
FALLBACK_GPU_CEILING_W = 1000.0

POWERCAP_DIR = Path("/sys/class/powercap")
HWMON_DIR = Path("/sys/class/hwmon")


@dataclass(frozen=True)
class PowerReading:
    gpu_power_w: float | None = None
    gpu_power_peak_w: float | None = None
    cpu_power_w: float | None = None
    cpu_power_peak_w: float | None = None
    energy_wh: float | None = None


# --------------------------------------------------------------------------- #
# sources
# --------------------------------------------------------------------------- #


def _read_text(path: Path) -> str:
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def _read_number(path: Path) -> float | None:
    try:
        return float(_read_text(path))
    except ValueError:
        return None


def _parse_watts(text: str) -> float | None:
    try:
        return float(text.strip())
    except ValueError:
        return None  # "[N/A]", "[Unknown Error]", ...


def gpu_power_ceiling(selector: str) -> float:
    """1.5x the largest power limit the GPU reports."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=power.max_limit,power.default_limit",
             "--format=csv,noheader,nounits", "-i", selector],
            capture_output=True, text=True, check=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return FALLBACK_GPU_CEILING_W
    limits = [w for part in result.stdout.split(",") if (w := _parse_watts(part))]
    return 1.5 * max(limits) if limits else FALLBACK_GPU_CEILING_W


class RaplPackage:
    """CPU package power from the RAPL energy counter (microjoules)."""

    def __init__(self, zone: Path):
        self.zone = zone
        self.wrap = _read_number(zone / "max_energy_range_uj") or 0.0
        self.previous: tuple[float, float] | None = None

    @classmethod
    def find(cls) -> "RaplPackage | None":
        for zone in sorted(POWERCAP_DIR.glob("*:*")):
            if _read_text(zone / "name").startswith("package") and _read_number(zone / "energy_uj") is not None:
                return cls(zone)
        return None

    def watts(self) -> float | None:
        energy, now = _read_number(self.zone / "energy_uj"), time.monotonic()
        if energy is None:
            return None
        previous, self.previous = self.previous, (energy, now)
        if previous is None or now <= previous[1]:
            return None
        delta = energy - previous[0]
        if delta < 0:  # the counter wrapped
            delta += self.wrap
        return delta / 1e6 / (now - previous[1])


class ApuPpt:
    """AMD APU socket power from the amdgpu hwmon PPT sensor (microwatts)."""

    def __init__(self, sensor: Path):
        self.sensor = sensor

    @classmethod
    def find(cls) -> "ApuPpt | None":
        for hwmon in sorted(HWMON_DIR.glob("hwmon*")):
            if _read_text(hwmon / "name") == "amdgpu":
                if _read_text(hwmon / "power1_label") != "PPT":
                    continue
                vram = _read_number(hwmon / "device" / "mem_info_vram_total")
                if vram is None or vram > APU_MAX_VRAM_BYTES:
                    continue  # a discrete card: its PPT is GPU board power
                for sensor in ("power1_average", "power1_input"):
                    if _read_number(hwmon / sensor) is not None:
                        return cls(hwmon / sensor)
        return None

    def watts(self) -> float | None:
        microwatts = _read_number(self.sensor)
        return microwatts / 1e6 if microwatts is not None else None


def find_cpu_source() -> "RaplPackage | ApuPpt | None":
    return RaplPackage.find() or ApuPpt.find()


# --------------------------------------------------------------------------- #
# sampler
# --------------------------------------------------------------------------- #


def _window_stats(samples: list[tuple[float, float]], start: float, end: float,
                  grace: float) -> tuple[float | None, float | None]:
    """(mean, peak) of the samples inside [start, end]. A call shorter than
    the sampling interval may contain none; the first sample within `grace`
    after it ends stands in for it then."""
    inside = [w for t, w in samples if start <= t <= end]
    if not inside:
        inside = [w for t, w in samples if end < t <= end + grace][:1]
    if not inside:
        return None, None
    return sum(inside) / len(inside), max(inside)


class PowerSampler:
    """Background GPU and CPU power sampling for the life of a provider."""

    def __init__(self, interval: float = SAMPLE_INTERVAL_S, *, gpu: bool = True, cpu: bool = True):
        self.interval = interval
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._gpu: deque[tuple[float, float]] = deque()
        self._cpu: deque[tuple[float, float]] = deque()
        self._process: subprocess.Popen | None = None
        self._threads: list[threading.Thread] = []
        self._warmed_up = False

        if gpu:
            self._start_gpu()
        self._cpu_source = find_cpu_source() if cpu else None
        if self._cpu_source is not None:
            self._spawn(self._poll_cpu)

    @property
    def active(self) -> bool:
        return bool(self._threads)

    def _spawn(self, target) -> None:
        thread = threading.Thread(target=target, name=f"power-{target.__name__}", daemon=True)
        thread.start()
        self._threads.append(thread)

    def _start_gpu(self) -> None:
        selector = gpu_selector()
        if selector is None:
            return
        self._gpu_ceiling = gpu_power_ceiling(selector)
        try:
            self._process = subprocess.Popen(
                ["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader,nounits",
                 "-lms", str(int(self.interval * 1000)), "-i", selector],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1,
            )
        except (FileNotFoundError, OSError):
            self._process = None
            return
        self._spawn(self._read_gpu)

    def _record(self, samples: deque, watts: float) -> None:
        now = time.monotonic()
        with self._lock:
            samples.append((now, watts))
            while samples and samples[0][0] < now - RETENTION_S:
                samples.popleft()

    def _read_gpu(self) -> None:
        for line in self._process.stdout:
            if self._stop.is_set():
                break
            watts = _parse_watts(line)
            if watts is not None and 0 < watts <= self._gpu_ceiling:
                self._record(self._gpu, watts)

    def _poll_cpu(self) -> None:
        while not self._stop.wait(self.interval):
            watts = self._cpu_source.watts()
            if watts is not None and watts >= 0:
                self._record(self._cpu, watts)

    def reading(self, start: float, end: float) -> PowerReading:
        """Power over one call, `start`/`end` from time.monotonic()."""
        with self._lock:
            gpu, cpu = list(self._gpu), list(self._cpu)
        grace = 2 * self.interval
        gpu_mean, gpu_peak = _window_stats(gpu, start, end, grace)
        cpu_mean, cpu_peak = _window_stats(cpu, start, end, grace)
        measured = [w for w in (gpu_mean, cpu_mean) if w is not None]
        return PowerReading(
            gpu_power_w=gpu_mean,
            gpu_power_peak_w=gpu_peak,
            cpu_power_w=cpu_mean,
            cpu_power_peak_w=cpu_peak,
            energy_wh=sum(measured) * (end - start) / 3600 if measured else None,
        )

    def wait_for_samples(self, timeout: float) -> None:
        """Before the first call only: block until every source has produced
        a sample, since a waking laptop GPU can take seconds to. Later calls
        (or a source that never yields a valid reading) don't wait."""
        if self._warmed_up:
            return
        self._warmed_up = True
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                gpu_ready = self._process is None or bool(self._gpu)
                cpu_ready = self._cpu_source is None or bool(self._cpu)
            if gpu_ready and cpu_ready:
                return
            time.sleep(self.interval / 2)

    def close(self) -> None:
        self._stop.set()
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
        for thread in self._threads:
            thread.join(timeout=5)
