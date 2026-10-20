import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class ReceivedRequest:
    def __init__(self, headers, body):
        self.headers, self.body = headers, body

    @property
    def payload(self):
        return json.loads(self.body)


# A real HTTP server on a free local port: the delivery code runs exactly as against a
# remote one. Each request gets the next status of the list, or the last one again.
class RecordingReceiver:
    def __init__(self, *statuses, location=None):
        self.statuses = list(statuses) or [200]
        self.location = location
        self.received = []

    def __enter__(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.build_handler())
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc_info):
        self.server.shutdown()
        self.server.server_close()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.server_port}/hooks"

    def next_status(self):
        return self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]

    def build_handler(self):
        receiver = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                receiver.received.append(ReceivedRequest(dict(self.headers), body))
                self.send_response(receiver.next_status())
                if receiver.location:
                    self.send_header("Location", receiver.location)
                self.end_headers()

            def log_message(self, *args):
                pass

        return Handler
