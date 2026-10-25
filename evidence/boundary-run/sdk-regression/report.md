# PatchCourt compatibility evidence

Run: f92b77b4-51d0-4732-8076-9cf2c0795fc1
Recorded: 2026-10-25T07:20:39.831137+00:00
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
