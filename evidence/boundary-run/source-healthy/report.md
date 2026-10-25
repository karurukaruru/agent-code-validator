# PatchCourt compatibility evidence

Run: a6161482-c35d-450c-a4b5-1d09d58fc058
Recorded: 2026-10-25T07:20:38.520158+00:00
Mode: boundary-run

| Case | Verdict | Evidence |
|---|---|---|
| nvidia-boundary-pair | PASS | {'baseline_variant': 'reviewed-patch', 'candidate_variant': 'reviewed-patch', 'kind': 'reviewed local serializer execution; no model inference'} |

## Limitations

- Two reviewed implementations of one serializer; not an automatic dependency upgrade or arbitrary repository runner.
- Supports text and OpenAI function-call inputs only; unsupported metadata and content abstain.
- Separate -I -S processes, clean environment, timeout, output budget and Python audit hook; not an OS security sandbox. Installed dependencies must be trusted.
- Input is checked against each output. An unhealthy baseline cannot establish a regression verdict, even when both outputs match.
- No model, search, or provider requests. Hash checks provide integrity, not independent authentication.
