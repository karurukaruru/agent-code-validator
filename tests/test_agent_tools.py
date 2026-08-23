from pathlib import Path

import pytest

from acv.agent_tools import ProjectTools, ToolError


def test_list_files_uses_ignore_rules_and_limits_results(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "src" / "worker.py").write_text("pass\n", encoding="utf-8")
    ignored = tmp_path / "node_modules"
    ignored.mkdir()
    (ignored / "bad.py").write_text("raise RuntimeError\n", encoding="utf-8")

    result = ProjectTools(tmp_path, max_list_entries=1).execute("list_files")

    assert "src/app.py" in result.content
    assert "worker.py" not in result.content
    assert "node_modules" not in result.content
    assert "additional source file" in result.content


def test_read_file_is_line_numbered_bounded_and_cached(tmp_path: Path) -> None:
    source = tmp_path / "app.py"
    source.write_text("\n".join(f"line {number}" for number in range(1, 11)), encoding="utf-8")
    tools = ProjectTools(tmp_path, max_read_lines=3)

    first = tools.execute(
        "read_file", {"path": "app.py", "start_line": 2, "end_line": 9}
    )
    second = tools.execute(
        "read_file", {"path": "app.py", "start_line": 2, "end_line": 9}
    )

    assert "     2 | line 2" in first.content
    assert "     4 | line 4" in first.content
    assert "line 5" not in first.content
    assert "request truncated to 3 lines" in first.content
    assert second.cached is True
    assert second.content == first.content
    assert tools.files_inspected == {"app.py"}


def test_search_code_returns_paths_lines_and_small_context(tmp_path: Path) -> None:
    (tmp_path / "auth.py").write_text(
        "def authenticate_user():\n    return True\n\nauthenticate_user()\n",
        encoding="utf-8",
    )

    tools = ProjectTools(tmp_path)
    result = tools.execute(
        "search_code", {"query": "authenticate_user", "context_lines": 0}
    )

    assert "auth.py:1" in result.content
    assert "auth.py:4" in result.content
    assert "| def authenticate_user():" in result.content
    assert tools.files_observed == {"auth.py"}


@pytest.mark.parametrize(
    "unsafe_path",
    ["../outside.py", "..\\outside.py", "C:\\Windows\\win.ini"],
)
def test_read_file_cannot_escape_project_root(tmp_path: Path, unsafe_path: str) -> None:
    tools = ProjectTools(tmp_path)

    with pytest.raises(ToolError):
        tools.read_file(unsafe_path)


def test_read_file_rejects_symlink_even_when_target_is_inside_root(tmp_path: Path) -> None:
    target = tmp_path / "target.py"
    target.write_text("print('target')\n", encoding="utf-8")
    link = tmp_path / "link.py"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("Creating symbolic links is not permitted on this system")

    with pytest.raises(ToolError, match="symbolic links"):
        ProjectTools(tmp_path).read_file("link.py")


def test_agent_file_listing_does_not_follow_linked_directory(tmp_path: Path) -> None:
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

    listing = ProjectTools(root).list_files()

    assert "secret.py" not in listing
    assert "no supported source files" in listing
