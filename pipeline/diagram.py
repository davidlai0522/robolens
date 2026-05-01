# pipeline/diagram.py
import json
from llm import ask


def maybe_generate_mermaid(
    extraction: dict,
    figures: list[dict],
    tokenizer,
    model,
) -> str | None:
    """
    Generate a Mermaid fallback diagram ONLY when:
      - No real figures were extracted from the PDF, AND
      - The extraction step flagged that a diagram is needed.
    """
    if figures:
        print("  Real figures found — skipping Mermaid generation")
        return None

    if not extraction.get("needs_fallback_diagram", False):
        print("  No diagram needed — skipping Mermaid generation")
        return None

    print("  No figures in PDF — generating Mermaid fallback diagram")
    components = extraction["architecture_components"]

    prompt = f"""Generate a Mermaid flowchart (graph TD) for this neural network \
architecture. Use only the component names and connections described below. \
Return ONLY the raw Mermaid code — no explanation, no markdown fences.

Components:
{json.dumps(components, indent=2)}"""

    code = ask(prompt, tokenizer, model, temperature=0.05)
    return f"```mermaid\n{code.strip()}\n```"
