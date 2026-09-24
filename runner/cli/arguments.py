"""
argparse options shared by the main_* and run_all_* entry points, so the
same flag means the same thing (and has the same choices) everywhere.
"""

import argparse

from runner.sonar_tests.edit_pipeline import PROMPT_NAME_BY_EDIT_MODE

EDIT_MODE_HELP = (
    "How the model expresses its fix: 'diff' (default, unchanged unified-diff "
    "behavior), 'structured' (line-number-free JSON edit list parsed from text), "
    "or 'toolcall' (native tool/function calling, requires supports_tools in the "
    "model config)."
)


def add_config_argument(parser: argparse.ArgumentParser, default: str) -> None:
    parser.add_argument(
        "--config",
        default=default,
        help=f"Model config name under configs/ to use (default: {default}).",
    )


def add_device_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--device",
        choices=["cuda", "cpu"],
        default="cuda",
        help="Run local (llama.cpp) models on the GPU (default) or force CPU-only.",
    )


def add_edit_mode_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--edit-mode",
        choices=list(PROMPT_NAME_BY_EDIT_MODE),
        default="diff",
        help=EDIT_MODE_HELP,
    )


def add_sonar_argument(parser: argparse.ArgumentParser, help: str) -> None:
    parser.add_argument(
        "--sonar",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=help,
    )


def add_run_id_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "run_id",
        help="Run directory name under results/ (or a path to it directly).",
    )
