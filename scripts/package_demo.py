"""Package only an explicit allowlist of judge-facing static evidence."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist"
OUT.mkdir(exist_ok=True)
archive = OUT / "patchcourt-demo-0.3.0.zip"
allowed = ["index.html", "report.json", "report.md", "manifest.json", "ASM-ChatNVIDIA.md", "minimal-counterexample.json", "nvidia-repair.diff", "crewai-repair.diff", "test_regression.py"]
with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
    for name in allowed:
        path = ROOT / "evidence" / "demo" / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("Missing or unsafe evidence file: " + name)
        bundle.write(path, name)
    bundle.writestr("START-HERE.txt", "PatchCourt offline evidence viewer\nOpen index.html, then Open evidence and select report.json.\nOr run python -m http.server 8765 --bind 127.0.0.1 from this folder.\nHistorical failures and repairs are recorded source-boundary evidence. No live model use is claimed.\nFull SDK evidence and source are in the repository.\n")
    bundle.write(ROOT / "LICENSE", "LICENSE")
manifest = {p.name: {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size} for p in OUT.iterdir() if p.suffix in {".whl", ".zip"}}
(OUT / "SHA256SUMS.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"archive": str(archive), "files": len(allowed) + 2, "sha256": manifest[archive.name]["sha256"]}))
