# -*- coding: utf-8 -*-
"""
deslop_rewrite_html.py — Surgical semantic de-AI-slop rewrite for 821224.com.

821224 renders articles as Jinja HTML (templates/article.html). Each
content/<sub>/<slug>/index.html contains:

    <div class="article-content">
        <body part 1>
        <!-- Ad Mid-Content -->
        <div class="ad-slot" ...> ... </div>
        <body part 2>
        <!-- COMMUNITY-SECTION-START --> ...reddit/hn... <!-- COMMUNITY-SECTION-END -->
    </div>

This script rewrites ONLY the article prose to strip SEMANTIC AI-slop patterns
(colon_reveal / binary_contrast / faux_insight / weasel_attribution /
interpretive_metadiscourse / etc. from no-ai-slop). It:
  - preserves the COMMUNITY-SECTION block VERBATIM (real human discussion),
  - preserves the mid-content ad-slot (re-inserted at the 1/3 boundary),
  - preserves Key Takeaways / tables / cited sources / URLs / numbers,
  - checkpoint/resume via .deslop_done.txt,
  - atomic writes with retries.

Trigger = ONLY non-cosmetic SEMANTIC slop (em_dash / emoji_heading excluded),
matching stackinsider's approach. Uses agnes-3.0-flash via the OpenAI client.
"""
import os
import re
import sys
import time
import datetime
from pathlib import Path
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = ROOT / "content"
DONE_FILE = ROOT / ".deslop_done.txt"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from no_ai_slop_rules import SLOP_INSTRUCTIONS, audit_slop  # noqa: E402

# --- model / client ---------------------------------------------------------
api_key = os.environ.get("AGNES_API_KEY") or os.environ.get("MISTRAL_API_KEY")
if not api_key:
    print("Neither AGNES_API_KEY nor MISTRAL_API_KEY set. Abort.")
    sys.exit(1)
_base_url = ("https://apihub.agnes-ai.com/v1" if os.environ.get("AGNES_API_KEY")
             else "https://api.mistral.ai/v1")
client = OpenAI(api_key=api_key, base_url=_base_url)
MODEL_NAME = os.environ.get("AGNES_MODEL", "agnes-3.0-flash")

TODAY = datetime.date.today().strftime("%Y-%m-%d")
COSMETIC = {"em_dash", "curly_quotes", "emoji_heading"}

# ---------------------------------------------------------------------------
# HTML surgery helpers
# ---------------------------------------------------------------------------
AC_OPEN = '<div class="article-content">'
CS_START = "<!-- COMMUNITY-SECTION-START -->"
CS_END = "<!-- COMMUNITY-SECTION-END -->"
AD_RE = re.compile(
    r"<!-- Ad Mid-Content -->\s*<div class=\"ad-slot\"[^>]*>[\s\S]*?</div>",
    re.IGNORECASE,
)


def split_article(html: str):
    """Return (ac_open_idx, ac_close_end_idx, community_block, prose_region).

    ac_open_idx      : index of '<div class="article-content">'
    ac_close_end_idx : index just AFTER the </div> closing article-content
    community_block  : the COMMUNITY-SECTION block string ('' if absent)
    prose_region     : HTML between ac open and community block (or ac close)
    """
    ac_open = html.find(AC_OPEN)
    if ac_open == -1:
        return None
    ac_open_end = ac_open + len(AC_OPEN)

    if CS_START in html and CS_END in html:
        cs_s = html.find(CS_START)
        cs_e = html.find(CS_END) + len(CS_END)
        community_block = html[cs_s:cs_e]
        # article-content closes at the first </div> after CS_END
        close = html.find("</div>", cs_e)
        if close == -1:
            return None
        ac_close_end = close + len("</div>")
        prose_region = html[ac_open_end:cs_s]
    else:
        # no community block: find matching close via depth count from ac_open
        close = html.find("</div>", ac_open_end)
        if close == -1:
            return None
        ac_close_end = close + len("</div>")
        community_block = ""
        prose_region = html[ac_open_end:close]
    return ac_open, ac_close_end, community_block, prose_region


def prose_without_ad(region: str):
    """Return (prose, ad_slot). ad_slot is '' if none found."""
    m = AD_RE.search(region)
    if not m:
        return region, ""
    ad_slot = m.group(0)
    prose = region[: m.start()] + region[m.end():]
    return prose, ad_slot


def reinsert_ad(prose: str, ad_slot: str):
    """Insert ad_slot at roughly the 1/3 boundary of prose (matches template)."""
    if not ad_slot:
        return prose
    cut = max(len(prose) // 3, 200)
    # prefer to insert after the first heading/paragraph boundary near cut
    pos = prose.find("</h2>", cut)
    if pos == -1:
        pos = prose.find("</h3>", cut)
    if pos == -1:
        pos = prose.find("</p>", cut)
    if pos == -1 or pos > len(prose) * 0.7:
        pos = cut
    else:
        pos = pos + len("</p>") if prose[pos:pos + 4] == "</p>" else pos
    return prose[:pos] + "\n" + ad_slot + "\n" + prose[pos:]


# ---------------------------------------------------------------------------
# LLM rewrite
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are a senior insurance-technology copy editor. Rewrite the supplied "
    "HTML article BODY to remove generic 'AI slop' sentence patterns while "
    "preserving every concrete fact, statistic, organisation name, year, report "
    "title, URL, product name, price, and table. Keep all headings (h2/h3), "
    "paragraphs, lists, comparison tables, and blockquotes exactly in meaning.\n"
    "Do NOT add any 'Community perspectives', 'What readers say', Reddit, or "
    "discussion section. Do NOT add or move the mid-article ad slot. "
    "Output ONLY the cleaned HTML body (starting with <h2> or <p>), no code "
    "fences, no preamble, no commentary."
    + SLOP_INSTRUCTIONS
)


def rewrite(prose: str, url: str, max_retries=3):
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Article: {url}\n\n{prose}"},
                ],
                temperature=0.5,
                max_tokens=9000,
                timeout=180,
            )
            out = resp.choices[0].message.content.strip()
            if out.startswith("```"):
                nl = out.find("\n")
                out = out[nl + 1:] if nl != -1 else out[3:]
            if out.rstrip().endswith("```"):
                out = out.rstrip()[:-3].rstrip()
            out = out.strip()
            if len(out) < 200:
                raise ValueError(f"content too short ({len(out)} chars)")
            return out
        except Exception as e:
            last_err = e
            print(f"    x attempt {attempt} failed: {e}")
            time.sleep(6)
    print(f"    x all {max_retries} retries failed: {last_err}")
    return None


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    audit_only = "--audit" in sys.argv

    done = set()
    if DONE_FILE.exists():
        done = {l.strip() for l in DONE_FILE.read_text(encoding="utf-8").splitlines() if l.strip()}
    if done:
        print(f"[resume] {len(done)} files already processed, will skip.\n")

    files = []
    for sd in sorted(CONTENT_DIR.iterdir()):
        if not sd.is_dir():
            continue
        for af in sorted(sd.iterdir()):
            if af.is_dir() and (af / "index.html").exists():
                files.append(af / "index.html")
    print(f"Total article files: {len(files)}\n")

    total = len(files)
    rewritten = skipped = failed = empty = 0

    for i, fpath in enumerate(files):
        url = "/" + fpath.relative_to(CONTENT_DIR).parent.as_posix() + "/"
        if url in done:
            skipped += 1
            continue

        html = fpath.read_text(encoding="utf-8")
        parts = split_article(html)
        if parts is None:
            print(f"[{i+1}/{total}] {url}: NO article-content, SKIP")
            done.add(url)
            continue
        ac_open, ac_close_end, community_block, prose_region = parts
        prose, ad_slot = prose_without_ad(prose_region)

        slop_hits = [h for h in audit_slop(prose) if h not in COSMETIC]
        if not slop_hits:
            if audit_only:
                pass
            else:
                skipped += 1
                done.add(url)
                continue

        if audit_only:
            print(f"[{i+1}/{total}] {url}: slop={slop_hits}")
            empty += 1
            continue

        print(f"[{i+1}/{total}] {url}: slop={slop_hits} -> REWRITE")
        new_prose = rewrite(prose, url)
        if new_prose is None:
            failed += 1
            done.add(url)  # don't loop forever; revisit manually
            continue

        # guard against truncated/shortened rewrites (would lose article content)
        if len(new_prose) < 0.6 * len(prose):
            print(f"    x rewrite too short ({len(new_prose)} vs {len(prose)}), SKIP")
            failed += 1
            done.add(url)
            continue

        # verify community block still preserved (it is, we never touched it)
        new_with_ad = reinsert_ad(new_prose, ad_slot)
        new_ac = AC_OPEN + "\n" + new_with_ad + "\n" + community_block + "\n</div>"
        new_html = html[:ac_open] + new_ac + html[ac_close_end:]

        # sanity: community block survived
        if CS_START in community_block and CS_START not in new_html:
            print("    x community block lost, SKIP")
            failed += 1
            done.add(url)
            continue

        # atomic write + retry
        tmp = str(fpath) + ".tmp"
        ok = False
        for _w in range(5):
            try:
                with open(tmp, "w", encoding="utf-8") as fh:
                    fh.write(new_html)
                os.replace(tmp, str(fpath))
                ok = True
                break
            except (OSError, PermissionError):
                time.sleep(1.5)
        if ok:
            rewritten += 1
            done.add(url)
            with open(DONE_FILE, "a", encoding="utf-8") as df:
                df.write(url + "\n")
            new_slop = [h for h in audit_slop(new_prose) if h not in COSMETIC]
            print(f"    ✓ written (slop {len(slop_hits)}->{len(new_slop)})")
        else:
            failed += 1
            done.add(url)

        if (rewritten + failed) % 5 == 0:
            print(f"    [progress: {rewritten} rewritten, {failed} failed]")
        time.sleep(2)

    if audit_only:
        print(f"\nAUDIT DONE: {empty} articles carry semantic slop.")
    else:
        print(f"\n{'='*50}")
        print(f"DONE: rewritten={rewritten} skipped={skipped} failed={failed}")
        print(f"{'='*50}")


if __name__ == "__main__":
    main()
