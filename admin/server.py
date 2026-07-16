#!/usr/bin/env python3
"""
Herbivicus Admin Server — local only, no external dependencies.

Usage:
    python3 admin/server.py          # opens http://localhost:7771
    python3 admin/server.py 8080     # custom port
"""

import json
import os
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
IMAGES_DIR = ROOT / "images"
ADMIN_DIR = Path(__file__).resolve().parent

MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


# ── helpers ───────────────────────────────────────────────────────────────────

def safe_path(base: Path, relative: str) -> "Path | None":
    """Resolve `relative` under `base`, rejecting path-traversal attempts."""
    try:
        resolved = (base / relative).resolve()
        resolved.relative_to(base.resolve())  # raises ValueError if outside
        return resolved
    except (ValueError, OSError):
        return None


def load_json(path: Path) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"_parse_error": True, "products": []}
    except OSError:
        return {"products": []}


def save_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


# ── request handler ────────────────────────────────────────────────────────────

class AdminHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):  # quieter logs
        print(f"  {fmt % args}")

    # ── routing ────────────────────────────────────────────────────────────────

    def do_GET(self):
        p = urlparse(self.path).path
        if p in ("/", "/index.html"):
            return self._file(ADMIN_DIR / "index.html")
        if p.startswith("/api/"):
            return self._api_get(p[5:])
        if p.startswith("/images/"):
            rel = unquote(p[8:])
            fp = safe_path(IMAGES_DIR, rel)
            if fp and fp.is_file():
                return self._file(fp)
            return self._err(404)
        # static files from admin dir
        rel = unquote(p.lstrip("/"))
        fp = safe_path(ADMIN_DIR, rel)
        if fp and fp.is_file():
            return self._file(fp)
        self._err(404)

    def do_PUT(self):
        p = urlparse(self.path).path
        if p.startswith("/api/products/"):
            parts = p[14:].split("/", 1)
            if len(parts) == 2:
                return self._update(parts[0], unquote(parts[1]))
        self._err(404)

    def do_POST(self):
        p = urlparse(self.path).path
        if p.startswith("/api/products/"):
            cat = p[14:].strip("/")
            if cat:
                return self._create(cat)
        self._err(404)

    def do_DELETE(self):
        p = urlparse(self.path).path
        if p.startswith("/api/products/"):
            parts = p[14:].split("/", 1)
            if len(parts) == 2:
                return self._delete(parts[0], unquote(parts[1]))
        self._err(404)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    # ── API ────────────────────────────────────────────────────────────────────

    def _api_get(self, path: str):
        if path == "categories":
            cats = []
            for f in sorted(DATA_DIR.iterdir()):
                if f.suffix == ".json":
                    d = load_json(f)
                    cats.append({
                        "id": f.stem,
                        "count": len(d.get("products", [])),
                        "parse_error": d.get("_parse_error", False),
                    })
            return self._json(cats)

        if path.startswith("products/"):
            cat = path[9:].strip("/")
            fp = safe_path(DATA_DIR, cat + ".json")
            if fp and fp.is_file():
                d = load_json(fp)
                payload = {"products": d.get("products", [])}
                if d.get("_parse_error"):
                    payload["parse_error"] = True
                return self._json(payload)
            return self._err(404, "Category not found")

        self._err(404)

    def _update(self, cat: str, pid: str):
        fp = safe_path(DATA_DIR, cat + ".json")
        if not fp or not fp.is_file():
            return self._err(404, "Category not found")
        body = self._body()
        if body is None:
            return self._err(400, "Invalid JSON body")
        d = load_json(fp)
        products = d.get("products", [])
        for i, p in enumerate(products):
            if p.get("id") == pid:
                products[i] = body
                d["products"] = products
                d.pop("_parse_error", None)
                save_json(fp, d)
                return self._json(body)
        self._err(404, "Product not found")

    def _create(self, cat: str):
        fp = safe_path(DATA_DIR, cat + ".json")
        if not fp:
            return self._err(400, "Invalid category")
        body = self._body()
        if body is None:
            return self._err(400, "Invalid JSON body")
        d = load_json(fp) if fp.is_file() else {"products": []}
        products = d.get("products", [])
        if any(p.get("id") == body.get("id") for p in products):
            return self._err(409, "A product with that ID already exists")
        products.append(body)
        d["products"] = products
        d.pop("_parse_error", None)
        save_json(fp, d)
        self._json(body, 201)

    def _delete(self, cat: str, pid: str):
        fp = safe_path(DATA_DIR, cat + ".json")
        if not fp or not fp.is_file():
            return self._err(404, "Category not found")
        d = load_json(fp)
        products = d.get("products", [])
        new_products = [p for p in products if p.get("id") != pid]
        if len(new_products) == len(products):
            return self._err(404, "Product not found")
        d["products"] = new_products
        save_json(fp, d)
        self._json({"ok": True})

    # ── wire helpers ───────────────────────────────────────────────────────────

    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            return json.loads(self.rfile.read(length))
        except Exception:
            return None

    def _file(self, path: Path):
        mime = MIME.get(path.suffix.lower(), "application/octet-stream")
        try:
            data = path.read_bytes()
        except OSError:
            return self._err(404)
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _err(self, code: int, msg: str = ""):
        body = json.dumps({"error": msg or str(code)}).encode()
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "http://localhost:7771")
        self.send_header("Access-Control-Allow-Methods", "GET,PUT,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


# ── entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 7771
    server = HTTPServer(("127.0.0.1", port), AdminHandler)
    url = f"http://localhost:{port}"
    print(f"\n  🌿  Herbivicus Admin  →  {url}")
    print("      Press Ctrl+C to stop.\n")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")
