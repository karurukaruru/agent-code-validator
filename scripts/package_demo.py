"""Package only an explicit allowlist of judge-facing static evidence."""
import hashlib
import json
from pathlib import Path
import zipfile
import argparse
from patchcourt import __version__
from patchcourt.evidence import read_json

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source", type=Path, default=ROOT / "outputs" / "patchcourt")
parser.add_argument("--output", type=Path, default=ROOT / "dist")
args = parser.parse_args()
report = read_json(args.source / "report.json")
if report.get("environment", {}).get("patchcourt") != __version__:
    raise ValueError("Generate a fresh demo with the current PatchCourt version before packaging")
OUT = args.output
OUT.mkdir(exist_ok=True)
archive = OUT / f"patchcourt-demo-{__version__}.zip"
allowed = ["index.html", "report.json", "report.md", "manifest.json", "ASM-ChatNVIDIA.md", "minimal-counterexample.json", "nvidia-repair.diff", "crewai-repair.diff", "test_regression.py"]
with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
    for name in allowed:
        path = args.source / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("Missing or unsafe evidence file: " + name)
        bundle.write(path, name)
    bundle.writestr("START-HERE.txt", "PatchCourt offline evidence viewer\nOpen index.html, then Open evidence and select report.json.\nOr run python -m http.server 8765 --bind 127.0.0.1 from this folder.\nHistorical failures and repairs are recorded source-boundary evidence. No live model use is claimed.\nFull SDK evidence and source are in the repository.\n")
    bundle.write(ROOT / "LICENSE", "LICENSE")
manifest = {p.name: {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size} for p in OUT.iterdir() if p.suffix in {".whl", ".zip"}}
(OUT / "SHA256SUMS.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"archive": str(archive), "files": len(allowed) + 2, "sha256": manifest[archive.name]["sha256"]}))
