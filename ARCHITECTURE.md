# Architecture

```text
ACV bounded inspection → candidate conversion boundaries
recorded traces / pinned upstream functions / provider probes
  → semantic contracts → verdict or abstention
  → shared sanitized evidence → JSON / Markdown / static viewer
                              → scoped ASM observation
```

`semantic.py` normalizes supported message representations while preserving ordered content, calls and relationships. JSON whitespace/key order is irrelevant; boolean/integer types remain distinct. Invalid baselines require review; unknown semantics abstain. `recorder.py` exposes opt-in stage recording without global hooks.

`reproductions.py` verifies two exact source hashes and extracts audited functions using inert protocol types. Repairs are fixed source replacements with preconditions. Concrete assertions plus full semantic comparison validate NVIDIA repair; byte/MIME checks and controls validate Gemini repair. `examples/reproductions/full_sdk_nvidia.py` separately runs the real installed SDK in a clean child process and a reviewed patched module copy.

`providers.py` uses fixed HTTPS origins, no redirects/retries, bounded request/response sizes and socket timeouts. `reasoning.py` accepts bounded declarative proposals, never executable generated code. `lab.py` preserves all planned probe outcomes and a paired documentation experiment. Live evidence is unavailable without credentials.

`knowledge.py` applies ASM's identity, version, evidence, recovery and revalidation conventions. ASM is a Markdown skill/template, not a pre-existing Python runtime. Original template/license are in `docs`. Integrity checks are not signatures; untrusted writers could recompute them. A cache hit never skips current verification.

`runner.py` orchestrates cases, replay, minimization, reports and benchmark schedules. `cli.py` supplies trace checking, discovery, demo, lab and static loopback serving. The viewer treats loaded data as text and has no execution endpoint.

`upgrade_run.py` connects ACV discovery to two reviewed, unmodified NVIDIA
release environments. Explicit wheel-only preparation records installation and
file inventories. Shared constraints, Python identity and every dependency file
are checked before clean workers execute. `boundary_run.complete_pair` applies
one input-contract gate to release comparisons and reviewed patch comparisons;
an unhealthy baseline always remains NEEDS_REVIEW. `scripts/verify_sdk_upgrade.py`
executes the release pair, text control, scoped regression and recovery.

Not implemented: a general repository sandbox, arbitrary automated patch execution, full framework coverage or AUL preferences. No correctness inference depends on user preferences.
