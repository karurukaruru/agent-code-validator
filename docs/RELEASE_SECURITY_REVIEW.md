# Release security and correctness review

Reviewed on 2026-10-24 (Asia/Shanghai) by a separate agent from the implementation
author. Scope: provider transport/parsing, declarative model reasoning, reliability
lab verdicts, CLI/static serving, exported evidence and acceptance gates.

The reviewer owns only this document and
`tests/test_patchcourt_release_review.py`. Main-module fixes are made by the
implementation owner. Every provider interaction in this review is mocked with
dummy credentials. HTTP serving tests execute the real request handler against
in-memory request/response streams, without opening a port. These are regression
tests, not real Nebius, Tavily, model-quality, or penetration-test evidence.

## Findings and regression coverage

| Area | Finding | Required behavior |
| --- | --- | --- |
| Model test expectations | A proposal with any case received PASS even when its declared expectation disagreed with the independent comparator. | Preserve per-case verdicts; mismatches cannot produce aggregate PASS. |
| Unknown contracts | A proposal whose only cases were unsupported could receive PASS. | No determinate supported cases means INCONCLUSIVE. |
| Streaming lab | The lab's separate parser ignored roles, unknown delta semantics, extra choices, and repeated terminal events. | Reuse strict message reconstruction and reject unsupported/malformed streams. |
| Provider budgets | Empty/None inference payloads bypassed the conditional token-budget gate. | Require a dictionary with bounded integer max_tokens before transport. |
| Redaction | A provider echoing a credential as a JSON object key escaped value-only redaction. | Redact keys and values, including explicitly configured short keys. |
| Acceptance gates | `all([])` marked missing repair/control evidence as passing. | Require nonempty evidence before PASS. |
| Local file serving | Binding loopback alone did not reject an attacker-controlled Host during DNS rebinding. | Permit only the expected loopback/localhost Host and explicit static filenames. |
| Ablation aggregation | A known FAIL arm became INCONCLUSIVE at the aggregate level. | Preserve FAIL precedence; retain every arm's evidence. |
| JSON ambiguity | Provider JSON, SSE deltas, and schema-probe output accepted duplicate keys using last-value wins. | Apply strict JSON parsing at the actual untrusted boundaries. |
| Numeric overflow | JSON `1e999` became infinity despite rejection of literal NaN/Infinity. This could mark a response PASS and then fail evidence export. | Reject nonfinite decoded floats, including exponent overflow. |
| Malformed provider events | HTTP 200 `{"events":[1]}` caused uncaught AttributeError in usage extraction. | Return bounded failed-response evidence rather than aborting the run. |

The first seven areas were corrected while the independent tests were being
written and passed the initial test run. The first 22-test run independently
confirmed the ablation aggregation failure. Seven additional parser-boundary
tests expanded the suite to 29 and confirmed six failed assertions plus one
uncaught exception before those remaining fixes.

## Passing controls

- Well-formed streaming completion with a trailing usage-only event remains
  valid; false boolean output fails the requested contract.
- Malformed model choices become failure evidence without executing repairs.
- Invalid token counts, including booleans masquerading as integers, never
  invoke transport.
- Search URLs containing credentials, deceptive domain suffixes, or HTTP are
  excluded from allowlisted official-document results.
- Exported manifest SHA-256 matches the sanitized persisted report; the Markdown
  report does not retain the injected dummy secret.
- Invalid JSON passed through the CLI exits with uncertainty rather than a
  successful validation result.
- The static handler rejects plain/encoded traversal and unlisted files; POST
  exposes no mutation endpoint. Valid static reads include `nosniff` and
  `no-store` headers.
- Excessive JSON nesting is bounded.

## Reproduction

From the repository root, without credentials:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_patchcourt_release_review -v
```

The tests also work with the project's local pytest installation. This review
does not certify arbitrary imported reports, authenticate evidence against a
malicious local writer, establish complete filesystem isolation, or prove live
provider behavior. Evidence hashes remain integrity checks, not signatures.

Final independent verification: **29 tests passed**, with zero failures or
errors, after the implementation owner applied the remaining fixes. Ablation
retains FAIL precedence; provider, SSE, model-proposal and lab JSON use the strict
parser; decoded nonfinite numbers are rejected; malformed provider event shapes
produce failed evidence. The earlier controls remained passing in the final run.
