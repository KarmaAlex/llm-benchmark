from pathlib import Path

from runner.sonar_tests.compiler import Compiler
from runner.sonar_tests.patch_applier import PatchApplier
from runner.sonar_tests.workspace import Workspace
from runner.filesystem.benchmark_loader import BenchmarkLoader
from runner.filesystem.config_loader import ConfigLoader
from runner.filesystem.prompt_loader import PromptLoader
from runner.prompt_builder import PromptBuilder
from runner.providers.factory import ProviderFactory


case = BenchmarkLoader.load(
    Path("sonar/S1643")
)

prompt = PromptLoader.load("sonar_v2")

config = ConfigLoader.load("qwen2.5-coder-7b-q4")

chat_prompt = PromptBuilder.build(
    prompt,
    case,
)

print(f"Prompt:\n{chat_prompt}\n\n")

provider = ProviderFactory.create(config)

response = provider.generate(
    chat_prompt
)

run_directory = Path(
    "results/test"
)

run_directory.mkdir(
    parents=True,
    exist_ok=True,
)

project_directory = Workspace.create(
    case.project_path,
    run_directory / "project",
)

print(f"Response:\n{response.content}")

patch_result = PatchApplier.apply(
    project_directory,
    response.content,
)

print(f"Patch applied: {patch_result.applied}")

if not patch_result.applied:
    print(patch_result.error)
    raise SystemExit(1)

compilation = Compiler.compile(
    project_directory
)

print(
    f"Compilation successful: {compilation.compiled}"
)

print(
    f"Compilation time: "
    f"{compilation.execution_time:.2f}s"
)