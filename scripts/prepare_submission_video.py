"""Prepare an explicitly labelled browser replay and local narration from real evidence.

No provider request is made. A fresh output directory preserves earlier cuts.
Use --competition only after a real NVIDIA/Nebius workflow passes the local gate.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from patchcourt.evidence import digest, read_json
from scripts.package_judge_demo import verified_report, verify_sdk_report


def prepare(report_path, output, *, competition=False, sdk_report=None):
    spec = importlib.util.spec_from_file_location("submission_check", ROOT / "scripts/submission_check.py")
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    report_path = Path(report_path).resolve()
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a fresh output directory to preserve earlier recordings")
    if competition and not report_path.is_relative_to(ROOT):
        raise ValueError("Competition source evidence must be inside this checkout")
    report, _ = checker.verify_workflow(report_path.parent, report_path.name, competition=competition)
    manifest = read_json(report_path.parent / "manifest.json")
    sdk_path, sdk = None, None
    if sdk_report is not None:
        sdk_path = Path(sdk_report).resolve()
        sdk_path = sdk_path / "report.json" if sdk_path.is_dir() else sdk_path
        if sdk_path.name != "report.json":
            raise ValueError("SDK evidence must identify report.json or its directory")
        sdk = verified_report(sdk_path.parent)
        verify_sdk_report(sdk)
    provider, model = report["provider"], report["model"]
    spoken = {"deepseek": "DeepSeek Flash", "glm": "GLM five point three Flash", "nebius": "NVIDIA Nemotron"}.get(provider, provider)
    runtime = spoken + (" on Nebius Token Factory" if provider == "nebius" else " through its development API")
    if provider == "nebius":
        exact_model = re.sub(r"[-_/]+", " ", model.removeprefix("nvidia/"))
        runtime = exact_model + " on Nebius Token Factory"
    context = {"provider_spoken": spoken, "runtime_spoken": runtime,
               "request_count": len(report["requests"]), "tokens": report.get("total_reported_tokens") if report.get("total_reported_tokens") is not None else "unknown",
               "search_statement": "Tavily retrieved official documentation for this repair proposal." if report.get("retrieval", {}).get("status") == "PASS" else "No search benefit is claimed for this run.",
               "platform_scope": "The source records actual NVIDIA model inference on Nebius Token Factory. This playback is not a fresh cloud run." if competition else "This development provider does not satisfy the competition's separate NVIDIA and Nebius runtime requirement."}
    scenes = read_json(ROOT / "scripts/submission_video_narration.json")
    for scene in scenes:
        scene["text"] = scene["text"].format(**context)
        if competition:
            scene["text"] = scene["text"].replace(" development run", " competition workflow")
    if sdk is not None:
        scenes.insert(-1, {"scene": "sdk", "action": "sdk", "text": "SDK releases one point four point three and one point five point zero ran in separate local environments. Both dropped tool calls. Equal output did not earn a pass: the baseline already violated the input contract."})
    html = (ROOT / "patchcourt/web/live.html").read_text(encoding="utf-8")
    data = json.dumps(report, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    html = html.replace("<script>", '<script id="recorded-data" type="application/json">' + data + "</script><script>", 1)
    label = "NVIDIA / NEBIUS RECORDED WORKFLOW" if competition else "DEVELOPMENT SAMPLE / " + provider.upper()
    banner = '<div id="recording-disclosure" style="position:sticky;top:0;z-index:100;background:#153e33;color:#fff;padding:9px 5%;font:600 13px Arial;letter-spacing:.4px">' + label + ' &nbsp;·&nbsp; RECORDED REPLAY &nbsp;·&nbsp; No new inference during playback</div>'
    html = html.replace("<body>", "<body>" + banner, 1)
    html = html.replace("Ask the selected model to propose a repair, challenge it with independent checks, then run the real tool conversation.", "Replay the actual saved repair, independent checks, and real source conversation. Playback makes no new API requests.")
    output.mkdir(parents=True, exist_ok=True)
    website = output / "website"
    website.mkdir()
    (website / "index.html").write_text(html, encoding="utf-8")
    (website / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if sdk is not None:
        (website / "sdk").mkdir()
        shutil.copyfile(ROOT / "patchcourt/web/index.html", website / "sdk/index.html")
        shutil.copyfile(sdk_path, website / "sdk/report.json")
        shutil.copyfile(sdk_path.parent / "manifest.json", website / "sdk/manifest.json")
    (output / "narration.json").write_text(json.dumps(scenes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    metadata = {"kind": "prepared recorded-replay video", "capture_mode": "recorded-replay",
                "provider": provider, "model": model, "source_report": str(report_path.relative_to(ROOT)) if report_path.is_relative_to(ROOT) else str(report_path),
                "source_report_sha256": digest(report), "source_manifest_sha256": digest(manifest),
                "source_created_at": report["created_at"], "source_live_inference": True,
                "sdk_report_included": sdk is not None,
                "source_sdk_report": str(sdk_path.relative_to(ROOT)) if sdk_path is not None and sdk_path.is_relative_to(ROOT) else str(sdk_path) if sdk_path else None,
                "source_sdk_report_sha256": digest(sdk) if sdk is not None else None,
                "sdk_scope": "Recorded unmodified installed SDK releases 1.4.3 and 1.5.0; no model inference in the SDK comparison" if sdk is not None else None,
                "new_inference_during_recording": False, "competition_runtime_source_verified": competition,
                "scope": "A browser recording of an explicitly labelled saved-run replay; not fresh model inference. Playback timing is editorial. No publication or upload."}
    (output / "preparation.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--competition", action="store_true")
    parser.add_argument("--sdk-report", type=Path, help="Optional real installed SDK upgrade report.json or its directory")
    args = parser.parse_args()
    print(json.dumps(prepare(args.report, args.output, competition=args.competition, sdk_report=args.sdk_report), indent=2))


if __name__ == "__main__":
    main()
