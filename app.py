#!/usr/bin/env python3
"""Small local server for the Persian Markdown reader."""

import argparse
import html
import json
import re
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import markdown


ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"
DIRECTIVES = {"align-left", "align-right", "size-small", "size-large", "size-xlarge"}
TAGS = {
    "p", "br", "strong", "em", "del", "blockquote", "ul", "ol", "li", "hr",
    "h1", "h2", "h3", "h4", "h5", "h6", "pre", "code", "table", "thead",
    "tbody", "tr", "th", "td", "a", "img", "div", "sup", "sub",
}
VOID = {"br", "hr", "img"}


def safe_url(value: str) -> bool:
    value = html.unescape(value).strip()
    if re.search(r"[\x00-\x20]", value):
        return False
    parsed = urlsplit(value)
    return parsed.scheme.lower() in {"", "http", "https", "mailto"} and not value.startswith("//")


class CleanHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag not in TAGS:
            return
        kept = []
        for name, value in attrs:
            if value is None:
                continue
            if tag == "div" and name == "class" and value in DIRECTIVES:
                kept.append((name, value))
            elif tag == "a" and name in {"href", "title"}:
                if name != "href" or safe_url(value):
                    kept.append((name, value))
            elif tag == "img" and name in {"src", "alt", "title"}:
                if name != "src" or safe_url(value):
                    kept.append((name, value))
        attributes = "".join(f' {name}="{html.escape(value, quote=True)}"' for name, value in kept)
        self.parts.append(f"<{tag}{attributes}>")

    def handle_endtag(self, tag):
        if tag in TAGS and tag not in VOID:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        self.parts.append(html.escape(data, quote=False))

    def handle_entityref(self, name):
        self.parts.append(f"&{name};")

    def handle_charref(self, name):
        self.parts.append(f"&#{name};")


def prepare_source(source: str) -> str:
    lines = []
    depth = 0
    in_code = False
    fence = ""
    for line in source.splitlines():
        stripped = line.strip()
        match = re.match(r"^(`{3,}|~{3,})", stripped)
        if match:
            marker = match.group(1)
            if not in_code:
                in_code, fence = True, marker[0]
            elif marker[0] == fence:
                in_code = False
        if not in_code and stripped.startswith("::: ") and stripped[4:] in DIRECTIVES:
            lines.extend(["", f'<div class="{stripped[4:]}" markdown="1">', ""])
            depth += 1
        elif not in_code and stripped == ":::" and depth:
            lines.extend(["", "</div>", ""])
            depth -= 1
        else:
            lines.append(html.escape(line, quote=False))
    lines.extend(["", "</div>"] * depth)
    return "\n".join(lines)


def render(source: str) -> str:
    markup = markdown.markdown(
        prepare_source(source),
        extensions=["tables", "fenced_code", "md_in_html", "sane_lists", "nl2br"],
    )
    cleaner = CleanHTML()
    cleaner.feed(markup)
    return "".join(cleaner.parts)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            data = b"persian-md-reader\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        path = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css", "/vazirmatn.woff2": "vazirmatn.woff2"}.get(self.path)
        if not path:
            self.send_error(404)
            return
        data = (PUBLIC / path).read_bytes()
        kind = {"html": "text/html", "js": "text/javascript", "css": "text/css", "woff2": "font/woff2"}[path.rsplit(".", 1)[-1]]
        self.send_response(200)
        self.send_header("Content-Type", f"{kind}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache" if path != "vazirmatn.woff2" else "public, max-age=31536000")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path not in {"/render", "/export/docx"}:
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length < 0 or length > 2_000_000:
            self.send_error(413)
            return
        try:
            payload = json.loads(self.rfile.read(length))
            source = payload["source"]
            if not isinstance(source, str):
                raise ValueError("source must be a string")
            markup = render(source)
            if self.path == "/render":
                body = json.dumps({"html": markup}, ensure_ascii=False).encode()
                content_type = "application/json; charset=utf-8"
            else:
                from docx_export import export_docx

                body = export_docx(markup, payload.get("zoom", 100), payload.get("width", 700))
                content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        except (ValueError, KeyError, TypeError, OverflowError):
            self.send_error(400)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if self.path == "/export/docx":
            self.send_header("Content-Disposition", 'attachment; filename="document.docx"')
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Persian Markdown Reader")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Persian Markdown Reader: http://{args.host}:{args.port}", flush=True)
    server.serve_forever()
