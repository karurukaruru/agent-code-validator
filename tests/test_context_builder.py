from pathlib import Path

from acv.context_builder import build_context
from acv.scanner import ScanResult, SourceFile


def _source(path: str, content: str) -> SourceFile:
    return SourceFile(path=path, file_type="Python", content=content, size_bytes=len(content))


def test_context_keeps_paths_and_prioritizes_application_source() -> None:
    scan = ScanResult(
        project_path=Path("sample"),
        files=[_source("tests/test_app.py", "test code"), _source("src/app.py", "app code")],
    )

    result = build_context(scan, max_context_chars=180, max_file_chars=100)

    assert "src/app.py" in result.text
    assert result.included_files == ["src/app.py"]
    assert result.omitted_files == ["tests/test_app.py"]
    assert result.warnings


def test_context_truncates_oversized_file() -> None:
    scan = ScanResult(project_path=Path("sample"), files=[_source("app.py", "x" * 200)])

    result = build_context(scan, max_context_chars=500, max_file_chars=50)

    assert "file truncated by ACV" in result.text
    assert "Truncated app.py" in result.warnings[0]


def test_context_does_not_send_absolute_local_path() -> None:
    scan = ScanResult(
        project_path=Path("C:/Users/private/work/sample"),
        files=[_source("app.py", "app code")],
    )

    result = build_context(scan)

    assert "Project: sample" in result.text
    assert "C:/Users/private" not in result.text
