import json
from pathlib import Path

from acv import cli
from tests.fake_provider import FakeLLMProvider


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


def test_cli_agent_runs_end_to_end_with_fake_llm(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "app.py").write_text("print('hello')\n", encoding="utf-8")
    report = tmp_path / "agent-review.md"
    provider = FakeLLMProvider(
        [
            '{"action":"read_file","arguments":{"path":"app.py"}}',
            '{"action":"finish","reason":"The only source file was inspected"}',
            json.dumps(
                {
                    "issues": [
                        {
                            "severity": "medium",
                            "category": "bug",
                            "file": "app.py",
                            "location": "line 1",
                            "problem": "Terminal-visible finding",
                            "evidence": "The inspected line demonstrates the finding.",
                            "why_it_matters": "Users need to see the result immediately.",
                            "suggested_improvement": "Print structured agent findings.",
                            "confidence": "confirmed",
                        }
                    ]
                }
            ),
        ]
    )
    monkeypatch.setattr(cli, "load_config", lambda path: object())
    monkeypatch.setattr(cli, "LLMClient", lambda config: provider)

    status = cli.main(
        ["agent", str(project), "--output", str(report), "--max-steps", "5"]
    )

    output = capsys.readouterr()
    assert status == 0
    assert "Starting read-only Reviewer Agent" in output.out
    assert "Agent step 1: read_file" in output.out
    assert "Files inspected: 1" in output.out
    assert "AI agent review results: 1 issue(s)" in output.out
    assert "Problem: Terminal-visible finding" in output.out
    assert "Evidence: The inspected line demonstrates the finding." in output.out
    assert "Suggested change: Print structured agent findings." in output.out
    assert "# ACV Review Report" in report.read_text(encoding="utf-8")


def test_cli_agent_reviews_bundled_demo_project(
    tmp_path: Path, monkeypatch
) -> None:
    demo = Path(__file__).parents[1] / "examples" / "demo_project"
    report = tmp_path / "demo-agent-review.md"
    provider = FakeLLMProvider(
        [
            '{"action":"read_file","arguments":{"path":"calculator.py"}}',
            '{"action":"search_code","arguments":{"query":"average("}}',
            '{"action":"read_file","arguments":{"path":"main.py"}}',
            '{"action":"finish","reason":"Demo call path inspected"}',
            '{"issues":[]}',
        ]
    )
    monkeypatch.setattr(cli, "load_config", lambda path: object())
    monkeypatch.setattr(cli, "LLMClient", lambda config: provider)

    status = cli.main(["agent", str(demo), "--output", str(report)])

    assert status == 0
    text = report.read_text(encoding="utf-8")
    assert "`calculator.py`" in text
    assert "`main.py`" in text
