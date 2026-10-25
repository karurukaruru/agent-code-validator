# Nebius Reliability Lab — evidence-based feedback draft

Status: BLOCKED

This draft requires human technical review and completion of the official feedback field.

## Environment

```json
{
  "model": null,
  "endpoint": "https://api.tokenfactory.nebius.com/v1",
  "environment": {
    "python": "3.13.14",
    "platform": "Windows-11-10.0.26200-SP0",
    "patchcourt": "0.3.0"
  },
  "source_report_sha256": "c3dea1bc5385f1c31f4d9cfe4c575729002122dbee3568da0597bf6e62504d9e"
}
```

## Raw counts

| Probe | Planned | Observed HTTP | Pass | Fail | Excluded/blocked |
|---|---:|---:|---:|---:|---:|
| structured_json | 3 | 0 | 0 | 0 | 3 |
| tool_call | 3 | 0 | 0 | 0 | 3 |
| streaming | 3 | 0 | 0 | 0 | 3 |
| invalid_model_error | 3 | 0 | 0 | 0 | 3 |

No authenticated HTTP observations are available. No platform findings, strengths, weaknesses or reliability rates can be asserted. Missing credentials are not a Nebius defect.

## Uncertainty and publication checks

- Producer-declared HTTP provenance is not independently authenticated by this renderer.
- A contract failure is not automatically a platform bug: inspect model support, request validity, account limits and harness behavior.
- Repeated same-model trials can be correlated; Wilson intervals are descriptive under independent-binomial assumptions, not a population reliability guarantee.
- No observed HTTP response means no positive or negative platform claim.
- Exact Devpost field and character limit remain unverified.
