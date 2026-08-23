import pytest

from acv.reviewer import ReviewError, parse_review, review_code


def test_parse_review_accepts_fenced_json_and_sorts_severity() -> None:
    raw = """```json
    [
      {"severity":"low","category":"quality","file":"a.py","location":"line 1","problem":"p1","reason":"r1","suggestion":"s1"},
      {"severity":"high","category":"bug","file":"b.py","location":"line 2","problem":"p2","reason":"r2","suggestion":"s2"}
    ]
    ```"""

    issues = parse_review(raw)

    assert [issue.severity for issue in issues] == ["high", "low"]


def test_parse_review_accepts_empty_result() -> None:
    assert parse_review("[]") == []


def test_parse_review_rejects_missing_fields() -> None:
    with pytest.raises(ReviewError, match="missing"):
        parse_review('[{"severity": "high"}]')


def test_parse_review_rejects_null_required_value() -> None:
    raw = (
        '[{"severity":"high","category":"bug","file":"a.py",'
        '"location":null,"problem":"p","reason":"r","suggestion":"s"}]'
    )

    with pytest.raises(ReviewError, match="invalid values"):
        parse_review(raw)


def test_classic_reviewer_applies_selected_report_language() -> None:
    class CapturingClient:
        system_prompt = ""

        def complete(self, system_prompt: str, user_content: str) -> str:
            self.system_prompt = system_prompt
            return "[]"

    client = CapturingClient()

    assert review_code(client, "project context", report_language="en") == []
    assert "clear English" in client.system_prompt
