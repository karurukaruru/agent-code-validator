# Recorded workflow video

These tools turn existing, verified HTTP and SDK evidence into an explicitly
labelled replay. They make no inference or search request and do not upload or
publish a video. Playback timing is editorial. A replay is not a fresh cloud run.

Use a fresh output directory. For a development sample:

```powershell
python scripts/prepare_submission_video.py --report evidence/development-050/deepseek-live-01/report.json --sdk-report evidence/upgrade-run/real-sdk/upgrade --output outputs/video/new-cut
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/render_submission_voice.ps1 -Output outputs/video/new-cut
node scripts/record_submission_video.cjs --output outputs/video/new-cut --smoke
node scripts/record_submission_video.cjs --output outputs/video/new-cut
python scripts/encode_submission_video.py --output outputs/video/new-cut
```

The optional `--sdk-report` copies only the verified installed-release report,
its manifest and the source viewer. It adds a fifteen-second scene showing why
two equal broken SDK outputs cannot earn a compatibility PASS. The SDK
comparison contains no model inference.

The optional `--smoke` captures one screenshot per scene, checks the controls and
network requests, and writes `smoke.json`. It is not an encodable video capture.
The following full recording creates a separate `frames/` and `capture.json`.
Neither mode accepts an HTTP POST route. Chrome blocks HTTPS and the server
exposes only explicit local GET paths. The SDK iframe can fetch its same-origin
report; the repair replay cannot connect to an inference service.

For a competition cut, replace `--report` with an actual successful Nebius/NVIDIA
workflow and add `--competition`. The same runtime checker used for submission
must pass first; this option cannot relabel a DeepSeek or GLM recording. The
recording preflight reads actual local speech durations and refuses a cut longer
than 165 seconds.

Required local software: installed Chrome or Edge, Node 22+, Windows
System.Speech with Microsoft Zira Desktop, and ffmpeg. The ignored
`.video-deps/imageio_ffmpeg/binaries/` location is supported, or supply the
recorder/encoder's `--ffmpeg` argument. No external speech service is used.

The encoder verifies frame hashes, binds narration and subtitle hashes, checks
the actual encoded duration and fully decodes the result. It leaves
`visual_review` at `PENDING`. Inspect the extracted scene frames, captions,
English narration text and output before recording a real review. Preserve the
source files and earlier cuts. A separate YouTube publication and the entrant's
authenticated Devpost review are still required for the competition.
