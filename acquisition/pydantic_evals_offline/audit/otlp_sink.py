"""Local stand-in for an OTLP/HTTP collector: stores every POST body, answers 200.

Usage: python otlp_sink.py OUT_DIR [PORT]   (binds 127.0.0.1 only)

Used inside an isolated network namespace so that telemetry triggered by inherited
`OTEL_*` variables is captured locally instead of reaching any real service.
"""

from __future__ import annotations

import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

OUT = Path(sys.argv[1])
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 4318
COUNTER = [0]


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        COUNTER[0] += 1
        name = f'{COUNTER[0]:04d}{self.path.replace("/", "_")}.bin'
        (OUT / name).write_bytes(body)
        (OUT / f'{name}.headers').write_text(''.join(f'{k}: {v}\n' for k, v in self.headers.items()))
        self.send_response(200)
        self.send_header('Content-Type', 'application/x-protobuf')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
