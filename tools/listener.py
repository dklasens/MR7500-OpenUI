import http.server, socketserver, datetime, sys

LOG = r"C:\Users\david\AppData\Local\Temp\opencode\callback_log.txt"

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass
    def do_GET(self):
        line = "%s GET %s from %s\n" % (datetime.datetime.now().isoformat(), self.path, self.client_address[0])
        with open(LOG, "a") as f:
            f.write(line)
        self.send_response(200); self.end_headers(); self.wfile.write(b"OK")

open(LOG, "a").write("=== listener started %s ===\n" % datetime.datetime.now().isoformat())
with socketserver.TCPServer(("0.0.0.0", 8000), H) as httpd:
    httpd.serve_forever()
