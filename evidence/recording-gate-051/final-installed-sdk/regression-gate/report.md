# PatchCourt compatibility evidence

Run: bad5a322-8690-408a-85a4-59591720a5b1
Recorded: 2026-10-26T03:52:35.769239+00:00
Mode: recording-check

| Case | Verdict | Evidence |
|---|---|---|
| captured-boundary | FAIL | {'kind': 'User-supplied opt-in BoundaryRecorder transaction; no SDK is executed by this check', 'adapter': 'langchain-nvidia-ai-endpoints/convert_message_to_dict', 'version': '1.4.3', 'request_id': 'sdk-contract-1', 'recording_sha256': 'e7bbbe03820960f9655db4e4eecc5a416b08a2e5371f08ba51f176cb73f49390', 'timestamps': {'input': '2026-10-26T03:52:35.390355+00:00', 'output': '2026-10-26T03:52:35.390355+00:00'}, 'event_indexes': [0, 1]} |

## Limitations

- Checks a selected captured message pair without executing an SDK or application.
- A saved recording and its checksums do not independently authenticate its producer.
- A future regression gate requires a freshly captured candidate trace or recording.
