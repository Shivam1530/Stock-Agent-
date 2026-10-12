#!/usr/bin/env python3
"""Read-only local dashboard for the saved SRVCABLE research brief."""
import datetime as dt
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import preflight
import verify

ROOT = Path(__file__).parent
BRIEF = ROOT / "output" / "brief_ollama_latest.md"
AS_OF = dt.date.fromisoformat("2026-09-23")


def dashboard_state() -> dict:
    sources = preflight.load_sources(ROOT / "research_pack", AS_OF, "Sarvottam Cables Ltd", "SRVCABLE")
    report = preflight.build_report(sources, AS_OF, "Sarvottam Cables Ltd", "SRVCABLE")
    brief = BRIEF.read_text(encoding="utf-8") if BRIEF.exists() else ""
    problems = verify.verify(brief, sources) if brief else ["No saved brief found."]
    return {
        "company": "Sarvottam Cables Ltd",
        "ticker": "SRVCABLE",
        "as_of": AS_OF.isoformat(),
        "output_name": BRIEF.name,
        "updated": dt.datetime.fromtimestamp(BRIEF.stat().st_mtime).astimezone().isoformat(timespec="minutes") if BRIEF.exists() else None,
        "brief": brief,
        "report": report,
        "sources": [{
            "id": s.sid, "name": s.source, "type": s.tier_label,
            "published": s.published.isoformat() if s.published else "Unknown",
            "age_days": s.age_days, "stale": s.stale,
            "wrong_entity": bool(s.entity_flags), "injection_removed": bool(s.injections),
        } for s in sources],
        "checks": problems,
        "verified": not any(not p.startswith("WARN") for p in problems),
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        route = urlsplit(self.path).path
        if route == "/":
            body = (ROOT / "dashboard.html").read_bytes()
            content_type = "text/html; charset=utf-8"
        elif route == "/api/state":
            body = json.dumps(dashboard_state(), ensure_ascii=False).encode("utf-8")
            content_type = "application/json; charset=utf-8"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    print("SRVCABLE dashboard: http://127.0.0.1:8765")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
