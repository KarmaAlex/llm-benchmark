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
analysis/     Reading finished runs back: console reports and matplotlib/seaborn figures
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
pip install -e ".[analysis]"  # + matplotlib, seaborn, pandas, for the plotting scripts
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
| `run_all_reproducibility --model <name> [--repetitions N] [--suites ...]` |Runs both suites N times (default 10) with the same model and reports, per case, whether the responses changed between repetitions and how often the case passed. See *Reproducibility runs* below. |
| `run_all_models [--dry-run] [--local-only] [--models ...]` | Runs `run_all_reproducibility` for every available model, one after the other. See *Running every model* below. |

`run_all_sonar` performs the analysis phase inline by default; pass `--no-sonar` to skip it and run `analyze_sonar_run` later instead. `run_all_markdown`, `run_all_sonar` and `run_all_reproducibility` all take `--cases <id> ...` to run a subset.

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

**Hardware usage (local models, both suites)**: per case, `gpu_memory_mb` is read once after the call. It's this process's own GPU memory, so on a GPU shared with another job only our share counts. Only if process IDs are hidden (some containers) does it fall back to the whole card's usage. Power is sampled throughout the call:

- `gpu_power_w` / `gpu_power_peak_w`: GPU board power from `nvidia-smi`.
- `cpu_power_w` / `cpu_power_peak_w`: CPU package power, from the RAPL counter when it's readable (normally root only), otherwise an AMD APU's `PPT` sensor.
- `energy_wh`: what those two drew over the call.

The summary adds `peak_gpu_memory_mb`, `avg_gpu_power_w` / `avg_cpu_power_w` (weighted by call time), `peak_gpu_power_w` / `peak_cpu_power_w` and `total_energy_wh`. The per-case console table shows mean GPU + CPU power.

The sampler (`runner/providers/power.py`) runs in the background while a model is loaded. Each call takes the samples inside its own time window, so the call's timing isn't disturbed. Energy covers the GPU board and the CPU package only; RAM, display and power-supply losses aren't measured, so it's a lower bound on wall-socket energy. Anything the machine can't measure is `null`, as are all power fields for API models.

**Shared machines (SLURM)**: GPU readings target the GPUs in `CUDA_VISIBLE_DEVICES`, so a job measures the GPU it was allocated rather than whatever GPU 0 is. A MIG slice, or a job without a GPU, reads as unmeasured.

Each case also records `gpu_other_processes`: the number of other processes on its GPU holding at least 256 MiB. A desktop compositor's few MiB don't count. Any such process means the GPU was shared, so that case's power and latency include someone else's work. The summary counts these cases in `gpu_shared_cases`, and the console prints a warning. The field is `null` when it can't be told, for example inside a container that hides process IDs.

## Reproducibility runs

`python -m runner.run_all_reproducibility --model <name>` runs the markdown and sonar suites `--repetitions` times (default 10). Each suite uses `<name>-markdown` / `<name>-sonar` when that config exists, otherwise `<name>` itself; `--markdown-config` / `--sonar-config` pick one explicitly. The model is loaded once per suite and reused for every repetition, and llama.cpp configs pass their `seed` on every request, so a case's output doesn't depend on how many calls ran before it. `--edit-mode`, `--device`, `--no-sonar` and `--cases` behave as in the other runners.

```
results/<timestamp>/
    reproducibility.json          settings + per-suite, per-case aggregate
    markdown/rep-01/report.json   a normal run_all_markdown report
    sonar/rep-01/report.json      a normal run_all_sonar report (+ workspaces, sonar-logs)
```

Every `rep-NN/` directory is an ordinary run, so `analysis.report`, `validate_sonar_run` and `analyze_sonar_run` work on it. The aggregate is always rebuilt from those reports: `--aggregate-only <run_id>` re-grades a finished or interrupted run without calling the model.

Each case/repetition is compared at three levels:

| Level | Markdown | Sonar |
|---|---|---|
| **raw** | the exact response text | the response text plus the tool calls (toolcall mode) |
| **effective** | the parsed JSON, canonicalised (key order and code fences ignored) | the applied diff, with line endings and trailing whitespace normalised; `<not-applied>` if nothing applied |
| **verdict** | `matched` | `clean_fix`; `tests_passed` when the run used `--no-sonar` |

Each case gets the first classification that matches:

- `harness-error`: a repetition failed before the model answered, or a sonar case that passed its tests got no SonarQube verdict. Those repetitions are left out of everything else (`valid_classification` says how the rest behaved), so infrastructure problems aren't counted as model nondeterminism.
- `identical`: every raw response is byte-identical.
- `equivalent`: the raw responses differ, but the effective output is the same.
- `outcome-stable`: the effective outputs differ, but every repetition got the same verdict.
- `flaky`: the verdict changes between repetitions.

Per case the aggregate records:
- pass count and rate, and how many repetitions stopped at each pipeline stage;
- the number of distinct raw and effective outputs, and the agreement rate (share of repetitions giving the most common output);
- the completion-token range, latency mean/stdev, `finish_reason` values, and OpenAI `system_fingerprint` values;
- for cases whose repetitions disagree, the repetitions grouped by output (`A: reps 1,2,4`) and a sample diff between the two most common outputs.

Per suite it records:
- how many cases fall into each classification;
- how many passed every repetition, at least one, or none;
- the mean per-case pass rate;
- each repetition's pass rate with mean/stdev/min/max;
- the cases ordered from most to least unstable.

### Running every model

`python -m runner.run_all_models` runs the reproducibility benchmark for every available model in turn, so each one ends up with a full run to compare. Start with `--dry-run` to see the plan.

A model is a base config name, such as `qwen2.5-coder-7b-q4` rather than its `-markdown` / `-sonar` variants. It is available when every suite resolves to a config whose model can be loaded:

- **llama.cpp:** its GGUF file exists under `models/`.
- **openai:** `OPENAI_API_KEY` is set. These runs are billed per token; `--local-only` leaves them out.

The script also lists GGUF files under `models/` that no config points at, since those can't run until a config does.

- **Skipping existing runs:** a model that already has a full run with the same repetitions and edit mode is skipped, so re-running the script after an interruption only fills the gaps. Pass `--rerun` to run such models again.
- **Order and isolation:** local models run first, then API models. Each model runs in its own process, so its GPU memory is freed before the next one loads.
- **Failures:** a failing model doesn't stop the batch unless you pass `--stop-on-failure`. A summary at the end lists each model's outcome, duration and run directory.
- **Settings:** `--repetitions`, `--suites`, `--edit-mode`, `--device` and `--no-sonar` are passed through to each run. `--edit-mode` defaults to `structured`, like the existing full runs, so the results stay comparable.
- **Selecting models:** `--models BASE ...` / `--exclude BASE ...` pick which models run, and `--compare` runs `analysis.compare_models` at the end.

### Plotting reproducibility results

Both scripts need the `analysis` extra (`pip install -e ".[analysis]"`) and take `--format {png,pdf,svg}` (default `png` at `--dpi 200`) and `--out DIR`.

`python -m analysis.plot_reproducibility [<run_id>]` renders one reproducibility run (the newest by default) into `results/<run>/plots/`:

| Figure | Shows |
|---|---|
| `classification` | share of cases identical / equivalent / outcome-stable / flaky / harness-error, per suite |
| `pass_matrix` | cases × repetitions, pass / fail / harness error — a deterministic case is a solid row |
| `repetition_rate` | each repetition's pass rate with the mean and a ±1 sd band |
| `case_stability` | per case, the share of repetitions giving the most common output and how many distinct outputs there were |
| `sonar_funnel` | how many sonar trials reached each pipeline stage, and where each case's repetitions stopped |
| `latency_tokens` | per-case latency and completion-token spread across repetitions |
| `markdown_difficulty` | markdown pass rate by difficulty level |
| `cost_by_case` | what one attempt at each case costs (see *Cost estimates* below), plus `costs.csv` with per-suite totals |

Partial runs still plot whatever they contain; the script says what makes the run incomplete.

`python -m analysis.compare_models` compares commercial and open-source models, writing to `results/comparisons/<timestamp>/`. For each model it takes the newest **full** reproducibility run, meaning:

- both suites were run, on every case (no `--cases`);
- every repetition in `settings.repetitions` completed for both suites;
- sonar was graded on clean fixes (not `--no-sonar`, nothing pending validation);
- both suites used the same model.

A model is a config name without its ` (markdown)` / ` (sonar)` suffix, so quantizations (`Gemma-4-E4B-Q4` vs `-Q4-UD`) count as separate models. Its group comes from the `provider` in its `configs/*.yaml`: `openai` is commercial, `llama.cpp` is open source. Use `--group NAME=commercial|open` for a model the configs don't cover.

`--list` shows every reproducibility run, whether it's full (and why not), and which one each model contributes. `--models NAME ...` restricts the comparison, and `-v` explains skipped runs. The script warns when the selected runs differ in `edit_mode` or repetition count, or when one group has no models.

It writes `pass_rate` (pooled over every case × repetition trial, with a 95% Wilson interval), `classification`, `case_heatmap`, `agreement`, `sonar_funnel`, `efficiency` (pass rate against latency and completion tokens), `group_summary` (the mean of each group's models) and `cost` (one suite repetition and one passing trial, per model). It also writes the numbers behind the figures: `summary.csv` (per model × suite), `group_summary.csv`, `costs.csv`, `cost_assumptions.json` (every price and assumption used, with sources), and `selected_runs.json`, which records the run each model's numbers came from.

### Cost estimates

Both plotting scripts put a price in euros on each run. The rates are dated constants in `analysis/costs.py`, and every cost figure repeats them in a footnote.

- **API models** (`provider: openai`) cost tokens × OpenAI's standard-tier list price ([pricing page](https://developers.openai.com/api/docs/pricing), as of 2026-09-28). gpt-5 is \$1.25 input / \$10.00 output and gpt-5-mini is \$0.25 / \$2.00, per 1M tokens. Completion tokens already include reasoning tokens, which are billed as output. Runs don't record cached-input tokens, so all input is priced at the uncached rate, which makes this an upper bound. USD is converted at the ECB reference rate of 1 € = 1.1403 $ (2026-09-25).
- **Local models** (`provider: llama.cpp`) are costed on electricity alone, at €0.3163/kWh. That price is ARERA's Q3 2026 reference for the typical household customer, taxes included. Hardware depreciation is not counted. Where a run recorded `energy_wh` (see *Metrics extracted per run*), that measured energy is used (basis `electricity-measured`). Because it covers only the GPU board and the CPU package, it's a lower bound. Runs without measurements fall back to inference time × an assumed wall-power draw (basis `electricity`): 90 W by default (an RTX 4050 Laptop GPU near its 60 W limit, plus CPU and platform), shown with a 60–120 W band. Each trial uses whichever basis it has, and every figure's footnote names the bases it used.

- **Rented GPUs** (a llama.cpp run whose `settings.hardware.gpus` are all in `GPU_HOUR_PRICES_USD`) are costed in GPU-hours: inference time × the job's GPUs × the hourly rate. That's how a shared cluster GPU is paid for, and unlike a power reading it isn't affected by other jobs on the node. The default for the NVIDIA H200 NVL is the on-demand market rate of $3.79/GPU-hour (RunPod 1×), with a band of $3.52 (Vast.ai, the cheapest NVL listing) to $4.50 (the median across H200 providers), as of 2026-09-28. If your cluster has an internal rate, use it instead: `--gpu-hour-price "NVIDIA H200 NVL=<EUR>"`. A SLURM run on a GPU with no price (another GPU type on a mixed node) is reported as unpriced, never costed at household electricity prices, until `--gpu-hour-price` covers it. The GPU's exact name is in the run's `settings.hardware.gpus`. `costs.csv` also reports `gpu_hours` (model time) and `allocated_gpu_hours` (each repetition's wall-clock time × GPUs).

Only the model call is costed. Compile, test and SonarQube time is harness overhead that every model pays alike. Override any assumption for a run with `--local-watts`, `--local-watts-range LOW HIGH`, `--kwh-price` and `--usd-per-eur`. A model with no known price is reported as unpriced, never as free. To price a new API model, add it to `OPENAI_PRICES_USD_PER_1M`.

