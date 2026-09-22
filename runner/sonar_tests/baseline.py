"""
The "before" side of the comparison: SonarQube's findings for a case's
pristine project.

That set is a pure function of the fixture's source and the analyzer
version, so it is computed once and cached on disk. Across ten replication
runs of twenty cases that is twenty baseline analyses instead of two
hundred - which is most of the reason full validation is affordable at all.

The cache key hashes the fixture's sources together with the SonarQube image
and the pinned scanner version, so editing a fixture or bumping the analyzer
invalidates the entry by construction. There is no manual invalidation.
"""

import hashlib
import json
import shutil
from pathlib import Path

from runner.filesystem.paths import (
    BENCHMARK_DIR,
    SONAR_BASELINE_CACHE_DIR,
    SONAR_SCRATCH_DIR,
)
from runner.sonar_tests.issue_diff import normalize_all
from runner.sonar_tests.sonar_server import IMAGE, SONAR_MAVEN_PLUGIN, SonarServer

# Build output is derived, not source: including it would make the key
# depend on whether someone happened to compile the fixture.
_IGNORED_DIRECTORIES = {"target", ".git"}


class BaselineError(RuntimeError):
    pass


def case_project_dir(case_id: str) -> Path:
    return BENCHMARK_DIR / "sonar" / case_id / "project"


def fixture_hash(case_id: str) -> str:
    project_directory = case_project_dir(case_id)
    digest = hashlib.sha256()
    digest.update(f"{IMAGE}|{SONAR_MAVEN_PLUGIN}\0".encode())
    for path in sorted(project_directory.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(project_directory)
        if _IGNORED_DIRECTORIES & set(relative.parts):
            continue
        digest.update(str(relative).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:16]


def cache_path(case_id: str) -> Path:
    return SONAR_BASELINE_CACHE_DIR / case_id / f"{fixture_hash(case_id)}.json"


def is_cached(case_id: str) -> bool:
    return cache_path(case_id).exists()


def baseline_findings(
    case_id: str,
    server: SonarServer,
    expected: dict | None = None,
    quiet: bool = False,
    refresh: bool = False,
) -> list[dict]:
    """Normalized findings for the pristine fixture, from cache when possible.

    `expected` (the case's issue.json) is only used for a sanity check when
    the cache misses: if the rule the case claims to plant doesn't actually
    fire on the expected file, every run graded against this baseline would
    score "resolved" for free, so that is worth shouting about."""
    path = cache_path(case_id)
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))["findings"]

    if not quiet:
        print(f"  computing baseline for {case_id} (first time for this fixture)...")

    findings = _analyze_pristine(case_id, server)

    if expected is not None:
        matching = [
            finding for finding in findings
            if finding["rule"] == expected["rule"] and finding["file"] == expected["file"]
        ]
        if not matching and not quiet:
            print(
                f"  WARNING: baseline for {case_id} does not contain {expected['rule']} on "
                f"{expected['file']}. Every model would score 'resolved' on this case for "
                "free - check the fixture with scripts/verify_sonar_issues.py."
            )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"case_id": case_id, "fixture_hash": path.stem, "findings": findings}, indent=2),
        encoding="utf-8",
    )
    return findings


def _analyze_pristine(case_id: str, server: SonarServer) -> list[dict]:
    """Analyze a throwaway copy of the fixture. A copy, not the fixture
    itself, so the repo never picks up a target/ directory from this."""
    scratch = SONAR_SCRATCH_DIR / f"baseline-{case_id}"
    shutil.rmtree(scratch, ignore_errors=True)
    scratch.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(case_project_dir(case_id), scratch)
    shutil.rmtree(scratch / "target", ignore_errors=True)

    project_key = f"benchmark-baseline-{case_id}"
    try:
        outcome = server.analyze(scratch, project_key, compile_first=True)
        if not outcome.ok:
            raise BaselineError(f"baseline analysis failed for {case_id}: {outcome.error}")
        findings = normalize_all(server.fetch_findings(project_key), project_key)
    finally:
        server.delete_project(project_key)
        shutil.rmtree(scratch, ignore_errors=True)
    return findings
