"""Stand-in for an Electron dev build: serves /json/version on the --remote-debugging-port.

It opens no window and runs until it is terminated. When `FAKE_ELECTRON_ENV_DUMP` names a file, the
environment the process was started with is written there as JSON.
"""
import http.server
import json
import os
import sys


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"Browser": "FakeElectron/0"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


dump = os.environ.get("FAKE_ELECTRON_ENV_DUMP")
if dump:
    with open(dump, "w") as handle:
        json.dump(dict(os.environ), handle)

port = int([a for a in sys.argv if a.startswith("--remote-debugging-port=")][0].split("=")[1])
http.server.HTTPServer(("127.0.0.1", port), Handler).serve_forever()
