"""
Benchmark harness package.

Importing `runner` loads the project's .env, so `python -m runner.<entry>`
sees OPENAI_API_KEY and friends no matter which entry point is used.
"""

from runner.filesystem.env import load_env

load_env()
