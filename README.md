# LLM Sonar Benchmark

A modular benchmarking framework for evaluating the performance of commercial and open-source Large Language Models (LLMs) on software engineering tasks.

The project is being developed as part of a master's thesis comparing the effectiveness of different LLMs on automated software development tasks such as static analysis issue resolution and software engineering document understanding.

---

# Objectives

The benchmark aims to:

* Evaluate multiple LLMs using identical benchmark tasks.
* Support both local and cloud-hosted models through a common provider interface.
* Separate benchmark execution from evaluation and statistical analysis.
* Produce fully reproducible experiments.
* Generate objective metrics suitable for academic comparison.

The framework is intentionally model-agnostic and benchmark-agnostic, allowing new benchmark suites and providers to be added without modifying the core execution pipeline.

---

# Project Structure

```
benchmark/
    Benchmark definitions (read-only)

configs/
    Model configuration files

prompts/
    Versioned benchmark prompts

runner/
    Benchmark execution engine

evaluators/
    Automatic metric computation

analysis/
    Statistical analysis and plotting

results/
    Raw experiment outputs
```

---

# Current Architecture

The benchmark follows the pipeline below:

```
Benchmark Case
        │
        ▼
Benchmark Loader
        │
        ▼
Prompt Loader
        │
        ▼
Prompt Builder
        │
        ▼
Provider
(OpenAI / llama.cpp / ...)
        │
        ▼
Model Response
        │
        ▼
Results
```

The execution layer is intentionally separated from evaluation so that benchmark outputs can be re-evaluated without rerunning expensive model inference.

---

# Current Features

## Benchmark Loading

Benchmark cases are loaded dynamically.

Each benchmark directory may contain arbitrary resource files.

Example:

```
benchmark/
    markdown/
        md001/
            metadata.json
            document.md
            task.md
```

Every resource file automatically becomes available to prompt templates through placeholders.

Example:

```
{{document}}

{{task}}
```

No benchmark-specific loading logic is required.

---

## Prompt System

Prompts are versioned to ensure reproducibility.

```
prompts/

    system.md

    sonar_v1.md

    markdown_v1.md
```

The PromptBuilder performs placeholder substitution automatically.

For example,

```
{{rule}}

{{issue}}

{{document}}

{{task}}
```

are replaced using the benchmark resources.

Any unresolved placeholders produce an error.

---

## Model Configuration

Each model has its own configuration file.

Example:

```yaml
name: GPT-5

provider: openai

model: gpt-5

temperature: 0

max_tokens: 4096

context: 128000

parameters: {}
```

The execution engine is unaware of individual models and interacts only with these configuration files.

---

## Provider Interface

Every provider implements the same interface.

```
ChatPrompt
        │
        ▼
generate(...)
        │
        ▼
ModelResponse
```

Currently implemented:

* OpenAI
* llama.cpp

This allows local GGUF models and hosted APIs to be benchmarked identically.

---

## Current Output

A benchmark execution currently produces:

* Rendered prompt
* Raw model response
* Basic inference metrics

Example metrics:

```json
{
    "latency": 2.81,
    "prompt_tokens": 517,
    "completion_tokens": 183,
    "finish_reason": "stop"
}
```

---

# Implemented Components

* Project structure
* Filesystem utilities
* Benchmark loader
* Prompt loader
* Configuration loader
* Prompt builder
* Provider interface
* OpenAI provider
* llama.cpp provider
* Provider factory
* Common data models
* Initial benchmark prompts
* Example Markdown benchmark

The current implementation is capable of executing complete inference runs against both local and remote models.

---

# Planned Components

## Runner

Implement the experiment runner responsible for:

```
Load benchmark
        │
Build prompt
        │
Run provider
        │
Store raw response
```

Later versions will additionally perform:

```
Apply patch

Compile project

Execute tests

Run SonarQube

Store execution logs
```

---

## Patch Executor

Apply unified diffs returned by models to temporary project copies.

Responsibilities:

* Apply patches safely
* Detect patch failures
* Preserve original benchmark cases

---

## Build Executor

Execute project compilation.

Initially:

* Maven
* Gradle

Outputs:

* Compilation success
* Build logs
* Execution time

---

## Test Executor

Execute project test suites after patch application.

Metrics include:

* Test success
* Number of regressions
* Execution time

---

## Sonar Evaluator

Execute SonarQube analysis before and after applying a patch.

Automatically determine:

* Issue removed
* New issues introduced
* Remaining issues

---

## Metrics Evaluators

Generate benchmark-independent metrics such as:

* Patch applied
* Compilation success
* Test success
* Execution time
* Files changed
* Lines changed
* Token usage

Each execution produces a `metrics.json` file independent of the raw model output.

---

## Analysis Module

Aggregate all benchmark executions into a single dataset.

Generate:

* CSV exports
* LaTeX tables
* Statistical summaries
* Publication-quality figures

Planned visualizations include:

* Overall benchmark accuracy
* Success rate by benchmark category
* Compilation failures
* Token usage
* Latency distributions
* Cost per successful benchmark
* Success versus benchmark difficulty

---

# Reproducibility

Each experiment will be assigned a unique run identifier.

Every run will record:

* Benchmark version
* Prompt version
* Model configuration
* Temperature
* Random seed (where supported)
* Git commit
* Timestamp

This ensures that all experiments can be reproduced exactly.

---

# Current Status

The framework has reached the first functional milestone.

An end-to-end execution is now possible:

```
Benchmark
    ↓
Prompt
    ↓
Model
    ↓
Response
```

The next development milestone is implementing the experiment runner, result writer, and execution pipeline for patch application, compilation, testing, and automatic evaluation.
