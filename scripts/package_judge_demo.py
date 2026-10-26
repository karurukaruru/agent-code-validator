"""Build a free static judge demo from verified, recorded execution evidence.

The replay is explicitly labeled; the package has no credential or inference
endpoint. Its source report and every included request keep their integrity keys.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import sys
import zipfile
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from patchcourt import __version__
from patchcourt.evidence import digest
from scripts.submission_check import public_evidence, read_json, verify_workflow

LAUNCHER = '''"""Serve this exported judge demo locally. No installation or API access."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import webbrowser

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    directory = Path(__file__).resolve().parent
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    url = "http://127.0.0.1:" + str(server.server_port) + "/"
    print(url, flush=True)
    print("Recorded evidence only. No API key required. Press Ctrl+C to stop.", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == "__main__":
    main()
'''

WINDOWS_LAUNCHER = '''@echo off
setlocal
where py >nul 2>nul
if not errorlevel 1 (
    py -3 "%~dp0launch_demo.py"
    goto :finished
)
where python >nul 2>nul
if not errorlevel 1 (
    python "%~dp0launch_demo.py"
    goto :finished
)
echo Python 3 is required. Install Python, then double-click this file again.
:finished
if errorlevel 1 pause
endlocal
'''

def verified_report(folder):
    report, manifest = read_json(folder / "report.json"), read_json(folder / "manifest.json")
    if (not isinstance(report, dict) or not isinstance(manifest, dict)
            or not report.get("run_id") or report["run_id"] != manifest.get("run_id")
            or digest(report) != manifest.get("report_sha256")):
        raise ValueError("Source report integrity does not match its manifest")
    public_evidence(report)
    public_evidence(manifest)
    return report


def verify_sdk_report(report):
    """The portal's fixed narrative requires this exact recorded comparison."""
    from patchcourt.boundary_run import SDK_RELEASES
    from patchcourt.semantic import compare_messages
    if (report.get("mode") != "upgrade-run" or report.get("status") != "NEEDS_REVIEW"
            or not isinstance(report.get("cases"), list) or len(report["cases"]) != 1
            or report.get("provider_requests") != 0):
        raise ValueError("SDK inspector requires the recorded unhealthy-baseline installed-release comparison")
    case = report["cases"][0]
    provenance = case.get("provenance", {})
    if (case.get("execution") is not True or case.get("status") != "NEEDS_REVIEW"
            or provenance.get("dependency") != "langchain-nvidia-ai-endpoints"
            or provenance.get("baseline_version") != "1.4.3" or provenance.get("candidate_version") != "1.5.0"):
        raise ValueError("SDK narrative requires unmodified NVIDIA releases 1.4.3 and 1.5.0")
    executions, environments = report.get("executions", {}), report.get("environments", {})
    if set(executions) != {"baseline", "candidate"} or set(environments) != {"baseline", "candidate"}:
        raise ValueError("Both installed SDK executions and environments are required")
    for side, version in (("baseline", "1.4.3"), ("candidate", "1.5.0")):
        run, env = executions[side], environments[side]
        identity = run.get("provenance", {})
        if (run.get("status") != "EXECUTED" or run.get("input_conversion", {}).get("status") != "PASS"
                or run.get("output") != case.get(side) or run.get("provider_requests") != 0
                or identity.get("backend") != "installed-sdk" or identity.get("real_sdk_classes") is not True
                or identity.get("version") != version or identity.get("source_sha256") != SDK_RELEASES[version]
                or identity.get("executed_source_sha256") != SDK_RELEASES[version]
                or env.get("status") != "READY" or env.get("version") != version):
            raise ValueError("SDK report does not bind the claimed installed releases to their executed source and output")
    original, baseline, candidate = report.get("input"), case.get("baseline"), case.get("candidate")
    contracts = {"baseline": compare_messages(original, baseline), "candidate": compare_messages(original, candidate),
                 "difference": compare_messages(baseline, candidate)}
    if (contracts != case.get("contracts") or contracts["baseline"]["status"] != "FAIL"
            or contracts["candidate"]["status"] != "FAIL" or baseline != candidate
            or not any(row.get("code") == "UNHEALTHY_BASELINE" for row in case.get("findings", []))):
        raise ValueError("SDK headline is not supported by freshly checked equal, broken outputs")


def verify_wheel(path):
    path = Path(path)
    if path.is_symlink() or path.name != f"agent_code_validator-{__version__}-py3-none-any.whl" or not path.is_file():
        raise ValueError("Download must be the current regular Python wheel")
    with zipfile.ZipFile(path) as archive:
        if len(archive.infolist()) > 2000 or sum(row.file_size for row in archive.infolist()) > 50_000_000:
            raise ValueError("Wheel exceeds archive size limits")
        for row in archive.infolist():
            if row.filename.startswith(("/", "\\")) or ".." in row.filename.replace("\\", "/").split("/"):
                raise ValueError("Wheel contains an unsafe archive path")
            text = archive.read(row).decode("utf-8", errors="ignore")
            public_evidence(text)
    return path


def package(live_folder, sdk_folder, output, *, wheel=None, source_url=None):
    live_folder, sdk_folder, output = Path(live_folder), Path(sdk_folder), Path(output)
    if output.exists() or output.with_suffix(".zip").exists():
        raise ValueError("Refusing to overwrite an existing judge package")
    if source_url:
        url = urlsplit(source_url)
        if (url.scheme != "https" or url.hostname not in {"github.com", "gitlab.com", "bitbucket.org"}
                or url.username or url.password or url.port not in (None, 443)):
            raise ValueError("Source link must be a public HTTPS code-host URL")
    live, records = verify_workflow(live_folder.resolve(), "report.json")
    sdk = verified_report(sdk_folder)
    verify_sdk_report(sdk)
    wheel = verify_wheel(wheel) if wheel else None
    evidence_files = ["report.json", "manifest.json"]
    evidence_files.extend(row["name"] + ".json" for row, _ in records)
    output.mkdir(parents=True, exist_ok=False)
    (output / "evidence" / "live").mkdir(parents=True)
    for name in evidence_files:
        shutil.copyfile(live_folder / name, output / "evidence" / "live" / name)
    for name in ("report.json", "manifest.json"):
        shutil.copyfile(sdk_folder / name, output / name)
    shutil.copyfile(ROOT / "patchcourt/web/index.html", output / "sdk-upgrade.html")
    replay = (ROOT / "patchcourt/web/live.html").read_text(encoding="utf-8")
    embedded = json.dumps(live, ensure_ascii=True, allow_nan=False).replace("<", "\\u003c")
    replay = replay.replace("<script>", '<script id="recorded-data" type="application/json">' + embedded + "</script>\n<script>", 1)
    (output / "repair.html").write_text(replay, encoding="utf-8")
    provider = html.escape(live["provider"])
    model = html.escape(live["model"])
    checks = live["verification"]["checks"]
    passed = sum(c["status"] == "PASS" for c in checks)
    answer = html.escape(str(live["task"]["answer"]["inventory_value"]))
    scope = ("Recorded NVIDIA model inference on Nebius Token Factory."
             if live["provider"] == "nebius" else "Development run. Nebius/NVIDIA competition runtime is not established by this recording.")
    source = '<a href="' + html.escape(source_url, quote=True) + '">Source code ↗</a>' if source_url else ""
    download = ""
    if wheel:
        wheel = Path(wheel)
        shutil.copyfile(wheel, output / wheel.name)
        download = '<a class="secondary" href="' + html.escape(wheel.name, quote=True) + '" download>Download Python build ↓</a>'
    page = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<meta name="description" content="Catch silent agent SDK regressions with independently checked repair evidence."><title>PatchCourt — inspect the repair</title>
<style>:root{--ink:#172923;--muted:#64736c;--paper:#f4f5ef;--line:#d9dfd4;--green:#087454}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.6 system-ui,Arial}main,header,footer{max-width:1180px;margin:auto;padding:22px 30px}header{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line);gap:20px}.brand{font-size:23px;font-weight:800;letter-spacing:-1px}.brand span{color:var(--green)}nav{display:flex;gap:24px;font-size:13px}a{color:inherit;text-decoration:none}a:hover{text-decoration:underline}a:focus-visible{outline:3px solid var(--green);outline-offset:5px}.hero{padding:60px 0 34px;max-width:930px}.eyebrow{font:11px monospace;letter-spacing:1.8px;color:var(--green);text-transform:uppercase}h1{font-size:clamp(39px,5.2vw,66px);letter-spacing:-2.5px;line-height:1.06;margin:20px 0 24px;font-weight:700}h1 span{color:var(--green)}p{color:var(--muted)}.hero p{max-width:760px;font-size:17px}.actions{display:flex;flex-wrap:wrap;gap:12px;margin:29px 0 0}.primary,.secondary{display:inline-block;padding:13px 21px;border-radius:7px;font-size:14px;font-weight:650}.primary{background:var(--ink);color:white}.secondary{border:1px solid var(--line);background:white}.proof{border:1px solid var(--line);border-radius:11px;background:white;margin:14px 0 35px;overflow:hidden}.proof-top{padding:19px 23px;background:#eef5ee;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;gap:18px;font:12px monospace}.stats{display:grid;grid-template-columns:repeat(4,1fr)}.stat{padding:24px;border-right:1px solid var(--line)}.stat:last-child{border:0}.stat b{display:block;font-size:34px;line-height:1.2;margin-bottom:10px;color:var(--green)}.stat span{font-size:12px;color:var(--muted)}.grid{display:grid;grid-template-columns:1fr 1fr;gap:24px}.card{padding:25px;border:1px solid var(--line);border-radius:10px;background:#fff}.card h2{font-size:21px;margin:9px 0}.card p{font-size:14px}.card a{font-size:13px;font-weight:650;color:var(--green)}.scope{border-top:1px solid var(--line);padding-top:22px;margin-top:35px;font-size:12px;max-width:1000px}footer{font-size:11px;color:var(--muted);display:flex;justify-content:space-between;gap:20px;padding-bottom:30px}code{font:12px monospace;overflow-wrap:anywhere}@media(max-width:700px){main,header,footer{padding-left:20px;padding-right:20px}header{align-items:flex-start}nav{gap:12px;flex-wrap:wrap;justify-content:end}.hero{padding-top:38px}h1{letter-spacing:-1.5px}.grid{grid-template-columns:1fr}.stats{grid-template-columns:1fr 1fr}.stat:nth-child(2){border-right:0}.stat:nth-child(-n+2){border-bottom:1px solid var(--line)}.proof-top,footer{flex-direction:column;gap:6px}}</style></head><body>
<header><div class="brand">Patch<span>Court</span></div><nav><a href="repair.html">Repair evidence</a><a href="sdk-upgrade.html">SDK inspector</a>SOURCE_LINK</nav></header>
<main><section class="hero"><div class="eyebrow">AI Agent Compatibility Guardian</div><h1>The tools ran.<br><span>The next request forgot them.</span></h1><p>An SDK can silently drop tool calls after they execute. PatchCourt exposes the missing semantics, challenges a model-proposed repair, and verifies that the task recovers.</p><div class="actions"><a class="primary" href="repair.html">Replay the verified repair →</a><a class="secondary" href="sdk-upgrade.html">Inspect a real SDK upgrade →</a>DOWNLOAD_LINK</div></section>
<section class="proof" aria-label="Recorded execution results"><div class="proof-top"><span>PROVIDER_LABEL / MODEL_LABEL</span><span>Recorded evidence · no API key needed to replay</span></div><div class="stats"><div class="stat"><b>CHECKS_LABEL</b><span>Independent repair checks passed</span></div><div class="stat"><b>Rejected</b><span>Deliberately corrupted repair</span></div><div class="stat"><b>ANSWER_LABEL</b><span>Verified inventory task value</span></div><div class="stat"><b>REQUESTS_LABEL</b><span>Model requests in the saved run</span></div></div></section>
<div class="grid"><article class="card"><div class="eyebrow">01 / Detection</div><h2>Equal broken outputs do not mean compatible.</h2><p>Unmodified NVIDIA SDK releases 1.4.3 and 1.5.0 run independently. Each output is checked against the original input, so an already broken baseline remains visible.</p><a href="sdk-upgrade.html">Open recorded version comparison →</a></article><article class="card"><div class="eyebrow">02 / Independent verification</div><h2>The model cannot approve its own repair.</h2><p>A bounded field mapping faces controls for nested data, multiple calls and legacy behavior. A damaged repair must fail before the actual tool conversation can earn a verified result.</p><a href="evidence/live/report.json">Read complete model and task evidence →</a></article></div>
<p class="scope">SCOPE_LABEL Playback uses saved real execution data and sends no new inference requests. The adapter harness uses reviewed historical source and inert message types; the inventory tools are controlled local fixtures. This is not a general code sandbox. Checksums detect changes and do not independently authenticate a producer. Historical known SDK defects are credited in the source. Submission eligibility and final form completion require the separate checklist.</p>
<p class="scope">Run the installed project: <code>python -m patchcourt demo --output outputs/demo</code><br>Serve this static package: <code>python -m http.server 8765 --bind 127.0.0.1</code></p></main>
<footer><span>PatchCourt · VERSION_LABEL · inspect the evidence</span><span>Saved run: RUN_LABEL</span></footer></body></html>"""
    replacements = {"SOURCE_LINK": source, "DOWNLOAD_LINK": download, "PROVIDER_LABEL": provider, "MODEL_LABEL": model,
                    "CHECKS_LABEL": f"{passed}/{len(checks)}", "ANSWER_LABEL": answer, "REQUESTS_LABEL": str(len(live["requests"])),
                    "SCOPE_LABEL": html.escape(scope), "VERSION_LABEL": __version__, "RUN_LABEL": html.escape(live["run_id"])}
    for key, value in replacements.items():
        page = page.replace(key, value)
    (output / "index.html").write_text(page, encoding="utf-8")
    shutil.copyfile(ROOT / "LICENSE", output / "LICENSE")
    (output / "launch_demo.py").write_text(LAUNCHER, encoding="utf-8")
    (output / "Start-Judge-Demo.cmd").write_text(WINDOWS_LAUNCHER, encoding="ascii")
    (output / "START-HERE.txt").write_text("PatchCourt judge demo\n\nWindows: double-click Start-Judge-Demo.cmd.\nAny platform with Python 3: run python launch_demo.py.\nThe launcher serves only this exported folder on 127.0.0.1 with an available local port and opens your browser. Nothing is installed. Press Ctrl+C to close the server.\n\nRecorded repair playback and the SDK inspector need no API key or inference access. The replay is recorded execution evidence, not a new model call.\n", encoding="utf-8")
    hashes = {p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in output.rglob("*") if p.is_file()}
    (output / "package-manifest.json").write_text(json.dumps({"version": __version__, "live_run_id": live["run_id"],
        "provider": live["provider"], "model": live["model"], "files": hashes,
        "replay_only": True, "new_provider_requests": 0}, indent=2) + "\n", encoding="utf-8")
    archive = output.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for path in output.rglob("*"):
            if path.is_file():
                zipped.write(path, path.relative_to(output).as_posix())
    return {"status": "PACKAGED", "directory": str(output.resolve()), "archive": str(archive.resolve()),
            "provider": live["provider"], "replay_only": True, "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-report", type=Path, required=True)
    parser.add_argument("--sdk-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--source-url")
    args = parser.parse_args()
    print(json.dumps(package(args.live_report, args.sdk_report, args.output, wheel=args.wheel, source_url=args.source_url)))


if __name__ == "__main__":
    main()
