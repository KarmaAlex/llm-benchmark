"""
Download a model file from the Hugging Face Hub into models/.

Every local (`provider: llama.cpp`) config in configs/ points at a GGUF file
under models/ (gitignored - weights aren't committed). This is the
standalone counterpart: given a repo and a filename, it fetches exactly that
file into models/, so a config's `model:` path resolves without any manual
downloading.

Gated/private repos need a Hugging Face token. If HF_TOKEN is set in the
project's .env (see runner/filesystem/env.py), it's picked up automatically; otherwise
the download proceeds unauthenticated, which is all public GGUF repos need.

Examples:
    # See what's in a repo before picking a quantization.
    python -m scripts.download_model bartowski/Qwen2.5-Coder-7B-Instruct-GGUF --list

    # Download one file, keeping its name from the repo.
    python -m scripts.download_model \\
        bartowski/Qwen2.5-Coder-7B-Instruct-GGUF \\
        Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf

    # Download it under a different local filename (e.g. to match an
    # existing configs/*.yaml `model:` entry).
    python -m scripts.download_model \\
        bartowski/Qwen2.5-Coder-7B-Instruct-GGUF \\
        Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf \\
        --output-name qwen2.5-coder-7b-instruct-q4_k_m.gguf

    # A gated repo, using HF_TOKEN from .env.
    python -m scripts.download_model meta-llama/Llama-3.1-8B-Instruct-GGUF model.gguf
"""

import argparse
import os
import shutil

from huggingface_hub import hf_hub_download, list_repo_files
from huggingface_hub.errors import HfHubHTTPError

from runner.filesystem.env import load_env
from runner.filesystem.paths import MODELS_DIR

GGUF_SUFFIX = ".gguf"


def resolve_token(explicit: str | None) -> str | None:
    """--token wins if given; otherwise HF_TOKEN from .env or the real
    environment, exactly like ConfigLoader/OpenAIProvider pick up
    OPENAI_API_KEY. Returns None (unauthenticated) if neither is set -
    huggingface_hub then falls back to any hf CLI login on the machine,
    which is fine for public repos and simply fails clearly for gated ones."""
    if explicit:
        return explicit
    load_env()
    return os.environ.get("HF_TOKEN")


def list_files(repo_id: str, revision: str | None, token: str | None, show_all: bool) -> None:
    try:
        files = list_repo_files(repo_id, revision=revision, token=token)
    except HfHubHTTPError as e:
        raise SystemExit(f"Could not list files in '{repo_id}': {e}")

    if not show_all:
        files = [f for f in files if f.endswith(GGUF_SUFFIX)]

    if not files:
        kind = "GGUF files" if not show_all else "files"
        print(f"No {kind} found in {repo_id}. Pass --all to see the full file list.")
        return

    print(f"{'all files' if show_all else 'GGUF files'} in {repo_id}:")
    for name in sorted(files):
        print(f"  {name}")


def download(
    repo_id: str,
    filename: str,
    output_name: str | None,
    revision: str | None,
    token: str | None,
    force: bool,
) -> None:
    destination = MODELS_DIR / (output_name or filename)
    if destination.exists() and not force:
        print(f"{destination} already exists, skipping (use --force to re-download).")
        return

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {filename} from {repo_id}...")

    try:
        # local_dir writes the real file straight into models/ (no symlink
        # into a separate hub cache), so the config's `model:` path just works.
        downloaded_path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            revision=revision,
            token=token,
            local_dir=MODELS_DIR,
            force_download=force,
        )
    except HfHubHTTPError as e:
        raise SystemExit(f"Download failed: {e}")

    if output_name and output_name != filename:
        shutil.move(downloaded_path, destination)

    size_gb = destination.stat().st_size / (1024 ** 3)
    print(f"Saved to {destination} ({size_gb:.2f} GiB).")
    print(f"Point a config's `model:` field at: models/{destination.name}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("repo_id", help="Hugging Face repo, e.g. bartowski/Qwen2.5-Coder-7B-Instruct-GGUF.")
    parser.add_argument(
        "filename",
        nargs="?",
        help="File to download from the repo (required unless --list is given).",
    )
    parser.add_argument(
        "--output-name",
        help="Local filename under models/ (default: keep the repo's filename).",
    )
    parser.add_argument("--revision", help="Branch, tag or commit hash to download from (default: main).")
    parser.add_argument(
        "--token",
        help="Hugging Face token, overriding HF_TOKEN from .env / the environment.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if the destination file already exists.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List the repo's GGUF files (or every file with --all) instead of downloading, and exit.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="With --list, show every file in the repo, not just *.gguf.",
    )
    args = parser.parse_args()

    token = resolve_token(args.token)

    if args.list:
        list_files(args.repo_id, args.revision, token, args.all)
        return

    if not args.filename:
        parser.error("filename is required unless --list is given.")

    download(args.repo_id, args.filename, args.output_name, args.revision, token, args.force)


if __name__ == "__main__":
    main()
