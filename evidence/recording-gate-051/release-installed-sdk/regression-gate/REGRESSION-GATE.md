# Captured boundary regression gate

Run `python -m unittest discover -s . -p test_boundary_contract.py` from this folder. Only Python's standard library is required; the frozen PatchCourt checker source and license are bundled.

The default candidate is the actual observed output. A broken observation intentionally produces a failing test. Set `PATCHCOURT_CANDIDATE_TRACE` to a future message-array JSON file, or `PATCHCOURT_CANDIDATE_RECORDING` to a new BoundaryRecorder recording. Multi-transaction recordings also require `PATCHCOURT_REQUEST_ID`. A new recording must use the same adapter and preserve the frozen input; its SDK version and transaction ID may differ.

Capture the new SDK output before running the gate. This test does not execute or authenticate a future SDK or application. No model, network, generated model code or provider credentials are used. Review captured data before publishing it. Hashes detect accidental changes; they do not authenticate an untrusted producer.
