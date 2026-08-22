from pathlib import Path

from acv.report_generator import render_report, write_report
from acv.reviewer import ReviewIssue


def _issue() -> ReviewIssue:
    return ReviewIssue(
        severity="high",
        category="bug",
        file="calculator.py",
        location="line 5",
        problem="Division by zero is possible",
        reason="An empty input list causes a runtime failure.",
        suggestion="Validate that at least one value was supplied.",
    )


def test_render_report_contains_summary_and_issue_fields() -> None:
    report = render_report(project_path="demo", files_analyzed=2, issues=[_issue()])

    assert "# ACV Code Validation Report" in report
    assert "**Files analyzed:** 2" in report
    assert "[HIGH] Division by zero is possible" in report
    assert "`calculator.py`" in report
    assert "An empty input list" in report
    assert "Validate that" in report


def test_write_report_handles_no_findings(tmp_path: Path) -> None:
    destination = write_report(
        tmp_path / "reports" / "review.md",
        project_path="demo",
        files_analyzed=1,
        issues=[],
    )

    assert destination.exists()
    assert "No meaningful code-review issues" in destination.read_text(encoding="utf-8")
