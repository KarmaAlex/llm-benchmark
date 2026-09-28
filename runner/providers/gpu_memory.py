"""Best-effort GPU queries via `nvidia-smi`: memory in use, which GPUs this
process was given, and whether anything else is running on them.

Kept dependency-free (no torch/pynvml) since the benchmark runner's only
GPU-aware provider is llama-cpp-python, which doesn't expose memory stats
itself. Returns None wherever nvidia-smi isn't available (CPU-only configs,
the OpenAI provider, non-NVIDIA machines) so callers can treat it as
optional.

Which GPU: on a shared machine (a SLURM node) "GPU 0" may be another job's
GPU, so queries target the GPUs in CUDA_VISIBLE_DEVICES - the ones CUDA,
and so llama.cpp, will use - and fall back to GPU 0 when it isn't set.
nvidia-smi's -i accepts both of the forms SLURM and users put there: an
index or a GPU UUID. A MIG slice (MIG-...) has no board-level readings of
its own, so it reads as unavailable.
"""

import os
import subprocess

# CUDA_VISIBLE_DEVICES values meaning "no GPU" (SLURM uses NoDevFiles for
# jobs without a GPU allocation).
_NO_DEVICES = {"", "NoDevFiles", "-1", "none"}

# Another process only counts as sharing the GPU above this much memory: a
# desktop compositor holds a few MiB on a laptop GPU, a co-tenant job
# running a model holds gigabytes.
SHARING_MIN_MEMORY_MIB = 256


def visible_gpus() -> list[str] | None:
    """The GPUs this process may use, as nvidia-smi -i selectors. None if
    CUDA_VISIBLE_DEVICES isn't set (every GPU is visible then)."""
    value = os.environ.get("CUDA_VISIBLE_DEVICES")
    if value is None:
        return None
    if value.strip() in _NO_DEVICES:
        return []
    return [entry.strip() for entry in value.split(",") if entry.strip()]


def gpu_selector() -> str | None:
    """nvidia-smi -i value for the GPU llama.cpp computes on (CUDA device 0),
    or None when there's no usable one."""
    gpus = visible_gpus()
    if gpus is None:
        return "0"
    if not gpus or gpus[0].startswith("MIG-"):
        return None
    return gpus[0]


def nvidia_smi(*args: str, timeout: float = 5) -> list[str] | None:
    """nvidia-smi's output lines, or None if it isn't available or fails."""
    try:
        result = subprocess.run(
            ["nvidia-smi", *args], capture_output=True, text=True, check=True, timeout=timeout,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]


def _compute_apps() -> list[tuple[str, float | None]] | None:
    """(pid, MiB used or None if unreported) for each compute process on
    this process's GPU; None if that can't be queried."""
    selector = gpu_selector()
    if selector is None:
        return None
    lines = nvidia_smi("--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits",
                       "-i", selector)
    if lines is None:
        return None
    apps = []
    for line in lines:
        pid, _, memory = line.partition(",")
        try:
            apps.append((pid.strip(), float(memory)))
        except ValueError:
            apps.append((pid.strip(), None))  # "[N/A]"
    return apps


def _sizeable(mib: float | None) -> bool:
    """Big enough to be another job rather than, say, a desktop compositor.
    Unreported memory can't be ruled out, so it counts."""
    return mib is None or mib >= SHARING_MIN_MEMORY_MIB


def get_gpu_memory_used_mb() -> float | None:
    """GPU memory this process is using, in MiB, or None if unavailable.

    Read from this process's own entry where nvidia-smi attributes memory
    per process, so on a GPU shared with another job only our share
    counts; otherwise (a container hiding process IDs) the whole GPU's
    memory.used, which includes anyone else's."""
    own_pid = str(os.getpid())
    own = [mib for pid, mib in _compute_apps() or [] if pid == own_pid and mib is not None]
    if own:
        return own[0]
    selector = gpu_selector()
    if selector is None:
        return None
    lines = nvidia_smi("--query-gpu=memory.used", "--format=csv,noheader,nounits", "-i", selector)
    try:
        return float(lines[0]) if lines else None
    except ValueError:
        return None


def gpu_occupants() -> list[dict] | None:
    """Other sizeable processes on this process's GPU - for a check before
    a model loads, when anything listed is someone else's. None if the GPU
    can't be queried."""
    apps = _compute_apps()
    if apps is None:
        return None
    own_pid = str(os.getpid())
    return [{"pid": pid, "used_memory_mb": mib} for pid, mib in apps if pid != own_pid and _sizeable(mib)]


def other_gpu_processes() -> int | None:
    """Other sizeable compute processes (see SHARING_MIN_MEMORY_MIB) on this
    process's GPU while it's using it - any at all means the GPU is shared,
    and its power, memory and even this process's latency include someone
    else's work.

    None when it can't be told: no GPU, or this process isn't in the list
    (a container with its own PID namespace, or one that hides processes) -
    every entry would look like "another process" then."""
    apps = _compute_apps()
    own_pid = str(os.getpid())
    if not apps or not any(pid == own_pid for pid, _mib in apps):
        return None
    return sum(1 for pid, mib in apps if pid != own_pid and _sizeable(mib))


def gpu_names() -> list[str]:
    """Model names of the GPUs this process may use ([] when none)."""
    gpus = visible_gpus()
    if gpus is None:
        return nvidia_smi("--query-gpu=name", "--format=csv,noheader") or []
    names = []
    for gpu in gpus:
        if gpu.startswith("MIG-"):
            names.append("MIG slice")
            continue
        lines = nvidia_smi("--query-gpu=name", "--format=csv,noheader", "-i", gpu)
        if lines:
            names.append(lines[0])
    return names
