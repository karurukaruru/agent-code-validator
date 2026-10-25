from pathlib import Path

import pytest

from acv.scanner import ScanError, scan_project


def test_scanner_collects_supported_source_files(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    (tmp_path / "service.go").write_text("package main\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("not source", encoding="utf-8")

    result = scan_project(tmp_path)

    assert [source.path for source in result.files] == ["app.py", "service.go"]
    assert result.files[0].file_type == "Python"
    assert "hello" in result.files[0].content


def test_scanner_ignores_configured_directories(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "keep.ts").write_text("export const x = 1;", encoding="utf-8")
    for directory in (
        ".git",
        ".pytest_cache",
        ".tox",
        "node_modules",
        "site-packages",
        ".venv-dev",
        ".sdk-nvidia",
        ".sdk-crewai",
        ".sdk-environments",
        ".wheelhouse",
        "outputs",
        "venv",
        "dist",
        "target",
    ):
        ignored = tmp_path / directory
        ignored.mkdir()
        (ignored / "ignored.py").write_text("raise RuntimeError", encoding="utf-8")

    result = scan_project(tmp_path)

    assert [source.path for source in result.files] == ["src/keep.ts"]


def test_scanner_skips_large_and_binary_files(tmp_path: Path) -> None:
    (tmp_path / "large.py").write_text("x" * 20, encoding="utf-8")
    (tmp_path / "binary.py").write_bytes(b"hello\x00world")

    result = scan_project(tmp_path, max_file_bytes=10)

    assert not result.files
    assert len(result.warnings) == 2


def test_scanner_reports_missing_path(tmp_path: Path) -> None:
    with pytest.raises(ScanError, match="does not exist"):
        scan_project(tmp_path / "missing")


def test_scanner_skips_symbolic_link_files(tmp_path: Path) -> None:
    target = tmp_path / "target.py"
    target.write_text("print('real')\n", encoding="utf-8")
    link = tmp_path / "link.py"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("Creating symbolic links is not permitted on this system")

    result = scan_project(tmp_path)

    assert [source.path for source in result.files] == ["target.py"]
    assert any("symbolic links" in warning for warning in result.warnings)


def test_scanner_does_not_follow_linked_directory(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.py").write_text("secret = True\n", encoding="utf-8")
    link = root / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Creating directory links is not permitted on this system")

    result = scan_project(root)

    assert result.files == []
    assert any("directory links" in warning for warning in result.warnings)
