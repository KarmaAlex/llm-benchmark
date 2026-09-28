"""What a run ran on, recorded in its settings so results from different
machines (a laptop, a cluster node) can be told apart and costed correctly
- see analysis/costs.py, which prices runs on known GPUs by the GPU-hour."""

import os
import socket
from pathlib import Path

from runner.providers.gpu_memory import gpu_names


def cpu_model() -> str | None:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return None


def hardware_info() -> dict:
    return {
        "host": socket.gethostname(),
        "cpu": cpu_model(),
        # The GPUs this process could use (CUDA_VISIBLE_DEVICES), one entry
        # each: a SLURM job lists only what it was allocated.
        "gpus": gpu_names(),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
    }
