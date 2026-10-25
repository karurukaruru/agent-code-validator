"""Verify the built wheel actually contains and executes its packaged resources."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile
from patchcourt import __version__

ROOT = Path(__file__).resolve().parents[1]
wheel = ROOT / "dist" / (sys.argv[1] if len(sys.argv)>1 else f"agent_code_validator-{__version__}-py3-none-any.whl")
(ROOT / ".local-tmp").mkdir(exist_ok=True)
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
    assert (target / "installed" / "patchcourt" / "web" / "live.html").is_file()
    entrypoints = next(n for n in names if n.endswith("entry_points.txt"))
    assert "patchcourt = patchcourt.cli:main" in (target / "installed" / entrypoints).read_text()
    boundary_script = "import sys; sys.path.insert(0, sys.argv[1]); from patchcourt.cli import main; raise SystemExit(main(['boundary-run','--output',sys.argv[2]]))"
    boundary = subprocess.run([sys.executable, "-I", "-c", boundary_script, str(target / "installed"), str(target / "boundary")], cwd=target, capture_output=True, text=True, timeout=60)
    assert boundary.returncode == 1, boundary.stderr
    boundary_report = json.loads((target / "boundary" / "report.json").read_text(encoding="utf-8"))
    assert boundary_report["status"] == "FAIL"
    assert all(r["status"] == "EXECUTED" for r in boundary_report["executions"].values())
    assert boundary_report["cases"][0]["contracts"]["baseline"]["status"] == "PASS"
    assert (target / "installed" / "patchcourt" / "fixtures" / "nvidia-upgrade-constraints.txt").is_file()
    upgrade_script = "import sys; sys.path.insert(0,sys.argv[1]); from patchcourt.cli import main; raise SystemExit(main(['upgrade-run',sys.argv[2],'--from-version','1.4.3','--to-version','1.5.0','--environment-dir',sys.argv[3],'--output',sys.argv[4]]))"
    upgrade = subprocess.run([sys.executable, "-I", "-c", upgrade_script, str(target / "installed"), str(target), str(target / "missing-envs"), str(target / "upgrade")], cwd=target, capture_output=True, text=True, timeout=30)
    assert upgrade.returncode == 2, upgrade.stderr
    upgrade_report = json.loads((target / "upgrade" / "report.json").read_text(encoding="utf-8"))
    assert upgrade_report["status"] == "INCONCLUSIVE" and upgrade_report["provider_requests"] == 0
    print(json.dumps({"status":"PASS", "wheel":wheel.name, "isolated_mode":True, "summary":report["summary"], "entrypoint":"patchcourt", "fixtures_and_dashboard":True, "boundary_workers_executed_from_wheel":True, "upgrade_runner_and_constraints_packaged":True}))
