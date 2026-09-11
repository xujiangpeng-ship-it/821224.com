# no-ai-slop — vendored rules

These files (`SKILL.md`, `eval.md`) are vendored from the open-source project
[petergyang/no-ai-slop](https://github.com/petergyang/no-ai-slop) to harden our
article generation / rewrite pipeline against semantic "AI slop".

- **License:** MIT (see the upstream `LICENSE` file).
- **Vendored:** 2026-09-11.
- **Usage in this repo:** the curated pattern list is distilled into
  `generate/no_ai_slop_rules.py` (`SLOP_INSTRUCTIONS` for the LLM prompt and
  `audit_slop()` for detection). The upstream `SKILL.md`/`eval.md` are kept
  here as the authoritative reference and for traceability.

We reuse the *pattern catalogue and editing principles* only; the upstream is a
chat-agent skill, whereas here the same rules are applied inside our automated
Agnes/Mistral generation and remediation passes.
