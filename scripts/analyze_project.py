#!/usr/bin/env python3
"""
4-Agent Pipeline for blueprint analysis.
Agent 1: Guide Builder - Analyze pages, identify patterns
Agent 2: Guide Applier - Validate rules on test pages
Agent 3: Self-Validator - Check rule stability
Agent 4: Consolidator - Generate stable guide
"""

import argparse
import json
import sys
import base64
from pathlib import Path
from typing import Optional

try:
    import anthropic
except ImportError:
    print("Error: anthropic SDK required. Run: pip install anthropic", file=sys.stderr)
    sys.exit(1)


def load_prompt(prompt_name: str) -> str:
    """Load a prompt from assets/prompts/"""
    script_dir = Path(__file__).parent.parent
    prompt_path = script_dir / "assets" / "prompts" / f"{prompt_name}.md"
    
    if prompt_path.exists():
        return prompt_path.read_text()
    
    # Fallback prompts
    prompts = {
        "guide_builder": """Tu es un expert en analyse de plans de construction québécois.

Analyse ces pages de plans et identifie:
1. Les SYMBOLES et leur signification (légende)
2. Les PATTERNS de notation (dimensions, numéros de locaux)
3. Les CONVENTIONS utilisées (portes, fenêtres, murs)

IMPORTANT: Les dimensions sont TOUJOURS en pieds et pouces (ex: 25'-6")

Output JSON:
{
  "observations": [{"type": "...", "description": "...", "page": N}],
  "candidate_rules": [{"rule": "...", "confidence": 0.0-1.0}],
  "legend_extractions": [{"symbol": "...", "meaning": "..."}],
  "provisional_guide": "# Guide provisoire\\n..."
}""",
        
        "guide_applier": """Tu valides les règles du guide sur de nouvelles pages.

Pour chaque règle, vérifie si elle s'applique correctement.

Output JSON:
{
  "validation_reports": [
    {
      "rule": "...",
      "status": "CONFIRMED|CONTRADICTED|NOT_TESTABLE|VARIATION",
      "evidence": "...",
      "page": N
    }
  ]
}""",
        
        "self_validator": """Tu évalues la stabilité des règles après validation.

Analyse les rapports de validation et détermine:
- Quelles règles sont stables (confirmées partout)
- Quelles règles sont instables (contradictions)
- Score de confiance global

Output JSON:
{
  "can_generate_final": true|false,
  "confidence_score": 0.0-1.0,
  "stable_count": N,
  "partial_count": N,
  "unstable_count": N,
  "stable_rules": ["..."],
  "issues": ["..."]
}""",
        
        "consolidator": """Tu génères le guide final stable.

Basé sur les règles validées, crée:
1. Un guide markdown lisible
2. Des règles JSON machine-executable

Output JSON:
{
  "stable_guide": "# Guide Stable\\n...",
  "stable_rules_json": [
    {
      "kind": "dimension|room|door|symbol",
      "pattern": "...",
      "description": "..."
    }
  ]
}"""
    }
    
    return prompts.get(prompt_name, "")


def encode_image(image_path: Path) -> str:
    """Encode image as base64 for Claude API."""
    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def get_media_type(image_path: Path) -> str:
    """Get media type from file extension."""
    suffix = image_path.suffix.lower()
    types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp"
    }
    return types.get(suffix, "image/png")


def select_pages(manifest: dict, count: int = 5, strategy: str = "balanced") -> list:
    """Select pages for analysis."""
    pages = manifest["pages"]
    total = len(pages)
    
    if total <= count:
        return pages
    
    if strategy == "balanced":
        # First page (often legend), then spread evenly
        indices = [0]
        step = (total - 1) / (count - 1)
        for i in range(1, count):
            indices.append(min(int(i * step), total - 1))
        return [pages[i] for i in sorted(set(indices))]
    
    return pages[:count]


def call_agent(
    client: anthropic.Anthropic,
    prompt: str,
    images: list[Path],
    context: Optional[str] = None,
    model: str = "claude-sonnet-4-20250514"
) -> dict:
    """Call Claude with images and return parsed JSON."""
    
    content = []
    
    # Add images
    for img_path in images:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": get_media_type(img_path),
                "data": encode_image(img_path)
            }
        })
    
    # Add text prompt
    text = prompt
    if context:
        text = f"{context}\n\n---\n\n{prompt}"
    
    content.append({"type": "text", "text": text})
    
    response = client.messages.create(
        model=model,
        max_tokens=8192,
        messages=[{"role": "user", "content": content}]
    )
    
    # Extract JSON from response
    response_text = response.content[0].text
    
    # Try to parse as JSON directly
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass
    
    # Try to extract JSON from markdown code block
    import re
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response_text)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Return raw text wrapped
    return {"raw_response": response_text}


def run_pipeline(
    pages_dir: str,
    output_dir: str,
    model: str = "claude-sonnet-4-20250514",
    api_key: Optional[str] = None
) -> dict:
    """Run the 4-agent pipeline."""
    
    pages_dir = Path(pages_dir).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load manifest
    manifest_path = pages_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"Error: No manifest.json in {pages_dir}", file=sys.stderr)
        sys.exit(1)
    
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    print(f"Project: {manifest['source_pdf']}")
    print(f"Pages: {manifest['page_count']}")
    
    if api_key:
        client = anthropic.Anthropic(api_key=api_key)
    else:
        client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY env var
    
    # Agent 1: Guide Builder
    print("\n[Agent 1] Building provisional guide...")
    builder_pages = select_pages(manifest, count=5)
    builder_images = [Path(p["path"]) for p in builder_pages]
    
    builder_result = call_agent(
        client,
        load_prompt("guide_builder"),
        builder_images,
        model=model
    )
    
    print(f"  ✓ Found {len(builder_result.get('candidate_rules', []))} candidate rules")
    print(f"  ✓ Found {len(builder_result.get('legend_extractions', []))} legend symbols")
    
    # Agent 2: Guide Applier
    print("\n[Agent 2] Validating rules...")
    validation_pages = select_pages(manifest, count=3, strategy="balanced")
    # Avoid pages already used
    used_paths = {str(p["path"]) for p in builder_pages}
    validation_pages = [p for p in manifest["pages"] if str(Path(p["path"])) not in used_paths][:3]
    
    if not validation_pages:
        validation_pages = manifest["pages"][1:4]  # Fallback
    
    validation_images = [Path(p["path"]) for p in validation_pages]
    
    context = f"Guide provisoire:\n{builder_result.get('provisional_guide', '')}\n\nRègles candidates:\n{json.dumps(builder_result.get('candidate_rules', []), indent=2)}"
    
    applier_result = call_agent(
        client,
        load_prompt("guide_applier"),
        validation_images,
        context=context,
        model=model
    )
    
    reports = applier_result.get("validation_reports", [])
    confirmed = sum(1 for r in reports if r.get("status") == "CONFIRMED")
    print(f"  ✓ {confirmed}/{len(reports)} rules confirmed")
    
    # Agent 3: Self-Validator
    print("\n[Agent 3] Evaluating stability...")
    validator_context = f"Guide provisoire:\n{builder_result.get('provisional_guide', '')}\n\nRapports de validation:\n{json.dumps(reports, indent=2)}"
    
    validator_result = call_agent(
        client,
        load_prompt("self_validator"),
        [],  # No images needed
        context=validator_context,
        model=model
    )
    
    confidence = validator_result.get("confidence_score", 0)
    can_finalize = validator_result.get("can_generate_final", False)
    print(f"  ✓ Confidence: {confidence:.0%}")
    print(f"  ✓ Can finalize: {can_finalize}")
    
    # Agent 4: Consolidator
    print("\n[Agent 4] Generating stable guide...")
    consolidator_context = f"Guide provisoire:\n{builder_result.get('provisional_guide', '')}\n\nRapport de confiance:\n{json.dumps(validator_result, indent=2)}"
    
    consolidator_result = call_agent(
        client,
        load_prompt("consolidator"),
        [],
        context=consolidator_context,
        model=model
    )
    
    # Save outputs
    result = {
        "status": "VALIDATED" if can_finalize else "PROVISIONAL_ONLY",
        "confidence_score": confidence,
        "builder_result": builder_result,
        "applier_result": applier_result,
        "validator_result": validator_result,
        "consolidator_result": consolidator_result,
        "stable_guide": consolidator_result.get("stable_guide", ""),
        "stable_rules": consolidator_result.get("stable_rules_json", []),
        "legend": builder_result.get("legend_extractions", [])
    }
    
    # Save JSON
    guide_path = output_dir / "guide.json"
    with open(guide_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    # Save markdown guide
    guide_md_path = output_dir / "guide.md"
    with open(guide_md_path, "w") as f:
        f.write(result["stable_guide"])
    
    # Save legend
    legend_path = output_dir / "legend.json"
    with open(legend_path, "w") as f:
        json.dump(result["legend"], f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Pipeline complete!")
    print(f"  Status: {result['status']}")
    print(f"  Guide: {guide_path}")
    print(f"  Legend: {legend_path}")
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Run 4-agent pipeline on blueprint pages"
    )
    parser.add_argument("pages_dir", help="Directory with extracted pages")
    parser.add_argument(
        "-o", "--output",
        default="./output",
        help="Output directory (default: ./output)"
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-20250514",
        help="Claude model to use"
    )
    parser.add_argument(
        "--api-key",
        help="Anthropic API key (or set ANTHROPIC_API_KEY env var)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output full result as JSON to stdout"
    )
    
    args = parser.parse_args()
    
    result = run_pipeline(args.pages_dir, args.output, args.model, args.api_key)
    
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
