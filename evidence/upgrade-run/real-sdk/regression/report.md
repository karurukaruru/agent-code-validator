# PatchCourt compatibility evidence

Run: fa5524f1-8aa3-430e-8999-1e3144ffb17a
Recorded: 2026-10-25T12:57:40.547519+00:00
Mode: boundary-run

| Case | Verdict | Evidence |
|---|---|---|
| nvidia-boundary-pair | FAIL | {'baseline_variant': 'reviewed-patch', 'candidate_variant': 'upstream', 'kind': 'reviewed local serializer execution; no model inference'} |

## Limitations

- Two reviewed implementations of one serializer; not an automatic dependency upgrade or arbitrary repository runner.
- Supports text and OpenAI function-call inputs only; unsupported metadata and content abstain.
- Separate -I -S processes, clean environment, timeout, output budget and Python audit hook; not an OS security sandbox. Installed dependencies must be trusted.
- Input is checked against each output. An unhealthy baseline cannot establish a regression verdict, even when both outputs match.
- No model, search, or provider requests. Hash checks provide integrity, not independent authentication.
