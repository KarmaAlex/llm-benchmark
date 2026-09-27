"""Console rendering of a reproducibility aggregate (see aggregate.py)."""

RULE = "=" * 78


def _percent(rate: float) -> str:
    return f"{rate:.0%}"


def _stages(stages: dict) -> str:
    return ", ".join(f"{stage}×{count}" for stage, count in sorted(stages.items(), key=lambda s: -s[1]))


def _reps(reps: list[int]) -> str:
    return ",".join(str(r) for r in reps)


def print_suite(aggregate: dict) -> None:
    summary = aggregate["summary"]
    print(f"\n{RULE}")
    print(
        f"Reproducibility: {aggregate['suite']} ({', '.join(aggregate['configs'])}) - "
        f"{aggregate['repetitions']} repetition(s), pass = {aggregate['criterion']}"
    )
    print(RULE)

    print(
        f"\n{'Case':<10} {'Class':<15} {'Pass':<8} {'Outputs':<9} {'Agree':<7} "
        f"{'Tokens':<13} Stages"
    )
    for case in aggregate["cases"]:
        tokens = case["completion_tokens"]
        token_range = (
            str(tokens["min"]) if tokens["min"] == tokens["max"]
            else f"{tokens['min']}-{tokens['max']}"
        )
        outputs = f"{case['distinct_raw_outputs']}/{case['distinct_effective_outputs']}"
        passed = f"{case['pass_count']}/{case['n']}"
        print(
            f"{case['case_id']:<10} {str(case['classification']):<15} "
            f"{passed:<8} {outputs:<9} "
            f"{_percent(case['agreement_rate']):<7} {token_range:<13} {_stages(case['stages'])}"
        )
    print("(Outputs = distinct raw/effective outputs; Agree = share of reps giving the most common one)")

    counts = summary["classifications"]
    print("\nClassification: " + ", ".join(f"{name} {count}" for name, count in counts.items()))

    scored = summary["pass_any"] + summary["pass_none"]
    print(
        f"Passed every rep: {summary['pass_all']}/{scored}, at least once: "
        f"{summary['pass_any']}/{scored}, never: {summary['pass_none']}/{scored}"
    )
    print(f"Mean per-case pass rate: {_percent(summary['mean_case_pass_rate'])}")

    rate = summary["repetition_pass_rate"]
    per_rep = " ".join(_percent(r["pass_rate"]) for r in summary["per_repetition"])
    print(f"Per-repetition pass rate: {per_rep}")
    print(
        f"  mean {_percent(rate['mean'])}, stdev {rate['stdev'] * 100:.1f} pp, "
        f"min {_percent(rate['min'])}, max {_percent(rate['max'])}"
    )

    _print_details(aggregate["cases"], summary["most_unstable"])


def _print_details(cases: list[dict], most_unstable: list[str]) -> None:
    by_id = {c["case_id"]: c for c in cases}
    detailed = [by_id[case_id] for case_id in most_unstable
                if by_id[case_id]["classification"] in ("flaky", "outcome-stable", "harness-error")]
    if not detailed:
        return

    print("\nCases whose outcome or output changed between repetitions (most unstable first):")
    for case in detailed:
        print(f"\n  {case['case_id']} - {case['classification']}, passed {case['pass_count']}/{case['n']}")

        for error in case["harness_errors"]:
            first_line = (error["error"] or "").splitlines()[0] if error["error"] else ""
            print(f"    rep {error['rep']}: harness error - {first_line}")

        for group in case["output_groups"]:
            print(
                f"    {group['label']}: reps {_reps(group['reps'])} - "
                f"passed {group['pass_count']}/{len(group['reps'])} ({_stages(group['stages'])})"
            )

        if case["sample_diff"]:
            print("    sample difference between the two most common outputs:")
            for line in case["sample_diff"].splitlines():
                print(f"      {line}")


def print_reproducibility_report(aggregate: dict) -> None:
    if not aggregate["suites"] and not aggregate.get("pending_validation"):
        print("No completed repetitions to aggregate.")
        return
    for suite_aggregate in aggregate["suites"].values():
        print_suite(suite_aggregate)
    for suite in aggregate.get("pending_validation", []):
        print(
            f"\n{suite}: generated with --no-sonar, not yet validated - run "
            "`python -m runner.validate_sonar_run <rep-directory>` on each "
            "repetition, then re-run with --aggregate-only to grade it."
        )
