from dataclasses import dataclass
from pathlib import Path
from prompt import Prompt
from model_config import ModelConfig
from runner.models.benchmark import BenchmarkCase

@dataclass(frozen=True)
class Experiment:
    benchmark: BenchmarkCase
    model: ModelConfig
    prompt: Prompt
    run_directory: Path