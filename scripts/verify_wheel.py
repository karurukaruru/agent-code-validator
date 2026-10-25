"""Verify the built wheel actually contains and executes its packaged resources."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
wheel = ROOT / "dist" / "agent_code_validator-0.3.0-py3-none-any.whl"
with tempfile.TemporaryDirectory(dir=ROOT / ".local-tmp") as tmp:
    target = Path(tmp)
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        if any(name.startswith("/") or ".." in Path(name).parts for name in names):
            raise ValueError("Unsafe wheel entry")
        archive.extractall(target / "installed")
    script = "import sys; sys.path.insert(0, sys.argv[1]); from patchcourt.cli import main; raise SystemExit(main(['demo','--output',sys.argv[2]]))"
    result = subprocess.run([sys.executable, "-I", "-c", script, str(target / "installed"), str(target / "report")], cwd=target, capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError(result.stderr)
    report = json.loads((target / "report" / "report.json").read_text(encoding="utf-8"))
    assert report["summary"]["fail"] == 11 and report["summary"]["pass"] == 3
    assert (target / "report" / "index.html").is_file()
    entrypoints = next(n for n in names if n.endswith("entry_points.txt"))
    assert "patchcourt = patchcourt.cli:main" in (target / "installed" / entrypoints).read_text()
    print(json.dumps({"status":"PASS", "wheel":wheel.name, "isolated_mode":True, "summary":report["summary"], "entrypoint":"patchcourt", "fixtures_and_dashboard":True}))
