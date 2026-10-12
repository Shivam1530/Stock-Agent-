"""Post-hoc verifier: cheap deterministic checks on the generated brief. Returns a list of problems."""
from __future__ import annotations

import re

BANNED = [r"\bstrong buy\b", r"\bmultibagger\b", r"\bprice target\b", r"\btarget (price )?of\b",
          r"\byou should (buy|sell)\b", r"\b(buy|sell) (now|this)\b", r"analyst consensus (is|was) positive"]
SECTIONS = ["Snapshot", "Bull case", "Bear case", "Open questions", "Sources"]


def _num_tokens(text: str) -> set[str]:
    return {n.replace(",", "") for n in re.findall(r"\d[\d,]*\.?\d*", text) if len(n.replace(",", "")) >= 2}


def verify(brief: str, srcs) -> list[str]:
    problems: list[str] = []
    ids = {s.sid for s in srcs}
    # 1 structure
    for sec in SECTIONS:
        if not re.search(rf"^#+\s*\d*\.?\s*{sec}", brief, re.I | re.M):
            problems.append(f"missing section: {sec}")
    # 2 citations resolve
    cited = set(re.findall(r"\[(S\d+)", brief)) | set(re.findall(r"\bS\d+\b", brief))
    for c in cited - ids:
        problems.append(f"citation to unknown source {c}")
    body, _, table = brief.partition("## 5.")
    for s in srcs:
        if s.sid not in table:
            problems.append(f"source {s.sid} missing from Sources table")
    # 3 injected / banned content
    analysis = body.partition("## 4.")[0]
    for pat in BANNED:
        if re.search(pat, analysis, re.I):
            problems.append(f"banned phrase matched: {pat}")
    for s in srcs:
        for inj in s.injections:
            if inj[:40].lower() in brief.lower():
                problems.append(f"brief repeats injected text from {s.sid}")
    # 4 every bullet/sentence with a number has a citation
    for line in body.splitlines():
        if line.strip().startswith(("-", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")) and re.search(r"\d", line):
            if not re.search(r"\[S\d", line) and "derived" not in line.lower():
                problems.append(f"uncited numeric line: {line.strip()[:80]}")
    # 5 numbers grounded in sources (warn only; lines marked "derived" are exempt)
    src_vals = [float(n) for s in srcs for n in _num_tokens(s.raw_body) if re.fullmatch(r"\d+\.?\d*", n)]
    month = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    for line in body.splitlines():
        if line.lstrip().startswith(("#", "*As of")) or "derived" in line.lower():
            continue
        line = re.sub(rf"\b\d{{1,2}} {month}\w* ?\d{{0,4}}", "", line)  # dates
        line = re.sub(r"^\s*\d+\.\s", "", line)  # list numbering
        line = re.sub(r"\bS\d\b|\bQ\d\b|\bFY\d+\b|\bH\d\b|\bT\d\b", "", line)
        for n in _num_tokens(line):
            try:
                v = float(n.rstrip("."))
            except ValueError:
                continue
            if v in (2024, 2025, 2026) or any(abs(v - sv) <= 0.5 for sv in src_vals):
                continue
            problems.append(f"WARN number not found in any source and line not marked derived: {n} in '{line.strip()[:60]}'")
    # 6 length
    words = len(body.split())
    if words > 700:
        problems.append(f"too long for ~1 page: {words} words before sources")
    return problems
