import subprocess
import time
from pathlib import Path

from runner.models.command_result import CompilationResult

class Compiler:

    @staticmethod
    def compile(
        project_directory: Path,
        timeout: float = 300,
    ) -> CompilationResult:
        command = Compiler._detect_command(
            project_directory
        )
        if command is None:
            return CompilationResult(
                compiled=False,
                command=[],
                stdout="",
                stderr="No supported build system found.",
                execution_time=0.0,
            )
        start = time.perf_counter()
        try:
            result = subprocess.run(
                command,
                cwd=project_directory,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            execution_time = time.perf_counter() - start
            stdout = Compiler._decode_output(
                exc.stdout
            )
            stderr = Compiler._decode_output(
                exc.stderr
            )
            return CompilationResult(
                compiled=False,
                command=command,
                stdout=stdout,
                stderr=(
                    f"{stderr}\n"
                    "Compilation timed out."
                ),
                execution_time=execution_time,
            )
        execution_time = time.perf_counter() - start
        return CompilationResult(
            compiled=result.returncode == 0,
            command=command,
            stdout=result.stdout,
            stderr=result.stderr,
            execution_time=execution_time,
        )

    @staticmethod
    def _decode_output(
        output: str | bytes | None,
    ) -> str:
        if output is None:
            return ""
        if isinstance(output, bytes):
            return output.decode(
                "utf-8",
                errors="replace",
            )
        return output

    @staticmethod
    def _detect_command(
        project_directory: Path,
    ) -> list[str] | None:
        if (project_directory / "mvnw").exists():
            return [
                "./mvnw",
                "compile",
            ]
        if (project_directory / "pom.xml").exists():
            return [
                "mvn",
                "compile",
            ]
        return None