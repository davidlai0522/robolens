# pipeline/extract.py
import json
import pathlib
import re
from llm import ask


def extract_key_ideas(paper: dict, tokenizer, model) -> dict:
    """Use Gemma 4 to extract a structured outline from the full paper text."""
    cache_file = pathlib.Path(f"cache/{paper['id']}_extraction.json")
    if cache_file.exists():
        print("  (cached) Skipping LLM extraction")
        return json.loads(cache_file.read_text())

    # ~24K chars ≈ 6K tokens — covers abstract + intro + methods + results
    # which is all the model needs; full 100K chars exhausts KV cache VRAM.
    text = paper["full_text"][:24_000]

    prompt = f"""You are a senior ML researcher. Read the research paper below and \
extract a structured outline for a technical blog post. Be precise — use exact \
component names, numbers, and terms from the paper. Do not invent or paraphrase \
any quantitative results.

Return ONLY valid JSON (no preamble, no markdown fences) with these fields:
{{
  "one_sentence_summary": "...",
  "problem_statement": "...",
  "prior_art_gaps": ["...", "...", "..."],
  "key_contributions": ["...", "...", "..."],
  "method_overview": "150-word paragraph — precise, no vague terms",
  "architecture_components": [
    {{"name": "...", "description": "..."}}
  ],
  "key_results": [
    {{"metric": "...", "value": "...", "baseline": "...", "source": "Table X"}}
  ],
  "practitioner_takeaways": ["...", "...", "..."],
  "limitations": ["...", "..."],
  "needs_fallback_diagram": true or false
}}

Set needs_fallback_diagram=true ONLY if:
  1. The method has a novel architecture that is hard to understand from text alone, AND
  2. You judge no architecture figure exists in the paper.

Paper:
<paper>
{text}
</paper>"""

    raw = ask(prompt, tokenizer, model, temperature=0.1)

    # Strip any accidental markdown fences before parsing
    cleaned = (
        raw.strip()
        .removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )
    # Replace invalid JSON escape sequences (e.g. LaTeX \alpha, \text{})
    # Valid JSON escapes: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
    cleaned = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', cleaned)
    result = json.loads(cleaned)
    cache_file.write_text(json.dumps(result, indent=2))
    return result
