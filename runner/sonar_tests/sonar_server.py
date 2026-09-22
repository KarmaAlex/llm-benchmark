"""
A long-lived SonarQube server the benchmark can analyze projects against.

Unlike a throwaway per-run container, this one is named, backed by podman
volumes, and deliberately left running between invocations: SonarQube costs
1-2 minutes to boot and index its rules, and a replicability study runs the
benchmark many times. Paying that once and reusing the server (and its admin
token, which survives because the embedded database now lives on a volume) is
the difference between "analysis is free" and "analysis doubles the run".

Everything here is idempotent: ensure_running() is safe to call whether the
server is already up, merely stopped, or not created yet.

Manual control lives in scripts/sonar_server.py (start/stop/status/reset).
"""

import base64
import json
import os
import secrets
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from runner.filesystem.paths import MAVEN_REPO_DIR, PROJECT_ROOT

IMAGE = "docker.io/library/sonarqube:lts-community"
CONTAINER_NAME = "sonarqube-benchmark"
DATA_VOLUME = "sonarqube-benchmark-data"
EXTENSIONS_VOLUME = "sonarqube-benchmark-extensions"
CONTAINER_MEMORY = "3g"
HOST_PORT = 9000
BASE_URL = f"http://localhost:{HOST_PORT}"

# Credentials for a container that is thrown away on `reset` and reachable
# only on localhost, so a random password stored in plain text is fine.
STATE_FILE = PROJECT_ROOT / ".sonar-server.json"

STARTUP_TIMEOUT = 300
RECOVERY_TIMEOUT = 180
CE_TASK_TIMEOUT = 180
MVN_TIMEOUT = 600

# Pinned so Maven never has to resolve plugin version metadata (which also
# means an offline scanner run can work at all). Bump deliberately - the
# analyzer version is part of the baseline cache key, so a bump invalidates
# every cached baseline, which is exactly what you want.
SONAR_MAVEN_PLUGIN = "org.sonarsource.scanner.maven:sonar-maven-plugin:5.0.0.4389"

# Conservative, pinned heaps so the three bundled JVMs (web, compute engine,
# search/Elasticsearch) have a predictable total footprint instead of
# reaching for whatever the default sizing heuristic decides. On a
# memory-tight dev machine an unbounded SonarQube gets OOM-killed mid-run.
JAVA_OPTS_ENV = {
    "SONAR_SEARCH_JAVAOPTS": "-Xmx1g -Xms1g",
    "SONAR_WEB_JAVAOPTS": "-Xmx512m -Xms256m",
    "SONAR_CE_JAVAOPTS": "-Xmx512m -Xms256m",
}

TRANSIENT_ERROR_MARKERS = (
    "Connection refused",
    "Connection reset",
    "Broken pipe",
    "Not authorized",
    "404 Not Found",
    "bootstrapping has failed",
    "Failed to query server version",
)

# Marker next to the shared Maven repository recording that an online scanner
# run has already populated it, so later runs can go offline.
_MAVEN_WARM_MARKER = MAVEN_REPO_DIR.parent / "maven-repo.warm"


class SonarServerError(RuntimeError):
    pass


@dataclass
class AnalysisOutcome:
    ok: bool
    error: str = ""
    log: str = ""
    duration: float = 0.0


def sh(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def _request(
    method: str,
    path: str,
    token: str | None = None,
    password: str | None = None,
    data: dict | None = None,
    timeout: int = 30,
) -> tuple[int, dict | None]:
    """GET/POST against the server. Never raises on connection failure -
    callers see it as (0, None), the same shape as "responded with nothing
    useful". Auth is HTTP basic: either token-as-username with an empty
    password, or admin plus a password."""
    body = None
    if data is not None:
        body = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in data.items()).encode()
    req = urllib.request.Request(f"{BASE_URL}{path}", data=body, method=method)
    if token is not None:
        credentials = f"{token}:"
    elif password is not None:
        credentials = f"admin:{password}"
    else:
        credentials = None
    if credentials is not None:
        req.add_header("Authorization", f"Basic {base64.b64encode(credentials.encode()).decode()}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            return error.code, json.loads(raw)
        except json.JSONDecodeError:
            return error.code, None
    except (urllib.error.URLError, ConnectionError, TimeoutError):
        return 0, None


def server_status() -> str | None:
    _, payload = _request("GET", "/api/system/status")
    return payload.get("status") if payload else None


def wait_until_up(timeout: int = STARTUP_TIMEOUT, quiet: bool = False) -> bool:
    deadline = time.time() + timeout
    last_status = None
    while time.time() < deadline:
        last_status = server_status()
        if last_status == "UP":
            return True
        time.sleep(5)
    if not quiet:
        print(f"  (gave up waiting for SonarQube; last status seen: {last_status})")
    return False


def container_state() -> str:
    """'running', 'stopped' or 'absent'."""
    result = sh([
        "podman", "ps", "-a",
        "--filter", f"name=^{CONTAINER_NAME}$",
        "--format", "{{.State}}",
    ])
    state = result.stdout.strip().splitlines()
    if not state:
        return "absent"
    return "running" if state[0].lower().startswith("running") else "stopped"


def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.chmod(STATE_FILE, 0o600)


class SonarServer:
    """Handle on the shared server. Construct it with ensure_running()."""

    def __init__(self, token: str, password: str | None = None) -> None:
        self.token = token
        self.password = password

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #

    @classmethod
    def ensure_running(cls, quiet: bool = False) -> "SonarServer":
        def say(message: str) -> None:
            if not quiet:
                print(message)

        if server_status() != "UP":
            state = container_state()
            if state == "running":
                say("SonarQube container is running but not ready yet, waiting...")
            elif state == "stopped":
                say(f"Starting existing container '{CONTAINER_NAME}'...")
                result = sh(["podman", "start", CONTAINER_NAME])
                if result.returncode != 0:
                    raise SonarServerError(f"Failed to start container:\n{result.stderr}")
            else:
                say(f"Creating SonarQube container ({IMAGE}, memory capped at {CONTAINER_MEMORY})...")
                cls._create_container()
            if not wait_until_up():
                raise SonarServerError(
                    f"SonarQube did not reach status UP within {STARTUP_TIMEOUT}s. "
                    f"Check `podman logs {CONTAINER_NAME}`."
                )
            say("SonarQube is up.")

        return cls(*cls._authenticate())

    @staticmethod
    def _create_container() -> None:
        command = [
            "podman", "run", "-d", "--name", CONTAINER_NAME,
            "-p", f"{HOST_PORT}:9000",
            "--memory", CONTAINER_MEMORY,
            "-v", f"{DATA_VOLUME}:/opt/sonarqube/data",
            "-v", f"{EXTENSIONS_VOLUME}:/opt/sonarqube/extensions",
            "-e", "SONAR_ES_BOOTSTRAP_CHECKS_DISABLE=true",
        ]
        for key, value in JAVA_OPTS_ENV.items():
            command += ["-e", f"{key}={value}"]
        command.append(IMAGE)

        result = sh(command)
        if result.returncode != 0:
            raise SonarServerError(f"Failed to create container:\n{result.stderr}")

    @staticmethod
    def _authenticate() -> tuple[str, str | None]:
        """Reuse the stored token if it still works; otherwise mint a new one
        from the stored password; otherwise assume a fresh server still on
        admin/admin and bootstrap it."""
        state = _load_state()

        token = state.get("token")
        if token and _token_is_valid(token):
            return token, state.get("password")

        password = state.get("password")
        if password:
            token = _generate_token(password)
            if token:
                _save_state({"token": token, "password": password})
                return token, password

        password = secrets.token_urlsafe(24)
        if not _change_default_password(password):
            raise SonarServerError(
                "Could not authenticate against SonarQube: the stored credentials in "
                f"{STATE_FILE.name} don't work and the server is not on its default "
                "admin/admin password either.\n"
                "Start over with: python -m scripts.sonar_server reset"
            )
        token = _generate_token(password)
        if not token:
            raise SonarServerError("Changed the admin password but failed to generate a token.")
        _save_state({"token": token, "password": password})
        return token, password

    def reauthenticate(self) -> bool:
        """Called after something looked like a dead/restarted server. Waits
        for the server to come back and refreshes the token if needed."""
        if not wait_until_up(RECOVERY_TIMEOUT):
            return False
        try:
            self.token, self.password = self._authenticate()
        except SonarServerError:
            return False
        return True

    @staticmethod
    def stop() -> None:
        if container_state() != "absent":
            sh(["podman", "stop", CONTAINER_NAME])

    @staticmethod
    def reset() -> None:
        """Remove the container and its volumes - the only way back to a
        genuinely fresh server (and the escape hatch when the stored
        credentials stop working)."""
        sh(["podman", "rm", "-f", CONTAINER_NAME])
        for volume in (DATA_VOLUME, EXTENSIONS_VOLUME):
            sh(["podman", "volume", "rm", "-f", volume])
        STATE_FILE.unlink(missing_ok=True)

    # ------------------------------------------------------------------ #
    # web API
    # ------------------------------------------------------------------ #

    def http(self, method: str, path: str, data: dict | None = None) -> tuple[int, dict | None]:
        return _request(method, path, token=self.token, data=data)

    def delete_project(self, project_key: str) -> None:
        self.http("POST", "/api/projects/delete", data={"project": project_key})

    def fetch_findings(self, project_key: str) -> list[dict]:
        """Every finding SonarQube has for the project. Security Hotspots
        never show up in /api/issues/search - they live in a separate index -
        so they're fetched separately and normalized to the same shape
        (ruleKey -> rule)."""
        return self._fetch_issues(project_key) + self._fetch_hotspots(project_key)

    def _paged(self, path: str, key: str) -> list[dict]:
        items: list[dict] = []
        page = 1
        while True:
            separator = "&" if "?" in path else "?"
            _, payload = self.http("GET", f"{path}{separator}ps=500&p={page}")
            if not payload or key not in payload:
                break
            items.extend(payload[key])
            if len(items) >= payload.get("paging", {}).get("total", len(items)):
                break
            page += 1
        return items

    def _fetch_issues(self, project_key: str) -> list[dict]:
        return self._paged(f"/api/issues/search?componentKeys={project_key}", "issues")

    def _fetch_hotspots(self, project_key: str) -> list[dict]:
        hotspots = self._paged(f"/api/hotspots/search?projectKey={project_key}", "hotspots")
        for hotspot in hotspots:
            hotspot["rule"] = hotspot["ruleKey"]
        return hotspots

    def rule_info(self, rule: str) -> dict:
        if rule not in _rule_info_cache:
            _, payload = self.http("GET", f"/api/rules/show?key={rule}")
            _rule_info_cache[rule] = payload["rule"] if payload else {}
        return _rule_info_cache[rule]

    # ------------------------------------------------------------------ #
    # analysis
    # ------------------------------------------------------------------ #

    def analyze(
        self,
        project_directory: Path,
        project_key: str,
        log_path: Path | None = None,
        compile_first: bool = False,
    ) -> AnalysisOutcome:
        """Scan an already-compiled Maven project and wait for SonarQube to
        finish processing it. Retries once (after a health check) if the
        failure looks like the server went away mid-run."""
        for attempt in (1, 2):
            outcome = self._analyze_once(project_directory, project_key, log_path, compile_first)
            if outcome.ok:
                return outcome
            transient = any(marker in outcome.error or marker in outcome.log
                            for marker in TRANSIENT_ERROR_MARKERS)
            if attempt == 1 and transient:
                print("  analysis failed in a way that suggests the server restarted, recovering...")
                if self.reauthenticate():
                    continue
            return outcome
        return outcome

    def _analyze_once(
        self,
        project_directory: Path,
        project_key: str,
        log_path: Path | None,
        compile_first: bool,
    ) -> AnalysisOutcome:
        start = time.perf_counter()
        offline = _maven_is_warm()

        result = self._run_scanner(project_directory, project_key, offline, compile_first)
        output = result.stdout + result.stderr

        # A cold or partially-populated shared repo can't be used offline;
        # fall back to a networked run once and re-mark the repo as warm.
        if result.returncode != 0 and offline and _looks_like_offline_failure(output):
            result = self._run_scanner(project_directory, project_key, False, compile_first)
            output = result.stdout + result.stderr

        if result.returncode == 0:
            _mark_maven_warm()

        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(output, encoding="utf-8")

        if result.returncode != 0:
            tail = "\n".join(output.splitlines()[-15:])
            return AnalysisOutcome(False, tail, output, time.perf_counter() - start)

        task_id = _read_ce_task_id(project_directory)
        if task_id is None:
            return AnalysisOutcome(
                False, "scanner succeeded but produced no ceTaskId", output,
                time.perf_counter() - start,
            )

        ok, error = self._await_ce_task(task_id)
        return AnalysisOutcome(ok, error, output, time.perf_counter() - start)

    def _run_scanner(
        self,
        project_directory: Path,
        project_key: str,
        offline: bool,
        compile_first: bool,
    ) -> subprocess.CompletedProcess:
        MAVEN_REPO_DIR.mkdir(parents=True, exist_ok=True)
        command = ["mvn", "-q", "-B"]
        if offline:
            command.append("-o")
        if compile_first:
            command.append("compile")
        command += [
            f"{SONAR_MAVEN_PLUGIN}:sonar",
            f"-Dmaven.repo.local={MAVEN_REPO_DIR}",
            f"-Dsonar.host.url={BASE_URL}",
            # sonar.token is the modern spelling; SonarQube 9.9 LTS only
            # understands sonar.login. Sending both keeps one command line
            # working across server versions (newer servers just warn).
            f"-Dsonar.token={self.token}",
            f"-Dsonar.login={self.token}",
            f"-Dsonar.projectKey={project_key}",
            f"-Dsonar.projectName={project_key}",
            # The workspaces aren't git repositories and the scanner doesn't
            # ship its own JRE lookup for free - both probes are pure latency.
            "-Dsonar.scm.disabled=true",
            "-Dsonar.scanner.skipJreProvisioning=true",
        ]
        try:
            return sh(command, cwd=project_directory, timeout=MVN_TIMEOUT)
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(
                command, 1, "", f"Sonar analysis timed out after {MVN_TIMEOUT}s",
            )

    def _await_ce_task(self, task_id: str) -> tuple[bool, str]:
        deadline = time.time() + CE_TASK_TIMEOUT
        while time.time() < deadline:
            _, payload = self.http("GET", f"/api/ce/task?id={task_id}")
            status = payload["task"]["status"] if payload else None
            if status == "SUCCESS":
                return True, ""
            if status in ("FAILED", "CANCELED"):
                return False, f"Compute Engine task {status}: {payload}"
            time.sleep(2)
        return False, f"Compute Engine task did not finish within {CE_TASK_TIMEOUT}s"


_rule_info_cache: dict[str, dict] = {}


def _token_is_valid(token: str) -> bool:
    _, payload = _request("GET", "/api/authentication/validate", token=token)
    return bool(payload) and payload.get("valid") is True


def _change_default_password(new_password: str) -> bool:
    status, _ = _request(
        "POST", "/api/users/change_password",
        password="admin",
        data={"login": "admin", "previousPassword": "admin", "password": new_password},
    )
    return status in (200, 204)


def _generate_token(password: str) -> str | None:
    _, payload = _request(
        "POST", "/api/user_tokens/generate",
        password=password,
        data={"name": f"llm-benchmark-{secrets.token_hex(4)}"},
    )
    return payload.get("token") if payload else None


def _read_ce_task_id(project_directory: Path) -> str | None:
    report_task = project_directory / "target" / "sonar" / "report-task.txt"
    if not report_task.exists():
        return None
    for line in report_task.read_text(encoding="utf-8").splitlines():
        if line.startswith("ceTaskId="):
            return line.split("=", 1)[1]
    return None


def _maven_is_warm() -> bool:
    return _MAVEN_WARM_MARKER.exists()


def _mark_maven_warm() -> None:
    _MAVEN_WARM_MARKER.parent.mkdir(parents=True, exist_ok=True)
    _MAVEN_WARM_MARKER.touch()


def _looks_like_offline_failure(output: str) -> bool:
    markers = (
        "has not been downloaded from it before",
        "The repository system is offline",
        "Cannot access",
        "in offline mode",
        "Could not resolve dependencies",
        "Plugin org.sonarsource",
    )
    return any(marker in output for marker in markers)


def clear_maven_cache() -> None:
    shutil.rmtree(MAVEN_REPO_DIR, ignore_errors=True)
    _MAVEN_WARM_MARKER.unlink(missing_ok=True)
