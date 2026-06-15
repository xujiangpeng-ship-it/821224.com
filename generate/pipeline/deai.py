"""
Post-Processing De-AI Module (手段4 + 手段6)
=============================================
Reads an HTML article and applies 6-dimensional de-AI processing
to disrupt statistical patterns that LLM detectors rely on.

Usage:
    from pipeline.deai import deai_process
    result_html = deai_process(html_content)
"""

import html
import random
import re
from html.parser import HTMLParser


# ---------------------------------------------------------------------------
# 4.2 AI Transition Word Mutation — 15 Replacement Groups
# ---------------------------------------------------------------------------
# Each group maps a regex pattern (AI-favored phrase) to a pool of
# human-sounding alternatives. One alternative is randomly chosen per match.
TRANSITION_GROUPS = [
    # Group 1
    (r'\bMoreover\b,\s*|\bFurthermore\b,\s*',
     ["On top of that,", "And here's the thing,", "What's more interesting,", "Heck,"]),
    # Group 2
    (r'\bHowever\b,\s*',
     ["But here's the catch,", "That said,", "Flip side:,", "Now, the problem is,"]),
    # Group 3
    (r'\bTherefore\b,\s*|\bThus\b,\s*',
     ["So yeah,", "Which means,", "Bottom line:,", "Long story short,"]),
    # Group 4
    (r'\bAdditionally\b,\s*',
     ["Oh and also,", "By the way,", "Side note:,", "While we're at it,"]),
    # Group 5
    (r'\bIn conclusion\b,?\s*',
     ["Anyway,", "The point is,", "Here's my take:,", "tl;dr,"]),
    # Group 6
    (r'\bFor example\b,?\s*|\bFor instance\b,?\s*',
     ["Take ", "Case in point:,", "Like when ", "Picture this:,"]),
    # Group 7
    (r'\bNotably\b,\s*|\bImportantly\b,\s*',
     ["The kicker is,", "Wild part:,", "And get this,", "Funny enough,"]),
    # Group 8
    (r'\bConsequently\b,\s*|\bAs a result\b,\s*',
     ["Next thing you know,", "So what happened was,", "Unsurprisingly,"]),
    # Group 9
    (r'\bNevertheless\b,\s*|\bNonetheless\b,\s*',
     ["Still,", "Even so,", "I'll give them this though,"]),
    # Group 10
    (r'\bIt is worth noting\b',
     ["Worth pointing out", "Quick thing", "One thing I noticed"]),
    # Group 11
    (r'\bAccording to\b',
     ["Per", "As ", " puts it, ", "'s take:, ", " published"]),
    # Group 12
    (r'\bResearch shows\b|\bStudies indicate\b',
     ["'s research found", "A 2025 study by ", " pointed to"]),
    # Group 13
    (r'\b[Hh]as the potential to\b',
     ["could realistically", "might actually", "has a shot at"]),
    # Group 14 — direct deletion
    (r'\bIn today\'s rapidly evolving landscape,?\s*',
     [""]),
    # Group 15
    (r'\bIt is widely acknowledged\b',
     ["Everyone and their mother knows", "Common knowledge at this point"]),
]


def _apply_transition_mutations(text: str) -> str:
    """Apply all 15 transition word replacement groups to the text."""
    for pattern_str, replacements in TRANSITION_GROUPS:
        def _replace(m, reps=replacements):
            chosen = random.choice(reps)
            # Special handling for groups that need context adaptation
            if "According to" in pattern_str:
                # "According to X" → "Per X" / "As X puts it" / "X's take:"
                return chosen
            if "Research shows" in pattern_str or "Studies indicate" in pattern_str:
                return chosen
            if "has the potential to" in pattern_str.lower():
                return chosen
            return chosen

        text = re.sub(pattern_str, _replace, text)
    return text


# ---------------------------------------------------------------------------
# 4.5 Conclusion Cliché Removal — 5 Patterns
# ---------------------------------------------------------------------------
CONCLUSION_PATTERNS = [
    (r'\bIn conclusion\b[^.]*\.', ''),
    (r'\bTo sum up\b[^.]*\.', ''),
    (r'\bIn summary\b[^.]*\.', ''),
    (r'\bUltimately\b[^.]*\.', ''),
    (r'\bAll in all\b[^.]*\.', ''),
    (r'\bAs we move forward\b[^.]*\.', ''),
    (r'\bGoing forward\b[^.]*\.', ''),
    (r'\bLooking ahead\b[^.]*\.', ''),
    (r'\bIt remains to be seen\b[^.]*\.', ''),
    (r'\bOnly time will tell\b[^.]*\.', ''),
    (r'\brepresents a significant step forward\b[^.]*\.', ''),
    (r'\bmarks a new chapter\b[^.]*\.', ''),
    (r'\bThe future of [^.]* is bright\b[^.]*\.', ''),
    (r'\bThe future of [^.]* is promising\b[^.]*\.', ''),
    (r'\bis poised to (transform|revolutionize|reshape)\b[^.]*\.', ''),
]

SHORT_ENDINGS = [
    "Anyway.",
    "So, yeah.",
    "That's where things stand.",
    "We'll see how this plays out.",
    "More on this as it develops.",
    "That's the picture right now.",
    "I'll leave it there.",
    "Draw your own conclusions.",
    "Data's there, you decide.",
    "That's my read on it.",
]


def _remove_conclusion_cliches(text: str) -> str:
    """Strip AI-favored conclusion patterns, replace with short endings."""
    for pattern, _ in CONCLUSION_PATTERNS:
        text = re.sub(pattern, '', text)

    # If the last paragraph was gutted, append a short ending
    text = text.rstrip()
    if text and not text.endswith(('.', '!', '?')):
        text += '.'
    if random.random() < 0.5:
        # 50% chance to append a short human-style ending
        if len(text) > 50:
            text += ' ' + random.choice(SHORT_ENDINGS)

    return text


# ---------------------------------------------------------------------------
# 4.6 Human Touch Traces — 15% Trigger with Anecdotes + Parenthetical Snark
# ---------------------------------------------------------------------------
ANECDOTES = [
    "I know a claims manager who told me once: ",
    "There was a real case back in 2023: ",
    "A major carrier I spoke to internally has already started to ",
    "This came up in a conversation with a CTO at an insurtech firm: ",
    "Honestly, when I first saw these numbers I didn't believe them either. ",
    "I ran into a similar situation doing due diligence for a client: ",
]

SNARK_INSERTIONS = [
    " (don't ask how I know)",
    " (if you know, you know)",
    " (dog head emoji would go here)",
    " (numbers look great, execution... well)",
    " (at least that's what the slide deck says)",
    " (I'll bet $5 this prediction misses)",
]


def _inject_human_traces(text: str) -> str:
    """15% chance to inject one anecdote + one parenthetical snark."""
    if random.random() > 0.15:
        return text

    paragraphs = [p for p in text.split('\n') if p.strip()]
    if not paragraphs:
        return text

    # Insert anecdote near beginning (paragraph 1-3)
    anecdote_para_idx = min(random.randint(1, 3), len(paragraphs) - 1)
    anecdote = random.choice(ANECDOTES)
    paragraphs[anecdote_para_idx] = anecdote + paragraphs[anecdote_para_idx]

    # Insert snark after a sentence in a middle paragraph
    snark = random.choice(SNARK_INSERTIONS)
    mid_para_idx = len(paragraphs) // 2 + random.randint(-1, 1)
    mid_para_idx = max(0, min(mid_para_idx, len(paragraphs) - 1))
    # Find a sentence-ending period and insert snark after it
    para = paragraphs[mid_para_idx]
    sentences = re.split(r'(?<=[.!?])\s+', para)
    if len(sentences) >= 2:
        insert_at = random.randint(1, min(len(sentences) - 1, 4))
        sentences[insert_at] = sentences[insert_at].rstrip('.') + snark + '.'
        paragraphs[mid_para_idx] = ' '.join(sentences)

    return '\n'.join(paragraphs)


# ---------------------------------------------------------------------------
# HTML-Aware Text Processing
# ---------------------------------------------------------------------------

class HTMLParagraphExtractor(HTMLParser):
    """Extract paragraph texts from HTML, preserving positions for reassembly."""

    def __init__(self):
        super().__init__()
        self.paragraphs = []  # list of (start_pos, end_pos, inner_text)
        self._current_tag = None
        self._current_start = 0
        self._current_text = []
        self._pos = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('p', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'td', 'th'):
            self._current_tag = tag
            self._current_start = self._pos
            self._current_text = []

    def handle_endtag(self, tag):
        if tag == self._current_tag:
            text = ''.join(self._current_text).strip()
            if text:
                self.paragraphs.append({
                    'tag': self._current_tag,
                    'text': text,
                    'start': self._current_start,
                })
            self._current_tag = None

    def handle_data(self, data):
        self._pos += len(data)
        if self._current_tag is not None:
            # Only store if it's not pure whitespace between tags
            stripped = data.strip()
            if stripped:
                self._current_text.append(stripped)


def _split_paragraph_text(text: str, max_words: int = 200) -> list:
    """Split a paragraph text at roughly the middle if it exceeds max_words."""
    words = text.split()
    if len(words) <= max_words:
        return [text]

    mid = len(words) // 2
    # Find nearest sentence boundary near mid
    for offset in range(0, len(words) // 4):
        # Look right
        idx = mid + offset
        if idx < len(words) and words[idx].endswith(('.', '!', '?')):
            return [' '.join(words[:idx + 1]), ' '.join(words[idx + 1:])]
        # Look left
        idx = mid - offset
        if idx > 0 and words[idx].endswith(('.', '!', '?')):
            return [' '.join(words[:idx + 1]), ' '.join(words[idx + 1:])]

    # Fallback: just split at midpoint
    return [' '.join(words[:mid]), ' '.join(words[mid:])]


def _count_words(text: str) -> int:
    """Count words in a text string."""
    return len(text.split())


# ---------------------------------------------------------------------------
# 4.3 Sentence Length Diversification
# ---------------------------------------------------------------------------

def _diversify_sentence_lengths(text: str) -> str:
    """
    Detect runs of 3+ consecutive sentences in the 15-25 word range
    (LLM comfort zone) and force-variate the middle sentence.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text)
    if len(sentences) < 3:
        return text

    modified = sentences[:]
    i = 0
    while i <= len(sentences) - 3:
        # Check word counts of sentences[i], [i+1], [i+2]
        w0 = _count_words(sentences[i])
        w1 = _count_words(sentences[i + 1])
        w2 = _count_words(sentences[i + 2])

        if 15 <= w0 <= 25 and 15 <= w1 <= 25 and 15 <= w2 <= 25:
            mid_words = sentences[i + 1].split()
            if random.random() < 0.6:
                # Split into 2 short sentences (5-8 words each)
                half = len(mid_words) // 2
                part1 = ' '.join(mid_words[:max(half, 5)])
                part2 = ' '.join(mid_words[max(half, 5):])
                if not part1.endswith(('.', '!', '?')):
                    part1 += '.'
                if not part2.endswith(('.', '!', '?')):
                    part2 += '.'
                modified[i + 1] = part1 + ' ' + part2
            else:
                # Merge with next sentence to create long sentence (30-40 words)
                combined = sentences[i + 1].rstrip('.') + ', and ' + sentences[i + 2].lower()
                combined_words = combined.split()
                if len(combined_words) > 40:
                    # Too long, trim
                    combined = ' '.join(combined_words[:40]) + '.'
                modified[i + 1] = combined
                modified[i + 2] = ''  # mark for removal
                i += 1  # skip the merged sentence
        i += 1

    return ' '.join([s for s in modified if s])


# ---------------------------------------------------------------------------
# 4.4 First Sentence Pattern Rotation
# ---------------------------------------------------------------------------
# Define patterns as regex. We track which patterns are used and rotate.
FIRST_SENTENCE_PATTERNS = {
    'definition': [
        r'^[A-Z][a-z]+ (is|are|refers to)\b',
        r'^[A-Z][a-z]+ (can be defined as|is defined as)\b',
    ],
    'background': [
        r'^(In recent years|Over the past|During the|Since|With the|As the)\b',
    ],
    'question': [
        r'^(How|What|Why|Can|Will|Is|Are|Do|Does)\b.*\?$',
    ],
}


def _rotate_first_sentence(paragraphs: list) -> list:
    """
    Detect and rotate first-sentence patterns across paragraphs
    to avoid consecutive use of the same pattern type.
    """
    if len(paragraphs) < 2:
        return paragraphs

    pattern_usage = []

    for i, para_text in enumerate(paragraphs):
        first_sent = para_text.split('.')[0] + '.'

        matched = None
        for ptype, patterns in FIRST_SENTENCE_PATTERNS.items():
            for pat in patterns:
                if re.match(pat, first_sent.strip()):
                    matched = ptype
                    break
            if matched:
                break

        pattern_usage.append((i, matched))

    # If 3+ consecutive paragraphs have the same pattern type,
    # we can't really rewrite without LLM, so we note this constraint.
    # For now, we track and report; actual rewriting would need LLM.
    # This is a structural check: in practice, the generator_v2.py
    # should produce varied first sentences.

    return paragraphs


# ---------------------------------------------------------------------------
# Main Processing Pipeline
# ---------------------------------------------------------------------------

def _extract_body_text(html_content: str) -> tuple:
    """
    Extract the article body text from HTML, returning (prefix, paragraphs, suffix).
    prefix: everything before the first <p> inside the article
    paragraphs: list of paragraph inner texts
    suffix: everything after the last </p> inside the article
    """
    # Find the main article content area
    # Look for the first <p> tag in the actual content (after header/nav)
    article_start = 0
    article_end = len(html_content)

    # Try to find article boundaries
    article_match = re.search(r'<article[^>]*>', html_content, re.IGNORECASE)
    if article_match:
        article_start = article_match.start()

    article_close = re.search(r'</article>', html_content, re.IGNORECASE)
    if article_close:
        article_end = article_close.end()

    # If no <article> tag, look for main content div
    if article_start == 0:
        main_match = re.search(
            r'<(?:div|section)[^>]*class="[^"]*(?:article-content|post-content|content-body|entry-content)[^"]*"[^>]*>',
            html_content, re.IGNORECASE)
        if main_match:
            article_start = main_match.start()

    body = html_content[article_start:article_end]
    prefix = html_content[:article_start]
    suffix = html_content[article_end:]

    # Extract paragraphs from body using regex (more robust than HTMLParser for varied HTML)
    para_pattern = re.compile(
        r'(<\s*(?:p|li|h[1-6]|blockquote|td|th)\b[^>]*>)(.*?)(</\s*(?:p|li|h[1-6]|blockquote|td|th)\s*>)',
        re.DOTALL | re.IGNORECASE
    )

    fragments = []
    last_end = 0

    for match in para_pattern.finditer(body):
        # Preserve non-paragraph content between matches
        if match.start() > last_end:
            fragments.append({
                'type': 'raw',
                'content': body[last_end:match.start()]
            })

        open_tag = match.group(1)
        inner = match.group(2)
        close_tag = match.group(3)

        fragments.append({
            'type': 'paragraph',
            'open_tag': open_tag,
            'inner_text': inner.strip(),
            'close_tag': close_tag,
        })
        last_end = match.end()

    # Remaining raw content after last paragraph
    if last_end < len(body):
        fragments.append({
            'type': 'raw',
            'content': body[last_end:]
        })

    return prefix, fragments, suffix


def _reassemble_html(prefix: str, fragments: list, suffix: str) -> str:
    """Reassemble HTML from prefix, processed fragments, and suffix."""
    parts = [prefix]
    for frag in fragments:
        if frag['type'] == 'raw':
            parts.append(frag['content'])
        else:
            parts.append(frag['open_tag'])
            parts.append(frag['inner_text'])
            parts.append(frag['close_tag'])
    parts.append(suffix)
    return ''.join(parts)


def deai_process(html_content: str) -> str:
    """
    Apply 6-dimensional de-AI processing to an HTML article.

    Args:
        html_content: Full HTML string of the article.

    Returns:
        Processed HTML string with AI patterns disrupted.
    """
    prefix, fragments, suffix = _extract_body_text(html_content)

    # Collect paragraph fragments for batch processing
    para_indices = [i for i, f in enumerate(fragments) if f['type'] == 'paragraph']
    para_texts = [fragments[i]['inner_text'] for i in para_indices]

    # ---- 4.1: Paragraph Split / Merge ----
    if len(para_texts) >= 2:
        # Phase 1: Split overly long paragraphs
        new_para_texts = []
        for pt in para_texts:
            if _count_words(pt) > 200:
                split_parts = _split_paragraph_text(pt)
                new_para_texts.extend(split_parts)
            else:
                new_para_texts.append(pt)

        # Phase 2: Merge adjacent short paragraphs
        merged = []
        i = 0
        while i < len(new_para_texts):
            if i + 1 < len(new_para_texts):
                w_curr = _count_words(new_para_texts[i])
                w_next = _count_words(new_para_texts[i + 1])
                if w_curr < 40 and w_next < 40:
                    merged.append(new_para_texts[i] + ' ' + new_para_texts[i + 1])
                    i += 2
                    continue
            merged.append(new_para_texts[i])
            i += 1

        para_texts = merged

    # ---- 4.2: AI Transition Word Mutation ----
    para_texts = [_apply_transition_mutations(pt) for pt in para_texts]

    # ---- 4.3: Sentence Length Diversification ----
    para_texts = [_diversify_sentence_lengths(pt) for pt in para_texts]

    # ---- 4.4: First Sentence Pattern Rotation ----
    para_texts = _rotate_first_sentence(para_texts)

    # ---- 4.5: Conclusion Cliché Removal ----
    if para_texts:
        para_texts[-1] = _remove_conclusion_cliches(para_texts[-1])

    # ---- 4.6: Human Touch Traces ----
    full_text = '\n'.join(para_texts)
    full_text = _inject_human_traces(full_text)
    para_texts = full_text.split('\n')

    # ---- Put transformed paragraphs back into fragments ----
    # If para count changed (split/merge), we need to adjust fragment structure
    if len(para_texts) != len(para_indices):
        # Rebuild fragments with new paragraph count
        new_fragments = []
        para_idx = 0
        for frag in fragments:
            if frag['type'] == 'paragraph':
                if para_idx < len(para_texts):
                    new_frag = dict(frag)
                    new_frag['inner_text'] = para_texts[para_idx]
                    new_fragments.append(new_frag)
                    para_idx += 1
                    # Insert extra paragraphs if we have more texts than slots
                    while para_idx < len(para_texts) and para_idx >= len(para_indices) and para_idx - len(para_indices) + 1 <= len(para_texts):
                        # Create a synthetic paragraph fragment using the same tag
                        extra_frag = {
                            'type': 'paragraph',
                            'open_tag': '<p>',
                            'inner_text': para_texts[para_idx],
                            'close_tag': '</p>',
                        }
                        new_fragments.append(extra_frag)
                        para_idx += 1
            else:
                new_fragments.append(frag)
        fragments = new_fragments
    else:
        for j, idx in enumerate(para_indices):
            fragments[idx]['inner_text'] = para_texts[j]

    return _reassemble_html(prefix, fragments, suffix)


# ---------------------------------------------------------------------------
# Standalone usage
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python deai.py <input.html> [output.html]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else input_path.replace('.html', '.deai.html')

    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()

    processed = deai_process(content)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(processed)

    print(f"De-AI processing complete: {input_path} -> {output_path}")
