"""Exercise the local HTTP handler with synthetic replies and no sockets/API calls."""
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from patchcourt import providers
from patchcourt.cli import main
from patchcourt.live_demo import serve_live_demo
from tests.test_patchcourt_live_workflow import replies


class Connection:
    def __init__(self, request):
        self.request = request
        self.output = bytearray()

    def makefile(self, *args):
        return io.BytesIO(self.request)

    def sendall(self, value):
        self.output.extend(value)


class ImmediateThread:
    def __init__(self, target, daemon):
        self.target = target

    def start(self):
        self.target()


class LiveDemoKnowledgeTests(unittest.TestCase):
    def test_two_runs_save_then_revalidate_cache_through_fixed_http_workflow(self):
        states = []
        sessions = []

        class FakeServer:
            def __init__(self, address, handler):
                self.handler = handler
                self.server_address = address
                self.server_name, self.server_port = address

            def call(self, method, path, session=None):
                headers = [f"{method} {path} HTTP/1.0", "Host: 127.0.0.1:8780"]
                if method == "POST":
                    headers += ["Origin: http://127.0.0.1:8780", "Content-Type: application/json",
                                "Content-Length: 2", "X-PatchCourt-Session: " + session]
                connection = Connection(("\r\n".join(headers) + "\r\n\r\n").encode() +
                                        (b"{}" if method == "POST" else b""))
                self.handler(connection, ("127.0.0.1", 60000), self)
                header, body = bytes(connection.output).split(b"\r\n\r\n", 1)
                return header.split(b"\r\n", 1)[0], json.loads(body)

            def serve_forever(self):
                status, session = self.call("GET", "/session")
                if b"200" not in status:
                    raise AssertionError("Session unavailable")
                sessions.append(session)
                states.append(self.call("GET", "/state")[1])
                for _ in range(2):
                    status, _ = self.call("POST", "/run", session["session"])
                    if b"202" not in status:
                        raise AssertionError("Fixed run was not accepted")
                    states.append(deepcopy(self.call("GET", "/state")[1]))

            def server_close(self):
                pass

        with tempfile.TemporaryDirectory() as folder, patch(
                "patchcourt.live_demo.ThreadingHTTPServer", FakeServer), patch(
                "patchcourt.live_demo.threading.Thread", ImmediateThread), patch.object(
                providers, "request", side_effect=replies() + replies()[1:]) as api, patch(
                "sys.stdout", new_callable=io.StringIO):
            root = Path(folder)
            knowledge = root / "private-knowledge-directory"
            serve_live_demo(root / "runs", knowledge_dir=knowledge)
            self.assertEqual(api.call_count, 5)
            self.assertEqual(len(list(knowledge.glob("*.json"))), 1)
            self.assertNotIn(str(root), json.dumps(states + sessions))
        self.assertTrue(sessions[0]["knowledge_enabled"])
        self.assertTrue(states[0]["knowledge_enabled"])
        first, second = states[1]["report"], states[2]["report"]
        self.assertEqual([first["status"], second["status"]], ["PASS", "PASS"])
        self.assertTrue(first["knowledge"]["saved"])
        self.assertFalse(first["knowledge"]["hit"])
        self.assertTrue(second["knowledge"]["hit"])
        self.assertTrue(second["knowledge"]["revalidated"])
        self.assertEqual(second["repair_source"], "cached_verified_plan")
        self.assertEqual(second["repair_attempts"], [])
        self.assertEqual(len(second["verification"]["checks"]), 8)
        self.assertEqual(second["mutation_check"]["status"], "PASS")
        self.assertEqual(second["task"]["answer"]["inventory_value"], 21)
        self.assertEqual(first["execution_identity"], second["execution_identity"])

    def test_cli_forwards_explicit_knowledge_directory_without_starting_a_server(self):
        with patch("patchcourt.live_demo.serve_live_demo") as serve:
            self.assertEqual(main(["live-demo", "--provider", "deepseek", "--knowledge-dir", "outputs/verified-plans",
                                   "--output", "outputs/test-workbench", "--tavily"]), 0)
        serve.assert_called_once_with("outputs/test-workbench", 8780, provider="deepseek", model=None,
                                      use_tavily=True, knowledge_dir="outputs/verified-plans")


if __name__ == "__main__":
    unittest.main()
