#!/usr/bin/env python3
"""Research-brief agent.  python agent.py --ticker SRVCABLE --company "Sarvottam Cables Ltd" --pack research_pack

Pipeline:  preflight (deterministic)  ->  LLM draft  ->  verify (deterministic)  ->  one repair pass if needed
"""
import argparse
import datetime as dt
import sys
from pathlib import Path

import preflight
import verify
from llm import complete
from groww import get_quote

ROOT = Path(__file__).parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", default="SRVCABLE")
    ap.add_argument("--company", default="Sarvottam Cables Ltd")
    ap.add_argument("--pack", default=str(ROOT / "research_pack"))
    ap.add_argument("--as-of", default="2026-09-23", help="YYYY-MM-DD ('today' for the agent)")
    ap.add_argument("--prompt", default=str(ROOT / "prompts" / "system_prompt.md"))
    ap.add_argument("--out", default=str(ROOT / "output" / "brief.md"))
    ap.add_argument("--dry-run", action="store_true", help="print preflight + assembled prompt, no LLM call")
    ap.add_argument("--live-quote", action="store_true", help="include a current Groww NSE cash quote (requires GROWW_ACCESS_TOKEN)")
    ap.add_argument("--groww-symbol", help="Groww trading symbol; defaults to --ticker")
    a = ap.parse_args()

    as_of = dt.date.fromisoformat(a.as_of)
    srcs = preflight.load_sources(Path(a.pack), as_of, a.company, a.ticker)
    if a.live_quote:
        if as_of != dt.date.today():
            raise SystemExit(f"Live quotes require --as-of {dt.date.today().isoformat()} so the brief date matches the quote.")
        payload = get_quote(a.groww_symbol or a.ticker)
        fetched = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        fields = ("last_price", "day_change", "day_change_perc", "ohlc", "volume",
                  "week_52_high", "week_52_low", "market_cap")
        quote_body = "\n".join(f"{key}: {payload[key]}" for key in fields if key in payload)
        if "last_price" not in payload:
            raise SystemExit("Groww quote response did not include last_price.")
        srcs.append(preflight.Source(
            sid=f"S{len(srcs) + 1}", path="groww_live_quote", source=f"Groww live quote ({fetched})",
            url="https://api.groww.in/v1/live-data/quote", type="live quote",
            tier=5, tier_label="Live market data", body=quote_body, raw_body=quote_body,
            published=as_of,
        ))
    report = preflight.build_report(srcs, as_of, a.company, a.ticker)
    user_msg = preflight.build_user_message(srcs, report, a.ticker, a.company, as_of)
    system = Path(a.prompt).read_text(encoding="utf-8")
    if a.live_quote:
        system += ("\n\nA source labeled 'Live market data' is Groww's current quote snapshot. "
                   "Use it only for current market-price facts and cite its source ID. "
                   "Do not treat it as company fundamentals or as evidence for the historical pack date. "
                   "Clearly state the retrieval date when using it.")

    print(report, file=sys.stderr)
    # full audit trail for the human (verbatim removed text), never sent to the model
    log = ROOT / "logs" / f"preflight_{dt.datetime.now():%Y%m%d_%H%M%S}.txt"
    log.parent.mkdir(exist_ok=True)
    log.write_text(report + "\n\nVERBATIM REMOVED TEXT (audit only):\n" +
                   "\n".join(f"{s.sid}: {i}" for s in srcs for i in s.injections), encoding="utf-8")
    if a.dry_run:
        print("\n----- USER MESSAGE -----\n" + user_msg)
        return 0

    brief = complete(system, user_msg)
    problems = [p for p in verify.verify(brief, srcs)]
    hard = [p for p in problems if not p.startswith("WARN")]
    if hard:
        print("\nVerifier found problems, running one repair pass:\n- " + "\n- ".join(hard), file=sys.stderr)
        fix = (user_msg + "\n\nYOUR PREVIOUS DRAFT:\n" + brief +
               "\n\nA checker found these problems. Fix them and output the full corrected brief only:\n- " +
               "\n- ".join(hard))
        brief = complete(system, fix)
        problems = verify.verify(brief, srcs)

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(brief, encoding="utf-8")
    print(f"\nWrote {a.out}", file=sys.stderr)
    for p in problems:
        print("  verifier:", p, file=sys.stderr)
    return 1 if [p for p in problems if not p.startswith("WARN")] else 0


if __name__ == "__main__":
    sys.exit(main())
