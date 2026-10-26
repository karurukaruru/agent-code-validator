# Captured boundary integration evidence

`release-installed-sdk/` is the final 0.5.1 capture-to-gate integration. It uses
real installed NVIDIA SDK types, the unmodified 1.4.3 serializer and an explicitly
reviewed local patch. Its matrix checks the semantic assertion reached in each
red/green/corruption scenario under Python -I -S. Zero provider requests.

`installed-sdk/` and `final-installed-sdk/` retain earlier development checks.
Their exported checker snapshots predate the final source-loading hardening;
use the final `release-installed-sdk/regression-gate/` and release ZIPs.
These records preserve local execution provenance, not cloud inference or
independent producer authentication.
