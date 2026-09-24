"""
Token/latency statistics shared by every suite's per-case results and run
summaries. Case results only need the fields read here (prompt_tokens,
completion_tokens, execution_time, gpu_memory_mb), so the markdown and
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
        finish_reason=response.finish_reason,
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
