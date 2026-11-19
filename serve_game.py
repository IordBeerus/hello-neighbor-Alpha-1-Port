#!/usr/bin/env python3
"""Serve the Hello Neighbor web build.

The page only starts game.js once it is cross-origin isolated, so every
response carries COOP/COEP. The loader also streams the wasm parts in byte
ranges, so Range requests are supported. Standard library only.

    python serve_game.py           # http://localhost:8000/
    python serve_game.py 9000      # another port
    python serve_game.py 8000 --host 0.0.0.0

Note: browsers only treat a page as isolated in a secure context, i.e. https or
localhost. Serving a LAN address over plain http will not work; use https (or
the coi-sw.js fallback, which needs a secure context too) for that.
"""

import os
import re
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
CHUNK = 1 << 16
RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")


class Handler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "uewserve/1.0"

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("directory", ROOT)
        self._remaining = None
        super().__init__(*args, **kwargs)

    def end_headers(self):
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cross-Origin-Resource-Policy", "cross-origin")
        # applies to directory/index responses too, which skip send_head below
        self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()

    def guess_type(self, path):
        # game.wasm.0 .. game.wasm.9 must be application/wasm for streamed
        # compilation, and the .0 suffix defeats the mimetypes table
        if ".wasm" in os.path.basename(path):
            return "application/wasm"
        return super().guess_type(path)

    def send_head(self):
        self._remaining = None
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()
        if not os.path.isfile(path):
            self.send_error(404, "Not found")
            return None

        size = os.path.getsize(path)
        start, end, code = 0, size - 1, 200
        match = RANGE_RE.match((self.headers.get("Range") or "").strip())
        if match:
            first, last = match.groups()
            if first == "":
                if last != "":
                    start = max(0, size - int(last))
            else:
                start = int(first)
                if last != "":
                    end = min(int(last), size - 1)
                if start >= size:
                    self.send_error(416, "Range Not Satisfiable")
                    return None
            code = 206

        length = end - start + 1
        handle = open(path, "rb")
        handle.seek(start)
        self._remaining = length
        self.send_response(code)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        if code == 206:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
        self.end_headers()
        return handle

    def copyfile(self, source, outputfile):
        remaining = self._remaining
        if remaining is None:
            return super().copyfile(source, outputfile)
        while remaining > 0:
            chunk = source.read(min(CHUNK, remaining))
            if not chunk:
                break
            outputfile.write(chunk)
            remaining -= len(chunk)


def main():
    args = sys.argv[1:]
    port = 8000
    for arg in args:
        if arg.isdigit():
            port = int(arg)
    host = "127.0.0.1"
    if "--host" in args:
        host = args[args.index("--host") + 1]

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    shown = "localhost" if host in ("127.0.0.1", "0.0.0.0") else host
    print("serving %s" % ROOT)
    print("open http://%s:%d/" % (shown, port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
