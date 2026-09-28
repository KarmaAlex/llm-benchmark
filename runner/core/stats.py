"""
Token/latency statistics shared by every suite's per-case results and run
summaries. Case results only need the fields read here (prompt_tokens,
completion_tokens, execution_time, gpu_memory_mb and the power fields), so the markdown and
sonar result types can both be summarized the same way.
"""

from runner.models.model_response import ModelResponse


def tokens_per_second(completion_tokens: int, execution_time: float) -> float:
    if execution_time <= 0:
        return 0.0
    return completion_tokens / execution_time


def response_token_stats(response: ModelResponse) -> dict:
    """Per-case result fields derived from a single model response."""
    return dict(
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
        total_tokens=response.prompt_tokens + response.completion_tokens,
        tokens_per_second=tokens_per_second(response.completion_tokens, response.latency),
        gpu_memory_mb=response.gpu_memory_mb,
        gpu_power_w=response.gpu_power_w,
        gpu_power_peak_w=response.gpu_power_peak_w,
        cpu_power_w=response.cpu_power_w,
        cpu_power_peak_w=response.cpu_power_peak_w,
        energy_wh=response.energy_wh,
        gpu_other_processes=response.gpu_other_processes,
        finish_reason=response.finish_reason,
        system_fingerprint=response.system_fingerprint,
    )


def token_summary(results: list) -> dict:
    """Run-summary fields aggregating model usage across every case."""
    total = len(results)
    total_prompt_tokens = sum(r.prompt_tokens for r in results)
    total_completion_tokens = sum(r.completion_tokens for r in results)
    total_execution_time = sum(r.execution_time for r in results)

    return {
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_tokens": total_prompt_tokens + total_completion_tokens,
        "avg_tokens_per_second": tokens_per_second(total_completion_tokens, total_execution_time),
        "avg_execution_time": total_execution_time / total if total else 0.0,
        "total_execution_time": total_execution_time,
    }


def peak_gpu_memory_mb(results: list) -> float | None:
    samples = [r.gpu_memory_mb for r in results if r.gpu_memory_mb is not None]
    return max(samples) if samples else None


def _time_weighted_mean(results: list, field: str) -> float | None:
    """Mean power across cases, each weighted by how long its call ran."""
    pairs = [(getattr(r, field), r.execution_time) for r in results
             if getattr(r, field, None) is not None and r.execution_time > 0]
    total_time = sum(t for _w, t in pairs)
    return sum(w * t for w, t in pairs) / total_time if total_time else None


def _peak(results: list, field: str) -> float | None:
    samples = [getattr(r, field) for r in results if getattr(r, field, None) is not None]
    return max(samples) if samples else None


def power_summary(results: list) -> dict:
    """Run-summary power fields: mean (weighted by call time) and peak GPU
    and CPU power, and the total energy drawn by the model calls. All None
    for a run nothing was measured on (API models, unsupported hardware)."""
    energies = [r.energy_wh for r in results if getattr(r, "energy_wh", None) is not None]
    others = [r.gpu_other_processes for r in results if getattr(r, "gpu_other_processes", None) is not None]
    return {
        "avg_gpu_power_w": _time_weighted_mean(results, "gpu_power_w"),
        "peak_gpu_power_w": _peak(results, "gpu_power_peak_w"),
        "avg_cpu_power_w": _time_weighted_mean(results, "cpu_power_w"),
        "peak_cpu_power_w": _peak(results, "cpu_power_peak_w"),
        "total_energy_wh": sum(energies) if energies else None,
        # Cases whose GPU had another compute process on it: their power
        # and latency include someone else's work.
        "gpu_shared_cases": sum(1 for n in others if n > 0) if others else None,
    }
