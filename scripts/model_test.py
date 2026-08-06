"""
Simple llama.cpp benchmark utility.

Example:
    python test_llama.py ^
        --model models/qwen2.5-coder-3b-instruct-q4_k_m.gguf
"""

import argparse
import json
import time
from pathlib import Path

from llama_cpp import Llama


DEFAULT_PROMPT = """You are a helpful software engineer.

Write a Python function that returns the nth Fibonacci number using dynamic programming.
"""


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--model",
        required=True,
        help="Path to GGUF model"
    )

    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="Prompt to send"
    )

    parser.add_argument(
        "--ctx-size",
        type=int,
        default=8192,
    )

    parser.add_argument(
        "--gpu-layers",
        type=int,
        default=-1,
        help="-1 = offload as many layers as possible"
    )

    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0
    )

    parser.add_argument(
        "--max-tokens",
        type=int,
        default=256
    )

    args = parser.parse_args()

    model_path = Path(args.model)

    if not model_path.exists():
        raise FileNotFoundError(model_path)

    print("=" * 70)
    print("Loading model...")
    print("=" * 70)

    load_start = time.perf_counter()

    llm = Llama(
        model_path=str(model_path),
        n_ctx=args.ctx_size,
        n_gpu_layers=args.gpu_layers,
        verbose=False,
    )

    load_time = time.perf_counter() - load_start

    print(f"Loaded in {load_time:.2f}s\n")

    print("=" * 70)
    print("Generating...")
    print("=" * 70)

    start = time.perf_counter()

    response = llm.create_chat_completion(
        messages=[
            {
                "role": "user",
                "content": args.prompt,
            }
        ],
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )

    elapsed = time.perf_counter() - start

    message = response["choices"][0]["message"]["content"]

    usage = response.get("usage", {})

    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    total_tokens = usage.get("total_tokens", 0)

    print("\n")
    print("=" * 70)
    print("MODEL RESPONSE")
    print("=" * 70)
    print(message)

    print("\n")
    print("=" * 70)
    print("STATISTICS")
    print("=" * 70)

    print(f"Load time          : {load_time:.2f}s")
    print(f"Inference time     : {elapsed:.2f}s")
    print(f"Prompt tokens      : {prompt_tokens}")
    print(f"Completion tokens  : {completion_tokens}")
    print(f"Total tokens       : {total_tokens}")

    if elapsed > 0:
        print(f"Tokens/sec         : {completion_tokens / elapsed:.2f}")

    Path("response.json").write_text(
        json.dumps(response, indent=2),
        encoding="utf-8",
    )

    print("\nSaved raw response to response.json")


if __name__ == "__main__":
    main()