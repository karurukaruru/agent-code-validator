import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from acv import cli


def test_openai_compatible_http_request_runs_end_to_end(tmp_path: Path) -> None:
    received: dict[str, object] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers["Content-Length"])
            received["path"] = self.path
            received["body"] = json.loads(self.rfile.read(length))
            payload = {
                "id": "local-test",
                "object": "chat.completion",
                "created": 0,
                "model": "local-review-model",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "[]"},
                        "finish_reason": "stop",
                    }
                ],
            }
            encoded = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        project = tmp_path / "project"
        project.mkdir()
        (project / "app.py").write_text("print('hello')\n", encoding="utf-8")
        config = tmp_path / "config.json"
        config.write_text(
            json.dumps(
                {
                    "api_key": "local-test-key",
                    "model": "local-review-model",
                    "base_url": f"http://127.0.0.1:{port}/v1",
                    "timeout": 5,
                }
            ),
            encoding="utf-8",
        )
        report = tmp_path / "review.md"

        status = cli.main(
            [
                "review",
                str(project),
                "--config",
                str(config),
                "--output",
                str(report),
            ]
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert status == 0
    assert report.exists()
    assert "No meaningful code-review issues" in report.read_text(encoding="utf-8")
    assert received["path"] == "/v1/chat/completions"
    body = received["body"]
    assert isinstance(body, dict)
    assert body["model"] == "local-review-model"
    assert "max_tokens" not in body
    assert "max_completion_tokens" not in body
