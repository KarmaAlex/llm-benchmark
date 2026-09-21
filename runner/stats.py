def tokens_per_second(completion_tokens: int, execution_time: float) -> float:
    if execution_time <= 0:
        return 0.0
    return completion_tokens / execution_time
