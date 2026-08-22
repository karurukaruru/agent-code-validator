import pytest

from acv.reviewer import ReviewError, parse_review


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
