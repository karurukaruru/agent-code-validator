# Security boundaries

The public interface compares data and serves static evidence. It accepts no arbitrary commands, uploaded Python, remote repository execution or model-directed filesystem edits.

- ACV inspection rejects traversal, ignored trees, symlinks and Windows junctions, with bounded reads.
- Historical execution permits two exact reviewed source hashes and fixed patches. AST extraction is **not an OS sandbox** and must not be generalized to uploaded code.
- Installed-SDK validation uses a separate dependency target, an allowlisted child environment, 30-second timeout and Python socket audit blocking. It has no OS memory/CPU isolation. No model credentials enter the child; package installation itself needs network.
- Provider origins are fixed; redirects/retries are disabled; sizes/tokens/timeouts are bounded. Socket timeouts are not hard OS execution limits.
- Model output is declarative. Retrieved documents are untrusted data, and citations must match supplied sources. Models cannot certify repairs.
- Reports redact configured secrets and credential-like fields/patterns. Review actual source/API logs before publication: redaction is not a privacy guarantee.
- Static serving is loopback-only with an exact path allowlist and symlink refusal. The viewer uses textContent, CSP and bounded JSON loading; no third-party CDN.
- Knowledge files are locally trusted observations, not signed attestations. Every reuse reruns contracts.

Docker/general OS isolation was unavailable. Generic untrusted-code execution remains absent rather than silently using an unsafe fallback. Review findings and fixes are in `docs/INDEPENDENT_REVIEW.md`. Do not put secrets in public vulnerability reports; contact the repository owner privately through an available channel. No external messages were sent.
