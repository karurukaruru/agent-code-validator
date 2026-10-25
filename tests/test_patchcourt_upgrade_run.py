"""Environment identity and upgrade verdicts must fail closed."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from patchcourt.boundary_run import _run_side, run_boundary, validate_input
from patchcourt.cli import main
from patchcourt.counterexamples import tool_conversation
from patchcourt.evidence import digest, read_json, write_json
from patchcourt.upgrade_run import (CONSTRAINTS, PACKAGE, RECORD, _inventory, _runtime_identity, prepare_environment,
                                    run_upgrade, validate_environment)


class UpgradeRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        (self.repo / "requirements.txt").write_text(PACKAGE + "==1.4.3\n", encoding="utf-8")
        (self.repo / "app.py").write_text("# convert_message and tool_calls boundary\n", encoding="utf-8")

    def run_upgrade(self, **kwargs):
        return run_upgrade(self.repo, self.root / "result", baseline="1.4.3", candidate="1.5.0",
                           environment_dir=self.root / "environments", **kwargs)

    def test_missing_environments_never_install_or_execute_implicitly(self):
        with patch("patchcourt.upgrade_run.prepare_environment") as install, patch("patchcourt.upgrade_run._run_side") as worker:
            result = self.run_upgrade()
        install.assert_not_called(); worker.assert_not_called()
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertEqual(result["cases"][0]["findings"][0]["code"], "ENVIRONMENT_UNAVAILABLE")
        self.assertEqual(result["inspection"]["discovered_dependencies"][0]["framework"], PACKAGE)
        self.assertEqual(main(["verify", str(self.root / "result")]), 0)

    def test_invalid_input_does_not_install_dependencies(self):
        with patch("patchcourt.upgrade_run.prepare_environment") as install:
            result = self.run_upgrade(prepare=True, messages=[{"role": "user", "content": [], "unknown": True}])
        install.assert_not_called()
        self.assertEqual(result["status"], "INCONCLUSIVE")

    def test_secret_fields_in_serialized_arguments_abstain_before_installation(self):
        for arguments in ('{"password":"local-value"}', '{"nested":{"access_token":"local-value"}}'):
            messages = tool_conversation()
            messages[0]["tool_calls"][0]["function"]["arguments"] = arguments
            with self.subTest(arguments=arguments), patch("patchcourt.upgrade_run.prepare_environment") as install:
                with self.assertRaisesRegex(ValueError, "secret redaction"):
                    validate_input(messages)
                result = run_upgrade(self.repo, self.root / ("result-" + str(len(arguments))),
                                     baseline="1.4.3", candidate="1.5.0",
                                     environment_dir=self.root / "environments", prepare=True, messages=messages)
                install.assert_not_called()
                self.assertEqual(result["status"], "INCONCLUSIVE")
                self.assertIsNone(result["input"])
                output = self.root / ("result-" + str(len(arguments)))
                self.assertNotIn("local-value", (output / "report.json").read_text(encoding="utf-8"))
                self.assertNotIn("local-value", (output / "index.html").read_text(encoding="utf-8"))

    def test_boundary_abstention_does_not_export_serialized_secrets(self):
        messages = tool_conversation()
        messages[0]["tool_calls"][0]["function"]["arguments"] = '{"password":"local-value"}'
        with patch("patchcourt.boundary_run._run_side") as worker:
            result = run_boundary(self.root / "boundary", messages=messages)
        worker.assert_not_called()
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertNotIn("local-value", (self.root / "boundary" / "report.json").read_text(encoding="utf-8"))

    def test_deep_input_is_bounded_before_json_serialization(self):
        nested = {}
        for _ in range(70):
            nested = {"nested": nested}
        with self.assertRaisesRegex(ValueError, "depth"):
            validate_input([{"role": "user", "content": nested}])

    def test_unsupported_version_has_no_filesystem_side_effect(self):
        with self.assertRaises(ValueError):
            run_upgrade(self.repo, self.root / "result", baseline="../../escape", candidate="1.5.0", environment_dir=self.root / "envs", prepare=True)
        self.assertFalse((self.root / "result").exists())

    def test_existing_evidence_is_not_overwritten(self):
        output = self.root / "result"; output.mkdir()
        marker = output / "keep.txt"; marker.write_text("original", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self.run_upgrade()
        self.assertEqual(marker.read_text(encoding="utf-8"), "original")

    def test_two_existing_broken_releases_cannot_pass(self):
        def environment(target, version):
            return {"status": "READY", "version": version, "root": str(target), "dependencies": {PACKAGE: version, "langchain-core": "1.4.7"}}
        def worker(messages, variant, target):
            result = _run_side(messages, "upstream", None)
            result["provenance"]["version"] = "1.4.3" if target.endswith("1.4.3") else "1.5.0"
            return result
        with patch("patchcourt.upgrade_run.validate_environment", side_effect=environment), patch("patchcourt.upgrade_run._run_side", side_effect=worker):
            result = self.run_upgrade()
        self.assertEqual(result["status"], "NEEDS_REVIEW")
        self.assertEqual(result["cases"][0]["direction"], "baseline_and_candidate_unhealthy")
        self.assertEqual(result["cases"][0]["contracts"]["difference"]["status"], "NEEDS_REVIEW")
        self.assertEqual(result["provider_requests"], 0)

    def test_dependency_drift_prevents_execution_and_pass(self):
        def environment(target, version):
            return {"status": "READY", "version": version, "root": str(target), "dependencies": {PACKAGE: version, "langchain-core": version}}
        with patch("patchcourt.upgrade_run.validate_environment", side_effect=environment), patch("patchcourt.upgrade_run._run_side") as worker:
            result = self.run_upgrade()
        worker.assert_not_called()
        self.assertEqual(result["cases"][0]["findings"][0]["code"], "DEPENDENCY_DRIFT")
        self.assertEqual(result["status"], "INCONCLUSIVE")

    def test_install_failure_retains_both_sides(self):
        with patch("patchcourt.upgrade_run.prepare_environment", side_effect=ValueError("installation unavailable")) as install:
            result = self.run_upgrade(prepare=True)
        self.assertEqual(install.call_count, 2)
        self.assertEqual(set(result["environments"]), {"baseline", "candidate"})
        self.assertTrue(all("unavailable" in e["error"] for e in result["environments"].values()))

    def test_mismatched_executed_version_cannot_pass(self):
        def environment(target, version):
            return {"status": "READY", "version": version, "root": str(target), "dependencies": {PACKAGE: version}}
        with patch("patchcourt.upgrade_run.validate_environment", side_effect=environment), patch("patchcourt.upgrade_run._run_side", return_value={"status": "EXECUTED", "provenance": {"version": "wrong"}}):
            result = self.run_upgrade()
        self.assertEqual(result["status"], "INCONCLUSIVE")

    def test_incomplete_executed_result_cannot_pass(self):
        def environment(target, version):
            return {"status": "READY", "version": version, "root": str(target), "dependencies": {PACKAGE: version}}
        def worker(messages, variant, target):
            return {"status": "EXECUTED", "provenance": {"version": target.rsplit("-", 1)[1]}}
        with patch("patchcourt.upgrade_run.validate_environment", side_effect=environment), patch("patchcourt.upgrade_run._run_side", side_effect=worker):
            result = self.run_upgrade()
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertEqual(result["cases"][0]["findings"][0]["code"], "EXECUTION_UNCERTAIN")


class EnvironmentIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "langchain_nvidia_ai_endpoints" / "_utils.py"
        self.source.parent.mkdir(); self.source.write_bytes(b"# inert test source\n")
        self.add_distribution(PACKAGE, "1.4.3")
        self.sdk_hash = patch.dict("patchcourt.upgrade_run.SDK_RELEASES", {"1.4.3": hashlib.sha256(self.source.read_bytes()).hexdigest()})
        self.sdk_hash.start(); self.addCleanup(self.sdk_hash.stop)

    def add_distribution(self, name, version, directory=None):
        metadata = self.root / (directory or (name.replace("-", "_") + "-" + version + ".dist-info"))
        metadata.mkdir(); (metadata / "METADATA").write_text("Name: " + name + "\nVersion: " + version + "\n", encoding="utf-8")

    def record(self, dependencies=None, installation=None):
        install_report = {"install": [], "version": "1"}
        write_json(self.root / "pip-install.json", install_report)
        files = _inventory(self.root)
        identity = {"wheel_only": True, "python": sys.version.split()[0], "runtime": _runtime_identity(),
                    "constraints_sha256": hashlib.sha256(CONSTRAINTS.read_bytes()).hexdigest(),
                    "pip_report_sha256": digest(install_report)}
        identity.update(installation or {})
        write_json(self.root / RECORD, {"version": "1.4.3", "files": files, "inventory_sha256": digest(files),
                                      "dependencies": dependencies or {PACKAGE: "1.4.3"}, "installation": identity})

    def test_source_and_dependency_inventory_revalidated(self):
        self.record()
        self.assertEqual(validate_environment(self.root, "1.4.3")["status"], "READY")
        self.source.write_bytes(b"# altered source\n")
        with self.assertRaisesRegex(ValueError, "inventory changed"):
            validate_environment(self.root, "1.4.3")

    def test_exact_dependency_pin_enforced_even_for_matching_record(self):
        self.add_distribution("langchain-core", "0.0.1")
        self.record(dependencies={PACKAGE: "1.4.3", "langchain-core": "0.0.1"})
        with self.assertRaisesRegex(ValueError, "exact pins"):
            validate_environment(self.root, "1.4.3")

    def test_unreviewed_dependency_cannot_appear_in_verified_record(self):
        self.add_distribution("unreviewed-package", "1.0")
        self.record(dependencies={PACKAGE: "1.4.3", "unreviewed-package": "1.0"})
        with self.assertRaisesRegex(ValueError, "exact pins"):
            validate_environment(self.root, "1.4.3")

    def test_current_constraints_and_python_identity_required(self):
        for installation in ({"constraints_sha256": "old-constraints"}, {"python": "0.0.0"},
                             {"runtime": {"platform": "other"}}, {"wheel_only": False}):
            with self.subTest(installation=installation):
                self.record(installation=installation)
                with self.assertRaisesRegex(ValueError, "constraints or Python identity"):
                    validate_environment(self.root, "1.4.3")

    def test_runtime_identity_needs_no_hostname_network_or_subprocess(self):
        script = """import json, sys
sys.path.insert(0, sys.argv[1])
from patchcourt.upgrade_run import _runtime_identity
def audit(event, args):
    if event.startswith('socket.') or event in {'subprocess.Popen', 'os.system', 'os.posix_spawn'}:
        raise RuntimeError('Forbidden identity operation: ' + event)
sys.addaudithook(audit)
print(json.dumps(_runtime_identity()))
"""
        result = subprocess.run([sys.executable, "-I", "-S", "-c", script, str(Path(__file__).resolve().parent.parent)],
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True, timeout=10)
        self.assertEqual(json.loads(result.stdout), _runtime_identity())

    def test_installer_report_digest_checked_independently(self):
        self.record(installation={"pip_report_sha256": "incorrect"})
        with self.assertRaisesRegex(ValueError, "installation report"):
            validate_environment(self.root, "1.4.3")

    def test_duplicate_canonical_distribution_name_is_ambiguous(self):
        self.add_distribution("langchain_nvidia_ai_endpoints", "1.4.3", "shadow-1.4.3.dist-info")
        self.record()
        with self.assertRaisesRegex(ValueError, "ambiguous distribution"):
            validate_environment(self.root, "1.4.3")

    def test_secret_named_files_survive_inventory_serialization(self):
        (self.root / "secret.py").write_text("# harmless fixture\n", encoding="utf-8")
        self.record()
        self.assertEqual(validate_environment(self.root, "1.4.3")["status"], "READY")
        self.assertIn("secret.py", [entry["path"] for entry in read_json(self.root / RECORD)["files"]])

    def test_partial_installation_is_not_reused(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("patchcourt.upgrade_run.subprocess.Popen") as install:
                with self.assertRaises(FileNotFoundError):
                    prepare_environment(folder, "1.4.3")
            install.assert_not_called()


if __name__ == "__main__":
    unittest.main()
