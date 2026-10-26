"""Encode hash-checked replay captures with local voice and English captions.

No network or paid service. Visual review remains PENDING until a reviewer has
actually inspected the extracted representative frames and final video.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stamp(seconds, *, ass=False):
    ms = round(seconds * 1000)
    return (f"{ms // 3600000}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02}.{ms // 10 % 100:02}" if ass
            else f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}")


def encode(output, ffmpeg=None):
    output = Path(output).resolve()
    ffmpeg = Path(ffmpeg).resolve() if ffmpeg else next((ROOT / ".video-deps/imageio_ffmpeg/binaries").glob("ffmpeg*.exe"))
    capture = json.loads((output / "capture.json").read_text(encoding="utf-8"))
    if capture.get("status") != "CAPTURED" or capture.get("capture_mode") != "recorded-replay" or capture.get("new_model_requests") != 0 or capture.get("new_search_requests") != 0:
        raise ValueError("Expected a verified offline recorded-replay capture")
    duration = capture["duration_seconds"]
    if not 0 < duration <= 165 or len(capture["captures"]) != round(duration * capture["capture_fps"]):
        raise ValueError("Invalid frame duration or a cut longer than 165 seconds")
    audio_sources = {}
    for scene in capture["scenes"]:
        if not isinstance(scene.get("scene"), str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", scene["scene"]):
            raise ValueError("Narration scene name is unsafe")
        wave = output / (scene["scene"] + ".wav")
        if not wave.is_file() or wave.is_symlink():
            raise ValueError("Narration must be a regular local WAV file")
        audio_sources[wave.name] = sha(wave)
        if scene.get("voice_sha256") not in (None, audio_sources[wave.name]):
            raise ValueError("Narration differs from the captured source hash")
    for frame in capture["captures"]:
        if Path(frame["name"]).name != frame["name"] or sha(output / "frames" / frame["name"]) != frame["sha256"]:
            raise ValueError("Capture file was changed or has an unsafe filename")
    movie = output / "patchcourt-development-replay.mp4"
    if capture["competition_runtime_source_verified"]:
        movie = output / "patchcourt-nebius-recorded-workflow.mp4"
    if movie.exists():
        raise ValueError("Preserve the existing video; use a fresh output folder")
    captions = []
    ass = ["[Script Info]\nScriptType: v4.00+\nPlayResX: 1600\nPlayResY: 900\nWrapStyle: 0\n", "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Arial,28,&H00FFFFFF,&H00FFFFFF,&H0010221B,&H0010221B,0,0,0,0,100,100,0,0,1,0,0,2,70,70,16,1\n", "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"]
    number = 0
    for scene in capture["scenes"]:
        chunks = textwrap.wrap(scene["text"], width=150, break_long_words=False, break_on_hyphens=False)
        words = len(scene["text"].split())
        current = scene["start"]
        for chunk in chunks:
            end = current + scene["voice_seconds"] * len(chunk.split()) / words
            number += 1
            wrapped = "\n".join(textwrap.wrap(chunk, width=95))
            captions.append(f"{number}\n{stamp(current)} --> {stamp(end)}\n{wrapped}\n")
            ass_text = wrapped.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")
            ass.append(f"Dialogue: 0,{stamp(current, ass=True)},{stamp(end, ass=True)},Default,,0,0,0,,{ass_text}\n")
            current = end
    (output / "patchcourt-replay.en.srt").write_text("\n".join(captions), encoding="utf-8")
    (output / "captions.ass").write_text("".join(ass), encoding="utf-8")
    command = [str(ffmpeg), "-hide_banner", "-n", "-framerate", str(capture["capture_fps"]), "-i", "frames/frame-%06d.jpg"]
    for scene in capture["scenes"]:
        command += ["-i", scene["scene"] + ".wav"]
    filters = [f'[{i}:a]adelay={round(scene["start"] * 1000)}:all=1[a{i}]' for i, scene in enumerate(capture["scenes"], 1)]
    filters.append("".join(f"[a{i}]" for i in range(1, len(capture["scenes"]) + 1)) + f'amix=inputs={len(capture["scenes"])}:normalize=0[audio]')
    filters.append("[0:v]pad=1600:900:0:0:color=0x10221b,ass=captions.ass,fps=30[video]")
    command += ["-filter_complex", ";".join(filters), "-map", "[video]", "-map", "[audio]", "-t", str(duration), "-c:v", "libx264", "-preset", "fast", "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", movie.name]
    encoded = subprocess.run(command, cwd=output, capture_output=True, text=True, check=True)
    (output / "encode.log").write_text(encoded.stderr, encoding="utf-8")
    decoded = subprocess.run([str(ffmpeg), "-hide_banner", "-i", str(movie), "-f", "null", "-"], capture_output=True, text=True, check=True)
    (output / "decode.log").write_text(decoded.stderr, encoding="utf-8")
    if "1600x900" not in decoded.stderr or "Audio:" not in decoded.stderr:
        raise ValueError("The decoded video lacks the expected picture or narration track")
    actual = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", decoded.stderr)
    if not actual:
        raise ValueError("The encoded video duration could not be verified")
    actual_duration = int(actual[1]) * 3600 + int(actual[2]) * 60 + float(actual[3])
    if abs(actual_duration - duration) > 0.1:
        raise ValueError("Encoded duration differs from the reviewed capture timeline")
    inspected = output / "review-frames"
    inspected.mkdir()
    for scene in capture["scenes"]:
        subprocess.run([str(ffmpeg), "-hide_banner", "-loglevel", "error", "-n", "-ss", str(scene["start"] + min(3, scene["seconds"] / 2)), "-i", str(movie), "-frames:v", "1", str(inspected / (scene["scene"] + ".png"))], capture_output=True, check=True)
    result = {"status": "ENCODED_AND_DECODED", "visual_review": "PENDING", "capture_mode": "recorded-replay",
              "provider": capture["provider"], "model": capture["model"], "source_live_inference": True,
              "live_inference": False, "new_model_requests": 0, "new_search_requests": 0,
              "competition_runtime_source_verified": capture["competition_runtime_source_verified"],
              "sdk_report_included": capture.get("sdk_report_included", False),
              "source_sdk_report_sha256": capture.get("source_sdk_report_sha256"),
              "duration_seconds": actual_duration, "bytes": movie.stat().st_size, "sha256": sha(movie),
              "source_capture_manifest_sha256": sha(output / "capture.json"), "source_report_sha256": capture["source_report_sha256"],
              "audio": "Local Microsoft Zira synthesized English narration", "audio_source_sha256": audio_sources,
              "captions": "English burned-in captions and separate SRT; approximate proportional word timing",
              "caption_sha256": sha(output / "patchcourt-replay.en.srt"),
              "video_file": movie.name, "scope": capture["scope"]}
    (output / "video-manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path)
    args = parser.parse_args()
    print(json.dumps(encode(args.output, args.ffmpeg), indent=2))


if __name__ == "__main__":
    main()
