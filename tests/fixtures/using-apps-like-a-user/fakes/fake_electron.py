"""Stand-in for an Electron dev build: serves /json/version on the --remote-debugging-port.

It opens no window and runs until it is terminated.
"""
import http.server
import json
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


port = int([a for a in sys.argv if a.startswith("--remote-debugging-port=")][0].split("=")[1])
http.server.HTTPServer(("127.0.0.1", port), Handler).serve_forever()
