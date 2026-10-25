# PatchCourt compatibility evidence

Run: ab9429dd-32cd-4bbd-bd1f-86301740197c
Recorded: 2026-10-25T07:20:38.856224+00:00
Mode: boundary-run

| Case | Verdict | Evidence |
|---|---|---|
| nvidia-boundary-pair | NEEDS_REVIEW | {'baseline_variant': 'upstream', 'candidate_variant': 'reviewed-patch', 'kind': 'reviewed local serializer execution; no model inference'} |

## Limitations

- Two reviewed implementations of one serializer; not an automatic dependency upgrade or arbitrary repository runner.
- Supports text and OpenAI function-call inputs only; unsupported metadata and content abstain.
- Separate -I -S processes, clean environment, timeout, output budget and Python audit hook; not an OS security sandbox. Installed dependencies must be trusted.
- Input is checked against each output. An unhealthy baseline cannot establish a regression verdict, even when both outputs match.
- No model, search, or provider requests. Hash checks provide integrity, not independent authentication.
