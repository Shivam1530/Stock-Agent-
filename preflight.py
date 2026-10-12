"""Deterministic preflight: do the things LLMs are unreliable at *before* the LLM runs.

1. Parse front matter, assign stable source IDs, tier sources by trust.
2. Quarantine prompt-injection text (removed from what the model sees, reported separately).
3. Flag stale sources relative to the as-of date.
4. Flag possible wrong-entity sources (similar name, different company).
5. Reconcile reported revenue across sources against EBITDA / EBITDA-margin.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path

TIERS = {  # front-matter `type` keyword -> (tier, label)
    "exchange filing": (1, "T1 exchange filing"),
    "official company": (2, "T2 company statement"),
    "news": (3, "T3 news"),
    "blog": (4, "T4 blog/tips (not evidence)"),
}
STALE_DAYS = 180

INJECTION_PATTERNS = [
    re.compile(r"<!--.*?-->", re.S),  # hidden HTML comments
    re.compile(r"ignore (all )?(previous|prior|above) instructions", re.I),
    re.compile(r"(note|message|instruction)s? (for|to) (ai|llm|assistant|summar)", re.I),
    re.compile(r"do not mention (this|the) (note|instruction)", re.I),
    re.compile(r"(system prompt|you are now|disregard (your|the) (rules|guidelines))", re.I),
]


@dataclass
class Source:
    sid: str = ""
    path: str = ""
    source: str = ""
    url: str = ""
    published: dt.date | None = None
    type: str = ""
    tier: int = 9
    tier_label: str = ""
    body: str = ""  # sanitized body shown to the model
    raw_body: str = ""
    age_days: int = 0
    stale: bool = False
    injections: list[str] = field(default_factory=list)
    entity_flags: list[str] = field(default_factory=list)


def parse_front_matter(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, m.group(2).strip()


def classify(type_str: str) -> tuple[int, str]:
    t = type_str.lower()
    for key, val in TIERS.items():
        if key in t:
            return val
    return 3, "T3 news (unclassified type)"


def quarantine_injections(body: str) -> tuple[str, list[str]]:
    found: list[str] = []
    clean = body
    for pat in INJECTION_PATTERNS:
        for m in pat.finditer(clean):
            found.append(m.group(0).strip())
        clean = pat.sub("[REMOVED: suspected prompt-injection text]", clean)
    # de-duplicate while keeping order
    seen, uniq = set(), []
    for f in found:
        if f not in seen:
            seen.add(f)
            uniq.append(f)
    return clean, uniq


def entity_check(body: str, company: str, ticker: str) -> list[str]:
    """Flag mentions of look-alike names (same first word, not the legal name)."""
    stem = company.split()[0]
    pat = re.compile(rf"{re.escape(stem)}\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?")
    variants = {m.group(0) for m in pat.finditer(body)}
    legal = company.lower().rstrip(".")
    flags = []
    has_ticker = ticker.lower() in body.lower()
    for v in sorted(variants):
        if not legal.startswith(v.lower()) and not v.lower().startswith(legal.split(" ltd")[0]):
            if not has_ticker:
                flags.append(f"mentions '{v}' (not '{company}'), no ticker {ticker} in text")
    return flags


def load_sources(pack_dir: Path, as_of: dt.date, company: str, ticker: str) -> list[Source]:
    srcs: list[Source] = []
    for p in sorted(pack_dir.glob("*.md")):
        meta, body = parse_front_matter(p.read_text(encoding="utf-8"))
        s = Source(path=p.name, source=meta.get("source", p.stem), url=meta.get("url", ""),
                   type=meta.get("type", ""), raw_body=body)
        try:
            s.published = dt.date.fromisoformat(meta.get("published", ""))
        except ValueError:
            s.published = None
        s.tier, s.tier_label = classify(s.type)
        s.body, s.injections = quarantine_injections(body)
        if s.published:
            s.age_days = (as_of - s.published).days
            s.stale = s.age_days > STALE_DAYS
        s.entity_flags = entity_check(body, company, ticker)
        srcs.append(s)
    # stable IDs: best tier first, then newest first
    srcs.sort(key=lambda s: (s.tier, -(s.published.toordinal() if s.published else 0)))
    for i, s in enumerate(srcs, 1):
        s.sid = f"S{i}"
    return srcs


# ---------- numeric reconciliation ----------
_NUM = r"([\d,]+(?:\.\d+)?)"


def _f(x: str) -> float:
    return float(x.replace(",", ""))


def reconcile_revenue(srcs: list[Source]) -> list[str]:
    """Find a table with EBITDA + margin to imply revenue, then test every revenue claim."""
    notes: list[str] = []
    implied = None
    ref = None
    for s in srcs:
        e = re.search(rf"\|\s*EBITDA\s*\|\s*{_NUM}\s*\|", s.raw_body)
        m = re.search(rf"\|\s*EBITDA margin\s*\|\s*{_NUM}%", s.raw_body)
        if e and m:
            implied = _f(e.group(1)) / (_f(m.group(1)) / 100)
            ref = (s.sid, _f(e.group(1)), _f(m.group(1)))
            break
    if not implied:
        return ["No EBITDA+margin pair found; revenue claims could not be reconciled."]
    notes.append(f"{ref[0]} reports EBITDA {ref[1]:g} and margin {ref[2]:g}% -> implied revenue ~{implied:,.0f}.")
    for s in srcs:
        for m in re.finditer(rf"[Rr]evenue[^.\n]{{0,80}}?₹\**\s*{_NUM}\s*crore", s.raw_body):
            claim = _f(m.group(1))
            gap = abs(claim - implied) / implied
            pct = re.search(rf"{_NUM}%", s.raw_body[m.end():m.end() + 60])
            tag = "CONSISTENT" if gap < 0.03 else "CONFLICT"
            extra = f" (claimed growth {pct.group(1)}%)" if pct else ""
            notes.append(f"{s.sid} says revenue {claim:,.0f} crore{extra}: {tag}; "
                         f"EBITDA/{claim:,.0f} = {ref[1] / claim * 100:.1f}% vs stated margin {ref[2]:g}%.")
        if s.sid == ref[0]:
            continue
        for m in re.finditer(rf"[Rr]evenue (?:up|rose|jump\w*|grew|growth)[^.\n]{{0,20}}?{_NUM}%", s.raw_body):
            if not re.search(r"crore", s.raw_body[max(0, m.start() - 5):m.end() + 40]):
                notes.append(f"{s.sid} repeats a revenue growth claim of {m.group(1)}% without an amount "
                             f"(check against the highest-tier source).")
    return notes


def build_report(srcs: list[Source], as_of: dt.date, company: str, ticker: str) -> str:
    L = [f"PREFLIGHT REPORT for {company} ({ticker}), as of {as_of.isoformat()}", "",
         "Source registry (use these IDs when citing):"]
    for s in srcs:
        L.append(f"- {s.sid} | {s.tier_label} | published {s.published} ({s.age_days} days old) | {s.source} | {s.url}")
    L += ["", "Flags:"]
    flags = 0
    for s in srcs:
        if s.stale:
            L.append(f"- {s.sid} is STALE ({s.age_days} days old): historical context only, not current.")
            flags += 1
        for f in s.entity_flags:
            L.append(f"- {s.sid} POSSIBLE WRONG ENTITY: {f}.")
            flags += 1
        if s.injections:
            kinds = ["hidden HTML comment" if i.startswith("<!--") else "inline instruction text" for i in s.injections]
            L.append(f"- {s.sid} contained PROMPT-INJECTION text aimed at AI tools ({', '.join(kinds)}, "
                     f"{sum(len(i) for i in s.injections)} chars). It was removed and is deliberately NOT quoted here.")
            flags += 1
        if s.tier == 4:
            L.append(f"- {s.sid} is T4 (tips/blog): not evidence.")
            flags += 1
    if not flags:
        L.append("- none")
    L += ["", "Numeric cross-checks:"] + [f"- {n}" for n in reconcile_revenue(srcs)]
    return "\n".join(L)


def build_user_message(srcs: list[Source], report: str, ticker: str, company: str, as_of: dt.date) -> str:
    parts = [f"Ticker: {ticker}\nCompany: {company}\nToday: {as_of.isoformat()}\n", report, "\nSOURCES:\n"]
    for s in srcs:
        parts.append(f'<source id="{s.sid}" tier="{s.tier_label}" published="{s.published}" url="{s.url}">\n'
                     f"{s.body}\n</source>\n")
    parts.append("\nWrite the research brief now, following the system prompt exactly.")
    return "\n".join(parts)
