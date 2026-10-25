# Controlled SDK upgrade execution

PatchCourt 0.4.0 connects read-only repository discovery to **two real installed
NVIDIA SDK releases**. Both serializers run unmodified in separate processes,
with real LangChain message classes. Every output is checked against the input,
as well as against the other output. No model or provider request is made.

## Run

Install PatchCourt with Python 3.12 and pip, then run:

```bash
python -m pip install -e .
python -m patchcourt upgrade-run ./my-agent --from-version 1.4.3 --to-version 1.5.0 --environment-dir outputs/sdk-environments --prepare --output outputs/my-upgrade
python -m patchcourt verify outputs/my-upgrade
python -m patchcourt serve outputs/my-upgrade --port 8765
```

`--prepare` explicitly permits wheel-only installation from official PyPI into
new, dedicated targets. It never installs into the application or project venv.
Without it, the command only verifies and reuses existing environments. For
offline preparation, add `--wheelhouse /path/to/trusted/wheels`. Both modes use
the packaged shared constraints and record pip download URLs/archive hashes.
Installation failures are retained and produce INCONCLUSIVE evidence. A partial
or changed installation must be replaced with a fresh target directory.

The repository is inspected with ACV's bounded tools. Its application code is
never imported or run. Supply `--input messages.json` for a supported text/tool
conversation; otherwise the command uses the two-tool inventory fixture.
Each report output directory must be new. It contains JSON, Markdown, a manifest
and the evidence viewer.

## Interpret the verdict

| Result | Meaning | Exit |
|---|---|---|
| PASS | Both releases preserve this supported input | 0 |
| FAIL | A healthy baseline preserves the input and the candidate breaks it | 1 |
| NEEDS_REVIEW | The baseline is already broken, including equal broken outputs | 2 |
| INCONCLUSIVE | Unsupported input, unavailable/changed environment or failed execution | 2 |

Actual local execution found **both 1.4.3 and 1.5.0 drop normalized tool calls**
for the default fixture. The result is NEEDS_REVIEW, not proof of a newly
introduced regression. This is a scoped observation of the known
[upstream issue #387](https://github.com/langchain-ai/langchain-nvidia/issues/387).
Text controls pass. A reviewed fixed patch, executed separately with the
installed 1.4.3 classes, restores the deterministic task's value **21**.

The four-scenario reproducibility check is:

```bash
python scripts/verify_sdk_upgrade.py --environment-dir outputs/sdk-environments --prepare --output outputs/sdk-matrix
```

It preserves the upgrade, healthy text, regression and recovery reports and
checks their manifests, actual SDK workers and task outcome. A test matrix PASS
means its expected outcomes occurred; individual compatibility FAIL and
NEEDS_REVIEW statuses remain visible. The CI workflow includes this check on
Windows and Ubuntu. Local execution is separate from a remote CI result.

## Identity and limits

Only reviewed releases **1.4.3 and 1.5.0** are executable. Serializer SHA-256,
distribution version, current shared pins, complete dependency-file inventory,
pip report, constraints and Python identity are validated before execution.
Other dependencies must match across both sides. Unknown or altered releases
abstain rather than executing arbitrary installed source.

Workers have an environment allowlist, isolated Python startup, a fresh home,
execution/output limits and network/subprocess audit restrictions. `.pth`
startup is disabled. These controls are **not an OS sandbox**; installed wheels
and the local owner are trusted. Inventories are change detection, not signatures.

Supported inputs are text, null content and complete OpenAI-style function calls
with JSON object arguments. Unknown metadata/content and inputs that need
redaction abstain. No general dependency solver for arbitrary projects, complete
framework hook, arbitrary model-patch execution, live agent replay or vision
inference is claimed.
