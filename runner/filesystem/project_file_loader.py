from pathlib import Path


class ProjectFileLoader:

    @staticmethod
    def load(
        project_directory: Path,
        file_path: str,
        include_lines: bool=True
    ) -> str:
        path = project_directory / file_path
        if not path.exists():
            raise FileNotFoundError(
                f"Project file not found: {file_path}"
            )
        if not path.is_file():
            raise ValueError(
                f"Project path is not a file: {file_path}"
            )
        if not include_lines: return path.read_text(encoding="utf-8")
        sections: list[str] = []
        content = path.read_text(encoding="utf-8")
        lines = content.splitlines()
        numbered_lines = [
            f"{line_number:4} | {"<BLANK>" if line.strip() == "" else line}"
            for line_number, line in enumerate(lines, start=1)
        ]

        return "\n".join(numbered_lines)