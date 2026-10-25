# Security boundaries

The public interface compares data and serves static evidence. It accepts no arbitrary commands, uploaded Python, remote repository execution or model-directed filesystem edits.

- ACV inspection rejects traversal, ignored trees, symlinks and Windows junctions, with bounded reads.
- Historical execution permits two exact reviewed source hashes and fixed patches. AST extraction is **not an OS sandbox** and must not be generalized to uploaded code.
- Installed-SDK validation uses separate dependency targets, allowlisted child environments, execution/output budgets and Python socket/subprocess audit blocking. Upgrade execution checks current constraints, runtime identity, download records and complete dependency inventories; two supported serializer hashes are reviewed explicitly. It has no OS memory/CPU isolation. No model credentials enter the workers. Installation is explicit and wheel-only, from official PyPI or a trusted offline wheelhouse.
- Provider origins are fixed; redirects/retries are disabled; sizes/tokens/timeouts are bounded. Socket timeouts are not hard OS execution limits.
- Model output is declarative. Retrieved documents are untrusted data, and citations must match supplied sources. Models cannot certify repairs.
- Reports redact configured secrets and credential-like fields/patterns. Review actual source/API logs before publication: redaction is not a privacy guarantee.
- Static serving is loopback-only with an exact path allowlist and symlink refusal. The viewer uses textContent, CSP and bounded JSON loading; no third-party CDN.
- Knowledge files are locally trusted observations, not signed attestations. Every reuse reruns contracts.
- Tool argument JSON is validated before execution and before evidence export; inputs requiring redaction are omitted rather than silently transformed. Stream validation rejects malformed containers, non-integer indices, invalid terminal states and ambiguous tool identities.

Docker/general OS isolation was unavailable. Generic untrusted-code execution remains absent rather than silently using an unsafe fallback. Review findings and fixes are in `docs/INDEPENDENT_REVIEW.md`. Do not put secrets in public vulnerability reports; contact the repository owner privately through an available channel. No external messages were sent.
