#!/usr/bin/env python3
"""
Pipeline E2E — Blueprint Extractor

Orchestre l'extraction complète d'un PDF de plans d'architecture:
  1. PDF → extraction vectorielle (texte + dessins)
  2. Vecteurs → détection de locaux, dimensions, portes
  3. Résultats → construction de l'index RAG
  4. Validation → scoring de confiance + alertes
  5. Output → rapport JSON + résumé

Usage:
    python scripts/run_pipeline.py input.pdf --output-dir ./output/
    python scripts/run_pipeline.py input.pdf --pages 1-10 --output-dir ./output/
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))


def step_extract_vectors(pdf_path: Path, output_dir: Path, pages: str = None) -> dict:
    """Étape 1: Extraction vectorielle du PDF."""
    from extract_pdf_vectors import extract_pdf_vectors, parse_page_range

    output_file = output_dir / "vectors.json"
    page_list = parse_page_range(pages) if pages else None

    result = extract_pdf_vectors(
        str(pdf_path),
        output_file=str(output_file),
        pages=page_list,
    )

    return {
        "output_file": str(output_file),
        "pages_extracted": len(result.get("pages", [])),
        "total_text_blocks": sum(
            len(p.get("text_blocks", [])) for p in result.get("pages", [])
        ),
        "total_drawings": sum(
            len(p.get("drawings", [])) for p in result.get("pages", [])
        ),
    }


def step_detect_rooms(vectors_path: Path, output_dir: Path) -> dict:
    """Étape 2a: Détection des locaux."""
    from room_detector import detect_rooms

    output_file = output_dir / "rooms_detected.json"

    with open(vectors_path) as f:
        vectors = json.load(f)

    result = detect_rooms(vectors)

    # Wrap in standard format
    rooms_data = {
        "project": {"name": "Pipeline extraction"},
        "extraction_date": datetime.now().isoformat(),
        "rooms": result.get("rooms", []),
        "total_rooms": len(result.get("rooms", [])),
    }

    with open(output_file, "w") as f:
        json.dump(rooms_data, f, indent=2, ensure_ascii=False)

    return {
        "output_file": str(output_file),
        "rooms_detected": len(result.get("rooms", [])),
        "stats": result.get("stats", {}),
    }


def step_detect_dimensions(vectors_path: Path, output_dir: Path) -> dict:
    """Étape 2b: Détection des dimensions."""
    from dimension_detector import run_detection

    output_file = output_dir / "dimensions_detected.json"
    result = run_detection(str(vectors_path), str(output_file))

    return {
        "output_file": str(output_file),
        "dimensions_detected": len(result.get("dimensions", [])),
    }


def step_detect_doors(vectors_path: Path, output_dir: Path) -> dict:
    """Étape 2c: Détection des portes."""
    from door_detector import run_detection

    output_file = output_dir / "doors_detected.json"
    result = run_detection(str(vectors_path), str(output_file))

    return {
        "output_file": str(output_file),
        "doors_detected": len(result.get("doors", [])),
    }


def step_build_rag(output_dir: Path) -> dict:
    """Étape 3: Construction de l'index RAG."""
    from build_rag import build_index

    rooms_file = output_dir / "rooms_detected.json"
    rag_dir = output_dir / "rag"
    rag_dir.mkdir(exist_ok=True)

    # Load all detection results
    source_data = {}
    for name in ["rooms_detected", "dimensions_detected", "doors_detected"]:
        fpath = output_dir / f"{name}.json"
        if fpath.exists():
            with open(fpath) as f:
                source_data[name] = json.load(f)

    result = build_index(str(rooms_file), str(rag_dir))

    return {
        "output_dir": str(rag_dir),
        "index_entries": result.get("total_entries", 0),
    }


def step_validate(output_dir: Path) -> dict:
    """Étape 4: Scoring de confiance + alertes."""
    from confidence import enhance_rooms_file
    from alerts import analyze_extraction

    rooms_file = output_dir / "rooms_detected.json"
    confidence_file = output_dir / "confidence_report.json"
    alerts_file = output_dir / "alerts.json"

    # Enhance with confidence scores
    confidence_result = enhance_rooms_file(str(rooms_file), str(confidence_file))

    # Generate alerts
    alerts_result = analyze_extraction(str(rooms_file), str(alerts_file))

    return {
        "confidence_file": str(confidence_file),
        "alerts_file": str(alerts_file),
        "avg_confidence": confidence_result.get("quality", {}).get(
            "average_confidence", 0
        ),
        "total_alerts": alerts_result.get("total", 0),
        "errors": alerts_result.get("errors", 0),
        "warnings": alerts_result.get("warnings", 0),
    }


def step_generate_summary(output_dir: Path, pipeline_report: dict) -> dict:
    """Étape 5: Génère le rapport final et résumé."""
    summary_file = output_dir / "pipeline_summary.json"
    report_file = output_dir / "pipeline_report.md"

    # Save JSON report
    with open(summary_file, "w") as f:
        json.dump(pipeline_report, f, indent=2, ensure_ascii=False)

    # Generate markdown report
    steps = pipeline_report.get("steps", {})
    duration = pipeline_report.get("duration_seconds", 0)

    lines = [
        "# Blueprint Extractor — Rapport de Pipeline",
        "",
        f"**Date:** {pipeline_report.get('timestamp', 'N/A')}",
        f"**PDF:** {pipeline_report.get('input_pdf', 'N/A')}",
        f"**Durée:** {duration:.1f}s",
        "",
        "## Résultats",
        "",
    ]

    if "vectors" in steps:
        v = steps["vectors"]
        lines.append(f"- **Pages extraites:** {v.get('pages_extracted', 0)}")
        lines.append(f"- **Blocs texte:** {v.get('total_text_blocks', 0)}")
        lines.append(f"- **Dessins:** {v.get('total_drawings', 0)}")

    if "rooms" in steps:
        lines.append(f"- **Locaux détectés:** {steps['rooms'].get('rooms_detected', 0)}")

    if "dimensions" in steps:
        lines.append(
            f"- **Dimensions détectées:** {steps['dimensions'].get('dimensions_detected', 0)}"
        )

    if "doors" in steps:
        lines.append(f"- **Portes détectées:** {steps['doors'].get('doors_detected', 0)}")

    if "validation" in steps:
        val = steps["validation"]
        lines.append(f"- **Confiance moyenne:** {val.get('avg_confidence', 0):.1%}")
        lines.append(f"- **Alertes:** {val.get('total_alerts', 0)} ({val.get('errors', 0)} erreurs, {val.get('warnings', 0)} avertissements)")

    lines.extend(["", "## Fichiers générés", ""])
    for step_name, step_data in steps.items():
        if isinstance(step_data, dict):
            for k, v in step_data.items():
                if "file" in k or "dir" in k:
                    lines.append(f"- `{v}`")

    report_md = "\n".join(lines)
    with open(report_file, "w") as f:
        f.write(report_md)

    return {
        "summary_file": str(summary_file),
        "report_file": str(report_file),
    }


def run_pipeline(pdf_path: str, output_dir: str, pages: str = None) -> dict:
    """
    Exécute le pipeline complet d'extraction.

    Args:
        pdf_path: Chemin vers le PDF d'entrée
        output_dir: Répertoire de sortie
        pages: Plage de pages (ex: "1-10", "1,3,5")

    Returns:
        dict avec le rapport complet
    """
    pdf = Path(pdf_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if not pdf.exists():
        return {"success": False, "error": f"PDF not found: {pdf_path}"}

    report = {
        "success": False,
        "input_pdf": str(pdf),
        "output_dir": str(out),
        "timestamp": datetime.now().isoformat(),
        "steps": {},
        "errors": [],
    }

    start_time = time.time()

    # Step 1: Extract vectors
    try:
        print(f"[1/5] Extraction vectorielle de {pdf.name}...")
        report["steps"]["vectors"] = step_extract_vectors(pdf, out, pages)
        print(f"  → {report['steps']['vectors']['pages_extracted']} pages, "
              f"{report['steps']['vectors']['total_text_blocks']} blocs texte")
    except Exception as e:
        report["errors"].append(f"Vector extraction failed: {e}")
        report["duration_seconds"] = time.time() - start_time
        return report

    vectors_path = out / "vectors.json"

    # Step 2: Detect rooms, dimensions, doors (parallel-ready)
    try:
        print("[2/5] Détection des locaux...")
        report["steps"]["rooms"] = step_detect_rooms(vectors_path, out)
        print(f"  → {report['steps']['rooms']['rooms_detected']} locaux")
    except Exception as e:
        report["errors"].append(f"Room detection failed: {e}")

    try:
        print("[3/5] Détection des dimensions...")
        report["steps"]["dimensions"] = step_detect_dimensions(vectors_path, out)
        print(f"  → {report['steps']['dimensions']['dimensions_detected']} dimensions")
    except Exception as e:
        report["errors"].append(f"Dimension detection failed: {e}")

    try:
        print("[4/5] Détection des portes...")
        report["steps"]["doors"] = step_detect_doors(vectors_path, out)
        print(f"  → {report['steps']['doors']['doors_detected']} portes")
    except Exception as e:
        report["errors"].append(f"Door detection failed: {e}")

    # Step 3: Build RAG
    try:
        print("[5/5] Construction de l'index RAG + validation...")
        report["steps"]["rag"] = step_build_rag(out)
    except Exception as e:
        report["errors"].append(f"RAG build failed: {e}")

    # Step 4: Validate
    try:
        report["steps"]["validation"] = step_validate(out)
    except Exception as e:
        report["errors"].append(f"Validation failed: {e}")

    # Step 5: Summary
    report["duration_seconds"] = time.time() - start_time
    report["success"] = len(report["errors"]) == 0

    try:
        summary = step_generate_summary(out, report)
        report["steps"]["summary"] = summary
    except Exception as e:
        report["errors"].append(f"Summary generation failed: {e}")

    status = "✓" if report["success"] else "⚠"
    print(f"\n{status} Pipeline terminé en {report['duration_seconds']:.1f}s")
    if report["errors"]:
        for err in report["errors"]:
            print(f"  ✗ {err}")

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Blueprint Extractor — Pipeline E2E",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python scripts/run_pipeline.py plans.pdf --output-dir ./output/
  python scripts/run_pipeline.py plans.pdf --pages 1-10 --output-dir ./output/
  python scripts/run_pipeline.py plans.pdf --pages 4,8,12 --output-dir ./output/
        """,
    )
    parser.add_argument("pdf", help="Chemin vers le PDF des plans")
    parser.add_argument(
        "--output-dir", "-o", default="./output", help="Répertoire de sortie"
    )
    parser.add_argument(
        "--pages", "-p", default=None, help="Plage de pages (ex: 1-10, 1,3,5)"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Mode verbeux")

    args = parser.parse_args()

    result = run_pipeline(args.pdf, args.output_dir, args.pages)

    if args.verbose:
        print("\n" + json.dumps(result, indent=2, ensure_ascii=False))

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
