"""
Parameter counts of the open-source models, for the pass rate vs model size
figures.

Counts are the totals reported on each model card, in billions. Where a model
computes with fewer parameters than it stores, the card's effective/active
count is kept beside it and noted on the figure:

  - Gemma 4 E4B: "E" = effective. 8B with embeddings, 4.5B effective
    (per-layer embeddings are looked up, not multiplied).
  - Qwen3-Coder-30B-A3B: mixture of experts, 30.5B total, 3.3B active per token.

Commercial models have no published size and are not listed. The quantization
(Q4, Q8, F16) changes the memory a model needs, not its parameter count, so
every quantization of a family shares one entry. Notes are drawn in the
figures, so they are in Italian.

Sources (model cards, as of 2026-10-07):
  https://huggingface.co/google/Gemma-4-31B
  https://ai.google.dev/gemma/docs/core
  https://huggingface.co/microsoft/phi-4
  https://huggingface.co/microsoft/Phi-4-mini-instruct
  https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct
  https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct
  https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSize:
    params_b: float                   # total parameters, billions
    effective_b: float | None = None  # parameters used per token, if fewer
    note: str = ""                    # what the effective count means (Italian)


# Model family (the start of a comparison model name) -> size. The longest
# matching prefix wins, so "Phi4-mini-instruct-q8" isn't read as "Phi4".
MODEL_SIZES = {
    "Gemma-4-31B": ModelSize(30.7),
    "Gemma-4-E4B": ModelSize(8.0, 4.5, "4,5B effettivi"),
    "Phi4-mini-instruct": ModelSize(3.8),
    "Phi4": ModelSize(14.0),
    "Qwen2.5-Coder-3B": ModelSize(3.09),
    "Qwen2.5-Coder-7B": ModelSize(7.61),
    "Qwen3-Coder-30B": ModelSize(30.5, 3.3, "MoE, 3,3B attivi"),
}


def model_size(model: str) -> ModelSize | None:
    """The size of `model`'s family, or None if it isn't known."""
    name = model.lower()
    matches = [family for family in MODEL_SIZES if name.startswith(family.lower())]
    return MODEL_SIZES[max(matches, key=len)] if matches else None
