#!/usr/bin/env python3
"""Restore Key Takeaways section into 3 files that deslop accidentally dropped.
Takes the longest <section class="key-takeaways">...</section> block from HEAD
and inserts it right before the COMMUNITY-SECTION-START marker in the working file.
"""
import re, subprocess, pathlib

ROOT = pathlib.Path(r"C:/Users/Administrator/WorkBuddy/2026-08-30-22-49-28/821224.com")
FILES = [
    "content/ai-claims/ai-claims-audit-automation-the-8020-rule-no-one-wants-to-talk-about/index.html",
    "content/ai-claims/claims-lifecycle-management-ai-software-six-vendors-compared-by-real-world-trade/index.html",
    "content/ai-claims/loss-adjuster-cycle-time-fell-34-after-duck-creek-bolted-on-shift-technologys-de/index.html",
]
CS_MARK = "<!-- COMMUNITY-SECTION-START -->"
KT_RE = re.compile(r'<section class="key-takeaways".*?</section>', re.DOTALL | re.IGNORECASE)

for rel in FILES:
    p = ROOT / rel
    head = subprocess.check_output(["git", "show", f"HEAD:{rel}"], cwd=str(ROOT)).decode("utf-8", "replace")
    matches = KT_RE.findall(head)
    if not matches:
        print(f"SKIP (no KT in HEAD): {rel}")
        continue
    best = max(matches, key=len)
    work = p.read_text(encoding="utf-8")
    if "key-takeaways" in work.lower():
        print(f"SKIP (KT already present): {rel}")
        continue
    if CS_MARK not in work:
        print(f"SKIP (no community marker): {rel}")
        continue
    new = work.replace(CS_MARK, best + "\n\n" + CS_MARK, 1)
    tmp = str(p) + ".ktmp"
    p.write_text(new, encoding="utf-8")  # atomic-ish; small file
    print(f"RESTORED KT ({len(best)} chars) -> {rel}")
print("done")
