"""Deterministic synthetic prompts of any size, for scale measurements and tests. The output is plain prompt text:
nothing here knows about nodes or edges, so every graph built from it comes from the real analysis."""

from __future__ import annotations

VERBS = ("Extract", "Check", "Summarize", "Compare", "Classify", "Translate", "Verify", "Collect", "Review", "Draft")
NOUNS = ("invoice", "ticket", "contract", "report", "order", "message", "record", "document", "claim", "request")
RULES = ("Never reveal the {n} id.", "Keep every {n} summary under 80 words.", "Do not guess a missing {n} field.",
         "Use a neutral tone when discussing the {n}.", "Reply in at most 5 bullet points about the {n}.")  # fmt: skip
TOOLS = ("lookup_order", "search_tickets", "fetch_contract", "send_notice", "get_invoice", "create_report")


def synthetic_prompt(units: int, *, steps_per_section: int = 8) -> str:
    """About ``units`` prompt units: identity, a tools section, sections with numbered steps that depend on earlier
    steps, variables and tools, constraints per section, and an example block every few sections."""
    out = ["# Synthetic pipeline", "", "You are a careful operations assistant.", ""]
    out += ["## Tools", ""] + [f"### {t}\nCalls the {t.split('_')[1]} service and returns JSON." for t in TOOLS] + [""]
    made, section = 0, 0
    while made < units:
        section += 1
        out += [f"## Section {section}", ""]
        for step in range(1, steps_per_section + 1):
            i = made
            verb, noun = VERBS[i % len(VERBS)], NOUNS[(i // 3) % len(NOUNS)]
            if step == 1:
                out.append(f"1. {verb} the {noun} number from {{{{input_{section}}}}}.")
            elif step % 4 == 0:
                out.append(
                    f"{step}. Use the {TOOLS[i % len(TOOLS)]} tool to {verb.lower()} the {noun} from step {step - 1}."
                )
            else:
                out.append(f"{step}. {verb} the {noun} using the result of step {step - 1}.")
            made += 1
        out += ["", "Rules:"]
        for r in range(2):
            out.append("- " + RULES[(section + r) % len(RULES)].format(n=NOUNS[(section + r) % len(NOUNS)]))
            made += 1
        out.append("")
        if section % 3 == 0:
            out += ["Example:", f"Input: {NOUNS[section % len(NOUNS)]} number 4711", "Output: 4711", ""]
            made += 1
    return "\n".join(out)
