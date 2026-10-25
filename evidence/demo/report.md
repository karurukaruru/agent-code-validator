# PatchCourt compatibility evidence

Run: 629024a1-fac0-4598-bbf9-23a85339b12f
Recorded: 2026-10-24T13:33:09.876898+00:00
Mode: offline

| Case | Verdict | Evidence |
|---|---|---|
| langchain-nvidia-387 | FAIL | {'file': 'nvidia_utils.py.txt', 'sha256': 'ea569d556ed537e15bf5eea3db555adc9b4fb003a92543c70f1c719a9c47c873', 'git_blob': '8c23b708e8511c70e771f48fe71b4309d201f61b', 'version': 'upstream source blob (not a verified 1.4.3 wheel)', 'url': 'https://github.com/langchain-ai/langchain-nvidia/issues/387', 'kind': 'audited upstream function execution with inert LangChain stubs', 'full_sdk_verified': False} |
| crewai-8434 | FAIL | {'file': 'crewai_gemini.py.txt', 'sha256': '715e68f80b32cbd97011bf8c616b3746149454083a32b163cf2010f136a63383', 'git_blob': '1129d411257ce66d199f49ecb230c797374def24', 'version': '1.15.28 tag source', 'url': 'https://github.com/crewAIInc/crewAI/issues/8434', 'kind': 'audited upstream method with inert Gemini types and identity base formatter', 'full_sdk_verified': False} |
| unchanged-tool-workflow | PASS | negative control |
| json-formatting-equivalence | PASS | negative control |
| dropped-tool-calls | FAIL | controlled mutation |
| missing-call-id | FAIL | controlled mutation |
| duplicate-call-id | FAIL | controlled mutation |
| nested-argument-corruption | FAIL | controlled mutation |
| orphan-tool-result | FAIL | controlled mutation |
| invalid-role-conversion | FAIL | controlled mutation |
| truncated-arguments | FAIL | controlled mutation |
| image-control | PASS | negative control |
| lost-image-reference | FAIL | controlled mutation |
| lost-image-detail | FAIL | controlled mutation |
| unsupported-audio-abstention | INCONCLUSIVE | negative control |
| invalid-baseline-abstention | NEEDS_REVIEW | negative control |

## Limitations

- No Nebius/Nemotron or Tavily credentials: no live model or search claims.
- Historical reproductions execute hash-pinned upstream functions with inert SDK stubs; full SDK environments are not validated.
- NVIDIA snapshot is an upstream blob, not a verified release wheel; CrewAI snapshot comes from tag 1.15.28.
- Task recovery is a deterministic tool-protocol simulation, not a stochastic model outcome.
- Repair candidates are reviewed deterministic patches, not Nemotron-generated.
- The runner does not execute arbitrary repositories or model-generated Python; container execution is not implemented.
- Local knowledge is integrity-checked, not cryptographically authenticated against malicious writers.
