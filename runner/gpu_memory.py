"""Best-effort GPU memory sampling via `nvidia-smi`.

Kept dependency-free (no torch/pynvml) since the benchmark runner's only
GPU-aware provider is llama-cpp-python, which doesn't expose memory stats
itself. Returns None wherever nvidia-smi isn't available (CPU-only configs,
the OpenAI provider, non-NVIDIA machines) so callers can treat it as
optional.
"""

import subprocess


def get_gpu_memory_used_mb() -> float | None:
    """Memory currently used on GPU 0, in MiB, or None if unavailable."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        first_line = result.stdout.strip().splitlines()[0]
        return float(first_line)
    except (
        FileNotFoundError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        ValueError,
        IndexError,
    ):
        return None
