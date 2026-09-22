# LLM Benchmark

A framework for benchmarking commercial and open-source LLMs on software engineering tasks, built for comparing model effectiveness on automated software development work.

Two benchmark suites are implemented:

- **`markdown`** — structured data extraction from Markdown documents (headings, tables, checklists, and multi-document joins/correlations). Graded by exact JSON match against a reference answer.
- **`sonar`** — fixing a flagged SonarQube static-analysis issue in a real Maven/Java project. Graded by whether the model's patch applies, the project still compiles, and its existing unit tests still pass.

Both suites share the same execution pipeline: **Benchmark Loader → Prompt Loader → Prompt Builder → Provider (OpenAI / llama.cpp) → Model Response → grading**. Adding a new benchmark case is data-only (drop files into `benchmark/<suite>/<case_id>/`); no loader code changes are needed since every non-JSON file in a case directory is automatically exposed to the prompt template as a `{{placeholder}}`.

## Project structure

```
benchmark/    Benchmark case data (read-only): benchmark/markdown/mdNNN/, benchmark/sonar/<RULE_ID>/
configs/      Per-model YAML configs (base + -markdown/-sonar task variants)
prompts/      Versioned prompt templates (system_v1.md, markdown_v1.md, sonar_v1.md, ...)
runner/       The execution engine (installable package) — loaders, providers, grading, CLI entry points
scripts/      Standalone utility scripts (currently just a model smoke test)
tests/        pytest suite for the runner package
results/      Timestamped output of each run_all_* invocation, one report.json per run and resulting project for sonar runs
```

## Environment setup

Requires Python ≥ 3.11.

```bash
pip install -e .          # core deps: openai, llama-cpp-python, PyYAML, python-dotenv
pip install -e ".[dev]"   # + pytest, for running tests/
```

**Important** installing llama-cpp-python requires nvcc to use cuda devices, this also requires setting the CMAKE_ARGS="-DGGML_CUDA=on" environment variable before installing it

**API-based models** (`provider: openai` configs, e.g. `gpt5-markdown.yaml`): copy `.env.example` to `.env` and set `OPENAI_API_KEY`. it's loaded automatically on `import runner`, so no per-script setup is needed. An explicit `OPENAI_API_KEY=... python -m ...` in the shell still overrides the file.

**Local models** (`provider: llama.cpp` configs): place GGUF weight files under `models/` (gitignored) and point each config's `model:` field at the relative path. Inference goes through the `llama-cpp-python` bindings directly — no separate llama.cpp server process is required, though `llama-cpp-python` needs a working C/C++ toolchain (and CUDA, for GPU offload) to install.

**Sonar benchmark only**: requires `mvn`/`./mvnw` and a JDK on `PATH` (used to compile/test patched projects), and the system `patch` utility (used for `--edit-mode diff`).

## Configuring models

Each `configs/<name>.yaml` maps 1:1 to a `ModelConfig` and is loaded with `ConfigLoader.load("<name>")` (no `.yaml` suffix, no path). Task-specific variants (e.g. `qwen2.5-coder-3b-q4-markdown.yaml` vs `-sonar.yaml`) let token budgets and sampling differ per task without touching the underlying model definition.

Local llama.cpp example:

```yaml
name: Qwen2.5-Coder-3B-Q4
provider: llama.cpp
model: models/qwen2.5-coder-3b-instruct-q4_k_m.gguf
temperature: 0
max_tokens: 4096
context: 32768
parameters:
  n_gpu_layers: -1
  n_threads: 8
sampling:
  repeat_penalty: 1.0
```

OpenAI example:

```yaml
name: GPT-5 (markdown)
provider: openai
model: gpt-5
temperature: 1
max_tokens: 8192
context: 400000
parameters:
  max_tokens_param: max_completion_tokens
  supports_temperature: false
supports_tools: true
```

Every CLI entry point below also takes `--device {cuda,cpu}` (default `cuda`). It's a no-op for `openai` configs; for `llama.cpp` configs, `cpu` forces `n_gpu_layers: 0` for that run only, without editing the YAML file.

## Running the runner scripts

All commands run as `python -m runner.<script>` from the repo root.

| Script | What it does |
|---|---|
| `main_markdown <case> --config <name>` | Runs one markdown case, prints the rendered prompt, the model's response, and whether it matched. Exits non-zero on a mismatch. |
| `run_all_markdown --config <name>` | Runs every case under `benchmark/markdown/`, writes `results/<timestamp>/report.json` plus a per-case summary table to stdout. |
| `main_sonar <case> --config <name> --edit-mode {diff,structured,toolcall}` | Runs one sonar case end-to-end: generate → apply patch → compile → test. |
| `run_all_sonar --config <name> --edit-mode ...` | Runs every case under `benchmark/sonar/` through the full generate/apply/compile/test pipeline and writes `report.json`. |
| `run_all_sonar_generate --config <name> --edit-mode ...` | Generate + apply only (no compile/test) for every sonar case — for running the model-inference phase on a machine without a JDK/Maven. Writes `report.json` with `"validated": false`. |
| `validate_sonar_run <run_id>` | Re-runs compile + test for an already-generated run directory (from `run_all_sonar_generate`), without calling the model again, and updates that run's `report.json` in place (`"validated": true`). |

New benchmark cases (new `mdNNN/` or `<RULE_ID>/` directories under `benchmark/`) are picked up automatically by the `run_all_*` scripts — there's no manifest or registration step.

## How outputs are validated

**Markdown**: the model's response is extracted as JSON (`JsonExtractor`, tolerant of ` ```json ` code fences) and compared against each case's `expected.json` with strict structural equality (`JsonComparator`) — every key, value, type, and array order must match exactly. There is no partial credit or fuzzy matching.

**Sonar**: there's no reference patch to diff against. Instead, grading is a pass/fail pipeline run against an isolated copy of the case's Maven project (the original under `benchmark/sonar/<ID>/project/` is never mutated):

1. **Apply** — the model's edit is turned into file changes: a unified diff via the system `patch` command (`--edit-mode diff`), or exact/fuzzy text-block replacement (`--edit-mode structured`/`toolcall`).
2. **Compile** — `mvn compile` (or `./mvnw compile`) against the patched project.
3. **Test** — if compilation succeeds, `mvn test` is run and its Surefire summary line is parsed for pass/fail counts.

A case "passes" if the patch applies, the project compiles, and every existing unit test still passes — this checks for regression safety, not whether the model's fix matches any particular reference solution.

## Metrics extracted per run

Every `run_all_*` invocation writes `results/<timestamp>/report.json` with `{"config": ..., "summary": {...}, "cases": [...]}` — per-case detail plus an aggregate summary.

**Markdown** — per case: `matched` (bool), `execution_time`, `prompt_tokens`, `completion_tokens`, `tokens_per_second`, `finish_reason`, `parse_error`/`error`, the raw `response_text` and `parsed_output`. Aggregate summary adds: `matched_rate`, total/average token counts and throughput, `total_execution_time`/`wall_time`, and a `by_difficulty` breakdown (matched/total per difficulty level).

**Sonar** — per case: `applied`, `compiled`, `tests_ran`, `tests_passed`, `tests_run_count`/`tests_failed`/`tests_errored`, `execution_time`, `compile_time`, `test_time`, token counts, `tokens_per_second`, plus the generated `response_text`/`diff`. Aggregate summary adds: `applied_rate`, `compiled_rate`, and `tests_passed_rate` (computed over compiled cases only, since a case that fails to compile can't run tests), plus the same token/timing totals as markdown. `run_all_sonar_generate` writes a reduced summary (token/throughput/applied stats only, no compile/test fields) until `validate_sonar_run` fills the rest in.
