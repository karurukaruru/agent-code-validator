# Execute a reviewed boundary pair

`boundary-run` executes two reviewed implementations of NVIDIA's message serializer in separate local Python processes, captures their inputs and outputs, and checks whether each preserves the original message contract. It makes **zero provider or search requests**.

This fills a narrower gap than general upgrade automation: the implementations are `upstream` and a fixed `reviewed-patch`, not two selectable dependency releases. Arbitrary repositories, generated Python, automatic dependency installation and OS sandboxing are not supported.

## Run without keys or extra dependencies

```bash
python -m patchcourt boundary-run --output outputs/boundary-regression
python -m patchcourt verify outputs/boundary-regression
python -m patchcourt serve outputs/boundary-regression --port 8765
```

The default compares a reviewed repair as the baseline with the known broken upstream implementation as the candidate. **Exit 1 / FAIL is expected**: two normalized tool calls disappear. Each output directory must be new; existing evidence is never overwritten.

| Baseline | Candidate | Expected overall result on default input |
|---|---|---|
| `reviewed-patch` | `upstream` | FAIL, exit 1: candidate introduces loss |
| `reviewed-patch` | `reviewed-patch` | PASS, exit 0: both preserve input |
| `upstream` | `reviewed-patch` | NEEDS_REVIEW, exit 2: baseline broken; candidate restores contract |
| `upstream` | `upstream` | NEEDS_REVIEW, exit 2: identical broken outputs cannot establish compatibility |

Select the variants with `--baseline` and `--candidate`. The report separately records original-input → baseline, original-input → candidate, and baseline → candidate comparisons. A successful repair therefore remains visible even when the baseline cannot support a valid compatibility judgment.

The default fixture additionally replays the local inventory calculation (3 × 7 = 21). This is a deterministic protocol simulation, separate from the existing real GLM workflow; it does not prove model recovery.

## Use the installed SDK serializer

```bash
python -m patchcourt boundary-run --sdk-root .sdk-nvidia --output outputs/installed-boundary
```

`--sdk-root` must point to a **trusted, already installed** dependency target containing NVIDIA SDK 1.4.3 and its dependencies. Installation instructions and the resolved dependency list are in `evidence/full-sdk/README.md` and `evidence/full-sdk/requirements-resolved.txt`. The command itself never installs dependencies. Without this flag it uses the pinned historical source with inert message classes.

The installed backend checks the exact reviewed `_utils.py` SHA-256 and distribution version, then executes that serializer module with real LangChain message classes. It does not import/run the complete provider client or call NVIDIA inference. The source target is not modified; the reviewed patch is applied only in child-process memory. Original/executed source hashes and installed dependency versions are recorded per worker. Missing dependencies or changed source produce INCONCLUSIVE, not a fallback to stubs.

## Supply your own bounded messages

For already captured traces, `python -m patchcourt check baseline.json candidate.json --input original.json --output outputs/trace-check` checks both traces against their shared original message input. It uses the same three-contract display and reports NEEDS_REVIEW when the baseline is unhealthy. It does not establish where the supplied traces came from. Without `--input`, `check` retains its original comparison-only behavior. Invalid or unsupported original input causes abstention; JSON null does not silently disable the check.

`--input messages.json` accepts a JSON array of 1–100 messages, at most 128 KB. Supported fields are explicit `role`, text/null `content`, optional text `name`, assistant OpenAI `tool_calls` with JSON-object argument strings, and tool `tool_call_id`. Tool IDs, nesting, Unicode and boolean/number distinctions are checked. Unknown roles, metadata, multimodal blocks, ambiguous JSON and invalid tool relationships abstain before execution. Inputs requiring known-secret redaction also abstain, so redaction cannot create a false semantic regression. Do not use real credentials as test payloads.

## Evidence and boundaries

- Each side runs under `python -I -S`, with a new temporary home, an environment allowlist, a 45-second deadline and a monitored 2 MB combined output budget. Workers do not inherit API keys, Python import settings or tracing configuration.
- A Python audit hook rejects socket and subprocess operations. This is **not an OS security sandbox**, a filesystem boundary or protection against hostile dependencies/native code. Only trusted installed dependencies and the fixed reviewed serializer code belong here.
- `report.json` contains worker outcomes, errors, captured boundaries, source provenance, dependency versions and contract findings. Its manifest covers the entire JSON report. Checksums do not authenticate the producer.
- The dashboard exposes all three checks, original input, worker evidence and task replay. Markdown and JSON exports work without a web account.

## Recorded verification

`evidence/boundary-run/matrix.json` records eight executed scenarios: five pinned-source cases and three installed-SDK cases, all matching expected outcomes. Concrete fixture assertions independently check the two calls and results. Run a fresh matrix with:

```bash
python scripts/verify_boundary_run.py --output outputs/new-boundary-matrix --sdk-root .sdk-nvidia
```

Omit `--sdk-root` for the five dependency-free scenarios. `scripts/qa_boundary_viewer.cjs` checks the exported viewer using local Chrome; `evidence/boundary-run/browser/qa-results.json` records ten passing browser checks. The full local suite recorded **181 passed, 4 Windows permission skips** in `evidence/tests/pytest-boundary-032.txt`. This is local verification, not remote CI for 0.3.2.
