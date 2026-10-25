# PatchCourt compatibility evidence

Run: b636d412-7327-49b6-bd0c-595d6ad58e6e
Recorded: 2026-10-25T12:53:09.831518+00:00
Mode: upgrade-run

| Case | Verdict | Evidence |
|---|---|---|
| nvidia-release-upgrade | INCONCLUSIVE | {'kind': 'Two unmodified installed SDK releases; no model inference', 'dependency': 'langchain-nvidia-ai-endpoints', 'baseline_version': '1.4.3', 'candidate_version': '1.5.0'} |

## Limitations

- Executes only reviewed NVIDIA 1.4.3 and 1.5.0 text/tool serializers with real LangChain message classes.
- Repository inspection is read-only; application code and arbitrary model patches are never executed.
- Pinned common dependencies must match across both environments; SDK releases remain unmodified.
- Separate clean processes with deadlines and audit hooks; not an OS security sandbox. Dependencies must be trusted.
- Checks the original input as well as the version difference. Matching broken releases cannot PASS.
- Task replay is deterministic. No provider, model, Tavily or other paid requests are made.
- Inventories and checksums detect changes; they do not authenticate an untrusted local writer.
