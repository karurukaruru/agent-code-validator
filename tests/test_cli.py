import json
from pathlib import Path

from acv import cli


class FakeClient:
    def complete(self, system_prompt: str, user_content: str) -> str:
        assert "senior software engineer" in system_prompt
        assert "refactoring opportunities" in system_prompt
        assert "app.py" in user_content
        return json.dumps(
            [
                {
                    "severity": "medium",
                    "category": "error-handling",
                    "file": "app.py",
                    "location": "line 1",
                    "problem": "Example finding",
                    "reason": "It demonstrates the complete pipeline.",
                    "suggestion": "Handle the failure explicitly.",
                }
            ]
        )


def test_cli_review_runs_end_to_end_with_fake_llm(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "app.py").write_text("print('hello')\n", encoding="utf-8")
    report = tmp_path / "review.md"
    monkeypatch.setattr(cli, "load_config", lambda path: object())
    monkeypatch.setattr(cli, "LLMClient", lambda config: FakeClient())

    status = cli.main(["review", str(project), "--output", str(report)])

    output = capsys.readouterr()
    assert status == 0
    assert "Scanning project..." in output.out
    assert "AI review results: 1 issue(s)" in output.out
    assert "Problem: Example finding" in output.out
    assert "Why it matters: It demonstrates the complete pipeline." in output.out
    assert "Suggested change: Handle the failure explicitly." in output.out
    assert "Done." in output.out
    assert "Example finding" in report.read_text(encoding="utf-8")


def test_cli_puts_default_report_in_output_directory(
    tmp_path: Path, monkeypatch
) -> None:
    project = tmp_path / "sample project"
    project.mkdir()
    (project / "app.py").write_text("print('hello')\n", encoding="utf-8")
    output_dir = tmp_path / "all-reports"
    monkeypatch.setenv("ACV_OUTPUT_DIR", str(output_dir))
    monkeypatch.setattr(cli, "load_config", lambda path: object())
    monkeypatch.setattr(cli, "LLMClient", lambda config: FakeClient())

    status = cli.main(["review", str(project)])

    reports = list(output_dir.glob("sample_project_review_*.md"))
    assert status == 0
    assert len(reports) == 1
    assert "Example finding" in reports[0].read_text(encoding="utf-8")


def test_console_explains_when_no_issues(capsys) -> None:
    cli._print_review_results([])

    output = capsys.readouterr().out
    assert "AI review results: 0 issue(s)" in output
    assert "No meaningful issues" in output


def test_cli_handles_keyboard_interrupt(monkeypatch, capsys) -> None:
    def interrupted(args):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "_run_review", interrupted)

    status = cli.main(["review", "."])

    assert status == 130
    assert "Cancelled by user" in capsys.readouterr().err
