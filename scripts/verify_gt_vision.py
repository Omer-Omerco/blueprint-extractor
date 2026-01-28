#!/usr/bin/env python3
"""
Double-blind verification of ground truth using Claude Vision.

This script independently verifies room IDs and names from the ground truth
by cropping blueprint regions and sending them to Claude Vision for OCR.
This breaks the circular validation where GT was auto-enriched from PyMuPDF extractions.
"""

import json
import os
import sys
import base64
import random
import re
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image
import anthropic

# Config
WORKSPACE = Path(__file__).parent.parent
OUTPUT_DIR = WORKSPACE / "output"
PAGES_DIR = OUTPUT_DIR / "pages"
GT_FILE = WORKSPACE / "ground_truth" / "emj.json"
ROOMS_FILE = OUTPUT_DIR / "rooms_complete.json"
REPORT_JSON = WORKSPACE / "ground_truth" / "verification_report.json"
REPORT_MD = WORKSPACE / "ground_truth" / "verification_report.md"

SAMPLE_SIZE = 30
PADDING = 150  # pixels of padding around bbox
MODEL = "claude-sonnet-4-20250514"


def load_data():
    """Load GT and rooms_complete data."""
    gt = json.load(open(GT_FILE))
    rooms_complete = json.load(open(ROOMS_FILE))
    
    # Build lookup from rooms_complete by id
    rooms_by_id = {}
    for r in rooms_complete["rooms"]:
        rooms_by_id[r["id"]] = r
    
    return gt, rooms_by_id


def select_sample(gt, rooms_by_id):
    """Select a diverse sample of rooms for verification."""
    verified_rooms = gt["verified_rooms"]
    
    # Only include rooms that have bbox data
    candidates = [r for r in verified_rooms if r["id"] in rooms_by_id and rooms_by_id[r["id"]].get("bbox")]
    
    # Stratified sampling by block
    by_block = {}
    for r in candidates:
        b = r.get("block", "?")
        if b not in by_block:
            by_block[b] = []
        by_block[b].append(r)
    
    sample = []
    # Take proportional samples from each block
    total = sum(len(v) for v in by_block.values())
    for block, rooms in sorted(by_block.items()):
        n = max(3, round(SAMPLE_SIZE * len(rooms) / total))
        chosen = random.sample(rooms, min(n, len(rooms)))
        sample.extend(chosen)
    
    # Trim to SAMPLE_SIZE if over
    if len(sample) > SAMPLE_SIZE:
        sample = random.sample(sample, SAMPLE_SIZE)
    
    return sample


def crop_room(room_data, padding=PADDING):
    """Crop the room area from the page image."""
    bbox = room_data["bbox"]  # [x1, y1, x2, y2]
    page_file = PAGES_DIR / room_data["bbox_source"]
    
    if not page_file.exists():
        return None
    
    img = Image.open(page_file)
    w, h = img.size
    
    x1, y1, x2, y2 = bbox
    # Add padding
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(w, x2 + padding)
    y2 = min(h, y2 + padding)
    
    crop = img.crop((x1, y1, x2, y2))
    return crop


def image_to_base64(img):
    """Convert PIL Image to base64 string."""
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("utf-8")


def verify_room_vision(client, crop_img, room_id_hint=None):
    """Send cropped image to Claude Vision and get room identification."""
    b64 = image_to_base64(crop_img)
    
    prompt = (
        "Tu regardes une portion d'un plan d'architecture d'une école au Québec. "
        "Identifie le numéro de local et le nom du local que tu vois dans cette zone. "
        "Le numéro de local est typiquement au format LETTRE-NOMBRE (ex: A-104, B-201, C-100). "
        "Le nom est typiquement en MAJUSCULES sous ou à côté du numéro (ex: CLASSE, VESTIBULE, CORRIDOR). "
        "Si tu vois plusieurs locaux, identifie celui qui est le plus centré dans l'image. "
        "Réponds UNIQUEMENT en JSON valide, sans markdown: "
        '{\"room_id\": \"...\", \"room_name\": \"...\", \"confidence\": 0.0-1.0, \"notes\": \"...\"}'
    )
    
    response = client.messages.create(
        model=MODEL,
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": b64
                    }
                },
                {
                    "type": "text",
                    "text": prompt
                }
            ]
        }]
    )
    
    text = response.text if hasattr(response, 'text') else response.content[0].text
    
    # Parse JSON from response
    try:
        # Try to extract JSON from the response
        json_match = re.search(r'\{[^}]+\}', text)
        if json_match:
            result = json.loads(json_match.group())
        else:
            result = json.loads(text)
    except json.JSONDecodeError:
        result = {"room_id": "PARSE_ERROR", "room_name": "PARSE_ERROR", "confidence": 0, "notes": text}
    
    return result


def compare_results(gt_room, vision_result):
    """Compare GT vs Vision result."""
    gt_id = gt_room["id"].strip().upper()
    gt_name = gt_room["name"].strip().upper()
    
    vision_id = vision_result.get("room_id", "").strip().upper()
    vision_name = vision_result.get("room_name", "").strip().upper()
    
    id_match = gt_id == vision_id
    # Fuzzy name match: exact or one contains the other
    name_match = (
        gt_name == vision_name or
        gt_name in vision_name or
        vision_name in gt_name
    )
    
    return {
        "gt_id": gt_id,
        "gt_name": gt_name,
        "vision_id": vision_id,
        "vision_name": vision_name,
        "id_match": id_match,
        "name_match": name_match,
        "full_match": id_match and name_match,
        "vision_confidence": vision_result.get("confidence", 0),
        "vision_notes": vision_result.get("notes", "")
    }


def generate_report(results, total_gt_rooms):
    """Generate verification report."""
    total = len(results)
    full_matches = sum(1 for r in results if r["full_match"])
    id_matches = sum(1 for r in results if r["id_match"])
    name_matches = sum(1 for r in results if r["name_match"])
    mismatches = [r for r in results if not r["full_match"]]
    
    reliability_score = full_matches / total if total > 0 else 0
    
    report = {
        "verification_date": datetime.now().isoformat(),
        "model_used": MODEL,
        "method": "double-blind Vision AI verification",
        "total_gt_rooms": total_gt_rooms,
        "total_verified": total,
        "sample_percentage": round(100 * total / total_gt_rooms, 1),
        "results": {
            "full_matches": full_matches,
            "id_only_matches": id_matches,
            "name_only_matches": name_matches,
            "mismatches": len(mismatches)
        },
        "reliability_score": round(reliability_score, 4),
        "reliability_percentage": f"{reliability_score*100:.1f}%",
        "mismatches_detail": mismatches,
        "all_results": results
    }
    
    return report


def generate_markdown_report(report):
    """Generate markdown version of the report."""
    lines = [
        "# Rapport de Vérification Double-Blind du Ground Truth",
        "",
        f"**Date:** {report['verification_date']}",
        f"**Modèle:** {report['model_used']}",
        f"**Méthode:** {report['method']}",
        "",
        "## Résumé",
        "",
        f"| Métrique | Valeur |",
        f"|----------|--------|",
        f"| Rooms dans le GT | {report['total_gt_rooms']} |",
        f"| Rooms vérifiées | {report['total_verified']} |",
        f"| Échantillon | {report['sample_percentage']}% |",
        f"| **Matches complets** | **{report['results']['full_matches']}** |",
        f"| Matches ID seul | {report['results']['id_only_matches']} |",
        f"| Matches nom seul | {report['results']['name_only_matches']} |",
        f"| Mismatches | {report['results']['mismatches']} |",
        f"| **Score de fiabilité** | **{report['reliability_percentage']}** |",
        "",
    ]
    
    mismatches = report.get("mismatches_detail", [])
    if mismatches:
        lines.extend([
            "## Mismatches Détaillés",
            "",
            "| GT ID | GT Nom | Vision ID | Vision Nom | ID Match | Name Match | Confidence | Notes |",
            "|-------|--------|-----------|------------|----------|------------|------------|-------|",
        ])
        for m in mismatches:
            lines.append(
                f"| {m['gt_id']} | {m['gt_name']} | {m['vision_id']} | {m['vision_name']} "
                f"| {'✅' if m['id_match'] else '❌'} | {'✅' if m['name_match'] else '❌'} "
                f"| {m['vision_confidence']} | {m.get('vision_notes','')} |"
            )
        lines.append("")
    
    lines.extend([
        "## Tous les Résultats",
        "",
        "| # | GT ID | GT Nom | Vision ID | Vision Nom | Match | Conf |",
        "|---|-------|--------|-----------|------------|-------|------|",
    ])
    for i, r in enumerate(report["all_results"], 1):
        status = "✅" if r["full_match"] else ("⚠️" if r["id_match"] or r["name_match"] else "❌")
        lines.append(
            f"| {i} | {r['gt_id']} | {r['gt_name']} | {r['vision_id']} | {r['vision_name']} "
            f"| {status} | {r['vision_confidence']} |"
        )
    
    lines.extend([
        "",
        "## Conclusion",
        "",
        f"Le ground truth a un score de fiabilité de **{report['reliability_percentage']}** "
        f"basé sur la vérification indépendante par Vision AI de {report['total_verified']} rooms.",
    ])
    
    if report["reliability_score"] >= 0.9:
        lines.append("Le GT est **hautement fiable** et peut être utilisé comme référence.")
    elif report["reliability_score"] >= 0.7:
        lines.append("Le GT est **modérément fiable** — les mismatches identifiés doivent être corrigés.")
    else:
        lines.append("Le GT a des **problèmes significatifs** — une révision complète est recommandée.")
    
    return "\n".join(lines)


def main():
    random.seed(42)  # Reproducible sampling
    
    print("=" * 60)
    print("VÉRIFICATION DOUBLE-BLIND DU GROUND TRUTH")
    print("=" * 60)
    
    # Load data
    print("\n📂 Chargement des données...")
    gt, rooms_by_id = load_data()
    total_gt = len(gt["verified_rooms"])
    print(f"  GT: {total_gt} rooms")
    print(f"  rooms_complete: {len(rooms_by_id)} rooms")
    
    # Select sample
    print(f"\n🎯 Sélection de l'échantillon ({SAMPLE_SIZE} rooms)...")
    sample = select_sample(gt, rooms_by_id)
    print(f"  Échantillon: {len(sample)} rooms")
    blocks = {}
    for r in sample:
        b = r.get("block", "?")
        blocks[b] = blocks.get(b, 0) + 1
    print(f"  Par bloc: {dict(sorted(blocks.items()))}")
    
    # Init Anthropic client
    client = anthropic.Anthropic()
    
    # Verify each room
    print(f"\n🔍 Vérification en cours...")
    results = []
    for i, gt_room in enumerate(sample):
        room_id = gt_room["id"]
        room_data = rooms_by_id[room_id]
        
        print(f"  [{i+1}/{len(sample)}] {room_id} ({gt_room['name']})...", end=" ", flush=True)
        
        # Crop the room area
        crop = crop_room(room_data)
        if crop is None:
            print("⚠️ No image")
            results.append({
                "gt_id": room_id, "gt_name": gt_room["name"],
                "vision_id": "NO_IMAGE", "vision_name": "NO_IMAGE",
                "id_match": False, "name_match": False, "full_match": False,
                "vision_confidence": 0, "vision_notes": "Image not found"
            })
            continue
        
        # Send to Vision
        try:
            vision = verify_room_vision(client, crop, room_id)
            comparison = compare_results(gt_room, vision)
            results.append(comparison)
            
            status = "✅" if comparison["full_match"] else "❌"
            print(f"{status} Vision: {vision.get('room_id','?')} / {vision.get('room_name','?')}")
            
            # Rate limiting
            time.sleep(1)
            
        except Exception as e:
            print(f"❌ Error: {e}")
            results.append({
                "gt_id": room_id, "gt_name": gt_room["name"],
                "vision_id": "ERROR", "vision_name": "ERROR",
                "id_match": False, "name_match": False, "full_match": False,
                "vision_confidence": 0, "vision_notes": str(e)
            })
    
    # Generate report
    print(f"\n📊 Génération du rapport...")
    report = generate_report(results, total_gt)
    
    # Save JSON report
    json.dump(report, open(REPORT_JSON, "w"), indent=2, ensure_ascii=False)
    print(f"  Sauvegardé: {REPORT_JSON}")
    
    # Save MD report
    md = generate_markdown_report(report)
    open(REPORT_MD, "w").write(md)
    print(f"  Sauvegardé: {REPORT_MD}")
    
    # Summary
    print(f"\n{'=' * 60}")
    print(f"RÉSULTATS")
    print(f"{'=' * 60}")
    print(f"  Vérifié: {report['total_verified']}/{total_gt} rooms")
    print(f"  Matches complets: {report['results']['full_matches']}")
    print(f"  Mismatches: {report['results']['mismatches']}")
    print(f"  Score de fiabilité: {report['reliability_percentage']}")
    
    if report["results"]["mismatches"] > 0:
        print(f"\n⚠️  MISMATCHES:")
        for m in report["mismatches_detail"]:
            print(f"    {m['gt_id']} ({m['gt_name']}) → Vision: {m['vision_id']} ({m['vision_name']})")
    
    return report


if __name__ == "__main__":
    main()
