"""Controlled real-release comparison; no repository code or provider calls.

Only two reviewed NVIDIA releases are executable. Dependency installation is
explicit, wheel-only, and separate from execution. This is not an OS sandbox.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

from acv.scanner import _is_link_like
from .boundary_run import SDK_RELEASES, _run_side, complete_pair, validate_input
from .evidence import digest, read_json, write_json

PACKAGE = "langchain-nvidia-ai-endpoints"
RECORD = "patchcourt-environment.json"
INSTALL_TIMEOUT = 240
LOG_LIMIT = 2_000_000
CONSTRAINTS = Path(__file__).parent / "fixtures" / "nvidia-upgrade-constraints.txt"


def _runtime_identity():
    # platform.machine() calls platform.uname(), which queries the hostname and
    # can invoke WMI/subprocesses on Windows. Identity must work under the audit
    # policy without making network or subprocess calls.
    if hasattr(os, "uname"):
        machine = os.uname().machine
    else:
        architecture = re.search(r"bit \(([^()]*)\)", sys.version)
        machine = architecture.group(1) if architecture else "pointer-" + str(64 if sys.maxsize > 2**32 else 32)
    return {"implementation": sys.implementation.name, "cache_tag": sys.implementation.cache_tag,
            "platform": sys.platform, "machine": machine}


def _installed_versions(root):
    versions = {}
    for distribution in importlib.metadata.distributions(path=[str(root)]):
        name = distribution.metadata.get("Name")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
            raise ValueError("SDK environment has invalid distribution metadata")
        name = re.sub(r"[-_.]+", "-", name).lower()
        if name in versions or not distribution.version:
            raise ValueError("SDK environment has ambiguous distribution metadata")
        versions[name] = distribution.version
    return versions


def _check_pins(versions):
    pins = {}
    for line in CONSTRAINTS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*==[A-Za-z0-9.+!-]+", line):
            raise ValueError("SDK constraints must contain exact dependency pins")
        name, version = line.split("==")
        if name in pins:
            raise ValueError("SDK constraints contain duplicate dependency pins")
        pins[name] = version
    if not pins or any(pins.get(name) != version for name, version in versions.items() if name != PACKAGE):
        raise ValueError("SDK environment dependencies differ from reviewed exact pins")


def _environment_root(root):
    root = Path(root).absolute()
    if _is_link_like(root):
        raise ValueError("SDK environment must not be a link or junction")
    return root.resolve()


def _inventory(root):
    def unreadable(error):
        raise error
    files = []
    total = 0
    for directory, dirs, names in os.walk(root, followlinks=False, onerror=unreadable):
        for name in dirs + names:
            if _is_link_like(Path(directory) / name):
                raise ValueError("SDK environment must not contain links or junctions")
        for name in names:
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            if relative == RECORD:
                continue
            total += path.stat().st_size
            if len(files) >= 20000 or total > 500_000_000:
                raise ValueError("SDK environment exceeds inventory budget")
            files.append({"path": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return sorted(files, key=lambda item: item["path"])


def validate_environment(root, version):
    if version not in SDK_RELEASES:
        raise ValueError("Only reviewed NVIDIA releases are supported")
    root = _environment_root(root)
    if _is_link_like(root / RECORD):
        raise ValueError("SDK environment record must not be a link or junction")
    record = read_json(root / RECORD)
    if not isinstance(record, dict) or record.get("version") != version:
        raise ValueError("SDK environment version does not match requested release")
    files = _inventory(root)
    if not files or record.get("files") != files or record.get("inventory_sha256") != digest(files):
        raise ValueError("SDK environment inventory changed; create a fresh environment")
    installation = record.get("installation")
    if (not isinstance(installation, dict) or installation.get("wheel_only") is not True
            or installation.get("python") != sys.version.split()[0]
            or installation.get("runtime") != _runtime_identity()
            or installation.get("constraints_sha256") != hashlib.sha256(CONSTRAINTS.read_bytes()).hexdigest()):
        raise ValueError("SDK environment installation constraints or Python identity changed; create a fresh environment")
    if installation.get("pip_report_sha256") != digest(read_json(root / "pip-install.json")):
        raise ValueError("SDK installation report differs from installation record")
    versions = _installed_versions(root)
    _check_pins(versions)
    source = root / "langchain_nvidia_ai_endpoints" / "_utils.py"
    if (versions.get(PACKAGE) != version or versions != record.get("dependencies")
            or hashlib.sha256(source.read_bytes()).hexdigest() != SDK_RELEASES.get(version)):
        raise ValueError("SDK release identity differs from reviewed source and installation record")
    return {"status": "READY", "version": version, "root": str(root),
            "inventory_sha256": digest(files), "dependencies": versions,
            "installation": record["installation"], "reused": True}


def prepare_environment(root, version, *, wheelhouse=None):
    """Install a reviewed release in a new target. Existing targets are verified."""
    if version not in SDK_RELEASES:
        raise ValueError("Only reviewed NVIDIA releases are supported")
    root = _environment_root(root)
    if root.exists():
        return validate_environment(root, version)
    root.mkdir(parents=True, exist_ok=False)
    constraint = CONSTRAINTS
    command = [sys.executable, "-I", "-m", "pip", "--isolated", "--disable-pip-version-check",
               "install", "--only-binary=:all:", "--no-input", "--no-compile", "--no-cache-dir",
               "--timeout", "15", "--retries", "1",
               "--target", str(root), "--report", str(root / "pip-install.json"),
               "--constraint", str(constraint), PACKAGE + "==" + version]
    if wheelhouse:
        command.extend(["--no-index", "--find-links", str(Path(wheelhouse).resolve())])
    else:
        command.extend(["--index-url", "https://pypi.org/simple"])
    started = time.perf_counter()
    # A fresh home avoids user pip configuration, credentials and SDK telemetry.
    with tempfile.TemporaryDirectory(prefix="patchcourt-install-") as home:
        env = {k: os.environ[k] for k in ("SystemRoot", "WINDIR") if k in os.environ}
        env.update({"HOME": home, "USERPROFILE": home, "TEMP": home, "TMP": home})
        with tempfile.TemporaryFile() as stdout:
            proc = subprocess.Popen(command, cwd=home, env=env, stdin=subprocess.DEVNULL,
                                    stdout=stdout, stderr=subprocess.STDOUT)
            failure = None
            while True:
                try:
                    proc.wait(timeout=0.2)
                    break
                except subprocess.TimeoutExpired:
                    if time.perf_counter() - started > INSTALL_TIMEOUT:
                        failure = "SDK installation exceeded execution deadline"
                    if os.fstat(stdout.fileno()).st_size > LOG_LIMIT:
                        failure = "SDK installation exceeded output budget"
                    if failure:
                        proc.kill(); proc.wait(); break
            stdout.seek(0)
            raw = stdout.read(LOG_LIMIT + 1)
            log = raw.decode("utf-8", errors="replace")
            (root / "install.log").write_text(log[:LOG_LIMIT], encoding="utf-8")
            if len(raw) > LOG_LIMIT:
                failure = "SDK installation exceeded output budget"
            if failure or proc.returncode:
                raise ValueError(failure or "SDK wheel installation failed; inspect " + str(root / "install.log"))
    # pip's report records resolved versions, download URLs and archive hashes.
    install = read_json(root / "pip-install.json")
    versions = _installed_versions(root)
    _check_pins(versions)
    source_hash = hashlib.sha256((root / "langchain_nvidia_ai_endpoints" / "_utils.py").read_bytes()).hexdigest()
    if versions.get(PACKAGE) != version or source_hash != SDK_RELEASES[version]:
        raise ValueError("Downloaded SDK does not match the reviewed release")
    installation = {"python": sys.version.split()[0], "runtime": _runtime_identity(), "wheel_only": True,
                    "source": "local-wheelhouse" if wheelhouse else "official-pypi",
                    "pip_report_sha256": digest(install),
                    "constraints_sha256": hashlib.sha256(constraint.read_bytes()).hexdigest(),
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3)}
    files = _inventory(root)
    write_json(root / RECORD, {"version": version, "files": files, "inventory_sha256": digest(files),
                              "dependencies": versions, "installation": installation})
    return {**validate_environment(root, version), "reused": False}


def run_upgrade(repository, output, *, baseline, candidate, environment_dir, prepare=False,
                wheelhouse=None, messages=None):
    from .counterexamples import tool_conversation
    from .runner import make_report, export_report
    from .sentinel import inspect_repository
    if baseline not in SDK_RELEASES or candidate not in SDK_RELEASES:
        raise ValueError("Unsupported SDK version; choose a reviewed release: " + ", ".join(SDK_RELEASES))
    if wheelhouse and not prepare:
        raise ValueError("--wheelhouse requires --prepare")
    root = Path(output)
    root.mkdir(parents=True, exist_ok=False)
    default_task = messages is None
    messages = tool_conversation() if default_task else messages
    case = {"id": "nvidia-release-upgrade", "title": f"NVIDIA SDK {baseline} → {candidate}",
            "status": "INCONCLUSIVE", "execution": False, "findings": [],
            "provenance": {"kind": "Two unmodified installed SDK releases; no model inference",
                           "dependency": PACKAGE, "baseline_version": baseline, "candidate_version": candidate}}
    report = make_report([case])
    report.update({"mode": "upgrade-run", "status": "INCONCLUSIVE", "input": messages,
                   "executions": {}, "environments": {}, "provider_requests": 0,
                   "limitations": [
                       "Executes only reviewed NVIDIA 1.4.3 and 1.5.0 text/tool serializers with real LangChain message classes.",
                       "Repository inspection is read-only; application code and arbitrary model patches are never executed.",
                       "Pinned common dependencies must match across both environments; SDK releases remain unmodified.",
                       "Separate clean processes with deadlines and audit hooks; not an OS security sandbox. Dependencies must be trusted.",
                       "Checks the original input as well as the version difference. Matching broken releases cannot PASS.",
                       "Task replay is deterministic. No provider, model, Tavily or other paid requests are made.",
                       "Inventories and checksums detect changes; they do not authenticate an untrusted local writer.",
                   ]})
    def uncertain(code, message):
        case["findings"] = [{"code": code, "message": message}]
        report["summary"] = {"pass": 0, "fail": 0, "inconclusive": 1, "needs_review": 0}
        return export_report(report, root)
    try:
        validate_input(messages)
        report["inspection"] = inspect_repository(repository, PACKAGE, baseline, candidate)
    except (ValueError, OSError, TypeError, KeyError) as exc:
        report["input"] = None
        report["input_omitted_reason"] = "Unsupported input is not retained in exported evidence"
        return uncertain("UNSUPPORTED_INPUT", str(exc))
    for side, version in (("baseline", baseline), ("candidate", candidate)):
        target = Path(environment_dir) / ("nvidia-" + version)
        try:
            report["environments"][side] = (prepare_environment(target, version, wheelhouse=wheelhouse)
                                            if prepare else validate_environment(target, version))
        except (ValueError, OSError, TypeError, KeyError) as exc:
            report["environments"][side] = {"status": "INCONCLUSIVE", "version": version, "error": str(exc)}
    envs = report["environments"]
    if any(env["status"] != "READY" for env in envs.values()):
        return uncertain("ENVIRONMENT_UNAVAILABLE", "Prepare fresh SDK targets with --prepare; inspect environment errors and installation logs")
    common = [{k: v for k, v in envs[s]["dependencies"].items() if k != PACKAGE} for s in ("baseline", "candidate")]
    if common[0] != common[1]:
        return uncertain("DEPENDENCY_DRIFT", "Non-SDK dependencies differ; cannot isolate the effect of the SDK upgrade")
    for side in ("baseline", "candidate"):
        try:
            result = _run_side(messages, "release", envs[side]["root"])
            if result.get("status") == "EXECUTED" and (not isinstance(result.get("provenance"), dict)
                    or result["provenance"].get("version") != envs[side]["version"]):
                result = {"status": "INCONCLUSIVE", "error": "Executed SDK identity differs from requested release"}
            report["executions"][side] = result
        except (ValueError, OSError) as exc:
            report["executions"][side] = {"status": "INCONCLUSIVE", "error": str(exc)}
    return complete_pair(report, case, messages, default_task, root)
