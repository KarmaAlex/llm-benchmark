"""Console output shared by the main_* and run_all_* entry points."""

from runner.core.stats import tokens_per_second
from runner.models.model_response import ModelResponse


def print_response_stats(response: ModelResponse) -> None:
    print(
        f"Tokens: {response.prompt_tokens} prompt + {response.completion_tokens} "
        f"completion = {response.prompt_tokens + response.completion_tokens} total "
        f"(finish_reason={response.finish_reason})"
    )
    print(
        f"Latency: {response.latency:.2f}s "
        f"({tokens_per_second(response.completion_tokens, response.latency):.1f} tok/s)"
    )


def print_token_summary(summary: dict) -> None:
    """Print the fields produced by runner.core.stats.token_summary()."""
    print(f"Tokens:   {summary['total_prompt_tokens']} prompt + "
          f"{summary['total_completion_tokens']} completion = "
          f"{summary['total_tokens']} total")
    print(f"Throughput: {summary['avg_tokens_per_second']:.1f} completion tok/s (avg)")
    print(f"Avg model latency: {summary['avg_execution_time']:.2f}s per case")


def format_gpu_memory(gpu_memory_mb: float | None) -> str:
    return f"{gpu_memory_mb:.0f}" if gpu_memory_mb is not None else "n/a"


def print_run_footer(summary: dict) -> None:
    if summary.get("peak_gpu_memory_mb") is not None:
        print(f"Peak GPU memory: {summary['peak_gpu_memory_mb']:.0f} MiB")
    print(f"Wall-clock run time: {summary['wall_time']:.2f}s")
