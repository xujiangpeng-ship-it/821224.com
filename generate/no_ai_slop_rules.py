# no_ai_slop_rules.py
# ---------------------------------------------------------------------------
# De-AI-slop rules integrated from the open-source project:
#   https://github.com/petergyang/no-ai-slop   (MIT License)
# Vendored 2026-09-11 to harden the article generation / rewrite pipeline
# against SEMANTIC "AI slop" patterns that Google's human reviewers flag as
# low-value content -- the patterns missing from our older punctuation/word
# bans (binary contrasts, faux-insight setups, colon reveals, importance
# puffery, weasel attribution, interpretive metadiscourse, rhetorical setups,
# negative listing, fake-profound kickers, dramatic fragments).
#
# Public exports:
#   SLOP_INSTRUCTIONS : text block to APPEND to the LLM system prompt so the
#                       model avoids these patterns when generating/rewriting.
#   audit_slop(text)  : regex detector returning the list of slop pattern ids
#                       found in a piece of text (semantic, not cosmetic).
# ---------------------------------------------------------------------------
import re

SLOP_INSTRUCTIONS = """\

================================================================
ADDITIONAL ANTI-SLOP RULES (from the no-ai-slop project, MIT)
================================================================
Beyond the vocabulary and punctuation bans above, also eliminate these
SENTENCE-LEVEL AI patterns. They are the strongest signals that text was
machine-written, and Google's human reviewers flag them as "low value":

1. BINARY CONTRASTS -- "It's not X. It's Y." / "The question isn't X, it's Y."
   State Y directly in one sentence.
2. FAUX-INSIGHT SETUPS -- "What nobody tells you", "The part everyone misses",
   "What most people get wrong", "Here's what nobody tells you". Cut the
   setup; let the claim stand on its own.
3. COLON REVEALS -- a noun phrase, a colon, then a lowercase dramatic reveal
   ("The best part: it learns."). Rewrite as a plain sentence. Use colons for
   lists and labels only, not fake drama.
4. IMPORTANCE PUFFERY -- "marks a pivotal moment", "a testament to",
   "plays a vital role", "solidifies its position", "underscores its
   significance". State the fact; let the reader judge whether it matters.
5. WEASEL ATTRIBUTION -- "experts agree", "industry reports suggest",
   "many argue", "widely regarded as", "studies show". Name the real source
   (organisation + year + report title) or delete the claim.
6. INTERPRETIVE METADISCOURSE -- "That last part matters", "The key point is",
   "As you can see", "This distinction matters", "In other words". Delete it;
   let the prose carry the meaning.
7. RHETORICAL SETUPS -- "What if I told you", "Think about it:", "Plot twist:",
   self-answered "Question? Answer." Drop them and make the point.
8. NEGATIVE LISTING -- "Not a X. Not a Y. A Z." Just say Z.
9. FAKE-PROFOUND KICKERS -- a final "deep" line that turns the point into a
   cute metaphor, aphorism, or mic-drop ("The future isn't coming. It's
   already here."). Delete it; end on the clearest concrete sentence already
   in the draft.
10. DRAMATIC FRAGMENTS -- "X. And Y. And Z." / "That's it. That's the whole
    thing." Use complete sentences.

GENERAL: Lead with the point. Be concrete (names, numbers, dates, mechanisms).
Keep the writer's real voice and useful edge. Do not flatten distinctive
sentences into uniform, tidy prose."""

# (pattern_id, compiled_regex) -- semantic patterns detectable by regex.
_SLO_PATTERNS = [
    ("binary_contrast", re.compile(r"it'?s not (?:just |only )?[^.\n]{3,40}?,? (?:it'?s|this is|that'?s|—)\b", re.I)),
    ("binary_contrast", re.compile(r"the question isn'?t\b", re.I)),
    ("faux_insight", re.compile(r"what (?:nobody|everyone|most people) (?:tells|gets|misses)|here'?s what nobody tells you|the part everyone misses|what most people get wrong", re.I)),
    ("colon_reveal", re.compile(r"\b(?:the (?:best|real|key|secret|catch|trick|detail|point|magic|kicker|reason)|what matters|here'?s the thing|why it matters):\s+[a-z]", re.I)),
    ("importance_puffery", re.compile(r"marks? a pivotal moment|(?:(?:a|the)\s+)?testament to|plays? a vital role|solidifies? (?:its|their|the) position|underscores? (?:its|their|the) significance|\bbeacon of\b|\btapestry of\b", re.I)),
    ("weasel_attribution", re.compile(r"experts (?:agree|believe|argue)|industry reports? suggest|many argue|widely regarded as|studies show|research indicates|observers (?:have )?(?:noted|cited)|some critics argue", re.I)),
    ("interpretive_metadiscourse", re.compile(r"that last part matters|the key point is|as you can see|this distinction matters|in other words,|here'?s why (?:this|it) matters|what this means is", re.I)),
    ("rhetorical_setup", re.compile(r"what if i told you|think about it:|plot twist:|here'?s a thought:|consider this:", re.I)),
    ("negative_listing", re.compile(r"not a [^.\n]{3,40}?\.\s*not a [^.\n]{3,40}?\.", re.I)),
    ("fake_profound_kicker", re.compile(r"the future isn'?t coming\. it'?s already here|that'?s it\. that'?s the (?:whole )?(?:thing|point|secret)|this is what [^.]+ looks like", re.I)),
    ("summary_recap", re.compile(r"in conclusion|to sum (?:up|it)|in summary|wrapping (?:it )?up", re.I)),
    ("emoji_heading", re.compile(r"#[^#\n]*[\U0001F300-\U0001F9FF\u2600-\u27BF]")),
]

_EM_DASH = "—–"  # em dash + en dash


def audit_slop(text: str):
    """Return the list of semantic slop pattern ids found in `text`."""
    if not text:
        return []
    hits = []
    for name, rx in _SLO_PATTERNS:
        if rx.search(text):
            hits.append(name)
    if any(ch in text for ch in _EM_DASH):
        hits.append("em_dash")
    # de-dupe while preserving order
    seen = set()
    out = []
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


if __name__ == "__main__":
    import sys
    sample = sys.stdin.read()
    found = audit_slop(sample)
    print("slop patterns found:", found if found else "none")
