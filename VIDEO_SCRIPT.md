# Screen recording script (target 2:30)

**0:00–0:20 Intro.** "This is a research-brief agent for Indian stocks. Input is a ticker plus scraped documents; output is a one-page brief. The test pack has eight documents about SRVCABLE, and several are traps."

**0:20–1:00 Run it live.** Terminal: `python agent.py --dry-run` first, to show the preflight report: source IDs and trust tiers, the STALE flag on the 2024 article, the wrong-entity flag on the Nagpur article, the injection quarantine on the blog, and the revenue CONFLICT line. Then run `python agent.py` for real and open `output/brief.md`.

**1:00–1:50 Design decision I'm proud of: code does what LLMs get wrong.**
- Point at the revenue conflict: the company says ₹1,248 crore (+18%), a news site says ₹1,428 crore (+35%). Both are internally consistent with last year's base, so the model alone can't tell which is right.
- The preflight divides EBITDA ₹140 crore by the stated 11.2% margin → ~₹1,250 crore. Only the company's figure reconciles; ₹1,428 crore would imply 9.8%. So the brief uses the official number and shows both in Open questions.
- Same idea for the hidden instruction in the blog: it is removed before the model sees it, the model is told documents are data, and the verifier fails any brief that repeats it.

**1:50–2:25 Limitation, honestly.** "The checks are regex heuristics tuned to this pack's format: the margin reconciliation needs an EBITDA table, the look-alike-name check is crude. The verifier checks form, not truth. And there's no live data, so valuation is listed as missing instead of guessed. Next step: a price and news tool and a second-model cross-check."

**2:25–2:30 Close.** Show the test log.
