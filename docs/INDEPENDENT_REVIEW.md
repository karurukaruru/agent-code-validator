# Independent held-out review

Date: 2026-10-24 (Asia/Shanghai).

Scope: `patchcourt/semantic.py`, `reproductions.py`, `knowledge.py`, and
`evidence.py`. This review used a separate agent from the implementation author.
For the independent review, the reviewer changed only this report and
`tests/test_patchcourt_adversarial.py`. No provider API, credentials, or live
vision model was used. A subsequent separately authorized installed-SDK
reproduction is recorded below.

## Method

The independent suite uses Python standard-library `unittest`, unrelated tool
names/arguments, Unicode, false/zero values, reverse-order tool responses, two
distinct image payloads, malformed base64, unknown schemas, stream fragments,
tampered stored evidence, and redaction with an ephemeral dummy secret.

Run from `agent-code-validator`:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_patchcourt_adversarial -v
```

## Initial findings sent to implementation owner

1. **P1: Stream reconstruction discarded unsupported semantics.** A custom
   tool-call type, unknown function fields, or a non-assistant role was silently
   normalized into an ordinary assistant function call. Unknown schemas must
   reject/abstain rather than appear verified.
2. **P1: Ambiguous message fields could pass.** Contradictory `role` and `type`,
   and conflicting top-level versus `additional_kwargs.tool_calls`, were ignored
   based on field precedence rather than rejected as ambiguous.
3. **P1: Non-finite dictionary arguments could pass.** Infinity values supplied
   as Python dictionaries bypassed the strict JSON string parser. These are not
   valid JSON wire arguments.
4. **P1: Repair verification covered only part of the repaired result.** The
   NVIDIA verifier checked count and first-call fields, leaving the second
   call's arguments outside its verification predicate. A held-out mutation
   changes that second call while preserving the original sample's checks.
5. **P2: Redaction invalidated stored integrity hashes.** `KnowledgeStore.save`
   calculated integrity before `write_json` sanitized secret values. The stored
   record was correctly redacted but could not subsequently pass lookup.
6. **P1: Truthy execution strings could enter verified knowledge.** An
   observation with `execution: "false"` passed the original boolean gate. The
   gate must require the literal boolean `true`.

The initial 24-test run reproduced seven failed assertions (including separate
positive/negative infinity subtests) and one integrity error. Two subsequent
tests cover incomplete repair verification and the strict execution flag,
bringing the independent suite to 26 tests.

## Checks already passing at initial review

- Unknown audio content and unknown tool extensions abstained.
- Nested booleans were distinguished from integers; duplicate tool responses
  invalidated the baseline.
- Valid fragmented streaming arguments reconstructed exactly; truncated streams
  were rejected.
- Both source-boundary patches preserved additional held-out inputs: parallel
  tool calls with Unicode and two distinct image payloads in order.
- Malformed base64 and modified source hashes were rejected.
- Unexecuted or inconclusive observations could not enter verified knowledge;
  record tampering was detected and version changes prevented reuse.
- Nested authorization and API-key values were redacted.
- Reproduction evidence explicitly disclaimed full SDK verification and left
  the vision task inconclusive without model inference.

## Trust limits

The source execution harness accepts only exact reviewed source hashes and
deterministic reviewed patches. Its Python `exec` is not a process sandbox:
the safety boundary is the exact allowlist and the reviewed extracted function,
not isolation against arbitrary code. Do not widen inputs to arbitrary paths,
model-generated patches, or user-provided source without a separate isolation
design.

Knowledge integrity hashes detect accidental or unrehashed changes; they do
not authenticate a record against an attacker able to rewrite it and recompute
the hash. Caller-provided `execution: true` is a trusted internal assertion,
not cryptographic proof. Existing reuse text correctly requires re-execution
before a current PASS. No full SDK or provider compatibility conclusion follows
from these source-boundary checks.

Final independent rerun: **26 tests passed** using the command above after the
implementation owner fixed all six reported defects. This is a local regression
result for the reviewed scope, not a complete security audit or live SDK claim.

## Subsequent actual installed SDK reproduction

The official PyPI `langchain-nvidia-ai-endpoints==1.4.3` wheel and its dependencies
were subsequently installed into the ignored `.sdk-nvidia` target. The real
`langchain-core==1.7.0` `AIMessage` and original installed adapter reproduced the
loss of two normalized tool calls. The reviewed deterministic patched module
copy restored both calls with all expected fields and passed five controls,
including a deliberately corrupted second call that the oracle detected.

Evidence is in `agent-code-validator/evidence/full-sdk/nvidia-1.4.3-result.json`,
with source snapshots, original wheel metadata/RECORD/license, dependency pins,
and the repair diff alongside it. The reproducible reviewed runner is
`agent-code-validator/examples/reproductions/full_sdk_nvidia.py`.

The original installed SDK was not changed. Execution used a clean isolated
Python subprocess with a strict environment allowlist and no credential values;
socket connect/DNS/bind audit events were blocked. This is actual installed-SDK
serializer validation with real message classes, not provider end-to-end
verification or an OS sandbox claim. CrewAI remains a source-boundary harness.

The initially unavailable `.venv` pip module and successful retry through system
pip are documented in the evidence README. All package files were installed into
the local target; no global package was modified.
