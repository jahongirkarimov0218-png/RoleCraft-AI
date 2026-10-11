// A deterministic synthetic prompt for scale measurements (the same shape as tests/synthetic.py in the backend).
// It is plain prompt text: every node in the UI still comes from the real analysis.
const VERBS = ["Extract", "Check", "Summarize", "Compare", "Classify", "Translate", "Verify", "Collect", "Review", "Draft"];
const NOUNS = ["invoice", "ticket", "contract", "report", "order", "message", "record", "document", "claim", "request"];
const RULES = [
  "Never reveal the {n} id.",
  "Keep every {n} summary under 80 words.",
  "Do not guess a missing {n} field.",
  "Use a neutral tone when discussing the {n}.",
  "Reply in at most 5 bullet points about the {n}.",
];
const TOOLS = ["lookup_order", "search_tickets", "fetch_contract", "send_notice", "get_invoice", "create_report"];

export function syntheticPrompt(units: number, stepsPerSection = 8): string {
  const out = ["# Synthetic pipeline", "", "You are a careful operations assistant.", "", "## Tools", ""];
  for (const t of TOOLS) out.push(`### ${t}`, `Calls the ${t.split("_")[1]} service and returns JSON.`);
  out.push("");
  let made = 0;
  let section = 0;
  while (made < units) {
    section += 1;
    out.push(`## Section ${section}`, "");
    for (let step = 1; step <= stepsPerSection; step++) {
      const verb = VERBS[made % VERBS.length];
      const noun = NOUNS[Math.floor(made / 3) % NOUNS.length];
      if (step === 1) out.push(`1. ${verb} the ${noun} number from {{input_${section}}}.`);
      else if (step % 4 === 0) out.push(`${step}. Use the ${TOOLS[made % TOOLS.length]} tool to ${verb.toLowerCase()} the ${noun} from step ${step - 1}.`);
      else out.push(`${step}. ${verb} the ${noun} using the result of step ${step - 1}.`);
      made += 1;
    }
    out.push("", "Rules:");
    for (let r = 0; r < 2; r++) {
      out.push("- " + RULES[(section + r) % RULES.length].replace("{n}", NOUNS[(section + r) % NOUNS.length]));
      made += 1;
    }
    out.push("");
    if (section % 3 === 0) {
      out.push("Example:", `Input: ${NOUNS[section % NOUNS.length]} number 4711`, "Output: 4711", "");
      made += 1;
    }
  }
  return out.join("\n");
}
