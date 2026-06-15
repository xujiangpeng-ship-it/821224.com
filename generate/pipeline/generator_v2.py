#!/usr/bin/env python3
"""
generator_v2.py — 3-Pass Generation Engine (手段2 + 手段3)
===========================================================
Appends Pass 2 (stance injection) and Pass 3 (persona blending) onto
existing AI-generated article text. Uses LLM via generate/llm.py.

Usage:
    from pipeline.generator_v2 import enhance_article
    result = enhance_article(ai_text, metadata)
"""

import random
import logging

logger = logging.getLogger("generator_v2")

# ---------------------------------------------------------------------------
# Pass 2: 8 Stances with argument templates
# ---------------------------------------------------------------------------

STANCES = {
    "radical_optimist": {
        "name": "Radical Optimist",
        "prompt": (
            "You are a radical optimist about AI in insurance. Inject 2-3 paragraphs into the article "
            "that argue AI will transform insurance faster and more completely than most people expect. "
            "Emphasize exponential improvement curves, compound effects, and historical parallels to "
            "other industries that were disrupted in under 5 years. Be bold but data-anchored. "
            "Do not change the rest of the article — only add your perspective as clearly marked new paragraphs."
        ),
        "tag": "[Radical Optimist Perspective]",
    },
    "cautious_skeptic": {
        "name": "Cautious Skeptic",
        "prompt": (
            "You are a cautious skeptic about AI in insurance. Inject 2-3 paragraphs that raise "
            "critical questions about the claims made in the article: implementation timelines that "
            "are too aggressive, ROI assumptions that ignore hidden costs, regulatory hurdles that "
            "are underappreciated, or data quality issues that undermine model performance. "
            "Be constructive but unflinching. Do not change the rest of the article."
        ),
        "tag": "[Skeptical Counterpoint]",
    },
    "practitioner_pragmatist": {
        "name": "Practitioner Pragmatist",
        "prompt": (
            "You are a hands-on insurance practitioner who has actually deployed AI in production. "
            "Inject 2-3 paragraphs that add gritty operational detail: what breaks in production, "
            "the change management battles, the data cleaning nightmares, and the vendor promises "
            "that didn't survive contact with reality. Ground everything in lived experience. "
            "Do not change the rest of the article."
        ),
        "tag": "[Practitioner's Reality Check]",
    },
    "regulatory_watchdog": {
        "name": "Regulatory Watchdog",
        "prompt": (
            "You are a regulatory analyst focused on AI governance in financial services. Inject 2-3 "
            "paragraphs that examine the regulatory implications: what regulators (NAIC, EIOPA, state "
            "DOIs) are likely to scrutinize, what disclosure requirements are coming, what fairness "
            "and bias testing protocols will be expected, and where the compliance risks are highest. "
            "Be specific about regulatory frameworks. Do not change the rest of the article."
        ),
        "tag": "[Regulatory Lens]",
    },
    "investor_analyst": {
        "name": "Investor / Market Analyst",
        "prompt": (
            "You are an investment analyst covering insurtech. Inject 2-3 paragraphs that evaluate "
            "the topic from a capital allocation perspective: market sizing, TAM/SAM/SOM, competitive "
            "moats, unit economics, CAC/LTV dynamics, exit potential, and comparable public company "
            "valuations. Frame everything in terms of investment theses — bull case and bear case. "
            "Do not change the rest of the article."
        ),
        "tag": "[Investor Angle]",
    },
    "tech_geek": {
        "name": "Technical Geek",
        "prompt": (
            "You are a deeply technical AI engineer. Inject 2-3 paragraphs that drill into the "
            "technical architecture: model architectures (transformer variants, GNNs, XGBoost), "
            "training data requirements, inference latency tradeoffs, MLOps considerations, "
            "feature engineering specifics, and quantitative benchmarks. Use precise technical "
            "language. Do not change the rest of the article."
        ),
        "tag": "[Technical Deep Dive]",
    },
    "competitive_rival": {
        "name": "Competitive Rival",
        "prompt": (
            "You represent a competing approach or vendor. Inject 2-3 paragraphs that argue why "
            "an alternative approach might be better: a different technology stack, a different "
            "business model, a different sequencing of implementation, or a different market "
            "positioning. Be respectfully contrarian — the goal is to enrich the analysis, "
            "not to trash the article. Do not change the rest of the article."
        ),
        "tag": "[Alternative View]",
    },
    "consumer_advocate": {
        "name": "Consumer Advocate",
        "prompt": (
            "You are a consumer rights advocate focused on insurance fairness. Inject 2-3 paragraphs "
            "that examine the consumer impact: how AI affects claim outcomes for different demographic "
            "groups, the transparency and explainability gap for policyholders, potential disparate "
            "impact in automated decisions, and what safeguards consumers need. Center the human "
            "experience. Do not change the rest of the article."
        ),
        "tag": "[Consumer Perspective]",
    },
}

# ---------------------------------------------------------------------------
# Pass 3: 13 Persona Slices
# ---------------------------------------------------------------------------

PERSONAS = {
    "battle_scarred_vet": (
        "Rewrite selected paragraphs in the voice of a battle-scarred insurance veteran who has "
        "seen three technology cycles come and go. Use world-weary but wise tone. Pepper in phrases "
        "like 'in my experience', 'I've seen this movie before', 'the hard truth is'. "
        "Keep technical content intact but make the framing feel lived-in."
    ),
    "data_obsessive": (
        "Rewrite selected paragraphs in the voice of a data-obsessive quant who lives in "
        "spreadsheets and model metrics. Add specificity: mention confidence intervals, "
        "p-values, R-squared, AUC, precision/recall tradeoffs — but only where they fit "
        "organically. Use phrases like 'the numbers don't lie', 'statistically significant', "
        "'let me put that in context'."
    ),
    "storyteller": (
        "Rewrite selected paragraphs with a narrative flair. Open with a mini-anecdote or "
        "concrete scenario. Use vivid, specific imagery. Make abstract concepts tangible "
        "through stories of specific carriers, specific claims, specific people. "
        "Avoid marketing-speak; tell real operational stories."
    ),
    "contrarian": (
        "Rewrite selected paragraphs to inject contrarian energy. Challenge assumptions. "
        "Ask 'but what if the opposite is true?' Use phrases like 'here's the uncomfortable "
        "truth', 'most people miss this', 'the conventional wisdom is wrong here'. "
        "Be intellectually provocative but not obnoxious."
    ),
    "mentor": (
        "Rewrite selected paragraphs in the voice of a patient mentor explaining concepts "
        "to a junior colleague. Use 'you'll find that...', 'here's what I tell my team...', "
        "'the key insight is...'. Make complex ideas accessible without dumbing them down."
    ),
    "field_reporter": (
        "Rewrite selected paragraphs as if reporting from the front lines of insurance ops. "
        "Use present-tense, journalistic style. Mention specific locations, specific timing, "
        "specific operational details. 'I'm standing in the claims center in Des Moines...' "
        "energy — vivid, immediate, grounded."
    ),
    "systems_thinker": (
        "Rewrite selected paragraphs through a systems-thinking lens. Connect dots across "
        "the insurance value chain. Use phrases like 'second-order effects', 'feedback loops', "
        "'emergent behavior', 'the system responds by...'. Show how changes in one part "
        "ripple through the entire ecosystem."
    ),
    "provocateur": (
        "Rewrite selected paragraphs with provocative, debate-sparking framing. Use bold "
        "declarative statements. 'This will be obsolete in 18 months.' 'The incumbents "
        "are sleepwalking.' 'Here's the bet I'd make.' Push readers to react."
    ),
    "architect": (
        "Rewrite selected paragraphs from the perspective of someone who designs and builds "
        "these systems. Focus on design decisions, tradeoffs, what was considered and rejected, "
        "why certain architectural choices were made. Use 'we chose', 'the design principle was', "
        "'the constraint that shaped this was'."
    ),
    "skeptical_buyer": (
        "Rewrite selected paragraphs from the perspective of a carrier executive evaluating "
        "whether to buy this technology. Focus on: total cost of ownership, integration complexity, "
        "vendor lock-in risk, time-to-value, what the reference calls actually revealed. "
        "Use procurement-realist language."
    ),
    "academic": (
        "Rewrite selected paragraphs with academic rigor. Add citations to relevant research, "
        "mention specific studies and papers, use precise terminology, and frame findings in "
        "the context of the broader research literature. 'The academic consensus is shifting...', "
        "'A 2024 paper in...', 'The evidence base suggests...'."
    ),
    "product_manager": (
        "Rewrite selected paragraphs from a product management perspective. Focus on user needs, "
        "jobs-to-be-done, adoption funnels, feature prioritization, and what actually drives "
        "user engagement. Use 'users consistently tell us', 'the adoption data shows', "
        "'the feature that actually moved the needle was'."
    ),
    "futurist": (
        "Rewrite selected paragraphs with a 5-10 year forward-looking lens. Extrapolate trends, "
        "imagine second and third-order consequences, describe plausible future states. "
        "Use 'by 2030...', 'the trajectory suggests...', 'we're in the early innings of...'. "
        "Be ambitious but grounded in current trajectory data."
    ),
}

# ---------------------------------------------------------------------------
# Main enhance_article function
# ---------------------------------------------------------------------------

def enhance_article(
    article_text: str,
    article_metadata: dict = None,
    stance: str = None,
    personas: list = None,
    use_llm: bool = True,
) -> dict:
    """
    Enhance an AI-generated article with Pass 2 (stance injection) and Pass 3 (persona blending).

    Args:
        article_text: The original AI-generated article text (plain text or Markdown).
        article_metadata: Dict with keys like 'title', 'category', etc.
        stance: Override random stance selection. One of STANCES keys or None for random.
        personas: Override random persona selection. List of PERSONAS keys or None for random.
        use_llm: If False, returns text with placeholders instead of calling LLM.

    Returns:
        dict with keys: 'enhanced_text', 'stance_used', 'personas_used', 'llm_called'
    """
    metadata = article_metadata or {}

    # Select stance
    if stance and stance in STANCES:
        stance_key = stance
    else:
        stance_key = random.choice(list(STANCES.keys()))

    # Select 3-4 personas (no consecutive same)
    if personas and all(p in PERSONAS for p in personas):
        persona_keys = personas
    else:
        k = random.randint(3, 4)
        persona_keys = random.sample(list(PERSONAS.keys()), k)

    # Ensure no consecutive same persona
    for i in range(len(persona_keys) - 1, 0, -1):
        if persona_keys[i] == persona_keys[i - 1]:
            remaining = [p for p in PERSONAS if p != persona_keys[i]]
            persona_keys[i] = random.choice(remaining)

    stance_info = STANCES[stance_key]
    persona_info = [(p, PERSONAS[p]) for p in persona_keys]

    if not use_llm:
        # Fallback: inject stance tags as placeholders
        enhanced = article_text
        enhanced += f"\n\n{stance_info['tag']}\n[Stance: {stance_info['name']}]"
        for p_key, _ in persona_info:
            enhanced += f"\n[Persona: {PERSONAS[p_key].split('.')[0]}]"
        return {
            "enhanced_text": enhanced,
            "stance_used": stance_key,
            "personas_used": persona_keys,
            "llm_called": False,
        }

    # Build LLM prompts
    try:
        from generate.llm import generate_text

        # --- Pass 2: Stance injection ---
        system_prompt = (
            "You are an expert insurance technology analyst. Your task is to enhance an existing "
            "article by injecting a specific analytical perspective as 2-3 additional paragraphs. "
            "Output the complete enhanced article with your additions clearly integrated. "
            "Preserve all original content and structure."
        )
        user_prompt = f"{stance_info['prompt']}\n\nOriginal article:\n\n{article_text}"

        try:
            pass2_text = generate_text(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.8,
                max_tokens=8192,
            )
            llm_called = True
        except Exception as e:
            logger.warning(f"LLM call failed for stance injection: {e}. Using original text.")
            pass2_text = article_text
            llm_called = False

        # --- Pass 3: Persona blending ---
        # Split into paragraphs, assign personas to ~40-60% of paragraphs
        paragraphs = [p.strip() for p in pass2_text.split('\n\n') if p.strip()]
        if len(paragraphs) < 4:
            # Too short for meaningful persona blending; skip
            return {
                "enhanced_text": pass2_text,
                "stance_used": stance_key,
                "personas_used": persona_keys,
                "llm_called": llm_called,
            }

        num_to_rewrite = max(2, int(len(paragraphs) * random.uniform(0.4, 0.6)))
        indices_to_rewrite = sorted(random.sample(range(len(paragraphs)), min(num_to_rewrite, len(paragraphs))))

        # Assign personas to selected paragraphs round-robin (ensures no consecutive same)
        for idx_pos, para_idx in enumerate(indices_to_rewrite):
            p_key = persona_keys[idx_pos % len(persona_keys)]
            p_desc = PERSONAS[p_key]
            original_para = paragraphs[para_idx]

            try:
                sys_p = (
                    "You are an editor skilled at adapting writing style. Rewrite the given paragraph "
                    "in a specific voice while preserving all factual content, data points, citations, "
                    "and technical accuracy. The paragraph should remain coherent with surrounding text."
                )
                usr_p = f"{p_desc}\n\nParagraph to rewrite:\n\n{original_para}"
                rewritten = generate_text(
                    system_prompt=sys_p,
                    user_prompt=usr_p,
                    temperature=0.9,
                    max_tokens=1024,
                )
                paragraphs[para_idx] = rewritten.strip()
                llm_called = True
            except Exception as e:
                logger.warning(f"LLM call failed for persona '{p_key}' on paragraph {para_idx}: {e}")

        enhanced_text = '\n\n'.join(paragraphs)

        return {
            "enhanced_text": enhanced_text,
            "stance_used": stance_key,
            "personas_used": persona_keys,
            "llm_called": llm_called,
        }

    except ImportError:
        logger.warning("generate.llm not available. Returning text with placeholder tags.")
        enhanced = article_text
        enhanced += f"\n\n{stance_info['tag']}\n[Stance: {stance_info['name']}]"
        for p_key, _ in persona_info:
            enhanced += f"\n[Persona: {PERSONAS[p_key].split('.')[0]}]"
        return {
            "enhanced_text": enhanced,
            "stance_used": stance_key,
            "personas_used": persona_keys,
            "llm_called": False,
        }


# ---------------------------------------------------------------------------
# CLI entry point for batch processing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Add repo root to path for imports
    repo = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(repo / "generate"))

    if len(sys.argv) < 2:
        print("Usage: python generator_v2.py <article_html_path> [--stance STANCE_KEY] [--no-llm]")
        sys.exit(1)

    article_path = Path(sys.argv[1])
    use_llm = "--no-llm" not in sys.argv

    # Extract stance override
    stance_override = None
    for i, arg in enumerate(sys.argv):
        if arg == "--stance" and i + 1 < len(sys.argv):
            stance_override = sys.argv[i + 1]
            break

    if not article_path.exists():
        print(f"Error: file not found: {article_path}")
        sys.exit(1)

    html = article_path.read_text(encoding='utf-8')

    # Extract plain text from HTML (simple approach)
    import re as _re
    plain = _re.sub(r'<[^>]+>', ' ', html)
    plain = _re.sub(r'\s+', ' ', plain).strip()

    result = enhance_article(plain, use_llm=use_llm, stance=stance_override)

    print(f"Stance: {result['stance_used']} ({STANCES[result['stance_used']]['name']})")
    print(f"Personas: {', '.join(result['personas_used'])}")
    print(f"LLM called: {result['llm_called']}")
    print(f"Output length: {len(result['enhanced_text'])} chars")
