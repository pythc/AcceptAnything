"""Loopback-only research fixture. Deliberate defects, never a deployment template."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse


def serve(mode, port):
    fixed = mode == "fixed"
    state = {"note": "", "tokens": {}, "orders": {}, "next_order": 0}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, body, content_type="application/json"):
            data = json.dumps(body).encode() if content_type == "application/json" else body.encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def actor(self):
            return state["tokens"].get(self.headers.get("Authorization", ""))

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/health":
                return self.reply(200, {"mode": mode})
            if path == "/api/contract":
                return self.reply(200, {"count": 1 if fixed else "one"})
            if path == "/api/note":
                return self.reply(200, {"note": state["note"]})
            if path == "/api/me":
                return self.reply(200 if self.actor() else 401, {"user": self.actor()})
            if path == "/api/documents/bob-private":
                if not self.actor():
                    return self.reply(401, {"error": "unauthenticated"})
                if fixed and self.actor() != "bob":
                    return self.reply(403, {"error": "forbidden"})
                return self.reply(200, {"owner": "bob", "content": "synthetic-private-record"})
            if path == "/":
                label = '<label for="note">Note</label>' if fixed else ""
                return self.reply(200, f'''<!doctype html><html lang="en"><head><title>Acceptance fixture</title></head>
                <body><main><h1>Notes</h1>{label}<input id="note"><button id="save">Save</button>
                <p role="status" id="status"></p><output id="saved"></output></main>
                <script>
                async function load() {{ const r=await fetch('/api/note'); document.querySelector('#saved').textContent=(await r.json()).note; }}
                document.querySelector('#save').onclick=async()=>{{await fetch('/api/note',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{note:document.querySelector('#note').value}})}});document.querySelector('#status').textContent='Saved';await load();}};
                load();
                </script></body></html>''', "text/html; charset=utf-8")
            return self.reply(404, {"error": "not found"})

        def do_POST(self):
            path = urlparse(self.path).path
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or "{}")
            except (ValueError, TypeError):
                return self.reply(400, {"error": "invalid json"})
            if path == "/api/login":
                user = body.get("user")
                if user not in ("alice", "bob"):
                    return self.reply(400, {"error": "unknown fixture user"})
                token = "Bearer synthetic-" + user
                state["tokens"][token] = user
                return self.reply(200, {"token": token})
            if path == "/api/logout":
                if fixed:
                    state["tokens"].pop(self.headers.get("Authorization", ""), None)
                return self.reply(200, {"ok": True})
            if path == "/api/note":
                if fixed:
                    state["note"] = body.get("note", "")
                return self.reply(200, {"ok": True})
            if path == "/api/orders":
                key = self.headers.get("Idempotency-Key", "")
                if not key:
                    return self.reply(400, {"error": "key required"})
                if not fixed or key not in state["orders"]:
                    state["next_order"] += 1
                    state["orders"][key] = {"id": state["next_order"]}
                return self.reply(201, state["orders"][key])
            return self.reply(404, {"error": "not found"})

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["buggy", "fixed"], required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    serve(args.mode, args.port)
