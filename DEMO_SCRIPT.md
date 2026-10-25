# Actual live demonstration — 95 seconds

The completed local cut is `release/patchcourt-glm-live-demo.mp4`. It shows a real fresh GLM run initiated through the loopback workbench: historical call loss, model-proposed mapping, eight independent checks, rejected ID corruption and the real fixture-tool task recovering 21. It has local Microsoft Zira English narration, burned-in English captions, and separate English/Chinese SRT files.

| Time | Actual screen action |
|---|---|
| 0–8 s | Introduce the missing tool-call failure |
| 8–27 s | Click Run; actual model proposal, verification and task execution |
| 27–43 s | Inspect the returned mapping and all eight independent controls |
| 43–60 s | Inspect actual tool execution and recovered value |
| 60–80 s | Open evidence with exact model, token count, request count and honest scope |
| 80–95 s | Return to before/after result and close |

Reproduction assets: scripts/live_video_narration.json, scripts/render_live_voice.ps1, scripts/record_live_demo.cjs and scripts/encode_live_demo.py. The encoder uses the locally installed ffmpeg runtime, verifies every captured frame hash, adds narration/captions and decodes the whole result. Capture actions/times/report and six inspected frames are in evidence/live-video. Capture uses actual headless Chrome screenshots at 8 fps; encoding is 30 fps. Eight seconds of idle intro were removed; live execution was preserved. The video is a genuine automated browser recording with editorial pauses, not a recording of a human operator.

The older 112-second silent offline video is retained as an archived 0.3.0 artifact. Neither cut claims NVIDIA inference. No public YouTube upload has occurred; the local GLM cut alone does not establish competition eligibility. Update competition footage only after authorized required-platform execution exists.
