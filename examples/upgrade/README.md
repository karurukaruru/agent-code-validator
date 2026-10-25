# Minimal trace comparison

These are synthetic example traces, not recorded API calls. The candidate omits the assistant tool call while preserving its result.

```bash
python -m patchcourt check examples/upgrade/baseline.json examples/upgrade/candidate.json --output outputs/example-failure
```

Expected: FAIL and exit code 1, with missing call and orphan-result evidence. Negative control:

```bash
python -m patchcourt check examples/upgrade/baseline.json examples/upgrade/baseline.json --output outputs/example-control
```

Expected: PASS and exit code 0. Capture your actual baseline/candidate adapter outputs as the same JSON array format. The comparator validates semantics; it cannot authenticate the provenance of supplied traces.
