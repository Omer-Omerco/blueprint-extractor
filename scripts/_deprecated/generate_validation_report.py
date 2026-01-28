#!/usr/bin/env python3
"""
Génère un rapport de validation complet au format Markdown.
Combine cross-validation et validation ground truth.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from cross_validate import cross_validate, ValidationReport
from validate_gt import validate_against_ground_truth, validate_room_types, GTReport


def generate_validation_report(
    rooms_path: str,
    devis_path: str,
    ground_truth_path: str,
    output_path: str
) -> str:
    """
    Génère un rapport de validation complet.
    
    Args:
        rooms_path: Chemin vers rooms_complete.json
        devis_path: Chemin vers devis_final.json
        ground_truth_path: Chemin vers ground_truth/emj.json
        output_path: Chemin de sortie pour le rapport
    
    Returns:
        Contenu du rapport Markdown
    """
    # Charger les données
    with open(rooms_path) as f:
        rooms_data = json.load(f)
    
    with open(devis_path) as f:
        devis_data = json.load(f)
    
    with open(ground_truth_path) as f:
        gt_data = json.load(f)
    
    # Exécuter les validations
    cross_report = cross_validate(rooms_data, devis_data)
    gt_report = validate_against_ground_truth(rooms_data, gt_data)
    type_distribution = validate_room_types(rooms_data, gt_data)
    
    # Générer le rapport Markdown
    report = generate_markdown(
        rooms_data, 
        cross_report, 
        gt_report, 
        type_distribution,
        gt_data
    )
    
    # Sauvegarder
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        f.write(report)
    
    return report


def generate_markdown(
    rooms_data: dict,
    cross_report: ValidationReport,
    gt_report: GTReport,
    type_distribution: dict,
    gt_data: dict
) -> str:
    """Génère le contenu Markdown du rapport."""
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    project_name = rooms_data.get("project", {}).get("name", "Projet inconnu")
    
    # Métriques clés
    m = gt_report.metrics
    cs = cross_report.stats
    
    lines = [
        f"# Rapport de Validation - Blueprint Extractor",
        f"",
        f"**Projet:** {project_name}",
        f"**Date:** {now}",
        f"**Générateur:** Agent Validation",
        f"",
        f"---",
        f"",
        f"## Résumé Exécutif",
        f"",
        f"| Métrique | Valeur | Status |",
        f"|----------|--------|--------|",
        f"| Accuracy | {m.get('accuracy', 0):.1%} | {get_status_emoji(m.get('accuracy', 0))} |",
        f"| Precision | {m.get('precision', 0):.1%} | {get_status_emoji(m.get('precision', 0))} |",
        f"| Recall | {m.get('recall', 0):.1%} | {get_status_emoji(m.get('recall', 0))} |",
        f"| F1 Score | {m.get('f1', 0):.1%} | {get_status_emoji(m.get('f1', 0))} |",
        f"| Taux de correspondance Plans↔Devis | {cs.get('match_rate', 0):.1%} | {get_status_emoji(cs.get('match_rate', 0))} |",
        f"",
        f"### Verdict Global",
        f"",
    ]
    
    # Verdict basé sur F1
    f1 = m.get('f1', 0)
    if f1 >= 0.9:
        verdict = "✅ **EXCELLENT** - L'extraction est très fiable"
    elif f1 >= 0.8:
        verdict = "🟢 **BON** - L'extraction est fiable avec quelques ajustements mineurs"
    elif f1 >= 0.7:
        verdict = "🟡 **ACCEPTABLE** - L'extraction nécessite une révision manuelle"
    elif f1 >= 0.5:
        verdict = "🟠 **INSUFFISANT** - L'extraction a besoin d'améliorations significatives"
    else:
        verdict = "🔴 **CRITIQUE** - L'extraction doit être refaite"
    
    lines.append(verdict)
    lines.append("")
    
    # Section 1: Statistiques d'extraction
    lines.extend([
        f"---",
        f"",
        f"## 1. Statistiques d'Extraction",
        f"",
        f"### 1.1 Locaux",
        f"",
        f"| Statistique | Valeur |",
        f"|------------|--------|",
        f"| Total locaux extraits | {cs.get('total_rooms', 0)} |",
        f"| Locaux vérifiés (Ground Truth) | {m.get('ground_truth_count', 0)} |",
        f"| Matches parfaits | {m.get('perfect_matches', 0)} |",
        f"| Matches partiels | {m.get('partial_matches', 0)} |",
        f"| Manquants | {m.get('missing', 0)} |",
        f"",
    ])
    
    # Distribution par type
    lines.extend([
        f"### 1.2 Distribution par Type de Local",
        f"",
        f"| Type | Extrait | Attendu | Différence | Status |",
        f"|------|---------|---------|------------|--------|",
    ])
    
    for room_type, data in sorted(type_distribution.items()):
        diff = data['difference']
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        status = "✓" if data['match'] else "✗"
        lines.append(f"| {room_type} | {data['extracted']} | {data['ground_truth']} | {diff_str} | {status} |")
    
    lines.append("")
    
    # Section 2: Cross-validation
    lines.extend([
        f"---",
        f"",
        f"## 2. Cross-Validation Plans ↔ Devis",
        f"",
        f"### 2.1 Résumé",
        f"",
        f"| Catégorie | Nombre |",
        f"|-----------|--------|",
        f"| Correspondances trouvées | {len(cross_report.matches)} |",
        f"| Incohérences détectées | {len(cross_report.mismatches)} |",
        f"| Éléments manquants | {len(cross_report.missing)} |",
        f"",
    ])
    
    # Incohérences critiques
    critical_mismatches = [m for m in cross_report.mismatches if m.severity == 'critical']
    if critical_mismatches:
        lines.extend([
            f"### 2.2 Incohérences Critiques",
            f"",
        ])
        for mm in critical_mismatches[:10]:
            lines.append(f"- **{mm.room_id}** ({mm.field}): Plan=`{mm.plan_value}` vs Devis=`{mm.devis_value}`")
        lines.append("")
    
    # Éléments manquants
    if cross_report.missing:
        lines.extend([
            f"### 2.3 Éléments Manquants dans le Devis",
            f"",
        ])
        for missing in cross_report.missing[:10]:
            lines.append(f"- `{missing.item_id}` ({missing.item_name}): {missing.message}")
        lines.append("")
    
    # Section 3: Validation Ground Truth
    lines.extend([
        f"---",
        f"",
        f"## 3. Validation contre Ground Truth",
        f"",
        f"### 3.1 Métriques Détaillées",
        f"",
        f"- **Accuracy**: {m.get('accuracy', 0):.2%} - Qualité moyenne des correspondances",
        f"- **Precision**: {m.get('precision', 0):.2%} - % des extraits qui sont corrects",
        f"- **Recall**: {m.get('recall', 0):.2%} - % des éléments GT trouvés",
        f"- **F1 Score**: {m.get('f1', 0):.2%} - Moyenne harmonique precision/recall",
        f"",
    ])
    
    # Différences détectées
    if gt_report.mismatches:
        lines.extend([
            f"### 3.2 Différences Détectées",
            f"",
            f"| Local | Champ | Extrait | Attendu | Sévérité |",
            f"|-------|-------|---------|---------|----------|",
        ])
        for mm in gt_report.mismatches[:15]:
            severity_emoji = "🔴" if mm.severity == 'critical' else "🟡"
            lines.append(f"| {mm.item_id} | {mm.field} | {mm.extracted_value} | {mm.expected_value} | {severity_emoji} |")
        lines.append("")
    
    # Section 4: Recommandations
    lines.extend([
        f"---",
        f"",
        f"## 4. Recommandations",
        f"",
    ])
    
    recommendations = generate_recommendations(m, cs, cross_report, gt_report)
    for i, rec in enumerate(recommendations, 1):
        lines.append(f"{i}. {rec}")
    
    lines.append("")
    
    # Section 5: Détails techniques
    lines.extend([
        f"---",
        f"",
        f"## 5. Détails Techniques",
        f"",
        f"### 5.1 Sources Validées",
        f"",
        f"- Plans: {gt_data.get('source_documents', {}).get('plans', 'N/A')}",
        f"- Devis: {gt_data.get('source_documents', {}).get('devis', 'N/A')}",
        f"- Ground Truth: {len(gt_data.get('verified_rooms', []))} locaux, {len(gt_data.get('verified_products', []))} produits",
        f"",
        f"### 5.2 Structure du Bâtiment",
        f"",
    ])
    
    blocks = gt_data.get('building_structure', {}).get('blocks', [])
    floors = gt_data.get('building_structure', {}).get('floors', {})
    for block in blocks:
        block_floors = floors.get(block, [])
        lines.append(f"- Bloc {block}: Niveaux {block_floors}")
    
    lines.extend([
        f"",
        f"### 5.3 Notes de Validation",
        f"",
    ])
    
    for note in gt_data.get('validation_notes', []):
        lines.append(f"- {note}")
    
    lines.extend([
        f"",
        f"---",
        f"",
        f"*Rapport généré automatiquement par Blueprint Extractor*",
        f"*Agent Validation - {now}*",
    ])
    
    return "\n".join(lines)


def get_status_emoji(value: float) -> str:
    """Retourne un emoji de status basé sur la valeur (0-1)."""
    if value >= 0.9:
        return "✅"
    elif value >= 0.8:
        return "🟢"
    elif value >= 0.7:
        return "🟡"
    elif value >= 0.5:
        return "🟠"
    else:
        return "🔴"


def generate_recommendations(
    metrics: dict,
    cross_stats: dict,
    cross_report: ValidationReport,
    gt_report: GTReport
) -> list:
    """Génère des recommandations basées sur les résultats."""
    recommendations = []
    
    # Basé sur F1
    f1 = metrics.get('f1', 0)
    if f1 < 0.8:
        recommendations.append("**Améliorer la précision d'extraction** - Le F1 score est sous 80%")
    
    # Basé sur recall
    if metrics.get('recall', 0) < 0.9:
        recommendations.append("**Vérifier les locaux manquants** - Certains locaux du ground truth n'ont pas été extraits")
    
    # Basé sur les mismatches
    if gt_report.mismatches:
        critical = [m for m in gt_report.mismatches if m.severity == 'critical']
        if critical:
            recommendations.append(f"**Corriger {len(critical)} erreurs critiques** - Noms ou IDs de locaux incorrects")
    
    # Basé sur cross-validation
    if cross_report.missing:
        recommendations.append(f"**Valider {len(cross_report.missing)} locaux** non trouvés dans le devis")
    
    if cross_stats.get('match_rate', 0) < 0.7:
        recommendations.append("**Améliorer le parsing du devis** - Taux de correspondance faible")
    
    # Recommandations générales
    if not recommendations:
        recommendations.append("✅ Les résultats sont satisfaisants - Continuer avec la configuration actuelle")
    else:
        recommendations.append("Exécuter une nouvelle extraction après corrections et re-valider")
    
    return recommendations


def main():
    """Point d'entrée CLI."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Génère un rapport de validation complet")
    parser.add_argument("--rooms", "-r", help="Fichier JSON des locaux", 
                       default="output/rooms_complete.json")
    parser.add_argument("--devis", "-d", help="Fichier JSON du devis",
                       default="output/devis_final.json")
    parser.add_argument("--ground-truth", "-g", help="Fichier Ground Truth",
                       default="ground_truth/emj.json")
    parser.add_argument("--output", "-o", help="Fichier de sortie",
                       default="output/validation_report.md")
    
    args = parser.parse_args()
    
    # Résoudre les chemins relatifs
    base_path = Path(__file__).parent.parent
    rooms_path = base_path / args.rooms
    devis_path = base_path / args.devis
    gt_path = base_path / args.ground_truth
    output_path = base_path / args.output
    
    print(f"Génération du rapport de validation...")
    print(f"  Rooms: {rooms_path}")
    print(f"  Devis: {devis_path}")
    print(f"  Ground Truth: {gt_path}")
    print(f"  Output: {output_path}")
    print()
    
    report = generate_validation_report(
        str(rooms_path),
        str(devis_path),
        str(gt_path),
        str(output_path)
    )
    
    print(f"✅ Rapport généré: {output_path}")
    print(f"   Taille: {len(report)} caractères")
    
    # Afficher un aperçu
    print("\n--- Aperçu ---")
    lines = report.split("\n")
    for line in lines[:30]:
        print(line)
    print("...")


if __name__ == "__main__":
    main()
