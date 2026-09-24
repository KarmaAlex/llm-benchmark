import argparse

from runner.cli.arguments import add_config_argument, add_device_argument
from runner.cli.loading import load_model_config
from runner.cli.output import print_response_stats
from runner.markdown_tests.pipeline import build_chat_prompt, evaluate_response, load_case, load_prompt
from runner.providers.factory import ProviderFactory


parser = argparse.ArgumentParser(
    description="Run a single markdown-extraction benchmark case against a model."
)
parser.add_argument(
    "case",
    nargs="?",
    default="md001",
    help="Case id under benchmark/markdown/ to run (default: md001).",
)
add_config_argument(parser, default="qwen2.5-coder-3b-q4")
add_device_argument(parser)
args = parser.parse_args()

case = load_case(args.case)

config = load_model_config(args.config, args.device)

chat_prompt = build_chat_prompt(load_prompt(), case)

print(f"Prompt:\n{chat_prompt}\n\n")

provider = ProviderFactory.create(config)

response = provider.generate(
    chat_prompt
)

print(f"Response:\n{response.content}")

print_response_stats(response)

result = evaluate_response(case, response)

print(result.error or "Output matches the expected result.")

print(f"Matched: {result.matched}")

print(
    f"Execution time: "
    f"{result.execution_time:.2f}s"
)

if not result.matched:
    raise SystemExit(1)
