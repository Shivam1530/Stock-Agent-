# Stock-Agent- — SRVCABLE research-brief agent (Super Investing, AI Innovator Part B)

Input: an NSE ticker + a folder of scraped documents. Output: a one-page Markdown brief (Snapshot / Bull / Bear / Open questions / Sources) for a retail investor.

## How it thinks (the design in one picture)

```
research_pack/*.md
      │
      ▼
 1. PREFLIGHT  (preflight.py, plain code, no LLM)
      • parse source/url/date, assign IDs S1..Sn, tier by trust (T1 exchange filing → T4 tips blog)
      • quarantine prompt-injection text (removed from what the model sees)
      • flag stale sources (>180 days) and look-alike company names (wrong entity)
      • reconcile revenue claims against EBITDA ÷ margin (catches the 1,248 vs 1,428 conflict)
      ▼
 2. WRITE      (prompts/system_prompt.md + one LLM call)
      • documents are wrapped in <source> tags and treated as data, never as instructions
      • conflict rules: highest tier wins, show both numbers, say why
      • every sentence cited [S#]; derived numbers show their arithmetic; no buy/sell/targets
      ▼
 3. VERIFY     (verify.py, plain code)
      • all 5 sections present, citations resolve, every source listed
      • no banned phrases, no injected text repeated, numbers grounded or marked derived
      • on failure: one repair pass with the checker's complaints fed back
      ▼
 output/brief.md
```

Rationale: LLMs are good at synthesis and weak at three things this task tests: obeying text hidden in documents, noticing that two sources disagree, and checking their own arithmetic. Those are handled by code, so the model's job is only to write.

## Files
| File | What |
|---|---|
| `prompts/system_prompt.md` | The system prompt / skill file (separate, as required) |
| `preflight.py` | Source tiering, injection quarantine, staleness, entity and number checks |
| `verify.py` | Post-generation checks |
| `llm.py` | Stdlib-only client for Anthropic or any OpenAI-compatible API |
| `agent.py` | Orchestrator / CLI |
| `research_pack/` | The 8 SRVCABLE documents |
| `output/brief_SRVCABLE_reference.md` | Reference brief (see note below) |
| `TEST_LOG.md`, `VIDEO_SCRIPT.md` | Submission items 3 and 4 |

## Run it
No dependencies (Python 3.10+).

```bash
# Anthropic (default model: claude-sonnet-5-5)
export ANTHROPIC_API_KEY=...
python agent.py --ticker SRVCABLE --company "Sarvottam Cables Ltd" --pack research_pack --out output/brief.md

# Free-tier alternative: Gemini via its OpenAI-compatible endpoint
export LLM_PROVIDER=openai OPENAI_API_KEY=... LLM_MODEL=gemini-2.0-flash \
       OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
python agent.py --out output/brief_gemini.md

# See exactly what the model receives, without calling any API
python agent.py --dry-run
```
`--as-of` defaults to 2026-09-23, the date the assignment says to assume. The preflight audit trail (including the verbatim removed injection text) is written to `logs/`.

### Local dashboard

Run `python dashboard.py` and open `http://127.0.0.1:8765`. It reads the research pack and `output/brief_ollama_latest.md`, recalculates verifier status, and shows source flags and the revenue conflict. It is read-only and binds to localhost.

### Optional Groww live quote

The `--live-quote` option fetches an NSE cash-market quote and adds it as a cited source. It requires an active Groww Trading API subscription and a current access token; Groww access tokens expire daily at 6:00 AM. Set the token in the current PowerShell window and use a research pack for the same real company:

```powershell
$env:GROWW_ACCESS_TOKEN = "<your current Groww access token>"
python agent.py --ticker RELIANCE --company "Reliance Industries Ltd" `
  --pack path\to\reliance_research_pack --as-of (Get-Date -Format yyyy-MM-dd) `
  --live-quote --out output\reliance_brief.md
```

The Groww trading symbol defaults to `--ticker`; use `--groww-symbol` if it differs. The live quote is optional and is not requested for the fictional SRVCABLE assignment run. This integration only reads quote data; it does not place trades.

## Models and why
Default **Claude Sonnet** (`claude-sonnet-5-5`), temperature 0.2: follows a long, rule-heavy system prompt reliably, resists instructions embedded in documents, and is cheap enough for per-ticker use. Any other model works through `llm.py`; comparing a second model on the same pack is a good test-log entry.

## Honest status
- The code was exercised end to end here against a **mock LLM server** (request format, verifier, repair pass) but **not against a live model**, because no API key was available in the build environment.
- `output/brief_SRVCABLE_reference.md` was written by Claude in the build chat by following `system_prompt.md` by hand. It passes `verify.py`. It is **not** output of `agent.py`. For submission, run the agent yourself and paste *that* output, or say plainly that you used the reference and what you changed.

## Known limitations
- Revenue reconciliation and the look-alike-name check are regex heuristics tuned to this pack's format; other packs need the patterns widened.
- The verifier checks form (citations, numbers, banned phrases), not whether a claim is semantically true.
- Injection defence is layered (pattern quarantine + data/instruction separation in the prompt) but not a guarantee against novel phrasings.
- No live data: valuation and current price are reported as missing rather than guessed. Adding a price/news tool is the obvious next step.
