"""Open a fresh, local, credential-free demonstration for desktop users."""
from pathlib import Path
import threading
import uuid
import webbrowser

from .cli import serve_static
from .runner import demo


def main():
    output = Path("outputs") / ("desktop-" + uuid.uuid4().hex[:12])
    demo(output)
    url = "http://127.0.0.1:8765"
    print("PatchCourt offline demo — no API key required.", flush=True)
    print("Evidence: " + str(output.resolve()), flush=True)
    print("Open " + url + " — press Ctrl+C to stop.", flush=True)
    timer = threading.Timer(0.8, webbrowser.open, args=(url,))
    timer.daemon = True
    timer.start()
    try:
        return serve_static(output, 8765)
    finally:
        timer.cancel()


if __name__ == "__main__":
    raise SystemExit(main())
