"""Local-only browser fixture host; proxies read-only ENC assets from dev server."""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self' data: blob:; script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; connect-src 'self'",
        )
        super().end_headers()

    def do_GET(self):
        reference = self.headers.get("Referer", "")
        fail_engine = "failure=engine" in reference and self.path.endswith("/Cesium.js")
        fail_model = "failure=model" in reference and self.path.endswith(".glb")
        if fail_engine or fail_model:
            self.send_error(503, "Intentional browser acceptance failure")
            return
        if self.path.startswith("/api/"):
            try:
                with urlopen("http://127.0.0.1:8013" + self.path) as response:
                    body = response.read()
                    self.send_response(200)
                    self.send_header("Content-Type", response.headers["Content-Type"])
                    self.end_headers()
                    self.wfile.write(body)
            except Exception as error:
                self.send_error(502, str(error))
            return
        if self.path.startswith("/static/"):
            self.path = "/web_gui/" + self.path[len("/static/") :]
        super().do_GET()


ThreadingHTTPServer(("127.0.0.1", 8015), partial(Handler, directory=str(ROOT))).serve_forever()
