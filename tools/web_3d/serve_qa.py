"""Local-only browser fixture host; proxies read-only ENC assets from dev server."""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
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
