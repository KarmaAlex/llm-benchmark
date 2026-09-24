from typing import Callable, TypeVar

T = TypeVar("T")


def run_cases(
    case_ids: list[str],
    run_case: Callable[[str], T],
    failed_result: Callable[[str, str], T],
    verb: str = "Running",
) -> list[T]:
    """
    Run every case in order, turning an unexpected exception into a failed
    result (built by `failed_result(case_id, error)`) so one broken case
    doesn't abort the whole run.
    """
    results: list[T] = []
    for case_id in case_ids:
        print(f"{verb} {case_id}...")
        try:
            result = run_case(case_id)
        except Exception as e:
            result = failed_result(case_id, f"{type(e).__name__}: {e}")
        results.append(result)
    return results
