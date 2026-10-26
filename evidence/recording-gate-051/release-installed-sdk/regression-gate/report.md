# PatchCourt compatibility evidence

Run: 2ca9dc34-fc70-4a78-8578-5966a8fc35ad
Recorded: 2026-10-26T04:05:30.784153+00:00
Mode: recording-check

| Case | Verdict | Evidence |
|---|---|---|
| captured-boundary | FAIL | {'kind': 'User-supplied opt-in BoundaryRecorder transaction; no SDK is executed by this check', 'adapter': 'langchain-nvidia-ai-endpoints/convert_message_to_dict', 'version': '1.4.3', 'request_id': 'sdk-contract-1', 'recording_sha256': '91b9266cf626e05e2d5984269a03beb44ba7fc3080fd536be4501e8443f19942', 'timestamps': {'input': '2026-10-26T04:05:30.428661+00:00', 'output': '2026-10-26T04:05:30.430669+00:00'}, 'event_indexes': [0, 1]} |

## Limitations

- Checks a selected captured message pair without executing an SDK or application.
- A saved recording and its checksums do not independently authenticate its producer.
- A future regression gate requires a freshly captured candidate trace or recording.
