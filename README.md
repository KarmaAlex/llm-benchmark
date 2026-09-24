# LLM Benchmark

A framework for benchmarking commercial and open-source LLMs on software engineering tasks, built for comparing model effectiveness on automated software development work.

Two benchmark suites are implemented:

- **`markdown`** — structured data extraction from Markdown documents (headings, tables, checklists, and multi-document joins/correlations). Graded by exact JSON match against a reference answer.
- **`sonar`** — fixing a flagged SonarQube static-analysis issue in a real Maven/Java project. Graded by whether the model's patch applies, the project still compiles, its existing unit tests still pass, and — against a real SonarQube server — whether the reported issue is actually gone and no new issues were introduced.

Both suites share the same execution pipeline: **Benchmark Loader → Prompt Loader → Prompt Builder → Provider (OpenAI / llama.cpp) → Model Response → grading**. Adding a new benchmark case is data-only (drop files into `benchmark/<suite>/<case_id>/`); no loader code changes are needed since every non-JSON file in a case directory is automatically exposed to the prompt template as a `{{placeholder}}`.

## Project structure

```
benchmark/    Benchmark case data (read-only): benchmark/markdown/mdNNN/, benchmark/sonar/<RULE_ID>/
configs/      Per-model YAML configs (base + -markdown/-sonar task variants)
prompts/      Versioned prompt templates (system_v1.md, markdown_v1.md, sonar_v1.md, ...)
runner/       The execution engine (installable package) — loaders, providers, grading, CLI entry points
scripts/      Standalone utility scripts (SonarQube server control, fixture verification, model smoke test)
tests/        pytest suite for the runner package
results/      Timestamped output of each run_all_* invocation, one report.json per run and resulting project for sonar runs
```

## Environment setup

Requires Python ≥ 3.11.

```bash
pip install -e .          # core deps: openai, llama-cpp-python, PyYAML, python-dotenv, huggingface-hub
pip install -e ".[dev]"   # + pytest, for running tests/
```

**Important** installing llama-cpp-python requires nvcc to use cuda devices, this also requires setting the CMAKE_ARGS="-DGGML_CUDA=on" environment variable before installing it

**API-based models** (`provider: openai` configs, e.g. `gpt5-markdown.yaml`): copy `.env.example` to `.env` and set `OPENAI_API_KEY`. it's loaded automatically on `import runner`, so no per-script setup is needed. An explicit `OPENAI_API_KEY=... python -m ...` in the shell still overrides the file.

**Local models** (`provider: llama.cpp` configs): place GGUF weight files under `models/` (gitignored) and point each config's `model:` field at the relative path. Inference goes through the `llama-cpp-python` bindings directly — no separate llama.cpp server process is required, though `llama-cpp-python` needs a working C/C++ toolchain (and CUDA, for GPU offload) to install. `python -m scripts.download_model` fetches a GGUF file from the Hugging Face Hub straight into `models/` (see *Downloading models* below) instead of doing it by hand.

**Sonar benchmark only**: requires `mvn`/`./mvnw` and a JDK on `PATH` (used to compile/test patched projects), and the system `patch` utility (used for `--edit-mode diff`). The SonarQube analysis phase additionally needs `podman` — it runs a containerized SonarQube on `localhost:9000` (see *Sonar analysis phase* below). Without podman, runs still complete; the sonar fields are recorded as skipped.

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
| `main_sonar <case> --config <name> --edit-mode {diff,structured,toolcall}` | Runs one sonar case end-to-end: generate → apply patch → compile → test → SonarQube analysis (`--no-sonar` to skip), printing the remaining and newly introduced issues. |
| `run_all_sonar --config <name> --edit-mode ...` | Runs every case under `benchmark/sonar/` through the full generate/apply/compile/test pipeline and writes `report.json`. |
| `run_all_sonar_generate --config <name> --edit-mode ...` | Generate + apply only (no compile/test) for every sonar case — for running the model-inference phase on a machine without a JDK/Maven. Writes `report.json` with `"validated": false`. |
| `validate_sonar_run <run_id>` | Re-runs compile + test for an already-generated run directory (from `run_all_sonar_generate`), without calling the model again, and updates that run's `report.json` in place (`"validated": true`). |
| `analyze_sonar_run <run_id> [--cases ...]` | Runs the SonarQube analysis phase for an already-generated *and* compiled run directory, without calling the model again, and updates that run's `report.json` in place (`"sonar_analyzed": true`). |

`run_all_sonar` performs the analysis phase inline by default; pass `--no-sonar` to skip it and run `analyze_sonar_run` later instead.

Standalone scripts run as `python -m scripts.<script>`:

| Script | What it does |
|---|---|
| `sonar_server {start,status,stop,reset}` | Manual control of the shared SonarQube container. `reset` deletes the container, its volumes and the stored credentials. |
| `download_model <repo_id> [filename] [--list] [--output-name ...]` | Downloads a GGUF file from the Hugging Face Hub into `models/`. See *Downloading models* below. |

### Downloading models

`python -m scripts.download_model <repo_id> <filename>` fetches one file from a Hugging Face repo straight into `models/`, so a config's `model:` field resolves without a manual browser download. It's a thin wrapper over `huggingface_hub.hf_hub_download` and needs no separate `git-lfs`/`huggingface-cli` setup.

```bash
# See what's in a repo before picking a quantization.
python -m scripts.download_model bartowski/Qwen2.5-Coder-7B-Instruct-GGUF --list

# Download one file, keeping its name from the repo.
python -m scripts.download_model bartowski/Qwen2.5-Coder-7B-Instruct-GGUF Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf

# ...or save it under a different local filename, e.g. to match a configs/*.yaml `model:` entry.
python -m scripts.download_model bartowski/Qwen2.5-Coder-7B-Instruct-GGUF Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf \
    --output-name qwen2.5-coder-7b-instruct-q4_k_m.gguf
```

A file that already exists at the destination is left alone (`--force` to re-download); `--revision` pins a branch/tag/commit. Gated or private repos need a token: set `HF_TOKEN` in `.env` (loaded the same way as `OPENAI_API_KEY`, see `runner/filesystem/env.py`) and it's picked up automatically, or pass `--token` explicitly to override it for one call. Public GGUF repos generally don't need a token but you may be rate limited or the download may fail if it is particularly large.

## Reading a run back

`python -m analysis.report [<run_id> ...]` re-renders a finished run's `report.json` as a readable summary — the per-case table, where cases fell short, and what it cost. With no argument it takes the most recent run; `--list` shows what's available with a headline each, and `-v` prints the failures' full untruncated output.

The two suites are graded on different things, so they're reported differently and the suite is detected from the report: **markdown** gets the matched rate and a by-difficulty breakdown; **sonar** gets the five-stage funnel (applied → compiled → tests passed → issue resolved → clean fix), which cases dropped out where, and the issues that survived or were newly introduced. A sonar run that was never analyzed says so rather than showing a blank column.

## How the tests work

Every case is **zero-shot**: one system message plus one user message, no examples, no conversation history, no retries or self-correction loop. The model gets exactly one attempt to produce the final answer from the task description and the provided context

### Prompt construction

A chat prompt is assembled from three pieces, all under `prompts/`:

- **`system_v1.md`** — the shared system message for every suite: be an expert software engineering assistant, follow the task instructions exactly, and output nothing but what was asked for. This is the only part that doesn't vary per case.
- **A user-prompt template** — one file per suite/edit-mode combination (`markdown_v1.md`, `sonar_v2.md`, `sonar_structured_v1.md`, `sonar_toolcall_v1.md`), containing the task framing, the output-format contract, and `{{placeholder}}` tokens.
- **The benchmark case's own data** — `PromptBuilder.build()` (`runner/core/prompt_builder.py`) substitutes each placeholder: every key in the case's `metadata.json` and every other file in the case directory (`issue.json` → `{{issue}}`, `rule.md` → `{{rule}}`, etc.) is available by its filename stem, JSON-encoded if it isn't already a string. `{{files}}` is special-cased to concatenate every file listed in `metadata["files"]`, each rendered with `### File: <path>` headers; for sonar cases these are **line-numbered** (`ProjectFileLoader`, blank lines shown as `<BLANK>`) so the model can cite a precise location without the line numbers themselves being part of any diff it produces. Any placeholder left unresolved after substitution raises an error rather than silently sending `{{...}}` to the model.

Because template and data are cleanly separated, adding a benchmark case never touches prompt code — dropping files into `benchmark/<suite>/<case_id>/` is enough.

## How outputs are validated

**Markdown**: the model's response is extracted as JSON (`JsonExtractor`, tolerant of ` ```json ` code fences) and compared against each case's `expected.json` with strict structural equality (`JsonComparator`) — every key, value, type, and array order must match exactly. There is no partial credit or fuzzy matching.

**Sonar**: there's no reference patch to diff against. Instead, grading is a pass/fail pipeline run against an isolated copy of the case's Maven project (the original under `benchmark/sonar/<ID>/project/` is never mutated):

1. **Apply** — the model's edit is turned into file changes: a unified diff via the system `patch` command (`--edit-mode diff`), or exact/fuzzy text-block replacement (`--edit-mode structured`/`toolcall`).
2. **Compile** — `mvn compile` (or `./mvnw compile`) against the patched project.
3. **Test** — if compilation succeeds, `mvn test` is run and its Surefire summary line is parsed for pass/fail counts.
4. **Analyze** — if compilation succeeded, the patched project is scanned by a real SonarQube server and the findings are diffed against the pristine project's findings (see below).

The headline metric is `clean_fix`: the reported issue is gone, no new issue was introduced, and every existing unit test still passes. The weaker signals (`applied`, `compiled`, `tests_passed`, `target_resolved`) are all kept separately.

### Sonar analysis phase

The analysis runs against a containerized SonarQube on `localhost:9000`, started on demand and **deliberately left running between invocations** — booting it costs 1–2 minutes, and replicability work means running the benchmark many times. Its database lives on podman volumes, so a restart reuses both the data and the admin token (cached in a temporary file in the root of the project). Use `python -m scripts.sonar_server {stop, start, status}` to control it manually.

Two comparisons are made per case:

- **Issue resolved?** No finding of the case's rule remains anywhere in the case's file. Deliberately not line-based: any patch shifts line numbers.
- **New issues?** Post-fix findings are compared against the pristine project's findings as a multiset keyed on `(rule, file, message)`. Anything above the baseline count is new — so a rule that fired twice before and twice after is not a regression, but twice before and three times after is.

The baseline side of that comparison is a pure function of the fixture and the analyzer version, so it's computed once and cached under `.cache/sonar-baselines/` (keyed by a hash of the fixture's sources, so editing a case invalidates it automatically). Scanner invocations share one Maven repository under `.cache/maven-repo/` and run offline once it's warm. Together these keep a repeat analysis to a few seconds per case instead of tens of seconds.

## Metrics extracted per run

Every `run_all_*` invocation writes `results/<timestamp>/report.json` with `{"config": ..., "summary": {...}, "cases": [...]}` — per-case detail plus an aggregate summary.

**Markdown** — per case: `matched` (bool), `execution_time`, `prompt_tokens`, `completion_tokens`, `tokens_per_second`, `finish_reason`, `parse_error`/`error`, the raw `response_text` and `parsed_output`. Aggregate summary adds: `matched_rate`, total/average token counts and throughput, `total_execution_time`/`wall_time`, and a `by_difficulty` breakdown (matched/total per difficulty level).

**Sonar** — per case: `applied`, `compiled`, `tests_ran`, `tests_passed`, `tests_run_count`/`tests_failed`/`tests_errored`, `execution_time`, `compile_time`, `test_time`, token counts, `tokens_per_second`, plus the generated `response_text`/`diff`. From the analysis phase: `sonar_analyzed`, `target_resolved`, `new_issues_count`, `new_issues` (full detail per finding), `remaining_target_issues`, `baseline_issue_count`/`after_issue_count`, `sonar_time`, and `sonar_error` (why a case was skipped, e.g. it never compiled). Aggregate summary adds: `applied_rate`, `compiled_rate`, `tests_passed_rate` (computed over compiled cases only, since a case that fails to compile can't run tests), `resolved_rate` (over analyzed cases, for the same reason), `clean_fix_rate` (over all cases — this is the headline number), `new_issues_total`, plus the same token/timing totals as markdown. `run_all_sonar_generate` writes a reduced summary (token/throughput/applied stats only, no compile/test fields) until `validate_sonar_run` fills the rest in.
