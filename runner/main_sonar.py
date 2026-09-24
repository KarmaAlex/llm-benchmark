import argparse
import shutil
from pathlib import Path

from runner.cli.arguments import (
    add_config_argument,
    add_device_argument,
    add_edit_mode_argument,
    add_sonar_argument,
)
from runner.cli.loading import load_model_config
from runner.cli.output import print_response_stats
from runner.providers.factory import ProviderFactory
from runner.sonar_tests.analysis import analyze_case
from runner.sonar_tests.pipeline import (
    apply_to_workspace,
    build_chat_prompt,
    load_case,
    load_prompt,
    validate_case,
)
from runner.sonar_tests.sonar_server import SonarServer


parser = argparse.ArgumentParser(
    description="Run a single sonar issue-resolution benchmark case against a model."
)
parser.add_argument(
    "case",
    nargs="?",
    default="S1643",
    help="Case id under benchmark/sonar/ to run (default: S1643).",
)
add_config_argument(parser, default="qwen2.5-coder-7b-q4")
add_edit_mode_argument(parser)
add_device_argument(parser)
add_sonar_argument(
    parser,
    help=(
        "After compiling and testing, analyze the patched project with a real "
        "SonarQube and report whether the issue is gone and what it cost "
        "(default: on)."
    ),
)
args = parser.parse_args()

case = load_case(args.case)

config = load_model_config(args.config, args.device, args.edit_mode)

chat_prompt = build_chat_prompt(load_prompt(args.edit_mode), case, args.edit_mode)

print(f"Prompt:\n{chat_prompt}\n\n")

provider = ProviderFactory.create(config)

response = provider.generate(
    chat_prompt
)

print_response_stats(response)

run_directory = Path(
    "results/test"
)

if run_directory.exists():
    shutil.rmtree(run_directory)

run_directory.mkdir(
    parents=True,
    exist_ok=True,
)

print(f"Response:\n{response.content}")

outcome = apply_to_workspace(case, args.edit_mode, response, run_directory)

print(f"Applied: {outcome.applied}")

if outcome.edit_results is not None:
    for result in outcome.edit_results:
        print(
            f"  {result.path}: applied={result.applied} "
            f"kind={result.match_kind} similarity={result.similarity} "
            f"error={result.error}"
        )

if not outcome.applied:
    print(outcome.error)
    raise SystemExit(1)

print(f"Diff:\n{outcome.diff}")

validation = validate_case(run_directory)

print(
    f"Compilation successful: {validation['compiled']}"
)

print(
    f"Compilation time: "
    f"{validation['compile_time']:.2f}s"
)

if validation["compiled"]:
    tests_run = validation["tests_run_count"]
    failures = validation["tests_failed"]
    errors = validation["tests_errored"]

    print(
        f"Tests ran: {validation['tests_ran']}, passed: {validation['tests_passed']} "
        f"({tests_run - failures - errors}/{tests_run} passing, {failures} failures, "
        f"{errors} errors, {validation['tests_skipped']} skipped)"
    )
    print(
        f"Test execution time: {validation['test_time']:.2f}s"
    )

if validation["compiled"] and args.sonar:
    analysis = analyze_case(
        args.case,
        run_directory,
        SonarServer.ensure_running(),
        "single",
    )

    if not analysis["sonar_analyzed"]:
        print(f"Sonar analysis skipped: {analysis['sonar_error']}")
    else:
        print(f"Issue resolved: {analysis['target_resolved']}")
        for issue in analysis["remaining_target_issues"]:
            print(f"  still there: {issue['rule']} line {issue['line']} - {issue['message']}")
        print(f"New issues introduced: {analysis['new_issues_count']}")
        for issue in analysis["new_issues"]:
            print(f"  {issue['rule']} {issue['file']}:{issue['line']} - {issue['message']}")
        print(f"Sonar analysis time: {analysis['sonar_time']:.2f}s")
