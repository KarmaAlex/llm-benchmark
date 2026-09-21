"""
Environment loading for the benchmark harness.

Secrets (OPENAI_API_KEY, HF_TOKEN) live in a gitignored `.env` at the
project root rather than in the committed config files. `load_env()` is
called once from `runner/__init__.py`, so every entry point picks the
file up without per-script boilerplate.
"""

from pathlib import Path

from dotenv import load_dotenv

from runner.filesystem.paths import PROJECT_ROOT

ENV_FILE = PROJECT_ROOT / ".env"


def load_env(path: Path | None = None, *, override: bool = False) -> bool:
    """
    Load the project's .env file into os.environ.

    Returns True if a file was found and read. A missing .env is not an
    error: the harness only needs a key for `provider: openai` configs,
    and local llama.cpp runs need none.

    Real environment variables take precedence over the file unless
    `override` is set, so an explicit

        OPENAI_API_KEY=sk-... python -m runner.run_all_sonar ...

    still beats whatever .env says.
    """
    env_file = ENV_FILE if path is None else Path(path)

    if not env_file.is_file():
        return False

    return load_dotenv(env_file, override=override)
