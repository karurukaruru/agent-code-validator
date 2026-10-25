"""Encode recorded browser frames with full English subtitles; no synthetic UI."""
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIDEO = ROOT / "dist" / "video"
EVIDENCE = ROOT / "evidence" / "video"
FFMPEG = ROOT / ".video-deps" / "imageio_ffmpeg" / "binaries" / "ffmpeg-win-x86_64-v7.1.exe"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ass_time(seconds):
    return f"{seconds//3600}:{seconds//60%60:02d}:{seconds%60:02d}.00"


def main():
    manifest = json.loads((EVIDENCE / "capture-manifest.json").read_text(encoding="utf-8"))
    duration = manifest["encoded_duration_seconds"]
    if manifest["status"] != "CAPTURED" or duration >= 180:
        raise ValueError("Expected complete sub-three-minute capture")
    for frame in manifest["captures"]:
        if digest(VIDEO / "frames" / frame["file"]) != frame["sha256"]:
            raise ValueError("Capture integrity failure")
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1600
PlayResY: 900
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Arial,27,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,2,45,45,20,1
Style: Label,Arial,17,&H00B7DBC4,&H00B7DBC4,&H00000000,&H00000000,0,0,0,0,100,100,1,0,1,0,0,2,20,20,91,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [f"Dialogue: 1,0:00:00.00,{ass_time(duration)},Label,,0,0,0,,OFFLINE DEMO  |  REAL LOCAL EVIDENCE  |  NO LIVE INFERENCE"]
    for segment in manifest["segments"]:
        text = segment["text"].replace("\n", "\\N")
        lines.append(f"Dialogue: 0,{ass_time(segment['start'])},{ass_time(segment['start']+segment['seconds'])},Caption,,0,0,0,,{text}")
    (VIDEO / "captions.ass").write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    movie = VIDEO / "patchcourt-offline-demo.mp4"
    command = [str(FFMPEG), "-hide_banner", "-y", "-framerate", "2", "-i", "frames/frame-%05d.png",
               "-vf", "pad=1600:900:0:0:color=0x102128,ass=captions.ass,fps=30",
               "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
               "-t", str(duration), "-movflags", "+faststart", "-an", movie.name]
    completed = subprocess.run(command, cwd=VIDEO, capture_output=True, text=True, check=True)
    (EVIDENCE / "encode-log.txt").write_text(completed.stderr, encoding="utf-8")
    probe = subprocess.run([str(FFMPEG), "-hide_banner", "-i", str(movie), "-f", "null", "-"], capture_output=True, text=True, check=True)
    (EVIDENCE / "decode-check.txt").write_text(probe.stderr, encoding="utf-8")
    match = re.search(r"Duration: (\d\d):(\d\d):(\d\d\.\d+)", probe.stderr)
    observed = sum(float(v) * factor for v, factor in zip(match.groups(), (3600, 60, 1))) if match else None
    if observed != duration or "1600x900" not in probe.stderr:
        raise ValueError("Encoded duration or resolution did not match")
    for second, name in ((5, "opening"), (46, "task-replay"), (88, "blocked-lab"), (108, "closing")):
        subprocess.run([str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", "-ss", str(second), "-i", str(movie), "-frames:v", "1", str(EVIDENCE / (name + ".png"))], check=True)
    assets = [movie, VIDEO / "patchcourt-offline-demo.en.srt", VIDEO / "transcript.md", VIDEO / "captions.ass"]
    result = {"status": "VERIFIED", "duration_seconds": observed, "width": 1600, "height": 900,
              "full_decode_check": "PASS", "audio": "none; full English subtitles burned in and supplied as SRT",
              "capture_fps": 2, "output_fps": 30, "offline": True, "live_inference": False,
              "source_report_sha256": manifest["report_sha256"], "source_report_run_id": manifest["report_run_id"],
              "encoder": {"package": "imageio-ffmpeg", "version": "0.6.0", "origin": "https://pypi.org/project/imageio-ffmpeg/0.6.0/", "binary_sha256": digest(FFMPEG)},
              "assets": [{"path": str(p.relative_to(ROOT)).replace("\\", "/"), "bytes": p.stat().st_size, "sha256": digest(p)} for p in assets]}
    (EVIDENCE / "video-manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
