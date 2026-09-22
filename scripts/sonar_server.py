"""
Manual control for the shared SonarQube container the sonar benchmark
analyzes against.

The server is meant to stay up between runs - starting it costs 1-2 minutes
and a replicability study runs the benchmark many times - so nothing in the
pipeline ever stops it. That is what this script is for.

Usage:
    python -m scripts.sonar_server start      # create/start and wait for UP (idempotent)
    python -m scripts.sonar_server status
    python -m scripts.sonar_server stop       # keeps the volumes, so a restart is cheap
    python -m scripts.sonar_server reset      # delete container + volumes + stored credentials
    python -m scripts.sonar_server reset --clear-maven-cache
"""

import argparse

from runner.sonar_tests.sonar_server import (
    BASE_URL,
    CONTAINER_NAME,
    STATE_FILE,
    SonarServer,
    SonarServerError,
    clear_maven_cache,
    container_state,
    server_status,
)


def command_start() -> None:
    SonarServer.ensure_running()
    print(f"SonarQube is up at {BASE_URL} (token stored in {STATE_FILE.name}).")


def command_status() -> None:
    state = container_state()
    status = server_status()
    print(f"Container '{CONTAINER_NAME}': {state}")
    print(f"API status: {status or 'unreachable'}")
    print(f"Credentials file: {'present' if STATE_FILE.exists() else 'missing'}")
    if status == "UP" and STATE_FILE.exists():
        try:
            SonarServer.ensure_running(quiet=True)
            print("Stored token: valid")
        except SonarServerError as e:
            print(f"Stored token: unusable ({e})")


def command_stop() -> None:
    SonarServer.stop()
    print(f"Stopped '{CONTAINER_NAME}'. Volumes kept - the next start reuses its database and token.")


def command_reset(clear_maven: bool) -> None:
    answer = input(
        f"This removes container '{CONTAINER_NAME}', its volumes and the stored "
        "credentials. All analysis history is lost. Continue? [y/N] "
    )
    if answer.strip().lower() not in ("y", "yes"):
        print("Aborted.")
        return
    SonarServer.reset()
    print("Removed container, volumes and credentials.")
    if clear_maven:
        clear_maven_cache()
        print("Cleared the shared Maven repository too - the next analysis re-downloads it.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["start", "status", "stop", "reset"])
    parser.add_argument(
        "--clear-maven-cache",
        action="store_true",
        help="With 'reset', also delete the shared Maven repository.",
    )
    args = parser.parse_args()

    if args.command == "start":
        command_start()
    elif args.command == "status":
        command_status()
    elif args.command == "stop":
        command_stop()
    else:
        command_reset(args.clear_maven_cache)


if __name__ == "__main__":
    main()
