import json
from pathlib import Path

import pytest

from acv.agent_report import render_agent_report
from acv.agent_tools import ProjectTools
from acv.review_agent import AgentError, parse_agent_action, run_reviewer_agent
from tests.fake_provider import FakeLLMProvider


def _final_issue() -> str:
    return json.dumps(
        {
            "issues": [
                {
                    "severity": "high",
                    "category": "bug",
                    "file": "calculator.py",
                    "location": "line 2",
                    "problem": "除数可能为零",
                    "evidence": "divide 直接执行 total / count。",
                    "why_it_matters": "空输入会触发运行时异常。",
                    "suggested_improvement": "在除法前验证 count。",
                    "confidence": "confirmed",
                }
            ]
        },
        ensure_ascii=False,
    )


def test_agent_performs_multiple_tools_then_finishes(tmp_path: Path) -> None:
    (tmp_path / "calculator.py").write_text(
        "def divide(total, count):\n    return total / count\n",
        encoding="utf-8",
    )
    (tmp_path / "main.py").write_text(
        "from calculator import divide\nprint(divide(1, 0))\n",
        encoding="utf-8",
    )
    provider = FakeLLMProvider(
        [
            '{"action":"read_file","arguments":{"path":"calculator.py","start_line":1,"end_line":50}}',
            '{"action":"search_code","arguments":{"query":"divide("}}',
            '{"action":"read_file","arguments":{"path":"main.py","start_line":1,"end_line":50}}',
            '{"action":"finish","reason":"Call path and failure are confirmed"}',
            _final_issue(),
        ]
    )
    tools = ProjectTools(tmp_path)

    result = run_reviewer_agent(provider, tmp_path, tools=tools)

    assert [call[0] for call in tools.tool_calls] == [
        "list_files",
        "read_file",
        "search_code",
        "read_file",
    ]
    assert result.files_inspected == ["calculator.py", "main.py"]
    assert result.steps_used == 4
    assert result.stopped_by_limit is False
    assert result.issues[0].problem == "除数可能为零"


def test_max_steps_stops_an_infinite_investigation(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    provider = FakeLLMProvider(
        [
            '{"action":"list_files","arguments":{}}',
            '{"action":"list_files","arguments":{}}',
            '{"issues":[]}',
        ]
    )

    result = run_reviewer_agent(provider, tmp_path, max_steps=2)

    assert result.stopped_by_limit is True
    assert result.steps_used == 2
    assert result.finish_reason == (
        "Review stopped because the maximum agent step limit was reached."
    )
    assert result.warnings == [result.finish_reason]


def test_invalid_action_json_gets_a_bounded_repair_attempt(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    provider = FakeLLMProvider(
        [
            "not json",
            '{"action":"read_file","arguments":{"path":"app.py"}}',
            '{"action":"finish","reason":"The source file was inspected"}',
            '{"issues":[]}',
        ]
    )

    result = run_reviewer_agent(provider, tmp_path)

    assert result.steps_used == 2
    assert len(provider.calls) == 4
    assert "previous response was invalid" in provider.calls[1][1]


def test_agent_rejects_finish_before_any_file_is_read(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    provider = FakeLLMProvider(
        [
            '{"action":"finish","reason":"Too early"}',
            '{"action":"read_file","arguments":{"path":"app.py"}}',
            '{"action":"finish","reason":"Now there is evidence"}',
            '{"issues":[]}',
        ]
    )

    result = run_reviewer_agent(provider, tmp_path)

    assert result.steps_used == 3
    assert result.files_inspected == ["app.py"]
    assert "Finish rejected" in result.observations[1].result


def test_agent_report_has_required_sections_and_only_read_files(tmp_path: Path) -> None:
    (tmp_path / "calculator.py").write_text("return_value = 1\n", encoding="utf-8")
    provider = FakeLLMProvider(
        [
            '{"action":"read_file","arguments":{"path":"calculator.py"}}',
            '{"action":"finish","reason":"Enough evidence"}',
            _final_issue(),
        ]
    )

    report = render_agent_report(run_reviewer_agent(provider, tmp_path))

    assert "# ACV Review Report" in report
    assert "## Project Summary" in report
    assert "## Files Inspected" in report
    assert "`calculator.py`" in report
    assert "## Critical / High Priority Issues" in report
    assert "## Other Issues" in report
    assert "## Performance / Architecture Suggestions" in report
    assert "## Possible Issues Requiring Verification" in report
    assert "**Evidence**" in report


def test_parse_finish_accepts_reason_inside_native_tool_arguments() -> None:
    action = parse_agent_action(
        '{"action":"finish","arguments":{"reason":"Sufficient evidence"}}'
    )

    assert action.name == "finish"
    assert action.reason == "Sufficient evidence"


def test_parse_action_rejects_unknown_or_missing_tool_arguments() -> None:
    with pytest.raises(AgentError, match="unsupported arguments: typo"):
        parse_agent_action(
            '{"action":"read_file","arguments":{"path":"app.py","typo":1}}'
        )
    with pytest.raises(AgentError, match="missing required arguments: query"):
        parse_agent_action('{"action":"search_code","arguments":{}}')


def test_final_review_retries_when_issue_file_was_never_observed(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    (tmp_path / "unread.py").write_text("raise RuntimeError\n", encoding="utf-8")
    hallucinated = json.loads(_final_issue())
    hallucinated["issues"][0]["file"] = "unread.py"
    provider = FakeLLMProvider(
        [
            '{"action":"read_file","arguments":{"path":"app.py"}}',
            '{"action":"finish","reason":"The selected source was inspected"}',
            json.dumps(hallucinated, ensure_ascii=False),
            '{"issues":[]}',
        ]
    )

    result = run_reviewer_agent(provider, tmp_path)

    assert result.issues == []
    assert "unobserved project files: unread.py" in provider.calls[-1][1]


def test_agent_applies_selected_report_language(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    provider = FakeLLMProvider(
        [
            '{"action":"read_file","arguments":{"path":"app.py"}}',
            '{"action":"finish","reason":"Inspection complete"}',
            '{"issues":[]}',
        ]
    )

    run_reviewer_agent(provider, tmp_path, report_language="en")

    assert "finish reason in English" in provider.calls[0][0]
    assert "explanatory prose in clear English" in provider.calls[-1][0]
