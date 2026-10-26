# PatchCourt compatibility evidence

Run: 3fccd9d0-d23a-4af1-818c-5e965a9dab67
Recorded: 2026-10-26T03:20:29.368852+00:00
Mode: recording-check

| Case | Verdict | Evidence |
|---|---|---|
| captured-boundary | FAIL | {'kind': 'User-supplied opt-in BoundaryRecorder transaction; no SDK is executed by this check', 'adapter': 'langchain-nvidia-ai-endpoints/convert_message_to_dict', 'version': '1.4.3', 'request_id': 'sdk-contract-1', 'recording_sha256': '8e87320669233a73f1354c371294cdc7e2130da3e7cffc803db51b66bab7f4bb', 'timestamps': {'input': '2026-10-26T03:20:28.926230+00:00', 'output': '2026-10-26T03:20:28.926230+00:00'}, 'event_indexes': [0, 1]} |

## Limitations

- Checks a selected captured message pair without executing an SDK or application.
- A saved recording and its checksums do not independently authenticate its producer.
- A future regression gate requires a freshly captured candidate trace or recording.
