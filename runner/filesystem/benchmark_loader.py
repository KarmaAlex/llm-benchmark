import json
from pathlib import Path

from runner.models.benchmark import BenchmarkCase
from runner.filesystem.paths import BENCHMARK_DIR

class BenchmarkLoader:

    @staticmethod
    def load(case_directory: Path):
        metadata = json.loads(
            (case_directory / "metadata.json").read_text()
        )

        issue = json.loads(
            (case_directory / "issue.json").read_text()
        )

        rule = (
            case_directory / "rule.md"
        ).read_text()
        
        return BenchmarkCase(
            id=case_directory.name,
            suite=case_directory.parent.name,
            metadata=metadata,
            issue=issue,
            rule_text=rule,
            project_path=case_directory / "project",
            case_path=case_directory,
        )

    @staticmethod
    def load_all_cases():
        cases = []
        for suite in BENCHMARK_DIR.iterdir():
            if not suite.is_dir():
                continue

            for case in suite.iterdir():
                if case.is_dir():
                    cases.append(
                        BenchmarkLoader.load(case)
                    )

        return sorted(
            cases,
            key=lambda c: c.id
        )